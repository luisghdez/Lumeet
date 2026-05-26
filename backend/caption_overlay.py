"""
Caption Overlay Service

Burns caption text onto a video with full emoji support.

Strategy:
  1. Render the wrapped caption as a transparent PNG using Pillow,
     using Apple Color Emoji for emoji characters on macOS.
  2. Overlay the PNG onto the video using FFmpeg's overlay filter.
"""

import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from video_overlay_styles import DEFAULT_OVERLAY, normalize_overlay_spec


# ---------------------------------------------------------------------------
# Emoji detection
# ---------------------------------------------------------------------------

EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
    "\U0001F680-\U0001F6FF"  # Transport & Map
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Extended-A
    "\U00002702-\U000027B0"  # Dingbats
    "\U00002600-\U000026FF"  # Misc Symbols
    "\U0000FE0F"             # Variation Selector
    "\U0000200D"             # Zero Width Joiner
    "]+",
    re.UNICODE,
)


def _split_runs(text: str) -> list[tuple[str, str]]:
    """Split text into ('text', ...) and ('emoji', ...) runs."""
    runs = []
    last = 0
    for m in EMOJI_RE.finditer(text):
        if m.start() > last:
            runs.append(("text", text[last:m.start()]))
        runs.append(("emoji", m.group()))
        last = m.end()
    if last < len(text):
        runs.append(("text", text[last:]))
    return runs


# ---------------------------------------------------------------------------
# Font loading (macOS-first, with fallbacks)
# ---------------------------------------------------------------------------

_TEXT_FONT_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/Arial.ttf", None),
    ("/Library/Fonts/Arial.ttf", None),
    ("/System/Library/Fonts/Supplemental/Helvetica.ttf", None),
    ("/System/Library/Fonts/Helvetica.ttc", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", None),
]
_EMOJI_FONT_PATH = "/System/Library/Fonts/Apple Color Emoji.ttc"

# Apple Color Emoji is a bitmap (sbix) font – only certain pixel sizes exist.
_APPLE_EMOJI_VALID_SIZES = [20, 26, 32, 40, 48, 52, 64, 96, 160]


def _nearest_emoji_size(desired: int) -> int:
    """Return the closest valid Apple Color Emoji bitmap size."""
    return min(_APPLE_EMOJI_VALID_SIZES, key=lambda s: abs(s - desired))


def _load_text_font(size: int) -> ImageFont.FreeTypeFont:
    for path, index in _TEXT_FONT_CANDIDATES:
        if not os.path.isfile(path):
            continue
        try:
            if index is None:
                return ImageFont.truetype(path, size)
            return ImageFont.truetype(path, size, index=index)
        except Exception:
            continue
    return ImageFont.load_default(size)


def _load_emoji_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    """Load Apple Color Emoji at the nearest valid bitmap size."""
    if os.path.isfile(_EMOJI_FONT_PATH):
        target = _nearest_emoji_size(size)
        try:
            return ImageFont.truetype(_EMOJI_FONT_PATH, target)
        except Exception:
            pass
    return None


def _parse_hex_color(value: str) -> tuple[int, int, int, int]:
    raw = str(value or DEFAULT_OVERLAY["fontColor"]).strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return (255, 255, 255, 255)
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 255)
    except ValueError:
        return (255, 255, 255, 255)


def _outline_width_for_style(style: str) -> int:
    if style == "bold":
        return 5
    if style == "minimal":
        return 0
    return 3


# ---------------------------------------------------------------------------
# Caption rendering
# ---------------------------------------------------------------------------

def _wrap_caption(text: str, max_chars: int = 25) -> list[str]:
    """Word-wrap caption text into lines."""
    return textwrap.wrap(text, width=max_chars)


def _measure_run(draw: ImageDraw.ImageDraw, content: str,
                 font: ImageFont.FreeTypeFont) -> int:
    """Return the pixel width of a text/emoji run."""
    bbox = draw.textbbox((0, 0), content, font=font)
    return bbox[2] - bbox[0]


def _line_metrics(draw: ImageDraw.ImageDraw, line: str, text_font, emoji_font) -> tuple[int, int]:
    runs = _split_runs(line)
    width = 0
    height = 0
    for kind, content in runs:
        font = emoji_font if kind == "emoji" and emoji_font else text_font
        bbox = draw.textbbox((0, 0), content, font=font)
        width += bbox[2] - bbox[0]
        height = max(height, bbox[3] - bbox[1])
    return width, height


def _render_caption_png(
    caption_text: str,
    output_path: str,
    canvas_width: int,
    font_size: int = 48,
    max_chars: int = 25,
    border: int = 3,
    text_color: str = "#FFFFFF",
    style: str = "classic",
) -> str:
    """Render wrapped caption as a transparent PNG with emoji support."""
    lines = _wrap_caption(caption_text, max_chars=max_chars)
    if not lines:
        return None

    text_font = _load_text_font(font_size)
    emoji_font = _load_emoji_font(font_size)
    fill_rgba = _parse_hex_color(text_color)
    style = (style or "classic").strip().lower()
    border = border if border is not None else _outline_width_for_style(style)

    line_height = int(font_size * 1.6)
    img_h = len(lines) * line_height + 2 * max(border, 3) + 24

    img = Image.new("RGBA", (canvas_width, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    outline_offsets = []
    if style in {"classic", "bold"} and border > 0:
        outline_offsets = [
            (-border, 0), (border, 0), (0, -border), (0, border),
            (-border, -border), (border, -border),
            (-border, border), (border, border),
        ]

    y = max(border, 3) + 5
    for line in lines:
        runs = _split_runs(line)
        total_w = 0
        line_h = 0
        for kind, content in runs:
            font = emoji_font if kind == "emoji" and emoji_font else text_font
            w, h = _line_metrics(draw, content, text_font, emoji_font)
            total_w += w
            line_h = max(line_h, h)

        x = (canvas_width - total_w) // 2

        if style == "background":
            pad_x = 18
            pad_y = 10
            box = [x - pad_x, y - pad_y, x + total_w + pad_x, y + line_h + pad_y]
            draw.rounded_rectangle(box, radius=12, fill=(0, 0, 0, 170))

        for kind, content in runs:
            font = emoji_font if kind == "emoji" and emoji_font else text_font

            if kind == "text":
                for dx, dy in outline_offsets:
                    draw.text((x + dx, y + dy), content, font=font, fill=(0, 0, 0, 255))
                draw.text((x, y), content, font=font, fill=fill_rgba)
            else:
                draw.text((x, y), content, font=font, embedded_color=True)

            x += _measure_run(draw, content, font)

        y += line_height

    content_bbox = img.getbbox()
    if content_bbox:
        img = img.crop((0, 0, canvas_width, content_bbox[3] + 5))

    img.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Video probing / passthrough
# ---------------------------------------------------------------------------

def _probe_dimensions(video_path: str) -> tuple[int, int]:
    """Get video width and height via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split("x")
    return int(w), int(h)


def copy_video_without_overlay(video_path: str, output_path: Optional[str] = None) -> str:
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_plain{ext}"

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if os.path.abspath(video_path) == os.path.abspath(output_path):
        return output_path

    shutil.copyfile(video_path, output_path)
    return output_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def overlay_caption(
    video_path: str,
    caption_text: str,
    output_path: Optional[str] = None,
    font_size: int = 48,
    max_chars_per_line: int = 25,
    vertical_position: float = 0.55,
    text_color: str = "#FFFFFF",
    style: str = "classic",
) -> str:
    """
    Burn caption text onto a video with full emoji support.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not caption_text or not caption_text.strip():
        raise ValueError("caption_text must be a non-empty string.")

    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_captioned{ext}"

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    width, _ = _probe_dimensions(video_path)

    tmp_png = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_png.close()

    try:
        _render_caption_png(
            caption_text,
            tmp_png.name,
            canvas_width=width,
            font_size=font_size,
            max_chars=max_chars_per_line,
            text_color=text_color,
            style=style,
            border=_outline_width_for_style(style),
        )

        overlay_filter = f"overlay=(W-w)/2:{vertical_position}*H-h/2"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", tmp_png.name,
            "-filter_complex", overlay_filter,
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
    finally:
        if os.path.isfile(tmp_png.name):
            os.unlink(tmp_png.name)

    return output_path


def render_video_overlay(
    video_path: str,
    overlay_spec: dict,
    output_path: Optional[str] = None,
    max_chars_per_line: int = 25,
) -> str:
    """Render overlay from a normalized spec or return raw video when disabled."""
    spec = normalize_overlay_spec(overlay_spec)
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_overlay{ext}"

    if not spec["enabled"]:
        return copy_video_without_overlay(video_path, output_path)

    return overlay_caption(
        video_path,
        spec["text"],
        output_path=output_path,
        font_size=spec["fontSize"],
        max_chars_per_line=max_chars_per_line,
        vertical_position=spec["verticalPosition"],
        text_color=spec["fontColor"],
        style=spec["style"],
    )
