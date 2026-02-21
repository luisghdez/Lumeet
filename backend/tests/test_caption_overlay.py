"""
Tests for caption_overlay.py

Uses synthetic test videos from conftest.py to verify caption burning
via FFmpeg drawtext.
"""

import os
import subprocess

import pytest

from backend.caption_overlay import overlay_caption


class TestOverlayCaption:
    """Tests for the overlay_caption function."""

    def test_produces_output_video(self, single_scene_video, tmp_path):
        """Overlaying a caption should produce a valid output video."""
        output = os.path.join(str(tmp_path), "captioned.mp4")
        result = overlay_caption(single_scene_video, "Hello World", output_path=output)

        assert result == output
        assert os.path.isfile(result)
        assert os.path.getsize(result) > 0

    def test_output_is_playable(self, single_scene_video, tmp_path):
        """The captioned video should be a valid video file (ffprobe check)."""
        output = os.path.join(str(tmp_path), "captioned.mp4")
        overlay_caption(single_scene_video, "Test caption", output_path=output)

        # Verify with ffprobe
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", output],
            capture_output=True, text=True,
        )
        assert probe.returncode == 0
        duration = float(probe.stdout.strip())
        assert duration > 0

    def test_auto_generates_output_path(self, single_scene_video):
        """When no output_path is given, one should be auto-generated."""
        result = overlay_caption(single_scene_video, "Auto path test")

        try:
            assert os.path.isfile(result)
            assert "_captioned" in result
        finally:
            if os.path.isfile(result):
                os.remove(result)

    def test_empty_caption_raises(self, single_scene_video, tmp_path):
        """An empty caption should raise ValueError."""
        output = os.path.join(str(tmp_path), "captioned.mp4")
        with pytest.raises(ValueError, match="non-empty"):
            overlay_caption(single_scene_video, "", output_path=output)

    def test_none_caption_raises(self, single_scene_video, tmp_path):
        """A None caption should raise ValueError."""
        output = os.path.join(str(tmp_path), "captioned.mp4")
        with pytest.raises(ValueError, match="non-empty"):
            overlay_caption(single_scene_video, None, output_path=output)

    def test_invalid_video_path_raises(self, tmp_path):
        """A non-existent video should raise FileNotFoundError."""
        output = os.path.join(str(tmp_path), "captioned.mp4")
        with pytest.raises(FileNotFoundError):
            overlay_caption("/tmp/nonexistent.mp4", "Hello", output_path=output)

    def test_caption_with_special_chars(self, single_scene_video, tmp_path):
        """Captions with special characters (colons, quotes) should work."""
        output = os.path.join(str(tmp_path), "special.mp4")
        result = overlay_caption(
            single_scene_video,
            "POV: I finally get why EVERYBODY deleted chatGPT",
            output_path=output,
        )

        assert os.path.isfile(result)
        assert os.path.getsize(result) > 0

    def test_output_duration_matches_input(self, single_scene_video, tmp_path):
        """Overlaying a caption should not change the video duration."""
        output = os.path.join(str(tmp_path), "captioned.mp4")
        overlay_caption(single_scene_video, "Duration test", output_path=output)

        def get_dur(path):
            p = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, check=True,
            )
            return float(p.stdout.strip())

        orig_dur = get_dur(single_scene_video)
        new_dur = get_dur(output)
        assert abs(orig_dur - new_dur) < 0.5  # within 0.5s tolerance
