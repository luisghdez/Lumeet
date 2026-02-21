"""
Quick CLI script to process videos dropped into the input/ folder.

Usage:
    python process_video.py                  # processes all videos in input/
    python process_video.py my_video.mp4     # processes a specific file from input/

Requires OPENAI_API_KEY environment variable to be set.
"""

import os
import sys

from scene_detector import detect_first_scene_change, crop_to_first_scene
from caption_detector import detect_captions

INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv"}


def process_file(video_path: str):
    """Detect the first scene change, trim, and extract captions."""
    filename = os.path.basename(video_path)
    name, ext = os.path.splitext(filename)
    output_path = os.path.join(OUTPUT_DIR, f"{name}_trimmed{ext}")

    print(f"\n{'='*60}")
    print(f"Processing: {filename}")
    print(f"{'='*60}")

    # Step 1: Detect first scene change
    print("\n  [1/3] Detecting first scene change...")
    detection = detect_first_scene_change(video_path)

    if detection is None:
        print("  No scene change detected.")
    else:
        print(f"  First cut found at {detection['timecode']:.3f}s (frame {detection['frame']})")

    # Step 2: Crop to first scene
    if detection is not None:
        print(f"\n  [2/3] Trimming video to {detection['timecode']:.3f}s...")
        result = crop_to_first_scene(video_path, output_path=output_path)
        print(f"  Saved trimmed video to: {result['output_path']}")
        caption_video = result["output_path"]
    else:
        print("\n  [2/3] Skipping trim (no scene change).")
        caption_video = video_path

    # Step 3: Detect captions via OpenAI Vision
    print(f"\n  [3/3] Detecting on-screen captions (GPT-4o Vision)...")
    caption_result = detect_captions(caption_video, interval_sec=0.5)

    if caption_result is None or caption_result.get("caption") is None:
        print("  No captions detected.")
    else:
        print(f"  Frames analysed: {caption_result['frames_analysed']}")
        print(f"\n  Caption: \"{caption_result['caption']}\"")

    print(f"\n  Done!")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("  export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        video_path = os.path.join(INPUT_DIR, filename) if not os.path.isabs(filename) else filename
        if not os.path.isfile(video_path):
            print(f"Error: File not found: {video_path}")
            sys.exit(1)
        process_file(video_path)
    else:
        videos = [
            f for f in os.listdir(INPUT_DIR)
            if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
        ]

        if not videos:
            print(f"No video files found in {INPUT_DIR}/")
            print(f"Drop a video file there and re-run this script.")
            sys.exit(0)

        print(f"Found {len(videos)} video(s) in input/")
        for filename in sorted(videos):
            video_path = os.path.join(INPUT_DIR, filename)
            process_file(video_path)

    print(f"\nAll done! Check the output/ folder.")


if __name__ == "__main__":
    main()
