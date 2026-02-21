"""
Scene Recreator CLI
====================
Extracts a frame at second 2 from the reference video, then calls the
Gemini Nano Banana Pro API to recreate the scene with the model's identity.

Usage:
    cd backend && source venv/bin/activate
    export GEMINI_API_KEY='your-api-key'
    python run_scene_recreator.py
"""

import os
import sys

from frame_extractor import extract_frame
from scene_recreator import recreate_scene

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Reference video — prefer trimmed, fall back to original
TRIMMED_VIDEO = os.path.join(OUTPUT_DIR, "Download (6)_trimmed.mp4")
ORIGINAL_VIDEO = os.path.join(INPUT_DIR, "Download (6).mp4")

MODEL_IMAGE = os.path.join(INPUT_DIR, "model_image.png")

FRAME_TIMESTAMP = 2.0  # seconds
SCREENSHOT_FILENAME = "scene_screenshot.png"
OUTPUT_FILENAME = "recreated_scene.png"


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


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    # Pre-flight checks
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable is not set.")
        print("  export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)

    if not os.path.isfile(MODEL_IMAGE):
        print(f"ERROR: Model image not found at {MODEL_IMAGE}")
        sys.exit(1)

    video_path = _resolve_video_path()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Scene Recreator Pipeline (Nano Banana Pro)")
    print("=" * 60)
    print(f"  Video : {video_path}")
    print(f"  Model : {MODEL_IMAGE}")
    print(f"  Frame @ {FRAME_TIMESTAMP}s")
    print()

    # Step 1: Extract frame
    screenshot_path = os.path.join(OUTPUT_DIR, SCREENSHOT_FILENAME)
    print(f"[1/2] Extracting frame at {FRAME_TIMESTAMP}s …")
    extract_frame(video_path, timestamp_sec=FRAME_TIMESTAMP, output_path=screenshot_path)
    print(f"  ✓ Screenshot saved → {screenshot_path}")
    print()

    # Step 2: Recreate scene with Gemini
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    print("[2/2] Calling Gemini Nano Banana Pro …")
    print("  (this may take a minute)")
    result = recreate_scene(screenshot_path, MODEL_IMAGE, output_path=output_path)
    print(f"  ✓ Recreated scene saved → {result}")
    print()

    print("=" * 60)
    print(f"Done! Output saved to: {result}")
    print("=" * 60)


if __name__ == "__main__":
    main()
