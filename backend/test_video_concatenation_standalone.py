"""
Standalone test script for video concatenation service.

Tests Phase 2: Video Concatenation
Uses: backend/input/final_output_testing.mp4 (video1) + backend/input/extended.mp4 (video2)
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from video_concatenator import concatenate_videos, get_video_duration


def main():
    """Test video concatenation."""
    # Test file paths
    base_dir = os.path.dirname(__file__)
    video1_path = os.path.join(base_dir, "input", "final_output_testing.mp4")
    video2_path = os.path.join(base_dir, "input", "extended.mp4")
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_video = os.path.join(output_dir, "concatenated_video.mp4")

    print("=" * 60)
    print("Phase 2: Video Concatenation Test")
    print("=" * 60)
    print(f"Video 1 (pipeline output): {video1_path}")
    print(f"Video 2 (additional): {video2_path}")
    print(f"Output video: {output_video}")
    print()

    # Check if input files exist
    if not os.path.isfile(video1_path):
        print(f"ERROR: Video 1 not found: {video1_path}")
        sys.exit(1)
    if not os.path.isfile(video2_path):
        print(f"ERROR: Video 2 not found: {video2_path}")
        sys.exit(1)

    # Get video durations
    print("[1/4] Getting video durations...")
    try:
        video1_duration = get_video_duration(video1_path)
        video2_duration = get_video_duration(video2_path)
        print(f"  ✓ Video 1 duration: {video1_duration:.2f} seconds")
        print(f"  ✓ Video 2 duration: {video2_duration:.2f} seconds")
        expected_duration = video1_duration + video2_duration
        print(f"  ✓ Expected output duration: {expected_duration:.2f} seconds")
    except Exception as e:
        print(f"  ✗ Failed to get video durations: {e}")
        sys.exit(1)

    # Concatenate videos
    print("\n[2/4] Concatenating videos...")
    try:
        concatenated_path = concatenate_videos(video1_path, video2_path, output_video)
        print(f"  ✓ Videos concatenated: {concatenated_path}")
    except Exception as e:
        print(f"  ✗ Video concatenation failed: {e}")
        sys.exit(1)

    # Verify output file exists
    if not os.path.isfile(concatenated_path):
        print(f"  ✗ Output video not found: {concatenated_path}")
        sys.exit(1)

    # Get output video duration
    print("\n[3/4] Verifying concatenated video...")
    try:
        output_duration = get_video_duration(concatenated_path)
        print(f"  ✓ Output duration: {output_duration:.2f} seconds")
    except Exception as e:
        print(f"  ✗ Failed to get output duration: {e}")
        sys.exit(1)

    # Verify duration matches
    print("\n[4/4] Checking duration match...")
    duration_diff = abs(output_duration - expected_duration)
    if duration_diff < 0.5:  # Allow 0.5s tolerance
        print(f"  ✓ Duration matches (difference: {duration_diff:.2f}s)")
    else:
        print(f"  ✗ Duration doesn't match (difference: {duration_diff:.2f}s)")
        print("\n✗ Phase 2 test FAILED!")
        sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"  Video 1 duration:  {video1_duration:.2f} seconds")
    print(f"  Video 2 duration:  {video2_duration:.2f} seconds")
    print(f"  Output duration:    {output_duration:.2f} seconds")
    print(f"  Expected duration: {expected_duration:.2f} seconds")
    print("\n✓ Phase 2 test PASSED!")


if __name__ == "__main__":
    main()
