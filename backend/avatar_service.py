"""
Avatar Service
==============
Generates a fresh AI avatar portrait from a structured set of visual selections
(see src/lib/avatarOptions.js for the manifest used by the frontend), uploads
the result to GCS, and saves it as a reusable model in model_metadata_store
so it can immediately drive the existing video generation pipeline (modelId
parameter on POST /api/generations/video).

Image generation strategy (env-driven, with fallback):
    1. AVATAR_IMAGE_PROVIDER=gemini  -> google-genai (gemini-3-pro-image-preview)
    2. AVATAR_IMAGE_PROVIDER=openai  -> OpenAI Images (gpt-image-1.5/gpt-image-1)
    3. unset / "auto"                -> Try Gemini first (if GEMINI_API_KEY set),
                                        fall back to OpenAI (if OPENAI_API_KEY set).

The service deliberately only consumes a curated selections dict — never raw
freeform user prompt text — so prompts are deterministic and safe.
"""

from __future__ import annotations

import base64
import io
import os
import uuid
from datetime import datetime, timezone as _tz
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from config import GCS_MODELS_OBJECT_PREFIX
from model_metadata_store import model_metadata_store


class AvatarServiceError(Exception):
    """Raised when the avatar pipeline fails."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Selection manifest (mirror of src/lib/avatarOptions.js, prompt-fragment only)
# ---------------------------------------------------------------------------
# Keep this in sync with the frontend manifest. We only encode the prompt
# fragments here; the frontend supplies stable IDs we look up by section.

AVATAR_PROMPT_MANIFEST: Dict[str, Dict[str, str]] = {
    "gender": {
        "female": "female-presenting",
        "male": "male-presenting",
        "non_binary": "androgynous non-binary",
        "trans_woman": "trans woman",
        "trans_man": "trans man",
    },
    "ethnicity": {
        "african": "African features and heritage",
        "asian": "East Asian features and heritage",
        "european": "European features and heritage",
        "indian": "South Asian / Indian features and heritage",
        "middle_eastern": "Middle Eastern features and heritage",
        "mixed": "mixed-race features",
        "latin_american": "Latin American features and heritage",
        "indigenous": "Indigenous American features and heritage",
        "pacific_islander": "Pacific Islander features and heritage",
    },
    "skinTone": {
        "porcelain": "porcelain skin tone",
        "fair": "fair skin tone",
        "light": "light skin tone",
        "medium": "medium / olive skin tone",
        "tan": "tan / golden skin tone",
        "caramel": "caramel skin tone",
        "brown": "rich brown skin tone",
        "deep": "deep brown skin tone",
    },
    "eyeColor": {
        "brown": "brown eyes",
        "hazel": "hazel eyes",
        "amber": "amber eyes",
        "green": "green eyes",
        "blue": "blue eyes",
        "gray": "gray eyes",
        "violet": "unusual violet eyes",
        "heterochromia": "heterochromia, two different eye colors",
    },
    "age": {
        "young_adult": "in their early 20s, fresh and youthful",
        "adult": "in their mid 30s, confident and polished",
        "mature": "in their 50s, distinguished and graceful",
    },
    "bodyType": {
        "slim": "slim build",
        "athletic": "athletic toned build",
        "average": "average build",
        "curvy": "curvy hourglass build",
        "plus_size": "plus-size build",
        "muscular": "visibly muscular build",
    },
    "hairType": {
        "straight": "straight hair",
        "wavy": "soft wavy hair",
        "curly": "curly hair",
        "coily": "coily natural hair",
        "buzz": "buzz cut or bald",
    },
    "hairLength": {
        "short": "short hair",
        "medium": "medium-length hair",
        "long": "long flowing hair",
        "extra_long": "extra long hair past the waist",
    },
    "hairColor": {
        "jet_black": "jet black hair",
        "dark_brown": "dark brown hair",
        "brown": "medium brown hair",
        "auburn": "auburn red-brown hair",
        "red": "natural red ginger hair",
        "blonde": "blonde hair",
        "platinum": "platinum / silver-blonde hair",
        "gray": "silver gray hair",
        "white": "pure white hair",
        "pastel": "soft pastel pink hair",
        "electric_blue": "electric blue dyed hair",
        "lavender": "lavender purple hair",
    },
    "tattoos": {
        "none": "no visible tattoos",
        "subtle": "a few subtle small tattoos",
        "moderate": "noticeable arm or chest tattoos",
        "full_sleeve": "full sleeve tattoos",
    },
    "piercings": {
        "none": "no piercings",
        "ears": "simple earring studs",
        "septum": "septum nose piercing",
        "brow": "eyebrow piercing",
    },
    "extras": {
        "freckles": "natural freckles across the cheeks and nose",
        "glasses": "wearing thin-frame modern glasses",
        "beard": "well-groomed short beard",
        "mustache": "well-groomed mustache",
        "dimples": "soft dimples when smiling",
        "beauty_mark": "a small beauty mark near the lips",
    },
    "outfit": {
        "casual": "casual everyday outfit, simple t-shirt and jeans",
        "streetwear": "modern streetwear, oversized hoodie and chain",
        "formal": "sharp formal outfit, tailored blazer or dress",
        "athletic": "athletic activewear, sleek athleisure",
        "academia": "soft academia look, knit sweater and collared shirt",
        "cozy": "cozy oversized sweater and beanie, lounge vibe",
    },
}

# Order matters — produces a more legible final prompt.
_SECTION_ORDER: Tuple[str, ...] = (
    "gender",
    "age",
    "ethnicity",
    "skinTone",
    "bodyType",
    "hairType",
    "hairLength",
    "hairColor",
    "eyeColor",
    "extras",
    "tattoos",
    "piercings",
    "outfit",
)

REQUIRED_SECTIONS: Tuple[str, ...] = (
    "gender",
    "ethnicity",
    "skinTone",
    "age",
    "bodyType",
    "hairType",
    "hairColor",
    "outfit",
)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _flatten_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)]


def build_avatar_prompt(selections: Dict[str, Any]) -> str:
    """Compose a deterministic prompt fragment list from the selection IDs."""
    fragments: List[str] = []
    for section_id in _SECTION_ORDER:
        section_map = AVATAR_PROMPT_MANIFEST.get(section_id)
        if not section_map:
            continue
        ids = _flatten_value(selections.get(section_id))
        if not ids:
            continue
        section_fragments = [section_map[i] for i in ids if i in section_map]
        if section_fragments:
            fragments.append(", ".join(section_fragments))

    descriptor = ". ".join(fragments) if fragments else "a person"
    return (
        "Studio portrait of a single person — "
        f"{descriptor}. "
        "Photorealistic, sharp focus on the face, neutral seamless studio backdrop, "
        "soft cinematic lighting, head-and-shoulders 9:16 framing, looking directly at camera, "
        "natural skin texture, no text, no watermarks, no UI overlays, no logos."
    )


def validate_required(selections: Dict[str, Any]) -> List[str]:
    """Return list of required section IDs that are missing a selection."""
    missing: List[str] = []
    for section_id in REQUIRED_SECTIONS:
        ids = _flatten_value(selections.get(section_id))
        if not ids:
            missing.append(section_id)
    return missing


# ---------------------------------------------------------------------------
# Image generation backends
# ---------------------------------------------------------------------------

def _provider_pref() -> str:
    raw = (os.environ.get("AVATAR_IMAGE_PROVIDER") or "auto").strip().lower()
    if raw not in {"gemini", "openai", "auto"}:
        return "auto"
    return raw


def _generate_with_gemini(prompt: str, output_path: str) -> str:
    """Generate the avatar with Gemini's image-preview model.

    Returns the absolute output path. Raises AvatarServiceError on failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise AvatarServiceError("GEMINI_API_KEY is not set.")

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:  # pragma: no cover - import guard
        raise AvatarServiceError(f"google-genai SDK unavailable: {exc}") from exc

    model_id = os.environ.get("AVATAR_GEMINI_MODEL", "gemini-3-pro-image-preview")
    aspect_ratio = os.environ.get("AVATAR_ASPECT_RATIO", "9:16")

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                ),
            ),
        )
    except Exception as exc:
        raise AvatarServiceError(f"Gemini avatar generation failed: {exc}") from exc

    text_response = None
    for part in getattr(response, "parts", []) or []:
        if getattr(part, "text", None):
            text_response = part.text
        elif getattr(part, "inline_data", None) is not None:
            try:
                image = part.as_image()
                image.save(output_path)
                return output_path
            except Exception as exc:
                raise AvatarServiceError(
                    f"Failed to save Gemini image response: {exc}"
                ) from exc

    detail = f" API text: {text_response}" if text_response else ""
    raise AvatarServiceError(f"Gemini returned no image in its response.{detail}")


def _generate_with_openai(prompt: str, output_path: str) -> str:
    """Generate the avatar with OpenAI Images, falling back across model ids."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise AvatarServiceError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - import guard
        raise AvatarServiceError(f"openai SDK unavailable: {exc}") from exc

    client = OpenAI(api_key=api_key)

    candidates = [
        os.environ.get("AVATAR_OPENAI_MODEL", "gpt-image-1.5"),
        "gpt-image-1",
    ]
    seen: set = set()
    size = os.environ.get("AVATAR_OPENAI_SIZE", "1024x1536")  # ~9:16 portrait
    last_error: Optional[Exception] = None
    for model in candidates:
        if not model or model in seen:
            continue
        seen.add(model)
        try:
            result = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                n=1,
            )
        except Exception as exc:
            last_error = exc
            continue

        try:
            data = result.data[0]
        except (AttributeError, IndexError) as exc:
            last_error = exc
            continue

        # OpenAI may return either b64_json or url.
        b64 = getattr(data, "b64_json", None)
        url = getattr(data, "url", None)
        if b64:
            try:
                Image.open(io.BytesIO(base64.b64decode(b64))).save(output_path)
                return output_path
            except Exception as exc:
                last_error = exc
                continue
        if url:
            try:
                import requests as _requests
                resp = _requests.get(url, timeout=60)
                resp.raise_for_status()
                Image.open(io.BytesIO(resp.content)).save(output_path)
                return output_path
            except Exception as exc:
                last_error = exc
                continue
        last_error = AvatarServiceError(
            f"OpenAI image response missing both b64_json and url for model {model}."
        )

    raise AvatarServiceError(
        f"All OpenAI image model candidates failed: {last_error}"
    )


def _generate_image(prompt: str, output_path: str) -> Tuple[str, str]:
    """Run the configured backend(s) and return (output_path, provider_used)."""
    provider = _provider_pref()
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    if provider == "gemini":
        return _generate_with_gemini(prompt, output_path), "gemini"
    if provider == "openai":
        return _generate_with_openai(prompt, output_path), "openai"

    # auto: prefer Gemini if available, otherwise OpenAI.
    errors: List[str] = []
    if has_gemini:
        try:
            return _generate_with_gemini(prompt, output_path), "gemini"
        except AvatarServiceError as exc:
            errors.append(f"gemini: {exc}")
    if has_openai:
        try:
            return _generate_with_openai(prompt, output_path), "openai"
        except AvatarServiceError as exc:
            errors.append(f"openai: {exc}")

    if not errors:
        raise AvatarServiceError(
            "No image-generation provider configured. Set GEMINI_API_KEY or OPENAI_API_KEY."
        )
    raise AvatarServiceError("All avatar image providers failed: " + " | ".join(errors))


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def create_avatar_model(
    selections: Dict[str, Any],
    label: str,
    prompt_summary: str,
    jobs_dir: str,
    on_step: Optional[Any] = None,
) -> Dict[str, Any]:
    """Generate the avatar portrait, upload to GCS, and persist as a model record.

    ``on_step(step_key, status, message)`` is an optional callback used by the
    Generation Center to surface progress to the UI.

    Returns the saved model record (already refreshed for serving).
    """

    def _step(key: str, status: str, message: str = "") -> None:
        if callable(on_step):
            try:
                on_step(key, status, message)
            except Exception:
                pass

    _step("validate", "running", "Validating selections")
    missing = validate_required(selections)
    if missing:
        raise AvatarServiceError(
            "Missing required selections: " + ", ".join(missing)
        )
    _step("validate", "completed", "Selections look good")

    _step("prompt", "running", "Composing avatar prompt")
    prompt = build_avatar_prompt(selections)
    _step("prompt", "completed", "Prompt ready")

    model_id = uuid.uuid4().hex[:12]
    work_dir = os.path.join(jobs_dir, f"_avatar_{model_id}")
    os.makedirs(work_dir, exist_ok=True)
    output_path = os.path.join(work_dir, "avatar.png")

    _step("generate", "running", "Generating avatar image")
    try:
        _, provider = _generate_image(prompt, output_path)
    except AvatarServiceError:
        _step("generate", "failed", "Image generation failed")
        raise
    _step("generate", "completed", f"Generated via {provider}")

    if not os.path.isfile(output_path):
        raise AvatarServiceError("Avatar image was not produced.")

    _step("upload", "running", "Uploading avatar to GCS")
    try:
        from storage_gcs import GcsStorage
        gcs = GcsStorage()
        object_name = f"{GCS_MODELS_OBJECT_PREFIX.strip('/')}/{model_id}/avatar.png"
        gcs_info = gcs.upload_file_public(output_path, object_name)
    except Exception as exc:
        _step("upload", "failed", "Upload failed")
        raise AvatarServiceError(f"GCS upload failed: {exc}") from exc
    _step("upload", "completed", "Avatar uploaded")

    now_iso = datetime.now(_tz.utc).isoformat()

    # Strip any non-serialisable bits before persisting.
    safe_selections: Dict[str, Any] = {}
    for k, v in (selections or {}).items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            safe_selections[k] = v
        elif isinstance(v, list):
            safe_selections[k] = [str(x) for x in v]
        else:
            safe_selections[k] = str(v)

    record: Dict[str, Any] = {
        "modelId": model_id,
        "url": gcs_info.get("url", ""),
        "bucket": gcs_info.get("bucket", ""),
        "object": gcs_info.get("object", ""),
        "label": (label or "AI Avatar").strip()[:120],
        "filename": "avatar.png",
        "createdAt": now_iso,
        "source": "avatar_studio",
        "avatarConfig": safe_selections,
        "promptSummary": (prompt_summary or "").strip()[:500],
        "provider": provider,
    }

    _step("save", "running", "Saving avatar to library")
    model_metadata_store.save(model_id, record)
    _step("save", "completed", "Avatar saved")

    return record
