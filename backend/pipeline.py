"""
Unified Video Generation Pipeline
===================================
Orchestrates all services into a single end-to-end flow:

    1. Scene Detection   — trim the video at the first scene cut
    2. Frame Extraction   — screenshot at second 1
    3. Caption Detection  — detect on-screen captions via OpenAI Vision
    4. Scene Recreation   — Gemini Nano Banana identity swap
    5. Motion Control     — Fal AI Kling video generation
    6. Caption Overlay    — burn detected caption into the final video

Usage (standalone):
    cd backend && source venv/bin/activate
    export OPENAI_API_KEY='...'
    export GEMINI_API_KEY='...'
    export FAL_KEY='...'        # or FAL_AI
    python pipeline.py

Usage (as library):
    from pipeline import run_full_pipeline
    result = run_full_pipeline("input/video.mp4", "input/model.png", "output/")
"""

import os
import sys
from typing import Optional

from scene_detector import crop_to_first_scene
from frame_extractor import extract_frame
from caption_detector import detect_captions_summary
from scene_recreator import recreate_scene
from motion_control import generate_motion_video
from caption_overlay import overlay_caption


def run_full_pipeline(
    video_path: str,
    model_image_path: str,
    output_dir: str,
    prompt: Optional[str] = None,
    motion_prompt: str = "A young woman reacting to the camera",
) -> dict:
    """
    Run the full video generation pipeline.

    Args:
        video_path: Path to the raw input video.
        model_image_path: Path to the model/identity reference image.
        output_dir: Directory where all intermediate and final files are saved.
        prompt: Custom prompt for Gemini scene recreation. None uses the default.
        motion_prompt: Prompt for the Fal AI motion control step.

    Returns:
        A dict with paths and metadata for each step:
            - trimmed_video: path to the scene-cut-trimmed video (or original if no cut)
            - screenshot: path to the extracted frame
            - caption: detected caption text (or None)
            - recreated_scene: path to the Gemini-generated image
            - raw_video: path to the Kling-generated video (before caption)
            - final_video: path to the final output video (with caption if detected)

    Raises:
        FileNotFoundError: If input files don't exist.
        EnvironmentError: If required API keys are missing.
        RuntimeError: If any step fails.
    """
    # --- Validate inputs ---
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if not os.path.isfile(model_image_path):
        raise FileNotFoundError(f"Model image not found: {model_image_path}")

    os.makedirs(output_dir, exist_ok=True)

    result = {}

    # =========================================================================
    # Step 1: Scene Detection — trim at first scene cut
    # =========================================================================
    print("=" * 60)
    print("[1/6] Scene Detection")
    print("=" * 60)

    trimmed_path = os.path.join(output_dir, "trimmed.mp4")
    trim_result = crop_to_first_scene(video_path, output_path=trimmed_path)

    if trim_result is not None:
        result["trimmed_video"] = trim_result["output_path"]
        print(f"  ✓ Trimmed at {trim_result['cut_at_seconds']:.2f}s")
    else:
        # No scene change — use the original video
        result["trimmed_video"] = video_path
        print("  No scene change detected — using original video.")

    working_video = result["trimmed_video"]
    print()

    # =========================================================================
    # Step 2: Frame Extraction — screenshot at second 1
    # =========================================================================
    print("=" * 60)
    print("[2/6] Frame Extraction (1s)")
    print("=" * 60)

    screenshot_path = os.path.join(output_dir, "scene_screenshot.png")
    result["screenshot"] = extract_frame(
        working_video, timestamp_sec=1.0, output_path=screenshot_path
    )
    print(f"  ✓ Screenshot saved → {result['screenshot']}")
    print()

    # =========================================================================
    # Step 3: Caption Detection — OpenAI Vision
    # =========================================================================
    print("=" * 60)
    print("[3/6] Caption Detection (GPT-4o Vision)")
    print("=" * 60)

    caption = detect_captions_summary(working_video, interval_sec=0.5)
    result["caption"] = caption

    if caption:
        print(f"  ✓ Caption detected: \"{caption}\"")
    else:
        print("  No caption detected.")
    print()

    # =========================================================================
    # Step 4: Scene Recreation — Gemini Nano Banana Pro
    # =========================================================================
    print("=" * 60)
    print("[4/6] Scene Recreation (Gemini Nano Banana Pro)")
    print("=" * 60)

    recreated_path = os.path.join(output_dir, "recreated_scene.png")
    result["recreated_scene"] = recreate_scene(
        result["screenshot"],
        model_image_path,
        output_path=recreated_path,
        prompt=prompt,
    )
    print(f"  ✓ Recreated scene → {result['recreated_scene']}")
    print()

    # =========================================================================
    # Step 5: Motion Control — Fal AI Kling
    # =========================================================================
    print("=" * 60)
    print("[5/6] Motion Control (Fal AI Kling 2.6)")
    print("=" * 60)

    raw_video_path = os.path.join(output_dir, "generated_raw.mp4")
    result["raw_video"] = generate_motion_video(
        result["recreated_scene"],
        working_video,
        raw_video_path,
        prompt=motion_prompt,
    )
    print(f"  ✓ Generated video → {result['raw_video']}")
    print()

    # =========================================================================
    # Step 6: Caption Overlay — burn caption into the video
    # =========================================================================
    print("=" * 60)
    print("[6/6] Caption Overlay")
    print("=" * 60)

    if result["caption"]:
        final_path = os.path.join(output_dir, "final_output.mp4")
        result["final_video"] = overlay_caption(
            result["raw_video"],
            result["caption"],
            output_path=final_path,
        )
        print(f"  ✓ Final video with caption → {result['final_video']}")
    else:
        # No caption — the raw video IS the final video
        result["final_video"] = result["raw_video"]
        print("  No caption to overlay — raw video is the final output.")

    print()
    print("=" * 60)
    print(f"DONE! Final output: {result['final_video']}")
    print("=" * 60)

    return result


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point with default paths for testing."""
    INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

    video_path = os.path.join(INPUT_DIR, "Download (6).mp4")
    model_image = os.path.join(INPUT_DIR, "model_image.png")

    # Check required env vars upfront
    missing = []
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.environ.get("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")
    if not (os.environ.get("FAL_KEY") or os.environ.get("FAL_AI")):
        missing.append("FAL_KEY (or FAL_AI)")

    if missing:
        print("ERROR: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        sys.exit(1)

    result = run_full_pipeline(video_path, model_image, OUTPUT_DIR)

    print("\n--- Pipeline Summary ---")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
