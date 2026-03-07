"""
Unified Video Generation Pipeline
===================================
Orchestrates all services into a single end-to-end flow:

    1. Scene Detection   -- trim the video at the first scene cut
    2. Frame Extraction  -- screenshot at second 1
    3. Caption Detection  -- detect on-screen captions via OpenAI Vision
    4. Scene Recreation   -- Gemini Nano Banana identity swap
    5. Motion Control     -- Fal AI Kling video generation
    6. Caption Overlay    -- burn detected caption into the final video

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
from typing import Callable, Optional

from scene_detector import crop_to_first_scene
from frame_extractor import extract_frame
from caption_detector import detect_captions_summary
from scene_recreator import recreate_scene
from motion_control import generate_motion_video
from caption_overlay import overlay_caption
from audio_extractor import extract_audio
from video_concatenator import concatenate_videos
from audio_replacer import replace_audio
from config import ADDITIONAL_VIDEO_PATH


def _noop_callback(step_key: str, event: str, message: str = "") -> None:
    """Default no-op callback when no progress reporter is provided."""
    pass


def run_full_pipeline(
    video_path: str,
    model_image_path: str,
    output_dir: str,
    prompt: Optional[str] = None,
    motion_prompt: str = "A young woman reacting to the camera",
    on_step: Optional[Callable[[str, str, str], None]] = None,
    extended: bool = False,
    additional_video_path: Optional[str] = None,
) -> dict:
    """
    Run the full video generation pipeline.

    Args:
        video_path: Path to the raw input video.
        model_image_path: Path to the model/identity reference image.
        output_dir: Directory where all intermediate and final files are saved.
        prompt: Custom prompt for Gemini scene recreation. None uses the default.
        motion_prompt: Prompt for the Fal AI motion control step.
        on_step: Optional callback ``(step_key, event, message)`` where
                 event is ``'start'``, ``'complete'``, or ``'fail'``.
                 Used by the job manager to track progress.
        extended: If True, run extended pipeline (concatenate additional video and replace audio).
        additional_video_path: Path to additional video to append. If None and extended=True,
                              uses ADDITIONAL_VIDEO_PATH from config.

    Returns:
        A dict with paths and metadata for each step:
            - trimmed_video: path to the scene-cut-trimmed video (or original if no cut)
            - screenshot: path to the extracted frame
            - caption: detected caption text (or None)
            - recreated_scene: path to the Gemini-generated image
            - raw_video: path to the Kling-generated video (before caption)
            - final_video: path to the final output video (with caption if detected)
            - extracted_audio: path to extracted audio (if extended=True)
            - concatenated_video: path to concatenated video (if extended=True)
            - extended_final_video: path to final extended video (if extended=True)

    Raises:
        FileNotFoundError: If input files don't exist.
        EnvironmentError: If required API keys are missing.
        RuntimeError: If any step fails.
    """
    cb = on_step or _noop_callback

    # --- Validate inputs ---
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if not os.path.isfile(model_image_path):
        raise FileNotFoundError(f"Model image not found: {model_image_path}")

    os.makedirs(output_dir, exist_ok=True)

    result = {}

    # =========================================================================
    # Step 1: Scene Detection -- trim at first scene cut
    # =========================================================================
    cb("scene_detection", "start", "Detecting scene changes...")
    print("=" * 60)
    print("[1/6] Scene Detection")
    print("=" * 60)

    trimmed_path = os.path.join(output_dir, "trimmed.mp4")
    trim_result = crop_to_first_scene(video_path, output_path=trimmed_path)

    if trim_result is not None:
        result["trimmed_video"] = trim_result["output_path"]
        msg = f"Trimmed at {trim_result['cut_at_seconds']:.2f}s"
        print(f"  {msg}")
    else:
        result["trimmed_video"] = video_path
        msg = "No scene change detected -- using original video."
        print(f"  {msg}")

    working_video = result["trimmed_video"]
    cb("scene_detection", "complete", msg)
    print()

    # =========================================================================
    # Step 2: Frame Extraction -- screenshot at second 1
    # =========================================================================
    cb("frame_extraction", "start", "Extracting reference frame...")
    print("=" * 60)
    print("[2/6] Frame Extraction (1s)")
    print("=" * 60)

    screenshot_path = os.path.join(output_dir, "scene_screenshot.png")
    result["screenshot"] = extract_frame(
        working_video, timestamp_sec=1.0, output_path=screenshot_path
    )
    msg = f"Screenshot saved"
    print(f"  {msg}")
    cb("frame_extraction", "complete", msg)
    print()

    # =========================================================================
    # Step 3: Caption Detection -- OpenAI Vision
    # =========================================================================
    cb("caption_detection", "start", "Detecting on-screen captions...")
    print("=" * 60)
    print("[3/6] Caption Detection (GPT-4o Vision)")
    print("=" * 60)

    caption = detect_captions_summary(working_video, interval_sec=0.5)
    result["caption"] = caption

    if caption:
        msg = f'Caption: "{caption}"'
        print(f"  {msg}")
    else:
        msg = "No caption detected."
        print(f"  {msg}")
    cb("caption_detection", "complete", msg)
    print()

    # =========================================================================
    # Step 4: Scene Recreation -- Gemini Nano Banana Pro
    # =========================================================================
    cb("scene_recreation", "start", "Recreating scene with Gemini...")
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
    msg = "Recreated scene saved"
    print(f"  {msg}")
    cb("scene_recreation", "complete", msg)
    print()

    # =========================================================================
    # Step 5: Motion Control -- Fal AI Kling
    # =========================================================================
    cb("motion_control", "start", "Generating video with Kling AI (this may take a few minutes)...")
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
    msg = "Video generated"
    print(f"  {msg}")
    cb("motion_control", "complete", msg)
    print()

    # =========================================================================
    # Step 6: Caption Overlay -- burn caption into the video
    # =========================================================================
    cb("caption_overlay", "start", "Adding caption overlay...")
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
        msg = "Caption overlaid on video"
        print(f"  {msg}")
    else:
        result["final_video"] = result["raw_video"]
        msg = "No caption to overlay -- raw video is the final output."
        print(f"  {msg}")

    cb("caption_overlay", "complete", msg)
    print()

    # =========================================================================
    # Extended Pipeline Steps (if enabled)
    # =========================================================================
    if extended:
        # Determine additional video path
        if additional_video_path is None:
            additional_video_path = ADDITIONAL_VIDEO_PATH
        
        if not os.path.isfile(additional_video_path):
            raise FileNotFoundError(
                f"Additional video not found: {additional_video_path}"
            )

        # Step 7: Audio Extraction
        cb("audio_extraction", "start", "Extracting audio from original video...")
        print("=" * 60)
        print("[7/9] Audio Extraction")
        print("=" * 60)

        extracted_audio_path = os.path.join(output_dir, "extracted_audio.aac")
        result["extracted_audio"] = extract_audio(
            video_path, output_path=extracted_audio_path
        )
        msg = "Audio extracted from original video"
        print(f"  {msg}")
        cb("audio_extraction", "complete", msg)
        print()

        # Step 8: Video Concatenation
        cb("video_concatenation", "start", "Concatenating videos...")
        print("=" * 60)
        print("[8/9] Video Concatenation")
        print("=" * 60)

        concatenated_path = os.path.join(output_dir, "concatenated.mp4")
        result["concatenated_video"] = concatenate_videos(
            result["final_video"],
            additional_video_path,
            output_path=concatenated_path,
        )
        msg = "Videos concatenated"
        print(f"  {msg}")
        cb("video_concatenation", "complete", msg)
        print()

        # Step 9: Audio Replacement
        cb("audio_replacement", "start", "Replacing audio with original...")
        print("=" * 60)
        print("[9/9] Audio Replacement")
        print("=" * 60)

        extended_final_path = os.path.join(output_dir, "extended_final_output.mp4")
        result["extended_final_video"] = replace_audio(
            result["concatenated_video"],
            result["extracted_audio"],
            output_path=extended_final_path,
        )
        msg = "Audio replaced with original"
        print(f"  {msg}")
        cb("audio_replacement", "complete", msg)
        print()

        # Update final_video to point to extended version
        result["final_video"] = result["extended_final_video"]

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
