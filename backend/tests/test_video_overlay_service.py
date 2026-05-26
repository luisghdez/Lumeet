"""
Tests for video_overlay_service caption backfill helpers.
"""

from backend.video_overlay_service import _caption_from_generation


class TestVideoOverlayBackfill:
    def test_caption_from_generation_step_message(self, monkeypatch):
        monkeypatch.setattr(
            "backend.video_overlay_service.generation_store.get",
            lambda _generation_id: {
                "steps": [
                    {
                        "key": "caption_detection",
                        "message": 'Caption: "how i felt getting paid $10/hr"',
                    }
                ]
            },
        )
        assert _caption_from_generation("gen_1") == "how i felt getting paid $10/hr"

    def test_caption_from_generation_missing(self, monkeypatch):
        monkeypatch.setattr(
            "backend.video_overlay_service.generation_store.get",
            lambda _generation_id: None,
        )
        assert _caption_from_generation("gen_missing") == ""
