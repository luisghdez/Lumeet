"""
Unit tests for video concatenation service.
"""

import os
import pytest
import tempfile
import shutil

from video_concatenator import concatenate_videos, get_video_duration, _get_video_properties


@pytest.fixture
def test_video1_path():
    """Path to first test video file."""
    video_path = os.path.join(
        os.path.dirname(__file__), "..", "input", "final_output_testing.mp4"
    )
    if not os.path.isfile(video_path):
        pytest.skip(f"Test video 1 not found: {video_path}")
    return video_path


@pytest.fixture
def test_video2_path():
    """Path to second test video file."""
    video_path = os.path.join(
        os.path.dirname(__file__), "..", "input", "extended.mp4"
    )
    if not os.path.isfile(video_path):
        pytest.skip(f"Test video 2 not found: {video_path}")
    return video_path


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    tmp_dir = tempfile.mkdtemp(prefix="video_concatenator_test_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestVideoConcatenator:
    """Test video concatenation functionality."""

    def test_concatenate_videos_creates_file(
        self, test_video1_path, test_video2_path, temp_output_dir
    ):
        """Test that concatenation creates an output file."""
        output_path = os.path.join(temp_output_dir, "concatenated.mp4")
        
        result_path = concatenate_videos(
            test_video1_path, test_video2_path, output_path
        )
        
        assert os.path.isfile(result_path), "Concatenated video should be created"
        assert result_path == output_path, "Should return the output path"

    def test_concatenate_videos_auto_path(
        self, test_video1_path, test_video2_path, temp_output_dir
    ):
        """Test that concatenation works with auto-generated path."""
        # Copy video1 to temp dir for auto path generation
        temp_video1 = os.path.join(temp_output_dir, "test_video1.mp4")
        shutil.copy(test_video1_path, temp_video1)
        
        result_path = concatenate_videos(temp_video1, test_video2_path)
        
        assert os.path.isfile(result_path), "Concatenated video should be created"
        assert "_concatenated" in result_path, "Should have concatenated suffix"

    def test_concatenate_videos_duration(
        self, test_video1_path, test_video2_path, temp_output_dir
    ):
        """Test that concatenated video duration equals sum of inputs."""
        output_path = os.path.join(temp_output_dir, "concatenated.mp4")
        
        video1_duration = get_video_duration(test_video1_path)
        video2_duration = get_video_duration(test_video2_path)
        expected_duration = video1_duration + video2_duration
        
        concatenate_videos(test_video1_path, test_video2_path, output_path)
        output_duration = get_video_duration(output_path)
        
        # Allow 0.5s tolerance for encoding differences
        assert abs(output_duration - expected_duration) < 0.5, \
            f"Output duration ({output_duration:.2f}s) should equal sum of inputs ({expected_duration:.2f}s)"

    def test_concatenate_videos_nonexistent_file(
        self, test_video1_path, temp_output_dir
    ):
        """Test that concatenation raises FileNotFoundError for nonexistent file."""
        fake_path = os.path.join(temp_output_dir, "nonexistent.mp4")
        output_path = os.path.join(temp_output_dir, "output.mp4")
        
        with pytest.raises(FileNotFoundError):
            concatenate_videos(test_video1_path, fake_path, output_path)

    def test_get_video_properties(self, test_video1_path):
        """Test getting video properties."""
        width, height, fps = _get_video_properties(test_video1_path)
        
        assert width > 0, "Width should be positive"
        assert height > 0, "Height should be positive"
        assert fps > 0, "FPS should be positive"

    def test_get_video_duration(self, test_video1_path):
        """Test getting video duration."""
        duration = get_video_duration(test_video1_path)
        
        assert duration > 0, "Duration should be positive"
        assert isinstance(duration, float), "Duration should be a float"
