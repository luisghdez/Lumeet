"""
Configuration for the video pipeline.

Handles configuration values from environment variables or defaults.
"""

import os


# Additional video path for extended pipeline
# Can be set via environment variable ADDITIONAL_VIDEO_PATH
# For testing, defaults to backend/input/extended.mp4
ADDITIONAL_VIDEO_PATH = os.environ.get(
    "ADDITIONAL_VIDEO_PATH",
    os.path.join(os.path.dirname(__file__), "input", "extended.mp4")
)
