"""
Kling Motion Control 2.6 Service
==================================
Uploads a reference image and video to fal storage, submits a motion-control
generation request, polls for completion, and downloads the result.

Usage (standalone):
    cd backend && source venv/bin/activate
    export FAL_KEY='your-fal-api-key'
    python motion_control.py

Usage (as library):
    from motion_control import generate_motion_video
    output = generate_motion_video(image_path, video_path, output_path)
"""

import os
import sys
import time
from typing import Callable, Optional

import requests
import fal_client

from config import FAL_MOTION_CLIENT_TIMEOUT_SEC
from cancellation import PipelineCancelled

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_ID = "fal-ai/kling-video/v2.6/standard/motion-control"
CHARACTER_ORIENTATION = "video"  # match motions from the reference video (max 30s)
KEEP_ORIGINAL_SOUND = True

# Standalone-mode defaults
INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_fal_key() -> str:
    """Resolve and set the FAL_KEY env var. Returns the key."""
    fal_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_AI")
    if not fal_key:
        raise EnvironmentError(
            "FAL_KEY (or FAL_AI) environment variable is not set. "
            "Export it before calling this function."
        )
    # fal_client reads FAL_KEY, so ensure it's set
    os.environ["FAL_KEY"] = fal_key
    return fal_key


def upload_file(path: str, label: str) -> str:
    """Upload a local file to fal storage and return the URL."""
    print(f"  Uploading {label} ({os.path.basename(path)}) …")
    url = fal_client.upload_file(path)
    print(f"  ✓ Uploaded → {url}")
    return url


def download_file(url: str, dest: str, cancel_check: Optional[Callable[[], bool]] = None) -> None:
    """Download a file from a URL to a local path."""
    print(f"  Downloading result → {dest}")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if cancel_check and cancel_check():
                raise PipelineCancelled("Cancelled by user")
            if chunk:
                f.write(chunk)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"  ✓ Saved ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Reusable API function
# ---------------------------------------------------------------------------

def generate_motion_video(
    image_path: str,
    video_path: str,
    output_path: str,
    prompt: str = "A young woman reacting to the camera",
    on_fal_status: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> str:
    """
    Generate a motion-control video using Fal AI's Kling model.

    Uploads the image and video to fal storage, submits the request,
    polls for completion, and downloads the result.

    Args:
        image_path: Path to the reference image (the person/character).
        video_path: Path to the reference video (the motion source).
        output_path: Path where the generated video will be saved.
        prompt: Text prompt describing the scene.

    Returns:
        The path to the saved output video.

    Raises:
        FileNotFoundError: If image or video files don't exist.
        EnvironmentError: If FAL_KEY is not set.
        RuntimeError: If the API returns no video URL, or if ``client_timeout`` is exceeded
        (see ``FAL_MOTION_CLIENT_TIMEOUT_SEC`` in config).

    Optional ``on_fal_status`` receives short status strings while Fal queues/renders
    (wired to the UI as motion_control step progress).
    """
    def check_cancelled() -> None:
        if cancel_check and cancel_check():
            raise PipelineCancelled("Cancelled by user")

    # Validate
    check_cancelled()
    _ensure_fal_key()

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Reference image not found: {image_path}")
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Reference video not found: {video_path}")

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Upload files
    check_cancelled()
    print("  Uploading files to fal storage …")
    image_url = upload_file(image_path, "reference image")
    check_cancelled()
    video_url = upload_file(video_path, "reference video")
    check_cancelled()

    # Submit request
    print("  Submitting motion-control request …")
    arguments = {
        "prompt": prompt,
        "image_url": image_url,
        "video_url": video_url,
        "character_orientation": CHARACTER_ORIENTATION,
        "keep_original_sound": KEEP_ORIGINAL_SOUND,
    }
    print(f"  Model: {MODEL_ID}")

    fal_wait_started = time.time()
    _last_ui_emit = [0.0]  # throttle JSON writes for noisy InProgress ticks

    def _emit_ui(msg: str, *, min_interval_sec: float = 0.0) -> None:
        if not msg or not on_fal_status:
            return
        now = time.time()
        if min_interval_sec > 0 and (now - _last_ui_emit[0]) < min_interval_sec:
            return
        _last_ui_emit[0] = now
        on_fal_status(msg)

    def on_queue_update(status):
        """Callback to print queue status updates."""
        check_cancelled()
        elapsed_s = int(time.time() - fal_wait_started)
        if isinstance(status, fal_client.Queued):
            pos = getattr(status, "position", "?")
            print(f"  ⏳ Queued (position: {pos})")
            _emit_ui(f"Fal queue: position {pos} (~{elapsed_s}s)")
        elif isinstance(status, fal_client.InProgress):
            logs = getattr(status, "logs", None)
            if logs:
                for log in logs:
                    msg = log.get("message", "") if isinstance(log, dict) else str(log)
                    print(f"  🔄 {msg}")
                    if msg:
                        _emit_ui(f"Fal: {msg} (~{elapsed_s}s)")
            else:
                print("  🔄 In progress …")
                # Fal sends many InProgress ticks; avoid hammering the generation store.
                _emit_ui(f"Fal rendering… (~{elapsed_s}s)", min_interval_sec=12.0)
        elif isinstance(status, fal_client.Completed):
            print("  ✅ Completed!")
            _emit_ui("Fal finished, downloading result…")
        check_cancelled()

    start_time = time.time()
    timeout = FAL_MOTION_CLIENT_TIMEOUT_SEC if FAL_MOTION_CLIENT_TIMEOUT_SEC > 0 else None
    handle = None

    try:
        # Use the queue handle API so user cancellation can cancel the remote Fal request.
        handle = fal_client.submit(MODEL_ID, arguments=arguments)
        request_id = getattr(handle, "request_id", "")
        if request_id:
            _emit_ui(f"Fal request queued ({request_id[:8]})")

        for status in handle.iter_events(with_logs=True, interval=2.0):
            check_cancelled()
            on_queue_update(status)
            if timeout is not None and (time.time() - start_time) > timeout:
                raise TimeoutError()

        check_cancelled()
        result = handle.get()
    except PipelineCancelled:
        if handle is not None:
            try:
                handle.cancel()
                print("  Fal request cancelled.")
            except Exception as cancel_exc:
                print(f"  Fal cancel failed (non-fatal): {cancel_exc}")
        raise
    except AttributeError:
        # Older fal-client without submit/iter_events; cancellation can still stop
        # between queue callbacks, but a silent blocking subscribe cannot be interrupted.
        subscribe_kw: dict = {
            "arguments": arguments,
            "with_logs": True,
            "on_queue_update": on_queue_update,
        }
        if timeout is not None:
            subscribe_kw["client_timeout"] = timeout
        try:
            result = fal_client.subscribe(MODEL_ID, **subscribe_kw)
        except TypeError:
            subscribe_kw.pop("client_timeout", None)
            result = fal_client.subscribe(MODEL_ID, **subscribe_kw)
    except TimeoutError as exc:
        raise RuntimeError(
            f"Fal AI motion-control exceeded the client timeout ({timeout}s). "
            "Kling can take a long time for long videos — increase FAL_MOTION_CLIENT_TIMEOUT_SEC "
            "in backend/.env (default 1800 = 30 minutes)."
        ) from exc
    except Exception as exc:
        err = str(exc).lower()
        if timeout and ("timeout" in err or "timed out" in err):
            raise RuntimeError(
                f"Fal AI motion-control timed out after ~{timeout}s: {exc!r}. "
                "Try raising FAL_MOTION_CLIENT_TIMEOUT_SEC."
            ) from exc
        raise
    elapsed = time.time() - start_time
    print(f"  Generation finished in {elapsed:.0f}s")
    check_cancelled()

    # Download the output video
    video_info = result.get("video", {})
    video_download_url = video_info.get("url")

    if not video_download_url:
        raise RuntimeError(
            f"Fal AI returned no video URL in the result. Full result: {result}"
        )

    download_file(video_download_url, output_path, cancel_check=cancel_check)
    check_cancelled()

    return output_path


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def run_pipeline():
    """Standalone CLI entry point using default paths."""
    IMAGE_FILE = os.path.join(INPUT_DIR, "model_image.png")
    TRIMMED_VIDEO = os.path.join(OUTPUT_DIR, "Download (6)_trimmed.mp4")
    ORIGINAL_VIDEO = os.path.join(INPUT_DIR, "Download (6).mp4")
    OUTPUT_FILENAME = "motion_control_output.mp4"
    PROMPT = "A young woman reacting to the camera"

    # Resolve video
    if os.path.isfile(TRIMMED_VIDEO):
        video_path = TRIMMED_VIDEO
    elif os.path.isfile(ORIGINAL_VIDEO):
        video_path = ORIGINAL_VIDEO
    else:
        print("ERROR: No reference video found.")
        sys.exit(1)

    if not os.path.isfile(IMAGE_FILE):
        print(f"ERROR: Reference image not found at {IMAGE_FILE}")
        sys.exit(1)

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)

    print("=" * 60)
    print("Kling Motion Control 2.6 Pipeline")
    print("=" * 60)
    print(f"  Image : {IMAGE_FILE}")
    print(f"  Video : {video_path}")
    print(f"  Prompt: {PROMPT}")
    print()

    try:
        generate_motion_video(IMAGE_FILE, video_path, output_path, prompt=PROMPT)
    except EnvironmentError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"Done! Output saved to: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
