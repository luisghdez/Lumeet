"""
Ensure deliverable media is publicly accessible before publishing via Late/Zernio.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from config import GCS_VIDEO_OBJECT_PREFIX
from generation_store import generation_store
from job_manager import job_manager
from video_metadata_store import video_metadata_store

logger = logging.getLogger("lumeet.public_media")

JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")

_PRIVATE_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_JOB_RESULT_RE = re.compile(r"/api/jobs/([^/]+)/result(?:[?#].*)?$")
_OVERLAY_VERSION_RE = re.compile(r"[?&]v=(\d+)")


class PublicMediaError(Exception):
    """Raised when media cannot be made publicly accessible."""


def is_public_media_url(url: str) -> bool:
    cleaned = str(url or "").strip()
    if not cleaned.startswith(("http://", "https://")):
        return False
    if "/api/jobs/" in cleaned or "/api/generations/" in cleaned:
        return False

    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in _PRIVATE_HOSTS or host.endswith(".local"):
        return False

    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        pass

    return True


def extract_job_id_from_media_url(url: str) -> str:
    match = _JOB_RESULT_RE.search(str(url or ""))
    return match.group(1) if match else ""


def overlay_version_from_media_url(url: str) -> int:
    match = _OVERLAY_VERSION_RE.search(str(url or ""))
    if not match:
        return 0
    try:
        return max(0, int(match.group(1)))
    except ValueError:
        return 0


def find_local_deliverable_video(
    job_id: str,
    *,
    overlay_version: int = 0,
    extended: bool = False,
) -> str:
    if not job_id:
        return ""

    output_dir = os.path.join(JOBS_DIR, job_id, "output")
    if not os.path.isdir(output_dir):
        return ""

    extended_path = os.path.join(output_dir, "extended_final_output.mp4")
    use_extended = extended or os.path.isfile(extended_path)

    candidates: List[str] = []
    if overlay_version > 0:
        candidates.append(f"final_output_v{overlay_version}.mp4")
    if use_extended:
        candidates.append("extended_final_output.mp4")
    candidates.append("final_output.mp4")

    for name in candidates:
        path = os.path.join(output_dir, name)
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return ""


def _resolve_existing_public_url(job_id: str) -> str:
    if not job_id:
        return ""

    job = job_manager.get_job(job_id)
    if job and job.video_gcs and job.video_gcs.get("url"):
        url = str(job.video_gcs.get("url"))
        if is_public_media_url(url):
            return url

    video_record = video_metadata_store.get(job_id)
    if video_record and video_record.get("url"):
        url = str(video_record.get("url"))
        if is_public_media_url(url):
            return url

    for generation in generation_store.list_all(limit=500):
        if not isinstance(generation, dict):
            continue
        output = generation.get("output")
        if not isinstance(output, dict):
            continue
        if str(output.get("jobId") or "") != job_id:
            continue
        video_gcs = output.get("videoGcs")
        if isinstance(video_gcs, dict) and video_gcs.get("url"):
            url = str(video_gcs.get("url"))
            if is_public_media_url(url):
                return url
        video_url = str(output.get("videoUrl") or "")
        if is_public_media_url(video_url):
            return video_url

    return ""


def _object_name_for_job(job_id: str, overlay_version: int = 0, ext: str = ".mp4") -> str:
    prefix = GCS_VIDEO_OBJECT_PREFIX.strip("/")
    if overlay_version > 0:
        return f"{prefix}/{job_id}/final_output_v{overlay_version}{ext}"
    return f"{prefix}/{job_id}/final_output{ext}"


def _upload_video_public(local_path: str, object_name: str) -> dict:
    from storage_gcs import GcsStorage, GcsStorageError

    try:
        gcs = GcsStorage()
        return gcs.upload_file_public(local_path, object_name)
    except GcsStorageError as exc:
        raise PublicMediaError(exc.message) from exc


def persist_public_video_url(job_id: str, gcs_info: dict, *, extended: bool = False) -> None:
    if not job_id or not isinstance(gcs_info, dict):
        return

    job = job_manager.get_job(job_id)
    if job:
        job.video_gcs = gcs_info

    now_iso = datetime.now(timezone.utc).isoformat()
    video_metadata_store.save(
        job_id,
        {
            "videoId": job_id,
            "url": gcs_info.get("url", ""),
            "bucket": gcs_info.get("bucket", ""),
            "object": gcs_info.get("object", ""),
            "extended": extended,
            "createdAt": now_iso,
            "updatedAt": now_iso,
        },
    )


def ensure_public_media_url(
    url: str = "",
    *,
    job_id: str = "",
    overlay_version: int = 0,
    extended: bool = False,
) -> str:
    cleaned = str(url or "").strip()
    if is_public_media_url(cleaned):
        return cleaned

    resolved_job_id = str(job_id or extract_job_id_from_media_url(cleaned) or "").strip()
    version = overlay_version or overlay_version_from_media_url(cleaned)

    if not resolved_job_id:
        raise PublicMediaError(
            "Media URL is not publicly accessible. Connect GCS or provide a public video URL."
        )

    existing = _resolve_existing_public_url(resolved_job_id)
    if existing:
        return existing

    local_path = find_local_deliverable_video(
        resolved_job_id,
        overlay_version=version,
        extended=extended,
    )
    if not local_path:
        raise PublicMediaError(
            f"No public media URL or local deliverable video found for job {resolved_job_id}."
        )

    ext = os.path.splitext(local_path)[1] or ".mp4"
    object_name = _object_name_for_job(resolved_job_id, version, ext=ext)
    try:
        gcs_info = _upload_video_public(local_path, object_name)
    except Exception as exc:
        logger.exception("Failed to upload deliverable video for job %s", resolved_job_id)
        raise PublicMediaError(
            f"Could not upload deliverable video to public storage for job {resolved_job_id}: {exc}"
        ) from exc

    public_url = str((gcs_info or {}).get("url") or "")
    if not is_public_media_url(public_url):
        raise PublicMediaError(
            f"Upload completed but no publicly accessible URL was returned for job {resolved_job_id}."
        )

    persist_public_video_url(resolved_job_id, gcs_info, extended=extended)
    logger.info("Published deliverable video for job %s to %s", resolved_job_id, public_url)
    return public_url


def ensure_public_media_urls(
    media_urls: Optional[List[str]] = None,
    *,
    job_id: str = "",
    overlay_version: int = 0,
    extended: bool = False,
    include_result_video: bool = False,
) -> List[str]:
    resolved: List[str] = []

    for url in media_urls or []:
        if not url:
            continue
        extracted_job_id = extract_job_id_from_media_url(url)
        version = overlay_version or overlay_version_from_media_url(url)
        resolved.append(
            ensure_public_media_url(
                url,
                job_id=extracted_job_id or job_id,
                overlay_version=version,
                extended=extended,
            )
        )

    if include_result_video and job_id:
        resolved.append(
            ensure_public_media_url(
                "",
                job_id=job_id,
                overlay_version=overlay_version,
                extended=extended,
            )
        )

    deduped = list(dict.fromkeys(resolved))
    if not deduped and (media_urls or include_result_video):
        raise PublicMediaError("No publicly accessible media URL is available for this post.")
    return deduped
