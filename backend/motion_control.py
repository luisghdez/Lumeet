"""
Kling Motion Control 2.6 Pipeline
==================================
Uploads a reference image and video to fal storage, submits a motion-control
generation request, polls for completion, and downloads the result.

Usage:
    cd backend && source venv/bin/activate
    export FAL_KEY='your-fal-api-key'
    python motion_control.py
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

INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

IMAGE_FILE = os.path.join(INPUT_DIR, "model_image.png")
# Prefer the trimmed video; fall back to the original
TRIMMED_VIDEO = os.path.join(OUTPUT_DIR, "Download (6)_trimmed.mp4")
ORIGINAL_VIDEO = os.path.join(INPUT_DIR, "Download (6).mp4")

PROMPT = "A young woman reacting to the camera"
CHARACTER_ORIENTATION = "video"  # match motions from the reference video (max 30s)
KEEP_ORIGINAL_SOUND = True

OUTPUT_FILENAME = "motion_control_output.mp4"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_video_path() -> str:
    """Return the best available video path (trimmed > original)."""
    if os.path.isfile(TRIMMED_VIDEO):
        return TRIMMED_VIDEO
    if os.path.isfile(ORIGINAL_VIDEO):
        return ORIGINAL_VIDEO
    print("ERROR: No reference video found. Looked for:")
    print(f"  - {TRIMMED_VIDEO}")
    print(f"  - {ORIGINAL_VIDEO}")
    sys.exit(1)


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
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline():
    # -- Pre-flight checks --------------------------------------------------
    # Accept FAL_KEY or FAL_AI as the env var name
    fal_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_AI")
    if not fal_key:
        print("ERROR: FAL_KEY (or FAL_AI) environment variable is not set.")
        print("  export FAL_KEY='your-fal-api-key'")
        sys.exit(1)
    # fal_client reads FAL_KEY, so ensure it's set
    os.environ["FAL_KEY"] = fal_key

    if not os.path.isfile(IMAGE_FILE):
        print(f"ERROR: Reference image not found at {IMAGE_FILE}")
        sys.exit(1)

    video_path = _resolve_video_path()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Kling Motion Control 2.6 Pipeline")
    print("=" * 60)
    print(f"  Image : {IMAGE_FILE}")
    print(f"  Video : {video_path}")
    print(f"  Prompt: {PROMPT}")
    print(f"  Orientation: {CHARACTER_ORIENTATION}")
    print()

    # -- Step 1: Upload files -----------------------------------------------
    print("[1/4] Uploading files to fal storage …")
    image_url = upload_file(IMAGE_FILE, "reference image")
    video_url = upload_file(video_path, "reference video")
    print()

    # -- Step 2: Submit request ---------------------------------------------
    print("[2/4] Submitting motion-control request …")
    arguments = {
        "prompt": PROMPT,
        "image_url": image_url,
        "video_url": video_url,
        "character_orientation": CHARACTER_ORIENTATION,
        "keep_original_sound": KEEP_ORIGINAL_SOUND,
    }
    print(f"  Model: {MODEL_ID}")
    print(f"  Payload: {arguments}")
    print()

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

    # Use subscribe() which handles submit + polling in one call
    start_time = time.time()
    result = fal_client.subscribe(
        MODEL_ID,
        arguments=arguments,
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    elapsed = time.time() - start_time
    print(f"\n[3/4] Generation finished in {elapsed:.0f}s")
    print(f"  Result: {result}")
    print()

    # -- Step 3: Download the output video -----------------------------------
    video_info = result.get("video", {})
    video_download_url = video_info.get("url")

    if not video_download_url:
        print("ERROR: No video URL in the result.")
        print(f"  Full result: {result}")
        sys.exit(1)

    print("[4/4] Downloading generated video …")
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    download_file(video_download_url, output_path)
    print()

    print("=" * 60)
    print(f"Done! Output saved to: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
