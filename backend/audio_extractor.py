"""
Audio Extractor Service

Extracts the full-length audio track from a video file using FFmpeg.
"""

import os
import subprocess
from typing import Optional


def extract_audio(
    video_path: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Extract the audio track from a video file.

    Args:
        video_path: Path to the input video file.
        output_path: Path for the output audio file. If None, an auto-generated
                     path is used (e.g. ``video_audio.aac``).

    Returns:
        The path to the extracted audio file.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If FFmpeg fails to extract the audio.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Build output path if not provided
    if output_path is None:
        base, _ = os.path.splitext(video_path)
        output_path = f"{base}_audio.m4a"  # Use M4A (MP4 container) for better duration accuracy

    # Ensure the output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Get video duration to limit audio extraction
    video_duration = _get_video_duration(video_path)

    # Extract audio using FFmpeg
    # Use input seeking (-ss and -t before -i) to ensure accurate duration
    # -vn: disable video
    # Use M4A container (MP4) for better duration accuracy than raw AAC
    # -y: overwrite without asking
    cmd = [
        "ffmpeg",
        "-y",                   # overwrite without asking
        "-ss", "0",             # start from beginning
        "-t", str(video_duration),  # limit duration (input seeking)
        "-i", video_path,
        "-vn",                  # disable video
        "-acodec", "aac",       # convert to AAC format
        "-b:a", "192k",         # audio bitrate
        "-ar", "44100",         # sample rate
        "-f", "ipod",           # Use MP4/M4A container format
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg audio extraction failed (exit {result.returncode}): "
            f"{result.stderr}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"FFmpeg completed but output file not found: {output_path}"
        )

    return output_path


def _get_video_duration(video_path: str) -> float:
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
        "-select_streams", "v:0",  # select video stream
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    duration = result.stdout.strip()
    if not duration:
        # Fallback to format duration if stream duration not available
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = result.stdout.strip()
    
    return float(duration)


def get_audio_duration(audio_path: str) -> float:
    """
    Get the duration of an audio file in seconds using ffprobe.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Duration in seconds as a float.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        RuntimeError: If ffprobe fails.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())
