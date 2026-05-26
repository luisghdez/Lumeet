"""
Tests for video overlay service helpers.
"""

from backend.video_overlay_styles import (
    normalize_overlay_spec,
    overlay_spec_from_caption,
)


class TestVideoOverlayStyles:
    def test_overlay_spec_from_caption(self):
        spec = overlay_spec_from_caption('Hello world')
        assert spec["enabled"] is True
        assert spec["text"] == "Hello world"
        assert spec["style"] == "classic"

    def test_overlay_spec_from_empty_caption(self):
        spec = overlay_spec_from_caption("")
        assert spec["enabled"] is False
        assert spec["text"] == ""

    def test_normalize_overlay_spec_maps_size_labels(self):
        spec = normalize_overlay_spec({
            "enabled": True,
            "text": "Test",
            "fontSize": "large",
            "fontColor": "pink",
            "style": "bold",
        })
        assert spec["fontSize"] == 60
        assert spec["fontColor"] == "#FF0050"
        assert spec["style"] == "bold"

    def test_normalize_overlay_spec_disables_empty_text(self):
        spec = normalize_overlay_spec({"enabled": True, "text": "   "})
        assert spec["enabled"] is False
        assert spec["text"] == ""
