"""
Unit tests for audio extraction service.
"""

import os
import pytest
import tempfile
import shutil

from audio_extractor import extract_audio, get_audio_duration
from scene_detector import get_video_duration


@pytest.fixture
def test_video_path():
    """Path to test video file."""
    video_path = os.path.join(
        os.path.dirname(__file__), "..", "input", "Download (1).mp4"
    )
    if not os.path.isfile(video_path):
        pytest.skip(f"Test video not found: {video_path}")
    return video_path


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    tmp_dir = tempfile.mkdtemp(prefix="audio_extractor_test_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestAudioExtractor:
    """Test audio extraction functionality."""

    def test_extract_audio_creates_file(self, test_video_path, temp_output_dir):
        """Test that audio extraction creates an output file."""
        output_path = os.path.join(temp_output_dir, "test_audio.aac")
        
        result_path = extract_audio(test_video_path, output_path)
        
        assert os.path.isfile(result_path), "Audio file should be created"
        assert result_path == output_path, "Should return the output path"

    def test_extract_audio_auto_path(self, test_video_path, temp_output_dir):
        """Test that audio extraction works with auto-generated path."""
        # Copy video to temp dir for auto path generation
        temp_video = os.path.join(temp_output_dir, "test_video.mp4")
        shutil.copy(test_video_path, temp_video)
        
        result_path = extract_audio(temp_video)
        
        assert os.path.isfile(result_path), "Audio file should be created"
        assert result_path.endswith(".aac"), "Should have .aac extension"

    def test_extract_audio_duration_matches(self, test_video_path, temp_output_dir):
        """Test that extracted audio duration matches video duration."""
        output_path = os.path.join(temp_output_dir, "test_audio.aac")
        
        video_duration = get_video_duration(test_video_path)
        extract_audio(test_video_path, output_path)
        audio_duration = get_audio_duration(output_path)
        
        # Allow 0.5s tolerance for encoding differences
        assert abs(video_duration - audio_duration) < 0.5, \
            f"Audio duration ({audio_duration:.2f}s) should match video duration ({video_duration:.2f}s)"

    def test_extract_audio_nonexistent_file(self, temp_output_dir):
        """Test that extraction raises FileNotFoundError for nonexistent file."""
        fake_path = os.path.join(temp_output_dir, "nonexistent.mp4")
        output_path = os.path.join(temp_output_dir, "output.aac")
        
        with pytest.raises(FileNotFoundError):
            extract_audio(fake_path, output_path)

    def test_get_audio_duration(self, test_video_path, temp_output_dir):
        """Test getting audio duration."""
        output_path = os.path.join(temp_output_dir, "test_audio.aac")
        extract_audio(test_video_path, output_path)
        
        duration = get_audio_duration(output_path)
        
        assert duration > 0, "Duration should be positive"
        assert isinstance(duration, float), "Duration should be a float"

    def test_get_audio_duration_nonexistent_file(self, temp_output_dir):
        """Test that getting duration raises FileNotFoundError for nonexistent file."""
        fake_path = os.path.join(temp_output_dir, "nonexistent.aac")
        
        with pytest.raises(FileNotFoundError):
            get_audio_duration(fake_path)
