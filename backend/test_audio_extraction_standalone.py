"""
Standalone test script for audio extraction service.

Tests Phase 1: Audio Extraction
Uses: backend/input/Download (1).mp4
"""

import os
import sys
import subprocess

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from audio_extractor import extract_audio, get_audio_duration


def get_video_duration(video_path: str) -> float:
    """Get video duration using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def main():
    """Test audio extraction from video."""
    # Test file paths
    input_video = os.path.join(os.path.dirname(__file__), "input", "Download (1).mp4")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_audio = os.path.join(output_dir, "extracted_audio.m4a")

    print("=" * 60)
    print("Phase 1: Audio Extraction Test")
    print("=" * 60)
    print(f"Input video: {input_video}")
    print(f"Output audio: {output_audio}")
    print()

    # Check if input file exists
    if not os.path.isfile(input_video):
        print(f"ERROR: Input video not found: {input_video}")
        sys.exit(1)

    # Get original video duration
    print("[1/3] Getting original video duration...")
    try:
        video_duration = get_video_duration(input_video)
        print(f"  ✓ Video duration: {video_duration:.2f} seconds")
    except Exception as e:
        print(f"  ✗ Failed to get video duration: {e}")
        sys.exit(1)

    # Extract audio
    print("\n[2/3] Extracting audio from video...")
    try:
        extracted_path = extract_audio(input_video, output_audio)
        print(f"  ✓ Audio extracted: {extracted_path}")
    except Exception as e:
        print(f"  ✗ Audio extraction failed: {e}")
        sys.exit(1)

    # Verify audio file exists
    if not os.path.isfile(extracted_path):
        print(f"  ✗ Audio file not found: {extracted_path}")
        sys.exit(1)

    # Get extracted audio duration
    print("\n[3/3] Verifying extracted audio...")
    try:
        audio_duration = get_audio_duration(extracted_path)
        print(f"  ✓ Audio duration: {audio_duration:.2f} seconds")
    except Exception as e:
        print(f"  ✗ Failed to get audio duration: {e}")
        sys.exit(1)

    # Compare durations
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"  Video duration:  {video_duration:.2f} seconds")
    print(f"  Audio duration: {audio_duration:.2f} seconds")
    
    duration_diff = abs(video_duration - audio_duration)
    
    # Durations should match exactly (within 0.1s tolerance for encoding)
    if duration_diff < 0.1:
        print(f"  ✓ Durations match (difference: {duration_diff:.2f}s)")
        print("\n✓ Phase 1 test PASSED!")
    else:
        print(f"  ✗ Durations don't match (difference: {duration_diff:.2f}s)")
        print("\n✗ Phase 1 test FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
