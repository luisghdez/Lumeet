"""
Pytest fixtures for scene detection and caption detection tests.

Generates synthetic test videos using FFmpeg so we have deterministic
inputs with known scene-change points.
"""

import os
import subprocess
import tempfile
import shutil

import pytest


@pytest.fixture(scope="session")
def test_videos_dir():
    """Create a temporary directory for test videos, cleaned up after the session."""
    tmp_dir = tempfile.mkdtemp(prefix="scene_detect_tests_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def two_scene_video(test_videos_dir):
    """
    Generate a 6-second video with a clear scene change at ~3 seconds.

    - First 3 seconds: solid red (color 0xFF0000)
    - Last  3 seconds: solid blue (color 0x0000FF)
    """
    output_path = os.path.join(test_videos_dir, "two_scenes.mp4")

    red_path = os.path.join(test_videos_dir, "red.mp4")
    blue_path = os.path.join(test_videos_dir, "blue.mp4")

    # Generate 3 s of solid red
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=red:size=320x240:rate=30:duration=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            red_path,
        ],
        capture_output=True,
        check=True,
    )

    # Generate 3 s of solid blue
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=blue:size=320x240:rate=30:duration=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            blue_path,
        ],
        capture_output=True,
        check=True,
    )

    # Concatenate them into a single 6-second video
    concat_file = os.path.join(test_videos_dir, "concat.txt")
    with open(concat_file, "w") as f:
        f.write(f"file '{red_path}'\n")
        f.write(f"file '{blue_path}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output_path,
        ],
        capture_output=True,
        check=True,
    )

    return output_path


@pytest.fixture(scope="session")
def single_scene_video(test_videos_dir):
    """
    Generate a 5-second video with NO scene change (solid green throughout).
    """
    output_path = os.path.join(test_videos_dir, "single_scene.mp4")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=green:size=320x240:rate=30:duration=5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output_path,
        ],
        capture_output=True,
        check=True,
    )

    return output_path


@pytest.fixture(scope="session")
def video_with_text(test_videos_dir):
    """
    Generate a 3-second video with on-screen text including:
    - A regular caption: "Hello World"
    - A username: "@cooluser123"
    - The word "TikTok"

    This lets us verify OCR detection and filtering.
    """
    output_path = os.path.join(test_videos_dir, "with_text.mp4")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=white:size=720x1280:rate=30:duration=3",
            "-vf", (
                "drawtext=text='Hello World':fontsize=48:fontcolor=black"
                ":x=(w-text_w)/2:y=h/2-100,"
                "drawtext=text='@cooluser123':fontsize=36:fontcolor=black"
                ":x=(w-text_w)/2:y=h/2,"
                "drawtext=text='TikTok':fontsize=36:fontcolor=black"
                ":x=(w-text_w)/2:y=h/2+100"
            ),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output_path,
        ],
        capture_output=True,
        check=True,
    )

    return output_path


@pytest.fixture(scope="session")
def video_clean_caption(test_videos_dir):
    """
    Generate a 3-second video with only a clean caption (no usernames or TikTok).
    """
    output_path = os.path.join(test_videos_dir, "clean_caption.mp4")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=white:size=720x1280:rate=30:duration=3",
            "-vf", (
                "drawtext=text='This is a caption':fontsize=48:fontcolor=black"
                ":x=(w-text_w)/2:y=h/2"
            ),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output_path,
        ],
        capture_output=True,
        check=True,
    )

    return output_path
