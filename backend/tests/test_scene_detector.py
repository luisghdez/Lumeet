"""
Tests for the scene detection service.
"""

import os
import sys
import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scene_detector import (
    detect_first_scene_change,
    crop_to_first_scene,
    get_video_duration,
)


class TestDetectFirstSceneChange:
    """Tests for detect_first_scene_change."""

    def test_detects_scene_change_in_two_scene_video(self, two_scene_video):
        """The detector should find a cut near the 3-second mark."""
        result = detect_first_scene_change(two_scene_video)

        assert result is not None, "Expected a scene change to be detected"
        assert "timecode" in result
        assert "frame" in result

        # The cut should be approximately at 3.0 seconds (tolerance ±0.5 s)
        assert abs(result["timecode"] - 3.0) < 0.5, (
            f"Expected cut near 3.0s, got {result['timecode']}s"
        )

    def test_no_scene_change_in_single_scene_video(self, single_scene_video):
        """A solid-colour video should have no detectable scene change."""
        result = detect_first_scene_change(single_scene_video)
        assert result is None, "Expected no scene change for a uniform video"

    def test_invalid_video_path_raises(self):
        """Passing a non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            detect_first_scene_change("/tmp/nonexistent_video_abc123.mp4")


class TestCropToFirstScene:
    """Tests for crop_to_first_scene."""

    def test_crop_produces_shorter_video(self, two_scene_video, test_videos_dir):
        """The trimmed video should exist and be shorter than the original."""
        output_path = os.path.join(test_videos_dir, "cropped_output.mp4")

        result = crop_to_first_scene(
            two_scene_video,
            output_path=output_path,
        )

        assert result is not None, "Expected a crop result"
        assert os.path.isfile(result["output_path"]), "Trimmed file should exist"

        original_duration = get_video_duration(two_scene_video)
        trimmed_duration = get_video_duration(result["output_path"])

        assert trimmed_duration < original_duration, (
            f"Trimmed duration ({trimmed_duration}s) should be less than "
            f"original ({original_duration}s)"
        )

        # The trimmed duration should be roughly equal to the cut point
        assert abs(trimmed_duration - result["cut_at_seconds"]) < 0.5, (
            f"Trimmed duration ({trimmed_duration}s) should be close to "
            f"cut point ({result['cut_at_seconds']}s)"
        )

    def test_crop_returns_none_for_single_scene(self, single_scene_video):
        """Cropping a video with no scene change should return None."""
        result = crop_to_first_scene(single_scene_video)
        assert result is None

    def test_crop_auto_generates_output_path(self, two_scene_video):
        """When no output_path is given, an auto-generated path should be used."""
        result = crop_to_first_scene(two_scene_video)

        assert result is not None
        assert result["output_path"].endswith("_trimmed.mp4")
        assert os.path.isfile(result["output_path"])

        # Clean up the auto-generated file
        os.remove(result["output_path"])

    def test_crop_invalid_path_raises(self):
        """Passing a non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            crop_to_first_scene("/tmp/nonexistent_video_abc123.mp4")
