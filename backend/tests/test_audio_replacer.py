"""
Unit tests for audio replacement service.
"""

import os
import pytest
import tempfile
import shutil

from audio_replacer import replace_audio, _get_video_duration, _get_audio_duration
from audio_extractor import extract_audio
from video_concatenator import concatenate_videos


@pytest.fixture
def test_video_path():
    """Path to test video file."""
    video_path = os.path.join(
        os.path.dirname(__file__), "..", "input", "final_output_testing.mp4"
    )
    if not os.path.isfile(video_path):
        pytest.skip(f"Test video not found: {video_path}")
    return video_path


@pytest.fixture
def test_audio_path():
    """Path to test audio file (extracted from Download (1).mp4)."""
    base_dir = os.path.dirname(__file__)
    original_video = os.path.join(base_dir, "..", "input", "Download (1).mp4")
    
    if not os.path.isfile(original_video):
        pytest.skip(f"Original video not found: {original_video}")
    
    # Extract audio for testing
    temp_dir = tempfile.mkdtemp(prefix="audio_replacer_test_")
    audio_path = os.path.join(temp_dir, "test_audio.aac")
    
    try:
        extract_audio(original_video, audio_path)
        yield audio_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    tmp_dir = tempfile.mkdtemp(prefix="audio_replacer_test_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestAudioReplacer:
    """Test audio replacement functionality."""

    def test_replace_audio_creates_file(
        self, test_video_path, test_audio_path, temp_output_dir
    ):
        """Test that audio replacement creates an output file."""
        output_path = os.path.join(temp_output_dir, "output_with_audio.mp4")
        
        result_path = replace_audio(test_video_path, test_audio_path, output_path)
        
        assert os.path.isfile(result_path), "Output video should be created"
        assert result_path == output_path, "Should return the output path"

    def test_replace_audio_auto_path(
        self, test_video_path, test_audio_path, temp_output_dir
    ):
        """Test that audio replacement works with auto-generated path."""
        # Copy video to temp dir for auto path generation
        temp_video = os.path.join(temp_output_dir, "test_video.mp4")
        shutil.copy(test_video_path, temp_video)
        
        result_path = replace_audio(temp_video, test_audio_path)
        
        assert os.path.isfile(result_path), "Output video should be created"
        assert "_with_audio" in result_path, "Should have _with_audio suffix"

    def test_replace_audio_duration_trim_video(
        self, test_video_path, test_audio_path, temp_output_dir
    ):
        """Test that video is trimmed when it's longer than audio."""
        output_path = os.path.join(temp_output_dir, "output.mp4")
        
        video_duration = _get_video_duration(test_video_path)
        audio_duration = _get_audio_duration(test_audio_path)
        expected_duration = min(video_duration, audio_duration)
        
        replace_audio(test_video_path, test_audio_path, output_path)
        output_duration = _get_video_duration(output_path)
        
        # Allow 0.5s tolerance for encoding differences
        assert abs(output_duration - expected_duration) < 0.5, \
            f"Output duration ({output_duration:.2f}s) should match shorter input ({expected_duration:.2f}s)"

    def test_replace_audio_nonexistent_video(
        self, test_audio_path, temp_output_dir
    ):
        """Test that replacement raises FileNotFoundError for nonexistent video."""
        fake_path = os.path.join(temp_output_dir, "nonexistent.mp4")
        output_path = os.path.join(temp_output_dir, "output.mp4")
        
        with pytest.raises(FileNotFoundError):
            replace_audio(fake_path, test_audio_path, output_path)

    def test_replace_audio_nonexistent_audio(
        self, test_video_path, temp_output_dir
    ):
        """Test that replacement raises FileNotFoundError for nonexistent audio."""
        fake_path = os.path.join(temp_output_dir, "nonexistent.aac")
        output_path = os.path.join(temp_output_dir, "output.mp4")
        
        with pytest.raises(FileNotFoundError):
            replace_audio(test_video_path, fake_path, output_path)

    def test_get_video_duration(self, test_video_path):
        """Test getting video duration."""
        duration = _get_video_duration(test_video_path)
        
        assert duration > 0, "Duration should be positive"
        assert isinstance(duration, float), "Duration should be a float"

    def test_get_audio_duration(self, test_audio_path):
        """Test getting audio duration."""
        duration = _get_audio_duration(test_audio_path)
        
        assert duration > 0, "Duration should be positive"
        assert isinstance(duration, float), "Duration should be a float"
