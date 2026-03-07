"""
Standalone test script for audio replacement service.

Tests Phase 3: Audio Replacement
Uses: concatenated video from Phase 2 + audio from Phase 1 (Download (1).mp4)
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from audio_replacer import replace_audio, _get_video_duration, _get_audio_duration
from audio_extractor import extract_audio
from video_concatenator import concatenate_videos


def main():
    """Test audio replacement in video."""
    # Test file paths
    base_dir = os.path.dirname(__file__)
    input_dir = os.path.join(base_dir, "input")
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Input files
    original_video = os.path.join(input_dir, "Download (1).mp4")
    video1_path = os.path.join(input_dir, "final_output_testing.mp4")
    video2_path = os.path.join(input_dir, "extended.mp4")
    
    # Intermediate files
    extracted_audio = os.path.join(output_dir, "test_extracted_audio.aac")
    concatenated_video = os.path.join(output_dir, "test_concatenated.mp4")
    
    # Final output
    final_output = os.path.join(output_dir, "test_final_with_audio.mp4")

    print("=" * 60)
    print("Phase 3: Audio Replacement Test")
    print("=" * 60)
    print()

    # Step 1: Extract audio from original video (Phase 1)
    print("[1/5] Extracting audio from original video...")
    if not os.path.isfile(original_video):
        print(f"ERROR: Original video not found: {original_video}")
        sys.exit(1)
    
    try:
        extract_audio(original_video, extracted_audio)
        print(f"  ✓ Audio extracted: {extracted_audio}")
    except Exception as e:
        print(f"  ✗ Audio extraction failed: {e}")
        sys.exit(1)

    # Step 2: Concatenate videos (Phase 2)
    print("\n[2/5] Concatenating videos...")
    if not os.path.isfile(video1_path):
        print(f"ERROR: Video 1 not found: {video1_path}")
        sys.exit(1)
    if not os.path.isfile(video2_path):
        print(f"ERROR: Video 2 not found: {video2_path}")
        sys.exit(1)
    
    try:
        concatenate_videos(video1_path, video2_path, concatenated_video)
        print(f"  ✓ Videos concatenated: {concatenated_video}")
    except Exception as e:
        print(f"  ✗ Video concatenation failed: {e}")
        sys.exit(1)

    # Step 3: Get durations
    print("\n[3/5] Getting durations...")
    try:
        video_duration = _get_video_duration(concatenated_video)
        audio_duration = _get_audio_duration(extracted_audio)
        expected_duration = min(video_duration, audio_duration)
        print(f"  ✓ Video duration: {video_duration:.2f} seconds")
        print(f"  ✓ Audio duration: {audio_duration:.2f} seconds")
        print(f"  ✓ Expected output duration: {expected_duration:.2f} seconds")
    except Exception as e:
        print(f"  ✗ Failed to get durations: {e}")
        sys.exit(1)

    # Step 4: Replace audio
    print("\n[4/5] Replacing audio in video...")
    try:
        result_path = replace_audio(concatenated_video, extracted_audio, final_output)
        print(f"  ✓ Audio replaced: {result_path}")
    except Exception as e:
        print(f"  ✗ Audio replacement failed: {e}")
        sys.exit(1)

    # Step 5: Verify output
    print("\n[5/5] Verifying final output...")
    if not os.path.isfile(final_output):
        print(f"  ✗ Final output not found: {final_output}")
        sys.exit(1)
    
    try:
        output_duration = _get_video_duration(final_output)
        print(f"  ✓ Output duration: {output_duration:.2f} seconds")
    except Exception as e:
        print(f"  ✗ Failed to get output duration: {e}")
        sys.exit(1)

    # Verify duration matches
    duration_diff = abs(output_duration - expected_duration)
    if duration_diff < 0.5:  # Allow 0.5s tolerance
        print(f"  ✓ Duration matches (difference: {duration_diff:.2f}s)")
    else:
        print(f"  ✗ Duration doesn't match (difference: {duration_diff:.2f}s)")
        print("\n✗ Phase 3 test FAILED!")
        sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"  Video duration:     {video_duration:.2f} seconds")
    print(f"  Audio duration:     {audio_duration:.2f} seconds")
    print(f"  Output duration:    {output_duration:.2f} seconds")
    print(f"  Expected duration:  {expected_duration:.2f} seconds")
    print("\n✓ Phase 3 test PASSED!")


if __name__ == "__main__":
    main()
