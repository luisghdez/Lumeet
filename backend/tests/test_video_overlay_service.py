"""
Tests for video_overlay_service caption backfill helpers.
"""

from backend.video_overlay_service import _caption_from_generation, _parse_caption_step_message


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

    def test_parse_caption_step_message_with_internal_quotes(self):
        message = (
            'Caption: "When your prof asks "does anyone have any questions?" '
            "but you don't even understand the topic enough to have a question in the first place\""
        )
        assert _parse_caption_step_message(message) == (
            'When your prof asks "does anyone have any questions?" '
            "but you don't even understand the topic enough to have a question in the first place"
        )

    def test_caption_from_generation_internal_quotes(self, monkeypatch):
        message = (
            'Caption: "When your prof asks "does anyone have any questions?" '
            "but you don't even understand the topic enough to have a question in the first place\""
        )
        monkeypatch.setattr(
            "backend.video_overlay_service.generation_store.get",
            lambda _generation_id: {
                "steps": [{"key": "caption_detection", "message": message}]
            },
        )
        assert _caption_from_generation("gen_2") == _parse_caption_step_message(message)
