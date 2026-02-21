"""
Tests for scene_recreator.py

Uses mocked Gemini API calls to verify the scene recreation logic
without making real API requests.
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from backend.scene_recreator import recreate_scene, DEFAULT_PROMPT, MODEL_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scene_image(tmp_path):
    """Create a small dummy scene image."""
    img_path = tmp_path / "scene.png"
    img = Image.new("RGB", (320, 240), color="red")
    img.save(str(img_path))
    return str(img_path)


@pytest.fixture
def model_image(tmp_path):
    """Create a small dummy model/identity image."""
    img_path = tmp_path / "model.png"
    img = Image.new("RGB", (320, 240), color="blue")
    img.save(str(img_path))
    return str(img_path)


def _make_mock_response(with_image=True, text=None):
    """Build a mock Gemini response with optional image and text parts."""
    parts = []

    if text is not None:
        text_part = MagicMock()
        text_part.text = text
        text_part.inline_data = None
        parts.append(text_part)

    if with_image:
        image_part = MagicMock()
        image_part.text = None
        image_part.inline_data = True  # truthy to enter the elif
        # as_image() returns a PIL Image
        image_part.as_image.return_value = Image.new("RGB", (320, 240), color="green")
        parts.append(image_part)

    response = MagicMock()
    response.parts = parts
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecreateSceneValidation:
    """Input validation tests (no API calls needed)."""

    def test_missing_api_key_raises(self, scene_image, model_image, tmp_path):
        """Should raise EnvironmentError when GEMINI_API_KEY is not set."""
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="GEMINI_API_KEY"):
                recreate_scene(
                    scene_image, model_image,
                    output_path=str(tmp_path / "out.png"),
                )

    def test_missing_scene_image_raises(self, model_image, tmp_path):
        """Should raise FileNotFoundError for a non-existent scene image."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with pytest.raises(FileNotFoundError, match="Scene image"):
                recreate_scene(
                    "/tmp/does_not_exist.png", model_image,
                    output_path=str(tmp_path / "out.png"),
                )

    def test_missing_model_image_raises(self, scene_image, tmp_path):
        """Should raise FileNotFoundError for a non-existent model image."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with pytest.raises(FileNotFoundError, match="Model image"):
                recreate_scene(
                    scene_image, "/tmp/does_not_exist.png",
                    output_path=str(tmp_path / "out.png"),
                )


class TestRecreateSceneMocked:
    """Tests that mock the Gemini API client."""

    @patch("backend.scene_recreator.genai.Client")
    def test_returns_saved_image_path(self, mock_client_cls, scene_image, model_image, tmp_path):
        """A successful API call should save the image and return the path."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response(with_image=True)

        output = str(tmp_path / "result.png")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = recreate_scene(scene_image, model_image, output_path=output)

        assert result == output
        assert os.path.isfile(output)
        # Verify the saved file is a valid image
        saved_img = Image.open(output)
        assert saved_img.size == (320, 240)

    @patch("backend.scene_recreator.genai.Client")
    def test_passes_both_images_and_prompt(self, mock_client_cls, scene_image, model_image, tmp_path):
        """Should pass the prompt + both PIL images to generate_content."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response(with_image=True)

        output = str(tmp_path / "result.png")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            recreate_scene(scene_image, model_image, output_path=output)

        call_args = mock_client.models.generate_content.call_args
        # contents should be [prompt_str, scene_PIL, model_PIL]
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents")
        assert len(contents) == 3
        assert isinstance(contents[0], str)
        assert DEFAULT_PROMPT in contents[0]
        # Images 1 and 2 are PIL.Image instances
        assert isinstance(contents[1], Image.Image)
        assert isinstance(contents[2], Image.Image)

    @patch("backend.scene_recreator.genai.Client")
    def test_uses_correct_model(self, mock_client_cls, scene_image, model_image, tmp_path):
        """Should call the correct Gemini model."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response(with_image=True)

        output = str(tmp_path / "result.png")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            recreate_scene(scene_image, model_image, output_path=output)

        call_args = mock_client.models.generate_content.call_args
        model_arg = call_args.kwargs.get("model") or call_args[1].get("model")
        assert model_arg == MODEL_ID

    @patch("backend.scene_recreator.genai.Client")
    def test_custom_prompt(self, mock_client_cls, scene_image, model_image, tmp_path):
        """A custom prompt should override the default."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response(with_image=True)

        custom = "Just make it look cool"
        output = str(tmp_path / "result.png")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            recreate_scene(scene_image, model_image, output_path=output, prompt=custom)

        call_args = mock_client.models.generate_content.call_args
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents")
        assert contents[0] == custom

    @patch("backend.scene_recreator.genai.Client")
    def test_no_image_in_response_raises(self, mock_client_cls, scene_image, model_image, tmp_path):
        """If the API returns no image, RuntimeError should be raised."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response(
            with_image=False, text="I cannot generate that image."
        )

        output = str(tmp_path / "result.png")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with pytest.raises(RuntimeError, match="no image"):
                recreate_scene(scene_image, model_image, output_path=output)

    @patch("backend.scene_recreator.genai.Client")
    def test_response_with_text_and_image(self, mock_client_cls, scene_image, model_image, tmp_path):
        """When the API returns both text and an image, the image should be saved."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response(
            with_image=True, text="Here's the recreated scene."
        )

        output = str(tmp_path / "result.png")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = recreate_scene(scene_image, model_image, output_path=output)

        assert os.path.isfile(result)

    @patch("backend.scene_recreator.genai.Client")
    def test_auto_generates_output_path(self, mock_client_cls, scene_image, model_image):
        """When no output_path is given, it should auto-generate one."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response(with_image=True)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = recreate_scene(scene_image, model_image)

        try:
            assert os.path.isfile(result)
            assert result.endswith("recreated_scene.png")
        finally:
            if os.path.isfile(result):
                os.remove(result)
