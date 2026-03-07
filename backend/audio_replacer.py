"""
Audio Replacement Service

Replaces the audio track in a video with a new audio file.
If the video is longer than the audio, the video is trimmed to match the audio duration.
If the audio is longer than the video, the audio is trimmed to match the video duration.
"""

import os
import subprocess
from typing import Optional


def replace_audio(
    video_path: str,
    audio_path: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Replace the audio track in a video with a new audio file.

    The output duration will match the shorter of the two (video or audio).
    If video is longer than audio: video is trimmed to match audio.
    If audio is longer than video: audio is trimmed to match video.

    Args:
        video_path: Path to the input video file.
        audio_path: Path to the audio file to use as replacement.
        output_path: Path for the output video. If None, an auto-generated
                     path is used.

    Returns:
        The path to the output video with replaced audio.

    Raises:
        FileNotFoundError: If either video or audio file does not exist.
        RuntimeError: If FFmpeg fails to replace the audio.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Build output path if not provided
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_with_audio{ext}"

    # Ensure the output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Get durations
    video_duration = _get_video_duration(video_path)
    audio_duration = _get_audio_duration(audio_path)

    # Determine which is shorter and use that as the output duration
    output_duration = min(video_duration, audio_duration)

    # Build FFmpeg command
    # -i video: input video
    # -i audio: input audio
    # -t duration: limit output to this duration (trims if longer)
    # -map 0:v: use video from first input
    # -map 1:a: use audio from second input
    # -c:v copy: copy video codec (no re-encoding)
    # -c:a aac: encode audio as AAC
    # -shortest: automatically stop at shortest stream (alternative to -t)
    cmd = [
        "ffmpeg",
        "-y",                   # overwrite without asking
        "-i", video_path,       # input video
        "-i", audio_path,       # input audio
        "-t", str(output_duration),  # limit to shortest duration
        "-map", "0:v:0",        # map video stream from first input
        "-map", "1:a:0",        # map audio stream from second input
        "-c:v", "copy",         # copy video codec (no re-encoding)
        "-c:a", "aac",          # encode audio as AAC
        "-b:a", "192k",         # audio bitrate
        "-ar", "44100",         # sample rate
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg audio replacement failed (exit {result.returncode}): "
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
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def _get_audio_duration(audio_path: str) -> float:
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
