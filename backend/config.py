"""
Configuration for the video pipeline.

Handles configuration values from environment variables or defaults.
"""

import os


def _get_env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# Additional video path for extended pipeline
# Can be set via environment variable ADDITIONAL_VIDEO_PATH
# For testing, defaults to backend/input/extended.mp4
ADDITIONAL_VIDEO_PATH = os.environ.get(
    "ADDITIONAL_VIDEO_PATH",
    os.path.join(os.path.dirname(__file__), "input", "extended.mp4")
)

# Late API config
LATE_API_BASE_URL = _get_env("LATE_API_BASE_URL", "https://getlate.dev/api/v1")
LATE_API_KEY = _get_env("LATE_API_KEY", "")
LATE_CONNECT_REDIRECT_URL = _get_env("LATE_CONNECT_REDIRECT_URL", "")
LATE_REQUEST_TIMEOUT_SEC = _get_int_env("LATE_REQUEST_TIMEOUT_SEC", 20)

# Used to build publicly reachable result URLs for social scheduling.
PUBLIC_BACKEND_BASE_URL = _get_env("PUBLIC_BACKEND_BASE_URL", "http://127.0.0.1:8000")

# Useful for running local integrations without auth.
LATE_ALLOW_MISSING_API_KEY = _get_bool_env("LATE_ALLOW_MISSING_API_KEY", False)
