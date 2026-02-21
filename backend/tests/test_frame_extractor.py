"""
Tests for frame_extractor.py

Uses synthetic test videos from conftest.py to verify frame extraction
at various timestamps.
"""

import os
import struct

import pytest

from backend.frame_extractor import extract_frame


class TestExtractFrame:
    """Tests for the extract_frame function."""

    def test_extracts_frame_at_second_2(self, two_scene_video, tmp_path):
        """Extracting at second 2 of a 6s video should produce a valid PNG."""
        output = os.path.join(str(tmp_path), "frame.png")
        result = extract_frame(two_scene_video, timestamp_sec=2.0, output_path=output)

        assert result == output
        assert os.path.isfile(result)
        # Check the file starts with a PNG signature
        with open(result, "rb") as f:
            header = f.read(8)
        assert header[:4] == b"\x89PNG", "Output file is not a valid PNG"

    def test_extracts_frame_at_default_timestamp(self, two_scene_video, tmp_path):
        """Default timestamp (2.0s) should work without explicit argument."""
        output = os.path.join(str(tmp_path), "default.png")
        result = extract_frame(two_scene_video, output_path=output)

        assert os.path.isfile(result)
        assert os.path.getsize(result) > 0

    def test_auto_generates_output_path(self, two_scene_video):
        """When no output_path is given, one should be auto-generated."""
        result = extract_frame(two_scene_video, timestamp_sec=1.0)

        try:
            assert os.path.isfile(result)
            assert result.endswith("_frame_1.0s.png")
            assert os.path.getsize(result) > 0
        finally:
            # Clean up auto-generated file
            if os.path.isfile(result):
                os.remove(result)

    def test_output_is_valid_png(self, single_scene_video, tmp_path):
        """The output should be a proper PNG file with valid dimensions."""
        output = os.path.join(str(tmp_path), "check.png")
        extract_frame(single_scene_video, timestamp_sec=0.5, output_path=output)

        # Verify PNG header and IHDR chunk for width/height
        with open(output, "rb") as f:
            sig = f.read(8)
            assert sig == b"\x89PNG\r\n\x1a\n", "Invalid PNG signature"
            # IHDR chunk: 4 bytes length, 4 bytes 'IHDR', 4 bytes width, 4 bytes height
            length = struct.unpack(">I", f.read(4))[0]
            chunk_type = f.read(4)
            assert chunk_type == b"IHDR"
            width = struct.unpack(">I", f.read(4))[0]
            height = struct.unpack(">I", f.read(4))[0]
            assert width > 0
            assert height > 0

    def test_invalid_video_path_raises(self, tmp_path):
        """Passing a non-existent video should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_frame("/tmp/does_not_exist_video.mp4", output_path=str(tmp_path / "out.png"))

    def test_timestamp_beyond_duration_raises(self, single_scene_video, tmp_path):
        """A timestamp past the video duration should raise RuntimeError
        because FFmpeg produces no output frame."""
        output = os.path.join(str(tmp_path), "beyond.png")
        with pytest.raises(RuntimeError):
            extract_frame(single_scene_video, timestamp_sec=999.0, output_path=output)

    def test_timestamp_zero(self, two_scene_video, tmp_path):
        """Extracting at timestamp 0 should capture the very first frame."""
        output = os.path.join(str(tmp_path), "first.png")
        result = extract_frame(two_scene_video, timestamp_sec=0.0, output_path=output)

        assert os.path.isfile(result)
        assert os.path.getsize(result) > 0
