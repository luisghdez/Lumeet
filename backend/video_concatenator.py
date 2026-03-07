"""
Video Concatenation Service

Concatenates two videos together using FFmpeg.
Handles resolution and framerate mismatches by scaling/converting to match the first video.
Output video has no audio track (silent).
"""

import os
import subprocess
from typing import Optional


def concatenate_videos(
    video1_path: str,
    video2_path: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Concatenate two videos together.

    The second video will be scaled/converted to match the first video's
    resolution and framerate. The output video will have no audio track.

    Args:
        video1_path: Path to the first video (pipeline output).
        video2_path: Path to the second video (additional video to append).
        output_path: Path for the concatenated output video. If None, an
                     auto-generated path is used.

    Returns:
        The path to the concatenated video file.

    Raises:
        FileNotFoundError: If either video file does not exist.
        RuntimeError: If FFmpeg fails to concatenate the videos.
    """
    if not os.path.isfile(video1_path):
        raise FileNotFoundError(f"Video 1 not found: {video1_path}")
    if not os.path.isfile(video2_path):
        raise FileNotFoundError(f"Video 2 not found: {video2_path}")

    # Build output path if not provided
    if output_path is None:
        base, ext = os.path.splitext(video1_path)
        output_path = f"{base}_concatenated{ext}"

    # Ensure the output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Get video1 properties to match
    video1_width, video1_height, video1_fps = _get_video_properties(video1_path)

    # Use FFmpeg with separate inputs and filter_complex to scale and concat
    # Scale both videos to match video1's properties and concatenate without audio
    cmd = [
        "ffmpeg",
        "-y",                           # overwrite without asking
        "-i", video1_path,              # input video 1
        "-i", video2_path,              # input video 2
        "-filter_complex", (
            f"[0:v]scale={video1_width}:{video1_height},setsar=1:1,fps={video1_fps}[v0];"
            f"[1:v]scale={video1_width}:{video1_height},setsar=1:1,fps={video1_fps}[v1];"
            f"[v0][v1]concat=n=2:v=1:a=0[outv]"  # concat with no audio
        ),
        "-map", "[outv]",                # map the output video
        "-c:v", "libx264",               # video codec
        "-pix_fmt", "yuv420p",           # pixel format
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg video concatenation failed (exit {result.returncode}): "
            f"{result.stderr}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"FFmpeg completed but output file not found: {output_path}"
        )

    return output_path


def _get_video_properties(video_path: str) -> tuple[int, int, float]:
    """
    Get video width, height, and framerate using ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Tuple of (width, height, fps).

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If ffprobe fails.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Get width and height
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "csv=s=x:p=0",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    parts = result.stdout.strip().split("x")
    
    if len(parts) < 3:
        raise RuntimeError(f"Failed to parse video properties: {result.stdout}")

    width = int(parts[0])
    height = int(parts[1])
    
    # Parse framerate (format: "num/den" or just a number)
    fps_str = parts[2].strip()
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    else:
        fps = float(fps_str)

    return width, height, fps


def get_video_duration(video_path: str) -> float:
    """
    Get the duration of a video file in seconds using ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Duration in seconds as a float.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If ffprobe fails.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())
