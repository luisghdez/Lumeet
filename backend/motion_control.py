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
import requests
import fal_client

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


def download_file(url: str, dest: str) -> None:
    """Download a file from a URL to a local path."""
    print(f"  Downloading result → {dest}")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
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
        RuntimeError: If the API returns no video URL.
    """
    # Validate
    _ensure_fal_key()

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Reference image not found: {image_path}")
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Reference video not found: {video_path}")

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Upload files
    print("  Uploading files to fal storage …")
    image_url = upload_file(image_path, "reference image")
    video_url = upload_file(video_path, "reference video")

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

    def on_queue_update(status):
        """Callback to print queue status updates."""
        if isinstance(status, fal_client.Queued):
            print(f"  ⏳ Queued (position: {status.position})")
        elif isinstance(status, fal_client.InProgress):
            logs = getattr(status, "logs", None)
            if logs:
                for log in logs:
                    msg = log.get("message", "") if isinstance(log, dict) else str(log)
                    print(f"  🔄 {msg}")
            else:
                print("  🔄 In progress …")
        elif isinstance(status, fal_client.Completed):
            print("  ✅ Completed!")

    start_time = time.time()
    result = fal_client.subscribe(
        MODEL_ID,
        arguments=arguments,
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    elapsed = time.time() - start_time
    print(f"  Generation finished in {elapsed:.0f}s")

    # Download the output video
    video_info = result.get("video", {})
    video_download_url = video_info.get("url")

    if not video_download_url:
        raise RuntimeError(
            f"Fal AI returned no video URL in the result. Full result: {result}"
        )

    download_file(video_download_url, output_path)

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
