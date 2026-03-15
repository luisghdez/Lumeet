"""
Configuration for the video pipeline.

Handles configuration values from environment variables or defaults.
"""

import os


def _read_from_env_files(name: str) -> str:
    backend_dir = os.path.dirname(__file__)
    repo_dir = os.path.dirname(backend_dir)
    candidates = [
        os.path.join(backend_dir, ".env"),
        os.path.join(repo_dir, ".env"),
    ]
    for env_path in candidates:
        if not os.path.isfile(env_path):
            continue
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    lhs, rhs = line.split("=", 1)
                    if lhs.strip() != name:
                        continue
                    return rhs.strip().strip("'\"")
        except OSError:
            continue
    return ""


def _get_env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        file_value = _read_from_env_files(name)
        return file_value if file_value else default
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

# Carousel + GCS config
GCS_BUCKET_NAME = _get_env("GCS_BUCKET_NAME", "")
GCS_OBJECT_PREFIX = _get_env("GCS_OBJECT_PREFIX", "carousels")
GCS_VIDEO_OBJECT_PREFIX = _get_env("GCS_VIDEO_OBJECT_PREFIX", "videos")
GCS_SIGNED_URL_TTL_SEC = _get_int_env("GCS_SIGNED_URL_TTL_SEC", 60 * 60 * 24 * 7)
CAROUSEL_SUGGESTION_MINUTES_STEP = _get_int_env("CAROUSEL_SUGGESTION_MINUTES_STEP", 30)
CAROUSEL_METADATA_FILE = _get_env(
    "CAROUSEL_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "carousel_metadata.json"),
)
VIDEO_METADATA_FILE = _get_env(
    "VIDEO_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "video_metadata.json"),
)

# If credentials are provided via backend/.env or repo .env, expose them
# to libraries that rely on the exact process env var (e.g. OpenAI SDK, Gemini SDK, Fal AI SDK).
GOOGLE_APPLICATION_CREDENTIALS = _get_env("GOOGLE_APPLICATION_CREDENTIALS", "")
if GOOGLE_APPLICATION_CREDENTIALS and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

OPENAI_API_KEY = _get_env("OPENAI_API_KEY", "")
if OPENAI_API_KEY and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

GEMINI_API_KEY = _get_env("GEMINI_API_KEY", "")
if GEMINI_API_KEY and not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# fal_client accepts either FAL_KEY or FAL_AI — normalise both into FAL_KEY.
FAL_KEY = _get_env("FAL_KEY", "") or _get_env("FAL_AI", "")
if FAL_KEY:
    if not os.environ.get("FAL_KEY"):
        os.environ["FAL_KEY"] = FAL_KEY
    if not os.environ.get("FAL_AI"):
        os.environ["FAL_AI"] = FAL_KEY
