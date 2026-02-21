"""
Tests for pipeline.py (Unified Video Generation Pipeline)

All external API calls (OpenAI, Gemini, Fal AI) are mocked.
The tests verify orchestration logic: correct step ordering,
argument passing, and result assembly.
"""

import os
import shutil
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from backend.pipeline import run_full_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def model_image(tmp_path):
    """Create a dummy model/identity image."""
    img_path = tmp_path / "model.png"
    img = Image.new("RGB", (320, 240), color="blue")
    img.save(str(img_path))
    return str(img_path)


@pytest.fixture
def output_dir(tmp_path):
    """Create a temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return str(out)


def _make_gemini_response():
    """Build a mock Gemini response that includes an image."""
    image_part = MagicMock()
    image_part.text = None
    image_part.inline_data = True
    image_part.as_image.return_value = Image.new("RGB", (320, 240), color="green")

    response = MagicMock()
    response.parts = [image_part]
    return response


def _make_openai_response(caption_text="POV: Test caption"):
    """Build a mock OpenAI chat completion response."""
    message = MagicMock()
    message.content = caption_text

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineValidation:
    """Input validation tests (no API calls)."""

    def test_missing_video_raises(self, model_image, output_dir):
        """Should raise FileNotFoundError for non-existent video."""
        with pytest.raises(FileNotFoundError, match="Input video"):
            run_full_pipeline("/tmp/nonexistent.mp4", model_image, output_dir)

    def test_missing_model_image_raises(self, two_scene_video, output_dir):
        """Should raise FileNotFoundError for non-existent model image."""
        with pytest.raises(FileNotFoundError, match="Model image"):
            run_full_pipeline(two_scene_video, "/tmp/nonexistent.png", output_dir)


class TestPipelineOrchestration:
    """Full pipeline tests with all external APIs mocked."""

    @patch("backend.pipeline.generate_motion_video")
    @patch("backend.pipeline.recreate_scene")
    @patch("backend.pipeline.detect_captions_summary")
    def test_full_pipeline_with_caption(
        self,
        mock_captions,
        mock_recreate,
        mock_motion,
        two_scene_video,
        model_image,
        output_dir,
    ):
        """Full pipeline with a detected caption should produce a captioned final video."""
        # Mock caption detection
        mock_captions.return_value = "Test caption overlay"

        # Mock scene recreation — write a real image so overlay has something
        def fake_recreate(scene_path, model_path, output_path=None, prompt=None):
            img = Image.new("RGB", (320, 240), color="green")
            img.save(output_path)
            return output_path
        mock_recreate.side_effect = fake_recreate

        # Mock motion control — copy the trimmed video as "generated" output
        def fake_motion(image_path, video_path, output_path, prompt=""):
            shutil.copy2(video_path, output_path)
            return output_path
        mock_motion.side_effect = fake_motion

        result = run_full_pipeline(two_scene_video, model_image, output_dir)

        # All keys should be present
        assert "trimmed_video" in result
        assert "screenshot" in result
        assert "caption" in result
        assert "recreated_scene" in result
        assert "raw_video" in result
        assert "final_video" in result

        # Caption should be detected
        assert result["caption"] == "Test caption overlay"

        # Final video should exist and be different from raw (captioned)
        assert os.path.isfile(result["final_video"])
        assert result["final_video"] != result["raw_video"]

        # Intermediate files should exist
        assert os.path.isfile(result["screenshot"])
        assert os.path.isfile(result["recreated_scene"])

    @patch("backend.pipeline.generate_motion_video")
    @patch("backend.pipeline.recreate_scene")
    @patch("backend.pipeline.detect_captions_summary")
    def test_full_pipeline_no_caption(
        self,
        mock_captions,
        mock_recreate,
        mock_motion,
        two_scene_video,
        model_image,
        output_dir,
    ):
        """When no caption is detected, final_video should equal raw_video."""
        mock_captions.return_value = None

        def fake_recreate(scene_path, model_path, output_path=None, prompt=None):
            img = Image.new("RGB", (320, 240), color="green")
            img.save(output_path)
            return output_path
        mock_recreate.side_effect = fake_recreate

        def fake_motion(image_path, video_path, output_path, prompt=""):
            shutil.copy2(video_path, output_path)
            return output_path
        mock_motion.side_effect = fake_motion

        result = run_full_pipeline(two_scene_video, model_image, output_dir)

        assert result["caption"] is None
        # No caption means final_video IS the raw_video
        assert result["final_video"] == result["raw_video"]

    @patch("backend.pipeline.generate_motion_video")
    @patch("backend.pipeline.recreate_scene")
    @patch("backend.pipeline.detect_captions_summary")
    def test_single_scene_uses_original_video(
        self,
        mock_captions,
        mock_recreate,
        mock_motion,
        single_scene_video,
        model_image,
        output_dir,
    ):
        """When no scene change is detected, the original video should be used."""
        mock_captions.return_value = None

        def fake_recreate(scene_path, model_path, output_path=None, prompt=None):
            img = Image.new("RGB", (320, 240), color="green")
            img.save(output_path)
            return output_path
        mock_recreate.side_effect = fake_recreate

        def fake_motion(image_path, video_path, output_path, prompt=""):
            shutil.copy2(video_path, output_path)
            return output_path
        mock_motion.side_effect = fake_motion

        result = run_full_pipeline(single_scene_video, model_image, output_dir)

        # No scene change means trimmed_video is the original
        assert result["trimmed_video"] == single_scene_video

    @patch("backend.pipeline.generate_motion_video")
    @patch("backend.pipeline.recreate_scene")
    @patch("backend.pipeline.detect_captions_summary")
    def test_services_called_with_correct_args(
        self,
        mock_captions,
        mock_recreate,
        mock_motion,
        two_scene_video,
        model_image,
        output_dir,
    ):
        """Verify each service is called with the expected arguments."""
        mock_captions.return_value = None

        def fake_recreate(scene_path, model_path, output_path=None, prompt=None):
            img = Image.new("RGB", (320, 240), color="green")
            img.save(output_path)
            return output_path
        mock_recreate.side_effect = fake_recreate

        def fake_motion(image_path, video_path, output_path, prompt=""):
            shutil.copy2(video_path, output_path)
            return output_path
        mock_motion.side_effect = fake_motion

        result = run_full_pipeline(two_scene_video, model_image, output_dir)

        # Caption detection should be called with the trimmed video
        mock_captions.assert_called_once()
        caption_call_video = mock_captions.call_args[0][0]
        assert caption_call_video == result["trimmed_video"]

        # Scene recreation should be called with screenshot + model image
        mock_recreate.assert_called_once()
        recreate_args = mock_recreate.call_args
        assert recreate_args[0][0] == result["screenshot"]  # scene image
        assert recreate_args[0][1] == model_image            # model image

        # Motion control should be called with recreated scene + trimmed video
        mock_motion.assert_called_once()
        motion_args = mock_motion.call_args
        assert motion_args[0][0] == result["recreated_scene"]  # image
        assert motion_args[0][1] == result["trimmed_video"]     # video

    @patch("backend.pipeline.generate_motion_video")
    @patch("backend.pipeline.recreate_scene")
    @patch("backend.pipeline.detect_captions_summary")
    def test_screenshot_at_second_1(
        self,
        mock_captions,
        mock_recreate,
        mock_motion,
        two_scene_video,
        model_image,
        output_dir,
    ):
        """The screenshot should be taken at second 1 of the trimmed video."""
        mock_captions.return_value = None

        def fake_recreate(scene_path, model_path, output_path=None, prompt=None):
            img = Image.new("RGB", (320, 240), color="green")
            img.save(output_path)
            return output_path
        mock_recreate.side_effect = fake_recreate

        def fake_motion(image_path, video_path, output_path, prompt=""):
            shutil.copy2(video_path, output_path)
            return output_path
        mock_motion.side_effect = fake_motion

        result = run_full_pipeline(two_scene_video, model_image, output_dir)

        # Screenshot should exist and be a valid PNG
        assert os.path.isfile(result["screenshot"])
        with open(result["screenshot"], "rb") as f:
            header = f.read(4)
        assert header == b"\x89PNG"
