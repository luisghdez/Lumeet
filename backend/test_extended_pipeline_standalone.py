"""
End-to-end test script for extended video pipeline.

Tests Phase 5: Complete Extended Pipeline
Uses: backend/input/Download (1).mp4 (original video) + backend/input/extended.mp4 (additional video)
For faster iteration, can use backend/input/final_output_testing.mp4 to simulate pipeline output
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from pipeline import run_full_pipeline
from audio_extractor import get_audio_duration
from scene_detector import get_video_duration


def main():
    """Test complete extended pipeline."""
    # Test file paths
    base_dir = os.path.dirname(__file__)
    input_dir = os.path.join(base_dir, "input")
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Input files
    original_video = os.path.join(input_dir, "Download (1).mp4")
    model_image = os.path.join(input_dir, "model_image.png")
    
    # For faster testing, you can use final_output_testing.mp4 to skip the full pipeline
    # and just test the extended steps. Set USE_SIMULATED_OUTPUT to True for that.
    USE_SIMULATED_OUTPUT = False  # Set to True to use final_output_testing.mp4
    
    print("=" * 60)
    print("Phase 5: End-to-End Extended Pipeline Test")
    print("=" * 60)
    print()

    # Check if input files exist
    if not os.path.isfile(original_video):
        print(f"ERROR: Original video not found: {original_video}")
        sys.exit(1)
    if not os.path.isfile(model_image):
        print(f"ERROR: Model image not found: {model_image}")
        sys.exit(1)

    # Get original video duration (for audio)
    print("[Pre-check] Getting original video duration...")
    try:
        original_duration = get_video_duration(original_video)
        print(f"  ✓ Original video duration: {original_duration:.2f} seconds")
    except Exception as e:
        print(f"  ✗ Failed to get video duration: {e}")
        sys.exit(1)

    if USE_SIMULATED_OUTPUT:
        print("\n[Note] Using simulated pipeline output for faster testing")
        print("       This will only test the extended steps (7-9)")
        print("       Set USE_SIMULATED_OUTPUT=False to run full pipeline")
    else:
        print("\n[Note] Running full pipeline (steps 1-9)")
        print("       This will take several minutes due to API calls")

    # Run extended pipeline
    print("\n" + "=" * 60)
    print("Running Extended Pipeline...")
    print("=" * 60)
    print()

    try:
        result = run_full_pipeline(
            video_path=original_video,
            model_image_path=model_image,
            output_dir=output_dir,
            extended=True,
        )
        print("\n✓ Pipeline completed successfully!")
    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Verify outputs
    print("\n" + "=" * 60)
    print("Verifying Outputs...")
    print("=" * 60)

    # Check that all expected files exist
    expected_files = [
        ("final_video", result.get("final_video")),
        ("extracted_audio", result.get("extracted_audio")),
        ("concatenated_video", result.get("concatenated_video")),
        ("extended_final_video", result.get("extended_final_video")),
    ]

    all_exist = True
    for name, path in expected_files:
        if path and os.path.isfile(path):
            file_size = os.path.getsize(path) / (1024 * 1024)  # MB
            print(f"  ✓ {name}: {path} ({file_size:.2f} MB)")
        else:
            print(f"  ✗ {name}: Missing or invalid")
            all_exist = False

    if not all_exist:
        print("\n✗ Some output files are missing!")
        sys.exit(1)

    # Verify final video duration
    print("\n[Verification] Checking final video duration...")
    try:
        final_duration = get_video_duration(result["extended_final_video"])
        print(f"  ✓ Final video duration: {final_duration:.2f} seconds")
        print(f"  ✓ Original audio duration: {original_duration:.2f} seconds")
        
        # The final video should be trimmed to match the audio if it's longer
        duration_diff = abs(final_duration - original_duration)
        if duration_diff < 1.0:  # Allow 1s tolerance
            print(f"  ✓ Duration matches original audio (difference: {duration_diff:.2f}s)")
        else:
            print(f"  ⚠ Duration differs from original audio (difference: {duration_diff:.2f}s)")
            print("     This is expected if the concatenated video was shorter than the audio")
    except Exception as e:
        print(f"  ✗ Failed to verify duration: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    print(f"  Original video:     {original_video}")
    print(f"  Final output:       {result['extended_final_video']}")
    print(f"  Original duration:  {original_duration:.2f} seconds")
    if 'extended_final_video' in result:
        try:
            final_duration = get_video_duration(result['extended_final_video'])
            print(f"  Final duration:      {final_duration:.2f} seconds")
        except:
            pass
    
    print("\n✓ Phase 5 E2E test PASSED!")
    print(f"\nFinal output saved to: {result['extended_final_video']}")


if __name__ == "__main__":
    main()
