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

# TikTok organizer import config. Uses Apify by default because it returns
# public metadata without requiring us to download source videos.
TIKTOK_PROVIDER = _get_env("TIKTOK_PROVIDER", "apify")
APIFY_TOKEN = _get_env("APIFY_TOKEN", "")
APIFY_TIKTOK_ACTOR_ID = _get_env("APIFY_TIKTOK_ACTOR_ID", "clockworks/tiktok-scraper")
TIKTOK_SCAN_TIMEOUT_SEC = _get_int_env("TIKTOK_SCAN_TIMEOUT_SEC", 120)
TIKTOK_IMPORT_METADATA_FILE = _get_env(
    "TIKTOK_IMPORT_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "tiktok_import_metadata.json"),
)
ORGANIZER_SOURCE_BATCHES_FILE = _get_env(
    "ORGANIZER_SOURCE_BATCHES_FILE",
    os.path.join(os.path.dirname(__file__), "organizer_source_batches.json"),
)
ORGANIZER_VIDEO_REFERENCES_FILE = _get_env(
    "ORGANIZER_VIDEO_REFERENCES_FILE",
    os.path.join(os.path.dirname(__file__), "organizer_video_references.json"),
)
ORGANIZER_CREATORS_FILE = _get_env(
    "ORGANIZER_CREATORS_FILE",
    os.path.join(os.path.dirname(__file__), "organizer_creators.json"),
)
ORGANIZER_REVIEW_ACTIONS_FILE = _get_env(
    "ORGANIZER_REVIEW_ACTIONS_FILE",
    os.path.join(os.path.dirname(__file__), "organizer_review_actions.json"),
)
ORGANIZER_VIDEO_AI_TAGS_FILE = _get_env(
    "ORGANIZER_VIDEO_AI_TAGS_FILE",
    os.path.join(os.path.dirname(__file__), "organizer_video_ai_tags.json"),
)
VIDEO_ANALYSIS_TEMP_DIR = _get_env(
    "VIDEO_ANALYSIS_TEMP_DIR",
    os.path.join(os.path.dirname(__file__), "analysis_tmp"),
)
VIDEO_ANALYSIS_FRAME_DIR = _get_env(
    "VIDEO_ANALYSIS_FRAME_DIR",
    os.path.join(os.path.dirname(__file__), "analysis_frames"),
)
VIDEO_ANALYSIS_KEEP_FRAMES = _get_bool_env("VIDEO_ANALYSIS_KEEP_FRAMES", True)
VIDEO_ANALYSIS_SAMPLE_FPS = _get_int_env("VIDEO_ANALYSIS_SAMPLE_FPS", 1)
VIDEO_ANALYSIS_MAX_FRAMES = _get_int_env("VIDEO_ANALYSIS_MAX_FRAMES", 45)
VIDEO_ANALYSIS_FRAME_WIDTH = _get_int_env("VIDEO_ANALYSIS_FRAME_WIDTH", 224)
VIDEO_ANALYSIS_MAX_DOWNLOAD_MB = _get_int_env("VIDEO_ANALYSIS_MAX_DOWNLOAD_MB", 80)
VIDEO_ANALYSIS_DOWNLOAD_TIMEOUT_SEC = _get_int_env("VIDEO_ANALYSIS_DOWNLOAD_TIMEOUT_SEC", 120)
OPENAI_TAGGING_MODEL = _get_env("OPENAI_TAGGING_MODEL", "gpt-4o-mini")

# Used to build publicly reachable result URLs for social scheduling.
PUBLIC_BACKEND_BASE_URL = _get_env("PUBLIC_BACKEND_BASE_URL", "http://127.0.0.1:8000")

# Useful for running local integrations without auth.
LATE_ALLOW_MISSING_API_KEY = _get_bool_env("LATE_ALLOW_MISSING_API_KEY", False)

# Carousel + GCS config
GCS_BUCKET_NAME = _get_env("GCS_BUCKET_NAME", "")
GCS_OBJECT_PREFIX = _get_env("GCS_OBJECT_PREFIX", "carousels")
GCS_VIDEO_OBJECT_PREFIX = _get_env("GCS_VIDEO_OBJECT_PREFIX", "videos")
GCS_HOOKS_OBJECT_PREFIX = _get_env("GCS_HOOKS_OBJECT_PREFIX", "hooks")
GCS_SOUNDS_OBJECT_PREFIX = _get_env("GCS_SOUNDS_OBJECT_PREFIX", "sounds")
GCS_MODELS_OBJECT_PREFIX = _get_env("GCS_MODELS_OBJECT_PREFIX", "models")
GCS_EXTENSION_VIDEOS_OBJECT_PREFIX = _get_env("GCS_EXTENSION_VIDEOS_OBJECT_PREFIX", "extension_videos")
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
GENERATION_METADATA_FILE = _get_env(
    "GENERATION_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "generation_metadata.json"),
)
HOOK_METADATA_FILE = _get_env(
    "HOOK_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "hook_metadata.json"),
)
SOUND_METADATA_FILE = _get_env(
    "SOUND_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "sound_metadata.json"),
)
MODEL_METADATA_FILE = _get_env(
    "MODEL_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "model_metadata.json"),
)
EXTENSION_VIDEO_METADATA_FILE = _get_env(
    "EXTENSION_VIDEO_METADATA_FILE",
    os.path.join(os.path.dirname(__file__), "extension_video_metadata.json"),
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

# Max wall-clock time for fal_client.subscribe() on Kling motion-control (queue + inference).
# Increase for very long reference videos; decrease to fail faster during integration tests.
FAL_MOTION_CLIENT_TIMEOUT_SEC = _get_int_env("FAL_MOTION_CLIENT_TIMEOUT_SEC", 1800)
