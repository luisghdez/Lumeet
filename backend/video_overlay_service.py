"""
Re-render on-video text overlays for account plan posts.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
from typing import Any, Dict, Optional

import requests

from account_plan_store import account_plan_store
from caption_overlay import render_video_overlay
from config import GCS_VIDEO_OBJECT_PREFIX, PUBLIC_BACKEND_BASE_URL
from generation_store import generation_store
from video_overlay_styles import (
    DEFAULT_OVERLAY,
    normalize_overlay_spec,
    overlay_spec_from_caption,
)

JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")
_active_overlay_slots: set[str] = set()
_active_overlay_lock = threading.Lock()


class VideoOverlayError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _slot_key(plan_id: str, slot: int) -> str:
    return f"{plan_id}:{slot}"


def _find_post(plan: Dict[str, Any], slot: int) -> Optional[Dict[str, Any]]:
    for post in plan.get("plannedPosts") or []:
        if isinstance(post, dict) and int(post.get("slot") or 0) == int(slot):
            return post
    return None


def _local_raw_video_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id, "output", "generated_raw.mp4")


def _local_final_video_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id, "output", "final_output.mp4")


def _local_extended_video_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id, "output", "extended_final_output.mp4")


def _find_additional_video_path(job_id: str) -> str:
    input_dir = os.path.join(JOBS_DIR, job_id, "input")
    if not os.path.isdir(input_dir):
        return ""
    for entry in sorted(os.listdir(input_dir)):
        if entry.startswith("additional_video"):
            path = os.path.join(input_dir, entry)
            if os.path.isfile(path):
                return path
    return ""


def _is_extended_post(post: Dict[str, Any]) -> bool:
    return (post.get("purpose") or "relatable") == "hook_demo"


def _local_deliverable_video_path(job_id: str, post: Dict[str, Any]) -> str:
    if _is_extended_post(post):
        return _local_extended_video_path(job_id)
    return _local_final_video_path(job_id)


def _finalize_deliverable_video(job_id: str, post: Dict[str, Any], captioned_hook_path: str) -> str:
    if not _is_extended_post(post):
        return captioned_hook_path

    output_dir = os.path.join(JOBS_DIR, job_id, "output")
    additional_path = _find_additional_video_path(job_id)
    audio_path = os.path.join(output_dir, "extracted_audio.aac")
    if not additional_path or not os.path.isfile(audio_path):
        return captioned_hook_path

    from audio_replacer import replace_audio
    from video_concatenator import concatenate_videos

    concatenated_path = os.path.join(output_dir, "concatenated.mp4")
    concatenate_videos(captioned_hook_path, additional_path, output_path=concatenated_path)
    extended_path = _local_extended_video_path(job_id)
    replace_audio(concatenated_path, audio_path, output_path=extended_path)
    return extended_path


def _caption_from_generation(generation_id: str) -> str:
    generation = generation_store.get(generation_id)
    if not isinstance(generation, dict):
        return ""
    for step in generation.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if step.get("key") != "caption_detection":
            continue
        message = str(step.get("message") or "")
        match = re.search(r'Caption:\s*"([^"]*)"', message)
        if match:
            return match.group(1).strip()
        if message.startswith("Caption:"):
            return message.split("Caption:", 1)[1].strip().strip('"')
    return ""


def _raw_video_preview_url(post: Dict[str, Any]) -> str:
    stored = str(post.get("rawVideoUrl") or "").strip()
    if stored and "/api/jobs/" not in stored:
        return stored

    job_id = str(post.get("jobId") or "")
    if job_id and os.path.isfile(_local_raw_video_path(job_id)):
        return f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/jobs/{job_id}/raw"

    return stored


def ensure_post_overlay_metadata(plan_id: str, slot: int) -> Optional[Dict[str, Any]]:
    plan = account_plan_store.get(plan_id)
    if not plan:
        return None
    post = _find_post(plan, slot)
    if not post:
        return None

    updates: Dict[str, Any] = {}
    job_id = str(post.get("jobId") or "")
    generation_id = str(post.get("generationId") or "")

    if not post.get("videoOverlayOriginal"):
        caption = _caption_from_generation(generation_id)
        original = overlay_spec_from_caption(caption)
        updates["videoOverlayOriginal"] = original
        if not post.get("videoOverlay"):
            updates["videoOverlay"] = dict(original)

    if not post.get("rawVideoUrl") and job_id:
        local_raw = _local_raw_video_path(job_id)
        if os.path.isfile(local_raw):
            raw_gcs = _upload_video_to_gcs(job_id, local_raw, object_suffix="generated_raw")
            if raw_gcs and raw_gcs.get("url"):
                updates["rawVideoUrl"] = raw_gcs["url"]
            else:
                updates["rawVideoUrl"] = (
                    f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/jobs/{job_id}/raw"
                )

    if post.get("videoOverlayVersion") is None:
        updates["videoOverlayVersion"] = 0

    if updates:
        return account_plan_store.update_post(plan_id, slot, **updates)
    return plan


def get_plan_post_overlay(plan_id: str, slot: int) -> Dict[str, Any]:
    plan = ensure_post_overlay_metadata(plan_id, slot)
    if not plan:
        raise VideoOverlayError(f"Plan {plan_id} slot {slot} not found.", 404)

    post = _find_post(plan, slot)
    if not post:
        raise VideoOverlayError(f"Plan {plan_id} slot {slot} not found.", 404)

    if post.get("status") != "generated" and not post.get("generatedMediaUrl"):
        raise VideoOverlayError("Only generated posts support overlay editing.", 422)

    current = normalize_overlay_spec(post.get("videoOverlay") or post.get("videoOverlayOriginal") or DEFAULT_OVERLAY)
    original = normalize_overlay_spec(post.get("videoOverlayOriginal") or current)
    editable = _raw_video_available(post)

    return {
        "planId": plan_id,
        "slot": slot,
        "videoOverlay": current,
        "videoOverlayOriginal": original,
        "videoOverlayVersion": int(post.get("videoOverlayVersion") or 0),
        "rawVideoAvailable": editable,
        "rawVideoUrl": _raw_video_preview_url(post),
        "previewVideoUrl": post.get("generatedMediaUrl") or "",
    }


def render_plan_post_overlay(plan_id: str, slot: int, overlay_spec: Dict[str, Any]) -> Dict[str, Any]:
    plan = ensure_post_overlay_metadata(plan_id, slot)
    if not plan:
        raise VideoOverlayError(f"Plan {plan_id} slot {slot} not found.", 404)

    post = _find_post(plan, slot)
    if not post:
        raise VideoOverlayError(f"Plan {plan_id} slot {slot} not found.", 404)

    if post.get("status") != "generated" and not post.get("generatedMediaUrl"):
        raise VideoOverlayError("Only generated posts support overlay editing.", 422)

    key = _slot_key(plan_id, slot)
    with _active_overlay_lock:
        if key in _active_overlay_slots:
            raise VideoOverlayError("Overlay render already in progress for this post.", 409)
        _active_overlay_slots.add(key)

    try:
        normalized = normalize_overlay_spec(overlay_spec)
        raw_path = _resolve_raw_video_path(post)
        version = int(post.get("videoOverlayVersion") or 0) + 1
        job_id = str(post.get("jobId") or "")

        with tempfile.TemporaryDirectory() as tmp_dir:
            captioned_hook_path = os.path.join(tmp_dir, "captioned_hook.mp4")
            render_video_overlay(raw_path, normalized, output_path=captioned_hook_path)

            deliverable_path = captioned_hook_path
            if job_id:
                os.makedirs(os.path.join(JOBS_DIR, job_id, "output"), exist_ok=True)
                shutil.copyfile(captioned_hook_path, _local_final_video_path(job_id))
                deliverable_path = _finalize_deliverable_video(job_id, post, _local_final_video_path(job_id))

            gcs_info = _upload_video_to_gcs(job_id or f"plan_{plan_id}_{slot}", deliverable_path, version=version)
            media_url = (gcs_info or {}).get("url") or post.get("generatedMediaUrl") or ""
            if not (gcs_info or {}).get("url") and job_id:
                media_url = f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/jobs/{job_id}/result?v={version}"

        updates = {
            "videoOverlay": normalized,
            "videoOverlayVersion": version,
            "generatedMediaUrl": media_url,
        }
        account_plan_store.update_post(plan_id, slot, **updates)

        generation_id = post.get("generationId")
        if generation_id:
            generation = generation_store.get(generation_id)
            output = dict((generation or {}).get("output") or {})
            output["videoUrl"] = media_url
            if gcs_info:
                output["videoGcs"] = gcs_info
            output["videoOverlay"] = normalized
            output["videoOverlayVersion"] = version
            if job_id and os.path.isfile(_local_deliverable_video_path(job_id, post)):
                output["resultPath"] = _local_deliverable_video_path(job_id, post)
            generation_store.update(generation_id, output=output)

        refreshed = account_plan_store.get(plan_id)
        return refreshed or plan
    finally:
        with _active_overlay_lock:
            _active_overlay_slots.discard(key)


def revert_plan_post_overlay(plan_id: str, slot: int) -> Dict[str, Any]:
    plan = ensure_post_overlay_metadata(plan_id, slot)
    if not plan:
        raise VideoOverlayError(f"Plan {plan_id} slot {slot} not found.", 404)

    post = _find_post(plan, slot)
    if not post:
        raise VideoOverlayError(f"Plan {plan_id} slot {slot} not found.", 404)

    original = post.get("videoOverlayOriginal")
    if not isinstance(original, dict):
        raise VideoOverlayError("Original overlay snapshot is not available for this post.", 422)

    return render_plan_post_overlay(plan_id, slot, original)


def _raw_video_available(post: Dict[str, Any]) -> bool:
    try:
        _resolve_raw_video_path(post)
        return True
    except VideoOverlayError:
        return False


def _resolve_raw_video_path(post: Dict[str, Any]) -> str:
    job_id = str(post.get("jobId") or "")
    local_raw = _local_raw_video_path(job_id) if job_id else ""
    if local_raw and os.path.isfile(local_raw):
        return local_raw

    raw_url = str(post.get("rawVideoUrl") or "").strip()
    if raw_url:
        return _download_temp_video(raw_url, suffix="_raw.mp4")

    raise VideoOverlayError("Captionless source video is not available for this post.", 422)


def _download_temp_video(url: str, suffix: str = ".mp4") -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    with open(tmp.name, "wb") as handle:
        handle.write(resp.content)
    return tmp.name


def _upload_video_to_gcs(job_id: str, local_video_path: str, *, object_suffix: str = "final_output", version: Optional[int] = None) -> Optional[dict]:
    if not local_video_path or not os.path.isfile(local_video_path):
        return None
    try:
        from storage_gcs import GcsStorage

        gcs = GcsStorage()
        ext = os.path.splitext(local_video_path)[1] or ".mp4"
        if version is not None and object_suffix == "final_output":
            object_name = f"{GCS_VIDEO_OBJECT_PREFIX.strip('/')}/{job_id}/final_output_v{version}{ext}"
        else:
            object_name = f"{GCS_VIDEO_OBJECT_PREFIX.strip('/')}/{job_id}/{object_suffix}{ext}"
        return gcs.upload_file_public(local_video_path, object_name)
    except Exception:
        return None
