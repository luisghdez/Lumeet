"""
Frame Extractor Service

Extracts a single frame (screenshot) from a video at a specified timestamp
using FFmpeg.
"""

import os
import subprocess


def extract_frame(
    video_path: str,
    timestamp_sec: float = 2.0,
    output_path: str = None,
) -> str:
    """
    Extract a single frame from a video at the given timestamp.

    Args:
        video_path: Path to the input video file.
        timestamp_sec: The timestamp (in seconds) at which to capture the frame.
                       Defaults to 2.0.
        output_path: Path for the output PNG image. If None, an auto-generated
                     path is used (e.g. ``video_frame_2s.png``).

    Returns:
        The path to the saved PNG screenshot.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If FFmpeg fails to extract the frame.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Build output path if not provided
    if output_path is None:
        base, _ = os.path.splitext(video_path)
        output_path = f"{base}_frame_{timestamp_sec}s.png"

    # Ensure the output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",                       # overwrite without asking
        "-ss", str(timestamp_sec),  # seek to timestamp
        "-i", video_path,
        "-frames:v", "1",           # extract exactly one frame
        "-q:v", "2",                # high quality
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg frame extraction failed (exit {result.returncode}): "
            f"{result.stderr}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"FFmpeg completed but output file not found: {output_path}"
        )

    return output_path
