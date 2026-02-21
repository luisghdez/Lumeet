"""
Caption Overlay Service

Burns caption text onto a video using FFmpeg's drawtext filter,
styled to look like standard social-media captions.
"""

import os
import subprocess
from typing import Optional


def overlay_caption(
    video_path: str,
    caption_text: str,
    output_path: Optional[str] = None,
    font_size: int = 42,
) -> str:
    """
    Burn caption text onto a video as a styled text overlay.

    The caption is rendered as white text with a black outline,
    centered horizontally near the bottom of the frame.

    Args:
        video_path: Path to the input video.
        caption_text: The caption text to overlay.
        output_path: Path for the output video. If None, auto-generates
                     a ``_captioned`` suffix next to the input.
        font_size: Font size for the caption (default 42).

    Returns:
        The path to the output video with the caption overlay.

    Raises:
        FileNotFoundError: If the input video doesn't exist.
        ValueError: If caption_text is empty or None.
        RuntimeError: If FFmpeg fails.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not caption_text or not caption_text.strip():
        raise ValueError("caption_text must be a non-empty string.")

    # Build output path if not provided
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_captioned{ext}"

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Escape special characters for FFmpeg drawtext filter
    # FFmpeg drawtext needs : ; ' \ to be escaped
    escaped = caption_text.replace("\\", "\\\\\\\\")
    escaped = escaped.replace("'", "'\\\\\\''")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace(";", "\\;")

    # Build the drawtext filter
    # White text, black border, centered near the bottom
    drawtext_filter = (
        f"drawtext=text='{escaped}'"
        f":fontsize={font_size}"
        f":fontcolor=white"
        f":borderw=3"
        f":bordercolor=black"
        f":x=(w-text_w)/2"
        f":y=h-th-80"
        f":line_spacing=8"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", drawtext_filter,
        "-codec:a", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg caption overlay failed (exit {result.returncode}): "
            f"{result.stderr}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"FFmpeg completed but output file not found: {output_path}"
        )

    return output_path
