"""
Scene Detection Service

Detects the first scene cut/change in a raw video and trims the video
to that exact moment using PySceneDetect and FFmpeg.
"""

import os
import subprocess
from scenedetect import open_video, SceneManager, ContentDetector


def detect_first_scene_change(video_path: str, threshold: float = 27.0):
    """
    Detect the first scene change in a video.

    Uses PySceneDetect's ContentDetector to analyse frame-by-frame
    differences and find the first significant scene transition.

    Args:
        video_path: Path to the input video file.
        threshold: Sensitivity for scene detection. Lower values are
                   more sensitive. Default is 27.0 (PySceneDetect standard).

    Returns:
        A dict with 'timecode' (float seconds) and 'frame' (int) of the
        first scene change, or None if no scene change is detected.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If the video cannot be opened or processed.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    try:
        video = open_video(video_path)
    except Exception as exc:
        raise RuntimeError(f"Could not open video: {video_path}") from exc

    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    if len(scene_list) <= 0:
        # No scene change detected — video is a single continuous scene
        return None

    # The first entry in scene_list is (start, end) of the first scene.
    # The *cut point* is the end of the first scene (= start of the second).
    first_scene_start, first_scene_end = scene_list[0]

    return {
        "timecode": first_scene_end.get_seconds(),
        "frame": first_scene_end.get_frames(),
    }


def get_video_duration(video_path: str) -> float:
    """Return the duration of a video in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def crop_to_first_scene(
    video_path: str,
    output_path: str = None,
    threshold: float = 27.0,
):
    """
    Detect the first scene change and trim the video to that point.

    Args:
        video_path: Path to the input video file.
        output_path: Path for the trimmed output video. If None, an
                     auto-generated path is used (e.g. video_trimmed.mp4).
        threshold: Sensitivity for scene detection (see detect_first_scene_change).

    Returns:
        A dict with:
            - 'output_path': path to the trimmed video file
            - 'cut_at_seconds': the timestamp where the cut was made
            - 'cut_at_frame': the frame number of the cut
        or None if no scene change was detected.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If trimming fails.
    """
    detection = detect_first_scene_change(video_path, threshold=threshold)

    if detection is None:
        return None

    cut_seconds = detection["timecode"]
    cut_frame = detection["frame"]

    # Build output path if not provided
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_trimmed{ext}"

    # Use FFmpeg to trim the video from 0 to the cut point.
    # -to specifies the end timestamp; -c copy does a stream copy (fast).
    cmd = [
        "ffmpeg",
        "-y",                   # overwrite without asking
        "-i", video_path,
        "-to", str(cut_seconds),
        "-c", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg trimming failed (exit {result.returncode}): {result.stderr}"
        )

    return {
        "output_path": output_path,
        "cut_at_seconds": cut_seconds,
        "cut_at_frame": cut_frame,
    }
