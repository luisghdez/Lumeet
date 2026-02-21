"""
Tests for the caption detection service.

Unit tests for filtering run locally (no API needed).
Integration tests mock the OpenAI API response.
"""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from caption_detector import (
    clean_caption,
    detect_captions,
    extract_frames,
    frame_to_base64,
    pick_best_frames,
    _contains_blocked_keyword,
    _contains_username,
)


# ── Unit tests for filtering helpers ──────────────────────────────────────────

class TestFilterHelpers:
    """Test the individual filtering functions."""

    def test_blocked_keyword_tiktok(self):
        assert _contains_blocked_keyword("Follow me on TikTok") is True

    def test_blocked_keyword_tik_tok(self):
        assert _contains_blocked_keyword("tik tok trends") is True

    def test_blocked_keyword_clean(self):
        assert _contains_blocked_keyword("Hello World") is False

    def test_username_detected(self):
        assert _contains_username("@cooluser123") is True

    def test_username_in_sentence(self):
        assert _contains_username("follow @mypage for more") is True

    def test_no_username(self):
        assert _contains_username("Hello World") is False


class TestCleanCaption:
    """Test the clean_caption post-processor."""

    def test_keeps_clean_text(self):
        assert clean_caption("Hello World") == "Hello World"

    def test_discards_tiktok(self):
        assert clean_caption("TikTok") is None

    def test_discards_tiktok_line_in_multiline(self):
        result = clean_caption("Great caption\nTikTok\nMore text")
        assert result is not None
        assert "tiktok" not in result.lower()
        assert "Great caption" in result
        assert "More text" in result

    def test_discards_pure_username(self):
        assert clean_caption("@cooluser123") is None

    def test_strips_username_keeps_rest(self):
        result = clean_caption("Check out @user for more tips")
        assert result is not None
        assert "@user" not in result
        assert "tips" in result

    def test_discards_empty_string(self):
        assert clean_caption("") is None
        assert clean_caption("   ") is None

    def test_discards_none(self):
        assert clean_caption(None) is None

    def test_preserves_capitalisation(self):
        assert clean_caption("POV: I finally get why") == "POV: I finally get why"

    def test_no_caption_marker(self):
        # The model might return NO_CAPTION; that's handled upstream,
        # but clean_caption should still pass it through if it sees it
        result = clean_caption("NO_CAPTION")
        assert result == "NO_CAPTION"


# ── Frame extraction tests ────────────────────────────────────────────────────

class TestFrameExtraction:
    """Test frame extraction from video files."""

    def test_extracts_frames_from_video(self, single_scene_video):
        """Should extract multiple frames from a 5-second video."""
        frames = extract_frames(single_scene_video, interval_sec=1.0)
        assert len(frames) >= 4  # ~5 seconds at 1fps sampling

    def test_frame_has_timestamp_and_data(self, single_scene_video):
        frames = extract_frames(single_scene_video, interval_sec=1.0)
        assert len(frames) > 0
        ts, frame = frames[0]
        assert isinstance(ts, float)
        assert frame is not None
        assert len(frame.shape) == 3  # H x W x C

    def test_invalid_path_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_frames("/tmp/nonexistent_abc123.mp4")

    def test_frame_to_base64(self, single_scene_video):
        frames = extract_frames(single_scene_video, interval_sec=1.0)
        b64 = frame_to_base64(frames[0][1])
        assert isinstance(b64, str)
        assert len(b64) > 100  # should be a substantial base64 string

    def test_pick_best_frames_limits_count(self, single_scene_video):
        frames = extract_frames(single_scene_video, interval_sec=0.5)
        selected = pick_best_frames(frames, max_frames=2)
        assert len(selected) <= 2


# ── Integration tests (mocked OpenAI) ────────────────────────────────────────

class TestDetectCaptionsMocked:
    """Test detect_captions with a mocked OpenAI API."""

    def _mock_openai_response(self, text):
        """Create a mock OpenAI chat completion response."""
        mock_choice = MagicMock()
        mock_choice.message.content = text
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response

    @patch("caption_detector.OpenAI")
    def test_returns_caption(self, mock_openai_cls, video_with_text):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_openai_response(
            "POV: I finally get why EVERYBODY deleted ChatGPT"
        )
        mock_openai_cls.return_value = mock_client

        result = detect_captions(video_with_text, interval_sec=1.0)

        assert result is not None
        assert result["caption"] == "POV: I finally get why EVERYBODY deleted ChatGPT"
        assert result["frames_analysed"] > 0

    @patch("caption_detector.OpenAI")
    def test_returns_none_for_no_caption(self, mock_openai_cls, single_scene_video):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_openai_response(
            "NO_CAPTION"
        )
        mock_openai_cls.return_value = mock_client

        result = detect_captions(single_scene_video, interval_sec=1.0)

        assert result is not None
        assert result["caption"] is None

    @patch("caption_detector.OpenAI")
    def test_filters_tiktok_from_response(self, mock_openai_cls, video_with_text):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_openai_response(
            "Great caption here\nTikTok\n@someuser"
        )
        mock_openai_cls.return_value = mock_client

        result = detect_captions(video_with_text, interval_sec=1.0)

        assert result is not None
        assert "tiktok" not in (result["caption"] or "").lower()
        assert "@someuser" not in (result["caption"] or "")

    def test_invalid_path_raises(self):
        with pytest.raises(FileNotFoundError):
            detect_captions("/tmp/nonexistent_abc123.mp4")
