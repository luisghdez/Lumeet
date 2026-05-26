"""
Shared TikTok-style overlay presets for caption rendering.
"""

from __future__ import annotations

from typing import Any, Dict

OVERLAY_STYLE_PRESETS = {"classic", "bold", "background", "minimal"}

OVERLAY_FONT_SIZES = {
    "small": 36,
    "medium": 48,
    "large": 60,
}

OVERLAY_FONT_COLORS = {
    "white": "#FFFFFF",
    "yellow": "#FFE135",
    "pink": "#FF0050",
    "cyan": "#00F2EA",
}

DEFAULT_OVERLAY = {
    "enabled": True,
    "text": "",
    "fontSize": 48,
    "fontColor": "#FFFFFF",
    "style": "classic",
    "verticalPosition": 0.55,
}


def normalize_font_size(value: Any) -> int:
    if isinstance(value, str):
        key = value.strip().lower()
        if key in OVERLAY_FONT_SIZES:
            return OVERLAY_FONT_SIZES[key]
        try:
            return max(24, min(72, int(key)))
        except ValueError:
            return DEFAULT_OVERLAY["fontSize"]
    try:
        return max(24, min(72, int(value or DEFAULT_OVERLAY["fontSize"])))
    except (TypeError, ValueError):
        return DEFAULT_OVERLAY["fontSize"]


def normalize_font_color(value: Any) -> str:
    raw = str(value or DEFAULT_OVERLAY["fontColor"]).strip()
    if raw.lower() in OVERLAY_FONT_COLORS:
        return OVERLAY_FONT_COLORS[raw.lower()]
    if raw.startswith("#") and len(raw) in {4, 7}:
        return raw.upper()
    return DEFAULT_OVERLAY["fontColor"]


def normalize_overlay_style(value: Any) -> str:
    style = str(value or DEFAULT_OVERLAY["style"]).strip().lower()
    return style if style in OVERLAY_STYLE_PRESETS else DEFAULT_OVERLAY["style"]


def normalize_overlay_spec(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    text = str(payload.get("text") or "").strip()
    enabled = bool(payload.get("enabled", True)) and bool(text)
    return {
        "enabled": enabled,
        "text": text,
        "fontSize": normalize_font_size(payload.get("fontSize")),
        "fontColor": normalize_font_color(payload.get("fontColor")),
        "style": normalize_overlay_style(payload.get("style")),
        "verticalPosition": float(payload.get("verticalPosition") or DEFAULT_OVERLAY["verticalPosition"]),
    }


def overlay_spec_from_caption(caption: str | None) -> Dict[str, Any]:
    text = str(caption or "").strip()
    if not text:
        return {**DEFAULT_OVERLAY, "enabled": False, "text": ""}
    return {
        **DEFAULT_OVERLAY,
        "enabled": True,
        "text": text,
    }
