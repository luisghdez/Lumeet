"""
FastAPI Server
==============
Exposes the video generation pipeline as async HTTP endpoints.

Endpoints:
    POST /api/generate      -- Upload image + video, start a pipeline job
    GET  /api/jobs/{job_id}  -- Poll job status and step progress
    GET  /api/jobs/{job_id}/result -- Download the final video

Run:
    cd backend && source venv/bin/activate
    uvicorn api:app --reload --port 8000
"""

import os
import sys
import shutil
import threading
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure backend modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from job_manager import job_manager, JobStatus
from pipeline import run_full_pipeline
from cancellation import PipelineCancelled
from late_service import late_service, LateServiceError
from carousel_service import carousel_service, CarouselServiceError
from avatar_service import (
    create_avatar_model,
    validate_required as validate_avatar_selections,
    AvatarServiceError,
)
from video_metadata_store import video_metadata_store
from generation_store import generation_store, GenerationStatus
from hook_metadata_store import hook_metadata_store
from sound_metadata_store import sound_metadata_store
from model_metadata_store import model_metadata_store
from extension_video_metadata_store import extension_video_metadata_store
from tiktok_import_store import tiktok_import_store
from tiktok_organizer_service import (
    discover_tiktok_accounts_for_niche,
    list_discovery_niches as list_tiktok_discovery_niches,
    scan_tiktok_account,
    TikTokOrganizerError,
)
from organizer_store import APPROVAL_STATUSES, organizer_store
from organizer_account_discovery_store import organizer_account_discovery_store
from organizer_account_job_store import organizer_account_job_store
from video_analysis_service import analyze_video_reference, VideoAnalysisError
from account_planner_service import (
    AccountPlannerError,
    create_studytok_simple_plan,
    generate_account_plan,
    list_archetypes as list_account_planner_archetypes,
    swap_studytok_plan_post,
)
from account_plan_store import account_plan_store
from account_plan_generation_service import (
    AccountPlanGenerationError,
    schedule_generated_plan_posts,
    start_plan_generation,
)
from config import (
    PUBLIC_BACKEND_BASE_URL,
    GCS_VIDEO_OBJECT_PREFIX,
    GCS_HOOKS_OBJECT_PREFIX,
    GCS_SOUNDS_OBJECT_PREFIX,
    GCS_MODELS_OBJECT_PREFIX,
    GCS_EXTENSION_VIDEOS_OBJECT_PREFIX,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Lumeet Video Pipeline API", version="1.0.0")
logger = logging.getLogger("lumeet.api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base directory for job files
JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)


def _extract_legacy_job_id(url: str) -> str:
    match = re.search(r"/api/jobs/([^/]+)/result(?:[?#].*)?$", url or "")
    return match.group(1) if match else ""


def _is_safe_result_path(path: str) -> bool:
    if not path:
        return False
    try:
        abs_path = os.path.abspath(path)
        return abs_path.startswith(os.path.abspath(JOBS_DIR) + os.sep) and os.path.isfile(abs_path)
    except OSError:
        return False


def _generation_result_url(generation_id: str, output: Any) -> str:
    if not generation_id or not isinstance(output, dict):
        return ""
    result_path = str(output.get("resultPath") or "")
    if _is_safe_result_path(result_path):
        return f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/generations/{generation_id}/result"
    return ""


def _stable_video_url_for_job(job_id: str) -> str:
    if not job_id:
        return ""

    job = job_manager.get_job(job_id)
    if job and job.video_gcs and job.video_gcs.get("url"):
        return str(job.video_gcs.get("url"))

    video_record = video_metadata_store.get(job_id)
    if video_record and video_record.get("url"):
        return str(video_record.get("url"))

    generation = generation_store.get(job_id)
    if isinstance(generation, dict):
        output = generation.get("output") or {}
        if isinstance(output, dict):
            video_gcs = output.get("videoGcs") or {}
            if isinstance(video_gcs, dict) and video_gcs.get("url"):
                return str(video_gcs.get("url"))
            video_url = output.get("videoUrl") or ""
            if isinstance(video_url, str) and video_url and "/api/jobs/" not in video_url:
                return video_url

    for generation in generation_store.list_all(limit=500):
        if not isinstance(generation, dict):
            continue
        output = generation.get("output") or {}
        if not isinstance(output, dict):
            continue
        if str(output.get("jobId") or "") != job_id:
            continue
        video_gcs = output.get("videoGcs") or {}
        if isinstance(video_gcs, dict) and video_gcs.get("url"):
            return str(video_gcs.get("url"))
        video_url = output.get("videoUrl") or ""
        if isinstance(video_url, str) and video_url and "/api/jobs/" not in video_url:
            return video_url
        result_url = _generation_result_url(str(generation.get("generationId") or ""), output)
        if result_url:
            return result_url

    return ""


def _normalize_generation_output(output: Any, generation_id: str = "") -> Any:
    if not isinstance(output, dict):
        return output
    normalized = dict(output)
    video_gcs = normalized.get("videoGcs") if isinstance(normalized.get("videoGcs"), dict) else {}
    video_url = str(normalized.get("videoUrl") or "")
    stable_url = ""

    if isinstance(video_gcs, dict) and video_gcs.get("url"):
        stable_url = str(video_gcs.get("url"))
    elif video_url and "/api/jobs/" not in video_url:
        stable_url = video_url
    else:
        stable_url = _stable_video_url_for_job(str(normalized.get("jobId") or ""))
    if not stable_url:
        stable_url = _generation_result_url(generation_id, normalized)

    if stable_url:
        normalized["videoUrl"] = stable_url
        normalized["videoGcs"] = {
            **(video_gcs if isinstance(video_gcs, dict) else {}),
            "url": stable_url,
        }
    return normalized


def _normalize_generation_record(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)
    normalized["output"] = _normalize_generation_output(
        normalized.get("output"),
        str(normalized.get("generationId") or ""),
    )
    return normalized


def _normalize_plan_post(post: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(post)
    generated_media_url = str(normalized.get("generatedMediaUrl") or "")
    stable_url = ""
    if generated_media_url and "/api/jobs/" not in generated_media_url:
        stable_url = generated_media_url
    else:
        generation_id = str(normalized.get("generationId") or "")
        if generation_id:
            generation = generation_store.get(generation_id)
            if isinstance(generation, dict):
                output = _normalize_generation_output(generation.get("output"), generation_id)
                if isinstance(output, dict):
                    stable_url = str(output.get("videoUrl") or "")
        if not stable_url:
            stable_url = _stable_video_url_for_job(str(normalized.get("jobId") or ""))
    if stable_url:
        normalized["generatedMediaUrl"] = stable_url
    return normalized


def _normalize_plan_record(plan: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(plan)
    posts = normalized.get("plannedPosts") or []
    if isinstance(posts, list):
        normalized["plannedPosts"] = [
            _normalize_plan_post(post) if isinstance(post, dict) else post
            for post in posts
        ]
    return normalized


class LateProfileCreateRequest(BaseModel):
    sessionId: str = Field(default="local-dev-session")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class LatePlatformTarget(BaseModel):
    platform: str = Field(min_length=1, max_length=50)
    accountId: str = Field(min_length=1, max_length=120)


class LateCreatePostRequest(BaseModel):
    sessionId: str = Field(default="local-dev-session")
    profileId: Optional[str] = None
    content: str = Field(min_length=1, max_length=5000)
    platforms: List[LatePlatformTarget]
    timezone: Optional[str] = Field(default="UTC")
    scheduledFor: Optional[str] = None
    publishNow: bool = False
    mediaUrls: List[str] = Field(default_factory=list)
    includeResultVideo: bool = False
    jobId: Optional[str] = None


class CarouselCreateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    hook_style: str = Field(default="illustrated", pattern=r"^(illustrated|study_desk|study_girl|pinterest)$")
    carousel_style: str = Field(default="illustrated", pattern=r"^(illustrated|illustrated_2)$")


class AvatarCreateRequest(BaseModel):
    selections: Dict[str, Any] = Field(default_factory=dict)
    promptSummary: str = Field(default="", max_length=500)
    label: str = Field(default="", max_length=120)


class TikTokAccountScanRequest(BaseModel):
    account: str = Field(min_length=1, max_length=200)
    maxItems: int = Field(default=30, ge=1, le=100)


class OrganizerBatchFromScanRequest(BaseModel):
    scanId: str = Field(min_length=1, max_length=120)
    nicheHint: str = Field(default="", max_length=200)


class OrganizerReviewStatusRequest(BaseModel):
    approvalStatus: str = Field(pattern=r"^(pending|approved|rejected|saved_hook_only|saved_format_only|needs_deep_analysis)$")
    notes: str = Field(default="", max_length=1000)


class OrganizerBatchAnalyzeRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=25)
    retryFailed: bool = False


class OrganizerAccountProcessRequest(BaseModel):
    account: str = Field(min_length=1, max_length=200)
    maxItems: int = Field(default=100, ge=1, le=100)
    nicheHint: str = Field(default="", max_length=200)
    analyze: bool = True
    retryFailed: bool = False
    maxDurationSec: int = Field(default=30, ge=1, le=300)
    tagConcurrency: int = Field(default=2, ge=1, le=3)
    maxAnalysisFrames: int = Field(default=12, ge=1, le=45)


class OrganizerAccountDiscoveryRequest(BaseModel):
    niche: str = Field(min_length=1, max_length=80)
    limit: int = Field(default=25, ge=1, le=50)
    videosPerSource: int = Field(default=20, ge=1, le=50)
    refresh: bool = False


class AccountPlannerCreateRequest(BaseModel):
    archetype: str = Field(default="studytok", pattern=r"^studytok$")
    postCount: int = Field(default=30, ge=1, le=60)
    batchId: str = Field(default="", max_length=120)


class StudyTokSimplePlanCreateRequest(BaseModel):
    postCount: int = Field(default=30, ge=1, le=60)
    relatablePerDay: int = Field(default=3, ge=0, le=12)
    hookDemoPerDay: int = Field(default=1, ge=0, le=12)
    startDate: str = Field(default="", max_length=20)
    dailyTimes: List[str] = Field(default_factory=list)
    timezone: str = Field(default="UTC", max_length=80)


class AccountPlanPatchRequest(BaseModel):
    status: Optional[str] = Field(default=None, pattern=r"^(draft|approved|generating|generated|generation_failed|generation_dry_run)$")
    plannedPosts: Optional[List[Dict[str, Any]]] = None


class AccountPlanGenerateRequest(BaseModel):
    dryRun: bool = False
    limit: int = Field(default=0, ge=0, le=60)
    modelId: Optional[str] = Field(default=None, max_length=120)
    extensionVideoId: Optional[str] = Field(default=None, max_length=120)


class AccountPlanScheduleRequest(BaseModel):
    sessionId: str = Field(default="local-dev-session")
    profileId: Optional[str] = None
    platforms: List[LatePlatformTarget]
    timezone: Optional[str] = Field(default="UTC")


class AccountPlanPostPatchRequest(BaseModel):
    captionDraft: Optional[str] = Field(default=None, max_length=5000)
    suggestedScheduledFor: Optional[str] = Field(default=None, max_length=80)
    reviewStatus: Optional[str] = Field(default=None, pattern=r"^(pending|approved|rejected|scheduled)$")
    status: Optional[str] = Field(default=None, max_length=40)
    generatedMediaUrl: Optional[str] = Field(default=None, max_length=1000)
    latePostId: Optional[str] = Field(default=None, max_length=200)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_upload(upload: UploadFile, dest: str) -> None:
    """Save an UploadFile to disk."""
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)


def _upload_video_to_gcs(job_id: str, local_video_path: str) -> Optional[dict]:
    """Upload the final video to GCS and return metadata dict, or None on failure."""
    try:
        from storage_gcs import GcsStorage, GcsStorageError

        gcs = GcsStorage()
        ext = os.path.splitext(local_video_path)[1] or ".mp4"
        object_name = f"{GCS_VIDEO_OBJECT_PREFIX.strip('/')}/{job_id}/final_output{ext}"
        gcs_info = gcs.upload_file_public(local_video_path, object_name)
        logger.info("Uploaded video to GCS: %s", gcs_info.get("url"))
        return gcs_info
    except Exception as exc:
        logger.warning("GCS video upload failed (non-fatal): %s", exc)
        return None


def _save_hook_and_sound_to_gcs(job_id: str, result: dict, extended: bool, video_path: str = "") -> None:
    """Upload the raw hook video and extracted audio to GCS for the hook/sound libraries.

    For extended runs the audio comes from ``result["extracted_audio"]``.
    For non-extended runs we extract the audio from the reference *video_path*
    ourselves so that every generation gets a sound saved.
    """
    from datetime import datetime, timezone as _tz

    try:
        from storage_gcs import GcsStorage
        gcs = GcsStorage()
    except Exception as exc:
        logger.warning("GCS not available for hook/sound save (non-fatal): %s", exc)
        return

    now_iso = datetime.now(_tz.utc).isoformat()
    sound_id: Optional[str] = None

    # Determine the audio file to upload.
    # Extended pipeline already has it; for normal runs, extract from the reference video.
    extracted_audio_path = result.get("extracted_audio", "")
    if not extracted_audio_path or not os.path.isfile(extracted_audio_path):
        # Extract audio from the reference video on the fly
        if video_path and os.path.isfile(video_path):
            try:
                from audio_extractor import extract_audio
                output_dir = os.path.dirname(result.get("raw_video", "")) or os.path.dirname(video_path)
                extracted_audio_path = os.path.join(output_dir, "extracted_audio.aac")
                extract_audio(video_path, output_path=extracted_audio_path)
                logger.info("Extracted audio from reference video for sound library")
            except Exception as exc:
                logger.warning("Audio extraction from reference video failed (non-fatal): %s", exc)
                extracted_audio_path = ""

    if extracted_audio_path and os.path.isfile(extracted_audio_path):
        sound_id = f"snd_{job_id}"
        snd_object = f"{GCS_SOUNDS_OBJECT_PREFIX.strip('/')}/{sound_id}/audio.aac"
        try:
            snd_gcs = gcs.upload_file_public(extracted_audio_path, snd_object)
            # Get duration
            import subprocess
            dur_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                extracted_audio_path,
            ]
            dur_result = subprocess.run(dur_cmd, capture_output=True, text=True)
            duration = 0.0
            try:
                duration = float(dur_result.stdout.strip())
            except (ValueError, TypeError):
                pass

            sound_metadata_store.save(sound_id, {
                "soundId": sound_id,
                "sourceJobId": job_id,
                "sourceHookId": job_id,
                "url": snd_gcs.get("url", ""),
                "bucket": snd_gcs.get("bucket", ""),
                "object": snd_gcs.get("object", ""),
                "label": "",
                "durationSec": round(duration, 2),
                "createdAt": now_iso,
            })
            logger.info("Saved sound %s to GCS", sound_id)
        except Exception as exc:
            logger.warning("Sound GCS upload failed (non-fatal): %s", exc)
            sound_id = None

    # Upload generated_raw.mp4 as a hook (path from pipeline result["raw_video"])
    raw_hook_path = result.get("raw_video", "") or ""
    if raw_hook_path and os.path.isfile(raw_hook_path):
        hook_object = f"{GCS_HOOKS_OBJECT_PREFIX.strip('/')}/{job_id}/raw.mp4"
        try:
            hook_gcs = gcs.upload_file_public(raw_hook_path, hook_object)
            hook_metadata_store.save(job_id, {
                "hookId": job_id,
                "sourceJobId": job_id,
                "url": hook_gcs.get("url", ""),
                "bucket": hook_gcs.get("bucket", ""),
                "object": hook_gcs.get("object", ""),
                "originalSoundId": sound_id,
                "label": "",
                "createdAt": now_iso,
            })
            logger.info("Saved hook %s to GCS", job_id)
        except Exception as exc:
            logger.warning("Hook GCS upload failed (non-fatal): %s", exc)


def _run_pipeline_thread(
    job_id: str,
    video_path: str,
    image_path: str,
    output_dir: str,
    extended: bool = False,
    additional_video_path: Optional[str] = None,
    generation_id: Optional[str] = None,
    skip_scene_detection: bool = False,
) -> None:
    """Target for the background thread that runs the pipeline."""
    def cancel_check() -> bool:
        return job_manager.is_cancel_requested(job_id)

    if cancel_check():
        logger.info(
            "video pipeline not started because cancellation was already requested job_id=%s generation_id=%s",
            job_id,
            generation_id or "-",
        )
        if generation_id:
            generation_store.mark_failed(generation_id, "Cancelled by user")
        return

    job_manager.mark_processing(job_id)
    if generation_id:
        generation_store.mark_processing(generation_id, current_step="pipeline")

    logger.info(
        "video pipeline thread started job_id=%s generation_id=%s video=%s image=%s extended=%s skip_scene_detection=%s",
        job_id,
        generation_id or "-",
        os.path.basename(video_path),
        os.path.basename(image_path),
        extended,
        skip_scene_detection,
    )

    # Build a callback that updates both the legacy job_manager AND generation_store
    jm_cb = job_manager.make_step_callback(job_id)

    def cb(step_key: str, event: str, message: str = ""):
        if event != "progress":
            logger.info(
                "video pipeline step job_id=%s generation_id=%s step=%s event=%s message=%s",
                job_id,
                generation_id or "-",
                step_key,
                event,
                (message or "")[:220],
            )
        jm_cb(step_key, event, message)
        if generation_id:
            if event == "progress":
                generation_store.update_step(generation_id, step_key, "running", message)
            else:
                step_status = {"start": "running", "complete": "completed", "fail": "failed"}.get(event, event)
                generation_store.update_step(generation_id, step_key, step_status, message)

    try:
        result = run_full_pipeline(
            video_path=video_path,
            model_image_path=image_path,
            output_dir=output_dir,
            on_step=cb,
            extended=extended,
            additional_video_path=additional_video_path,
            skip_scene_detection=skip_scene_detection,
            cancel_check=cancel_check,
        )
        if cancel_check():
            raise PipelineCancelled("Cancelled by user")

        # Attempt to upload final video to GCS for stable public URL.
        gcs_info = _upload_video_to_gcs(job_id, result["final_video"])
        if cancel_check():
            raise PipelineCancelled("Cancelled by user")
        if gcs_info:
            result["final_video_gcs"] = gcs_info

        job_manager.mark_completed(job_id, result["final_video"], result)

        # Store GCS metadata on the job so it's exposed via to_dict().
        if gcs_info:
            job = job_manager.get_job(job_id)
            if job:
                job.video_gcs = gcs_info

            # Persist video metadata for the video library.
            from datetime import datetime, timezone as _tz

            video_metadata_store.save(job_id, {
                "videoId": job_id,
                "url": gcs_info.get("url", ""),
                "bucket": gcs_info.get("bucket", ""),
                "object": gcs_info.get("object", ""),
                "extended": extended,
                "createdAt": datetime.now(_tz.utc).isoformat(),
            })

        # Auto-save hook (generated_raw.mp4) and sound to GCS for the libraries.
        if cancel_check():
            raise PipelineCancelled("Cancelled by user")
        _save_hook_and_sound_to_gcs(job_id, result, extended, video_path=video_path)

        # Update generation store with completed output
        if cancel_check():
            raise PipelineCancelled("Cancelled by user")
        if generation_id:
            video_url = (gcs_info or {}).get("url", "") if gcs_info else ""
            generation_store.mark_completed(generation_id, {
                "jobId": job_id,
                "videoUrl": video_url,
                "resultPath": result.get("final_video", ""),
                "videoGcs": gcs_info,
            })
        logger.info(
            "video pipeline completed job_id=%s generation_id=%s final=%s",
            job_id,
            generation_id or "-",
            os.path.basename(result.get("final_video", "") or ""),
        )
    except PipelineCancelled as exc:
        logger.info(
            "video pipeline CANCELLED job_id=%s generation_id=%s",
            job_id,
            generation_id or "-",
        )
        job_manager.request_cancel(job_id, str(exc) or "Cancelled by user")
        if generation_id:
            generation_store.mark_failed(generation_id, str(exc) or "Cancelled by user")
    except Exception as exc:
        logger.exception(
            "video pipeline FAILED job_id=%s generation_id=%s error=%s",
            job_id,
            generation_id or "-",
            exc,
        )
        job_manager.mark_failed(job_id, str(exc))
        if generation_id:
            generation_store.mark_failed(generation_id, str(exc))


def _run_carousel_thread(
    generation_id: str,
    prompt: str,
    timezone_name: str,
    hook_style: str = "illustrated",
    carousel_style: str = "illustrated",
) -> None:
    """Background thread that generates a carousel and updates the generation store."""
    generation_store.mark_processing(generation_id, current_step="generating")
    generation_store.update_step(generation_id, "generating", "running", "Generating carousel slides...")

    try:
        result = carousel_service.create_carousel(
            prompt=prompt,
            timezone_name=timezone_name,
            hook_style=hook_style,
            carousel_style=carousel_style,
        )
        generation_store.update_step(generation_id, "generating", "completed", "Carousel generated")
        generation_store.mark_completed(generation_id, {
            "carouselId": result.get("carouselId", ""),
            "mediaUrls": result.get("mediaUrls", []),
            "captionDraft": result.get("captionDraft", ""),
            "hashtags": result.get("hashtags", []),
            "slides": result.get("slides", []),
            "suggestedScheduledFor": result.get("suggestedScheduledFor", ""),
            "carousel": result,
        })
    except (CarouselServiceError, Exception) as exc:
        logger.exception(
            "carousel generation FAILED generation_id=%s error=%s",
            generation_id,
            exc,
        )
        generation_store.update_step(generation_id, "generating", "failed", str(exc))
        err_msg = exc.message if hasattr(exc, "message") else str(exc)
        generation_store.mark_failed(generation_id, err_msg)


def _run_avatar_thread(
    generation_id: str,
    selections: Dict[str, Any],
    label: str,
    prompt_summary: str,
) -> None:
    """Background thread that generates an AI avatar and saves it as a model."""
    generation_store.mark_processing(generation_id, current_step="validate")

    def _on_step(step_key: str, status: str, message: str = "") -> None:
        generation_store.update_step(generation_id, step_key, status, message)

    try:
        record = create_avatar_model(
            selections=selections,
            label=label,
            prompt_summary=prompt_summary,
            jobs_dir=JOBS_DIR,
            on_step=_on_step,
        )
        # Re-sign URL on completion so the frontend gets a fresh link.
        refreshed = _refresh_model_url(record)
        generation_store.mark_completed(generation_id, {
            "modelId": refreshed.get("modelId"),
            "model": refreshed,
            "promptSummary": refreshed.get("promptSummary", ""),
            "previewUrl": refreshed.get("url", ""),
        })
        logger.info(
            "avatar generation completed generation_id=%s model_id=%s",
            generation_id,
            refreshed.get("modelId"),
        )
    except AvatarServiceError as exc:
        logger.warning(
            "avatar generation failed generation_id=%s error=%s",
            generation_id,
            exc.message,
        )
        generation_store.mark_failed(generation_id, exc.message)
    except Exception as exc:
        logger.exception(
            "avatar generation crashed generation_id=%s error=%s",
            generation_id,
            exc,
        )
        generation_store.mark_failed(generation_id, str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/generate/no-trim")
@app.post("/api/generate")
async def generate(
    request: Request,
    image: UploadFile = File(..., description="Model / identity reference image"),
    video: UploadFile = File(..., description="Reference video"),
    extended: bool = Form(False, description="Enable extended pipeline (concatenate additional video and replace audio)"),
    additional_video: Optional[UploadFile] = File(None, description="Second section video to append (required when extended=True)"),
):
    """
    Start a new video generation pipeline job.

    Accepts multipart form data with:
      - ``image``: the model/identity reference image (PNG/JPG)
      - ``video``: the reference video (MP4)
      - ``extended``: optional boolean to enable extended pipeline (default: False)
      - ``additional_video``: second-section video to append; required when extended=True

    Returns the ``job_id`` which can be used to poll progress and
    download the result.
    """
    skip_scene_detection = request.url.path.endswith("/no-trim")

    # Basic validation
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="image must be an image file (PNG, JPG, etc.)")
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="video must be a video file (MP4, etc.)")

    # Extended-mode validation
    if extended:
        if additional_video is None or not additional_video.filename:
            raise HTTPException(
                status_code=400,
                detail="additional_video is required when extended=True",
            )
        if not additional_video.content_type or not additional_video.content_type.startswith("video/"):
            raise HTTPException(
                status_code=400,
                detail="additional_video must be a video file (MP4, etc.)",
            )

    # Create a job directory to hold uploads and outputs
    job = job_manager.create_job("", "", "", extended=extended)  # placeholder paths, filled below

    job_dir = os.path.join(JOBS_DIR, job.id)
    input_dir = os.path.join(job_dir, "input")
    output_dir = os.path.join(job_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Save uploaded files
    image_ext = os.path.splitext(image.filename or "image.png")[1] or ".png"
    video_ext = os.path.splitext(video.filename or "video.mp4")[1] or ".mp4"

    image_path = os.path.join(input_dir, f"model_image{image_ext}")
    video_path = os.path.join(input_dir, f"reference_video{video_ext}")

    _save_upload(image, image_path)
    _save_upload(video, video_path)

    # Save additional video if provided
    additional_video_path: Optional[str] = None
    if extended and additional_video is not None:
        add_ext = os.path.splitext(additional_video.filename or "additional.mp4")[1] or ".mp4"
        additional_video_path = os.path.join(input_dir, f"additional_video{add_ext}")
        _save_upload(additional_video, additional_video_path)

    # Update job with real paths
    job.video_path = video_path
    job.image_path = image_path
    job.output_dir = output_dir

    # Launch pipeline in background thread
    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(job.id, video_path, image_path, output_dir, extended, additional_video_path, None, skip_scene_detection),
        daemon=True,
    )
    thread.start()

    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the current status and step-by-step progress of a pipeline job.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """
    Download the final generated video.

    Returns 404 if the job doesn't exist, and 409 if it isn't complete yet.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    if job.status == JobStatus.FAILED:
        raise HTTPException(status_code=500, detail=f"Job failed: {job.error}")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not complete yet (status: {job.status.value}).",
        )

    if not job.result_path or not os.path.isfile(job.result_path):
        raise HTTPException(status_code=500, detail="Result file not found on server.")

    return FileResponse(
        job.result_path,
        media_type="video/mp4",
        filename="lumeet_output.mp4",
    )


@app.post("/api/late/profiles")
async def create_late_profile(payload: LateProfileCreateRequest):
    """Create a Late profile and bind it to the current local session."""
    logger.info("Late profile create requested for session=%s", payload.sessionId)
    try:
        result = late_service.create_profile(
            session_id=payload.sessionId,
            name=payload.name,
            description=payload.description,
        )
    except LateServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return result


@app.get("/api/late/connect-url")
async def get_late_connect_url(
    platform: str = Query(..., min_length=1),
    sessionId: str = Query("local-dev-session"),
    profileId: Optional[str] = Query(None),
    redirectUrl: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """Return OAuth authorization URL for connecting a social account via Late."""
    logger.info("Late connect URL requested for platform=%s session=%s", platform, sessionId)
    try:
        result = late_service.get_connect_url(
            session_id=sessionId,
            platform=platform,
            profile_id=profileId,
            redirect_url=redirectUrl,
            state=state,
        )
    except LateServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return result


@app.get("/api/late/accounts")
async def list_late_accounts(
    sessionId: str = Query("local-dev-session"),
    profileId: Optional[str] = Query(None),
):
    """List Late-connected accounts for a session/profile."""
    logger.info("Late accounts list requested for session=%s", sessionId)
    try:
        result = late_service.list_accounts(session_id=sessionId, profile_id=profileId)
    except LateServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return result


@app.get("/api/late/posts")
async def list_late_posts(
    sessionId: str = Query("local-dev-session"),
    profileId: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: Optional[int] = Query(25),
):
    """List scheduled/published posts from Late for dashboard visibility."""
    logger.info("Late posts list requested for session=%s", sessionId)
    try:
        result = late_service.list_posts(
            session_id=sessionId,
            profile_id=profileId,
            status=status,
            limit=limit,
        )
    except LateServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return result


@app.post("/api/late/posts")
async def create_late_post(payload: LateCreatePostRequest):
    """Create/schedule a social post via Late."""
    logger.info(
        "Late post create requested session=%s targets=%d includeResultVideo=%s mediaUrls=%d scheduledFor=%s",
        payload.sessionId,
        len(payload.platforms),
        payload.includeResultVideo,
        len(payload.mediaUrls),
        payload.scheduledFor,
    )
    try:
        result = late_service.create_post(
            session_id=payload.sessionId,
            content=payload.content,
            platforms=[p.model_dump() for p in payload.platforms],
            profile_id=payload.profileId,
            scheduled_for=payload.scheduledFor,
            publish_now=payload.publishNow,
            timezone=payload.timezone,
            media_urls=payload.mediaUrls,
            include_result_video=payload.includeResultVideo,
            job_id=payload.jobId,
        )
    except LateServiceError as exc:
        logger.warning(
            "Late post failed: status=%s message=%s details=%s",
            exc.status_code,
            exc.message,
            exc.details,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return result


@app.post("/api/carousels")
async def create_carousel(payload: CarouselCreateRequest):
    """Generate a carousel from prompt, upload media to GCS, and return review payload."""
    logger.info(
        "Carousel create requested timezone=%s hook_style=%s carousel_style=%s",
        payload.timezone,
        payload.hook_style,
        payload.carousel_style,
    )
    try:
        return carousel_service.create_carousel(
            prompt=payload.prompt,
            timezone_name=payload.timezone,
            hook_style=payload.hook_style,
            carousel_style=payload.carousel_style,
        )
    except CarouselServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/api/carousels/{carousel_id}")
async def get_carousel(carousel_id: str):
    """Fetch previously generated carousel metadata for review/scheduling."""
    try:
        return carousel_service.get_carousel(carousel_id)
    except CarouselServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/api/carousels")
async def list_carousels():
    """List saved carousel payloads for quick scheduling."""
    try:
        return carousel_service.list_carousels()
    except CarouselServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# ---------------------------------------------------------------------------
# TikTok Organizer Import Endpoints
# ---------------------------------------------------------------------------

SUGGESTED_TIKTOK_ACCOUNTS = [
    {
        "id": "sophc_studies",
        "handle": "sophc.studies",
        "displayName": "Soph Studies",
        "nicheHint": "study apps, productivity, student content",
        "accountType": "hook_demo",
        "reason": "Strong app-demo patterns mixed with StudyTok hooks.",
    },
    {
        "id": "notionway",
        "handle": "notionway",
        "displayName": "Notionway",
        "nicheHint": "productivity apps, notion templates, digital organization",
        "accountType": "hook_demo",
        "reason": "Useful seed for app and digital-product demo references.",
    },
    {
        "id": "gracevanslooten",
        "handle": "gracevanslooten",
        "displayName": "Grace Van Slooten",
        "nicheHint": "fashion, gym clothing, lifestyle",
        "accountType": "ugc_physical_product",
        "reason": "Good seed for clothing and lifestyle product references.",
    },
    {
        "id": "mikaylanogueira",
        "handle": "mikaylanogueira",
        "displayName": "Mikayla Nogueira",
        "nicheHint": "beauty, skincare, makeup",
        "accountType": "ugc_physical_product",
        "reason": "High-volume beauty product and skincare UGC examples.",
    },
    {
        "id": "charlidamelio",
        "handle": "charlidamelio",
        "displayName": "Charli D'Amelio",
        "nicheHint": "trending audio, dance, lifestyle",
        "accountType": "trending_audio_dance",
        "reason": "Useful seed for simple dance and trending-audio references.",
    },
    {
        "id": "adamw",
        "handle": "adamw",
        "displayName": "Adam W",
        "nicheHint": "relatable comedy, creator skits, lifestyle",
        "accountType": "relatable_content",
        "reason": "Useful seed for relatable skit and one-scene content patterns.",
    },
]


def _jobs_by_handle() -> Dict[str, Dict[str, Any]]:
    jobs = organizer_account_job_store.list_all(limit=250)
    jobs_by_handle: Dict[str, Dict[str, Any]] = {}
    for job in jobs:
        handle = (job.get("creatorHandle") or job.get("account") or "").strip().lstrip("@").lower()
        if handle and handle not in jobs_by_handle:
            jobs_by_handle[handle] = job
    return jobs_by_handle


def _attach_account_job_status(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    jobs_by_handle = _jobs_by_handle()
    suggestions = []
    for account in accounts:
        handle = (account.get("handle") or "").lower()
        last_job = jobs_by_handle.get(handle)
        suggestions.append({
            **account,
            "lastJob": last_job,
            "lastProcessedAt": last_job.get("completedAt") if last_job else None,
            "status": last_job.get("status") if last_job else "not_processed",
        })
    return suggestions


def _suggested_accounts_with_status(niche: str = "") -> List[Dict[str, Any]]:
    niche_key = (niche or "").strip().lower()
    if niche_key:
        discovery = organizer_account_discovery_store.latest_for_niche(niche_key)
        accounts = discovery.get("accounts", []) if discovery else []
        return _attach_account_job_status(accounts)
    latest_discoveries = organizer_account_discovery_store.list_all(limit=25)
    discovered_accounts: List[Dict[str, Any]] = []
    seen = set()
    for discovery in latest_discoveries:
        if discovery.get("status") != "completed":
            continue
        for account in discovery.get("accounts") or []:
            handle = (account.get("handle") or "").lower()
            if not handle or handle in seen:
                continue
            discovered_accounts.append(account)
            seen.add(handle)
            if len(discovered_accounts) >= 25:
                break
        if len(discovered_accounts) >= 25:
            break
    if discovered_accounts:
        return _attach_account_job_status(discovered_accounts)
    return _attach_account_job_status(SUGGESTED_TIKTOK_ACCOUNTS)


def _account_job_progress_for_tagging(done: int, total: int) -> int:
    if total <= 0:
        return 85
    return min(99, 35 + int((done / total) * 60))


def _video_duration_sec(video: Dict[str, Any]) -> Optional[float]:
    value = video.get("durationSec")
    if value in (None, ""):
        value = (video.get("aiTag") or {}).get("duration_sec")
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _run_organizer_account_job(job_id: str) -> None:
    job = organizer_account_job_store.get(job_id)
    if not job:
        return

    try:
        account = job.get("account") or ""
        max_items = int(job.get("maxItems") or 100)
        niche_hint = job.get("nicheHint") or ""
        retry_failed = bool(job.get("retryFailed"))
        max_duration_sec = int(job.get("maxDurationSec") or 30)
        tag_concurrency = max(1, min(int(job.get("tagConcurrency") or 2), 3))
        max_analysis_frames = int(job.get("maxAnalysisFrames") or 12)

        organizer_account_job_store.mark_processing(job_id, "scanning", progress=5)
        scan = scan_tiktok_account(account, max_items)
        tiktok_import_store.save(scan["scanId"], scan)
        scanned_count = len(scan.get("videos") or [])
        organizer_account_job_store.update_counts(
            job_id,
            counts={"scanned": scanned_count, "total": scanned_count},
            scanId=scan.get("scanId", ""),
            creatorHandle=scan.get("creatorHandle", ""),
            current_step="importing",
            progress=25,
        )

        batch = organizer_store.create_batch_from_scan(scan, niche_hint=niche_hint)
        videos = batch.get("videos") or []
        organizer_account_job_store.update_counts(
            job_id,
            counts={
                "imported": len(videos),
                "total": len(videos),
                "skipped": max(0, scanned_count - len(videos)),
            },
            batchId=batch.get("id", ""),
            batch=batch,
            current_step="tagging" if job.get("analyze", True) else "completed",
            progress=35,
        )

        if not job.get("analyze", True):
            organizer_account_job_store.mark_completed(
                job_id,
                batchId=batch.get("id", ""),
                batch=organizer_store.get_batch(batch.get("id", "")) or batch,
            )
            return

        candidates = []
        skipped_already_tagged = 0
        skipped_failed = 0
        skipped_duration = 0
        for video in videos:
            status = video.get("aiTagStatus") or (video.get("aiTag") or {}).get("status") or "not_tagged"
            if status == "tagged":
                skipped_already_tagged += 1
                continue
            if status == "tag_failed" and not retry_failed:
                skipped_failed += 1
                continue
            duration_sec = _video_duration_sec(video)
            if duration_sec is not None and duration_sec > max_duration_sec:
                skipped_duration += 1
                continue
            candidates.append(video)

        import_skips = max(0, scanned_count - len(videos))
        tagged = 0
        failed = 0
        total_to_process = len(candidates)
        total_skipped = import_skips + skipped_already_tagged + skipped_failed + skipped_duration
        organizer_account_job_store.update_counts(
            job_id,
            counts={
                "eligible": total_to_process,
                "tagged": tagged,
                "failed": failed,
                "skipped": total_skipped,
                "skippedDuration": skipped_duration,
                "skippedAlreadyTagged": skipped_already_tagged,
                "skippedFailed": skipped_failed,
                "total": len(videos),
            },
            current_step="tagging",
            progress=_account_job_progress_for_tagging(0, total_to_process),
        )

        completed = 0

        def analyze_candidate(video: Dict[str, Any]) -> bool:
            video_id = video.get("id")
            if not video_id:
                return False
            try:
                _run_video_reference_analysis(video_id, max_analysis_frames=max_analysis_frames)
                return True
            except HTTPException:
                return False

        if candidates:
            with ThreadPoolExecutor(max_workers=tag_concurrency) as executor:
                futures = [executor.submit(analyze_candidate, video) for video in candidates]
                for future in as_completed(futures):
                    completed += 1
                    if future.result():
                        tagged += 1
                    else:
                        failed += 1
                    organizer_account_job_store.update_counts(
                        job_id,
                        counts={
                            "eligible": total_to_process,
                            "tagged": tagged,
                            "failed": failed,
                            "skipped": total_skipped,
                            "skippedDuration": skipped_duration,
                            "skippedAlreadyTagged": skipped_already_tagged,
                            "skippedFailed": skipped_failed,
                            "total": len(videos),
                        },
                        current_step="tagging",
                        progress=_account_job_progress_for_tagging(completed, total_to_process),
                    )
        else:
            organizer_account_job_store.update_counts(
                job_id,
                counts={
                    "eligible": total_to_process,
                    "tagged": tagged,
                    "failed": failed,
                    "skipped": total_skipped,
                    "skippedDuration": skipped_duration,
                    "skippedAlreadyTagged": skipped_already_tagged,
                    "skippedFailed": skipped_failed,
                    "total": len(videos),
                },
                current_step="tagging",
                progress=99,
            )

        refreshed_batch = organizer_store.get_batch(batch.get("id", "")) or batch
        organizer_account_job_store.mark_completed(
            job_id,
            counts={
                "scanned": scanned_count,
                "imported": len(videos),
                "eligible": total_to_process,
                "tagged": tagged,
                "failed": failed,
                "skipped": total_skipped,
                "skippedDuration": skipped_duration,
                "skippedAlreadyTagged": skipped_already_tagged,
                "skippedFailed": skipped_failed,
                "total": len(videos),
            },
            batchId=batch.get("id", ""),
            batch=refreshed_batch,
        )
    except TikTokOrganizerError as exc:
        logger.warning("Organizer account job failed for TikTok provider: job_id=%s error=%s", job_id, exc.message)
        organizer_account_job_store.mark_failed(job_id, exc.message)
    except Exception as exc:
        logger.exception("Organizer account job failed: %s", job_id)
        organizer_account_job_store.mark_failed(job_id, str(exc))


def _run_organizer_account_discovery(discovery_id: str) -> None:
    discovery = organizer_account_discovery_store.get(discovery_id)
    if not discovery:
        return

    try:
        organizer_account_discovery_store.mark_processing(discovery_id, "discovering", progress=15)
        result = discover_tiktok_accounts_for_niche(
            discovery.get("niche") or "",
            limit=int(discovery.get("limit") or 25),
            videos_per_source=int(discovery.get("videosPerSource") or 20),
        )
        organizer_account_discovery_store.mark_completed(
            discovery_id,
            accounts=result.get("accounts") or [],
            counts=result.get("counts") or {},
        )
        organizer_account_discovery_store.update(
            discovery_id,
            nicheLabel=result.get("nicheLabel", ""),
            nicheHint=result.get("nicheHint", ""),
            provider=result.get("provider", ""),
            providerInput=result.get("providerInput") or {},
        )
    except TikTokOrganizerError as exc:
        logger.warning("Organizer account discovery failed for TikTok provider: discovery_id=%s error=%s", discovery_id, exc.message)
        organizer_account_discovery_store.mark_failed(discovery_id, exc.message)
    except Exception as exc:
        logger.exception("Organizer account discovery failed: %s", discovery_id)
        organizer_account_discovery_store.mark_failed(discovery_id, str(exc))


@app.get("/api/organizer/tiktok/niches")
async def list_organizer_tiktok_niches():
    """List supported niche presets for TikTok account discovery."""
    return {"niches": list_tiktok_discovery_niches()}


@app.post("/api/organizer/tiktok/account-discovery")
async def create_organizer_account_discovery(payload: OrganizerAccountDiscoveryRequest):
    """Start a metadata-only TikTok account discovery job for one niche."""
    if not payload.refresh:
        existing = organizer_account_discovery_store.latest_for_niche(payload.niche)
        if existing:
            return existing
    discovery = organizer_account_discovery_store.create(
        niche=payload.niche.strip().lower(),
        limit=payload.limit,
        videos_per_source=payload.videosPerSource,
    )
    thread = threading.Thread(target=_run_organizer_account_discovery, args=(discovery["discoveryId"],), daemon=True)
    thread.start()
    return discovery


@app.get("/api/organizer/tiktok/account-discovery/{discovery_id}")
async def get_organizer_account_discovery(discovery_id: str):
    """Fetch TikTok account discovery job status and ranked suggestions."""
    discovery = organizer_account_discovery_store.get(discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail=f"Organizer account discovery {discovery_id} not found.")
    return {
        **discovery,
        "accounts": _attach_account_job_status(discovery.get("accounts") or []),
    }


@app.get("/api/organizer/tiktok/suggested-accounts")
async def list_suggested_tiktok_accounts(niche: str = Query("", max_length=80)):
    """List seed TikTok accounts that can be one-tap processed."""
    return {"accounts": _suggested_accounts_with_status(niche)}


@app.post("/api/organizer/tiktok/account-jobs")
async def create_organizer_account_job(payload: OrganizerAccountProcessRequest):
    """Start a background scan -> batch -> AI-tag job for one TikTok account."""
    job = organizer_account_job_store.create(
        account=payload.account,
        max_items=payload.maxItems,
        niche_hint=payload.nicheHint,
        analyze=payload.analyze,
        retry_failed=payload.retryFailed,
        max_duration_sec=payload.maxDurationSec,
        tag_concurrency=payload.tagConcurrency,
        max_analysis_frames=payload.maxAnalysisFrames,
    )
    thread = threading.Thread(target=_run_organizer_account_job, args=(job["jobId"],), daemon=True)
    thread.start()
    return job


@app.get("/api/organizer/tiktok/account-jobs")
async def list_organizer_account_jobs(limit: int = Query(25, ge=1, le=100)):
    """List recent one-tap account processing jobs."""
    return {"jobs": organizer_account_job_store.list_all(limit=limit)}


@app.get("/api/organizer/tiktok/account-jobs/{job_id}")
async def get_organizer_account_job(job_id: str):
    """Fetch one-tap account processing job status."""
    job = organizer_account_job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Organizer account job {job_id} not found.")
    return job


@app.post("/api/organizer/tiktok/account-scan")
async def scan_tiktok_account_endpoint(payload: TikTokAccountScanRequest):
    """Fetch public TikTok account video metadata without downloading videos."""
    try:
        scan = scan_tiktok_account(payload.account, payload.maxItems)
        tiktok_import_store.save(scan["scanId"], scan)
        return scan
    except TikTokOrganizerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/api/organizer/tiktok/scans/{scan_id}")
async def get_tiktok_scan(scan_id: str):
    """Fetch a saved TikTok account scan."""
    scan = tiktok_import_store.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"TikTok scan {scan_id} not found.")
    return scan


@app.get("/api/organizer/tiktok/scans")
async def list_tiktok_scans(limit: int = Query(25, ge=1, le=100)):
    """List recent TikTok account scans."""
    return {"scans": tiktok_import_store.list_all(limit=limit)}


@app.post("/api/organizer/batches/from-tiktok-scan")
async def create_organizer_batch_from_tiktok_scan(payload: OrganizerBatchFromScanRequest):
    """Create source batch + video references from a saved TikTok scan."""
    scan = tiktok_import_store.get(payload.scanId)
    if not scan:
        raise HTTPException(status_code=404, detail=f"TikTok scan {payload.scanId} not found.")
    batch = organizer_store.create_batch_from_scan(scan, niche_hint=payload.nicheHint)
    return batch


@app.get("/api/organizer/batches")
async def list_organizer_batches(limit: int = Query(25, ge=1, le=100)):
    """List organizer source batches."""
    return {"batches": organizer_store.list_batches(limit=limit)}


@app.get("/api/organizer/batches/{batch_id}")
async def get_organizer_batch(batch_id: str):
    """Get organizer batch details including video references."""
    batch = organizer_store.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Organizer batch {batch_id} not found.")
    return batch


@app.patch("/api/organizer/video-references/{video_reference_id}/review")
async def update_organizer_video_review(video_reference_id: str, payload: OrganizerReviewStatusRequest):
    """Update a video reference approval/review status."""
    if payload.approvalStatus not in APPROVAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unsupported approval status: {payload.approvalStatus}")
    try:
        return organizer_store.update_review_status(
            video_reference_id=video_reference_id,
            approval_status=payload.approvalStatus,
            notes=payload.notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Video reference {video_reference_id} not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _run_video_reference_analysis(video_reference_id: str, max_analysis_frames: Optional[int] = None) -> Dict[str, Any]:
    video = organizer_store.get_video_reference(video_reference_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video reference {video_reference_id} not found.")
    try:
        organizer_store.set_video_analysis_status(video_reference_id, "tagging")
        result = analyze_video_reference(video, max_frames=max_analysis_frames)
        return organizer_store.save_video_analysis_result(video_reference_id, result)
    except VideoAnalysisError as exc:
        organizer_store.save_video_analysis_failure(video_reference_id, exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        message = f"Video analysis failed: {exc}"
        organizer_store.save_video_analysis_failure(video_reference_id, message)
        raise HTTPException(status_code=500, detail=message) from exc


@app.post("/api/organizer/video-references/{video_reference_id}/analyze")
async def analyze_organizer_video_reference(video_reference_id: str):
    """Run cheap motion + structured AI analysis for one video reference."""
    return _run_video_reference_analysis(video_reference_id)


@app.get("/api/organizer/video-references/{video_reference_id}/analysis")
async def get_organizer_video_analysis(video_reference_id: str):
    """Get saved analysis for a video reference."""
    analysis = organizer_store.get_video_analysis(video_reference_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis for {video_reference_id} not found.")
    return analysis


@app.post("/api/organizer/batches/{batch_id}/analyze")
async def analyze_organizer_batch(batch_id: str, payload: OrganizerBatchAnalyzeRequest):
    """Analyze a small batch of imported video references sequentially."""
    batch = organizer_store.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Organizer batch {batch_id} not found.")

    candidates = []
    for video in batch.get("videos", []):
        status = video.get("aiTagStatus") or (video.get("aiTag") or {}).get("status") or "not_tagged"
        if status == "tagged":
            continue
        if status == "tag_failed" and not payload.retryFailed:
            continue
        candidates.append(video)
        if len(candidates) >= payload.limit:
            break

    results = []
    for video in candidates:
        video_id = video.get("id")
        if not video_id:
            continue
        try:
            analysis = _run_video_reference_analysis(video_id)
            results.append({"videoReferenceId": video_id, "ok": True, "analysis": analysis})
        except HTTPException as exc:
            results.append({"videoReferenceId": video_id, "ok": False, "error": exc.detail})

    refreshed = organizer_store.get_batch(batch_id)
    return {
        "batch": refreshed,
        "attempted": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Account Planner Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/account-planner/archetypes")
async def get_account_planner_archetypes():
    """List account archetypes available for planner generation."""
    return list_account_planner_archetypes()


@app.post("/api/account-planner/plans")
async def create_account_plan(payload: AccountPlannerCreateRequest):
    """Generate a deterministic account content plan from tagged inspo videos."""
    try:
        return generate_account_plan(
            archetype=payload.archetype,
            post_count=payload.postCount,
            batch_id=payload.batchId,
        )
    except AccountPlannerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/api/account-planner/studytok/simple-plans")
async def create_studytok_simple_plan_endpoint(payload: StudyTokSimplePlanCreateRequest):
    """Create an ordered StudyTok plan from content mix/frequency only."""
    try:
        return create_studytok_simple_plan(
            post_count=payload.postCount,
            relatable_per_day=payload.relatablePerDay,
            hook_demo_per_day=payload.hookDemoPerDay,
            start_date=payload.startDate,
            daily_times=payload.dailyTimes,
            timezone=payload.timezone,
        )
    except AccountPlannerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/api/account-planner/plans")
async def list_account_plans(limit: int = Query(25, ge=1, le=100)):
    """List saved account plans."""
    return {"plans": [_normalize_plan_record(plan) for plan in account_plan_store.list_all(limit=limit)]}


@app.get("/api/account-planner/plans/{plan_id}")
async def get_account_plan(plan_id: str):
    """Get a saved account plan and current generation/review statuses."""
    plan = account_plan_store.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Account plan {plan_id} not found.")
    return _normalize_plan_record(plan)


@app.patch("/api/account-planner/plans/{plan_id}")
async def update_account_plan(plan_id: str, payload: AccountPlanPatchRequest):
    """Approve or update mutable plan fields such as ordered posts."""
    updates = {}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.plannedPosts is not None:
        updates["plannedPosts"] = payload.plannedPosts
    if not updates:
        plan = account_plan_store.get(plan_id)
    else:
        plan = account_plan_store.update(plan_id, **updates)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Account plan {plan_id} not found.")
    return plan


@app.post("/api/account-planner/plans/{plan_id}/generate")
async def generate_account_plan_posts(plan_id: str, payload: AccountPlanGenerateRequest):
    """Start controlled bulk generation for an approved StudyTok plan."""
    try:
        return start_plan_generation(
            plan_id,
            dry_run=payload.dryRun,
            limit=payload.limit,
            model_id=payload.modelId,
            extension_video_id=payload.extensionVideoId,
        )
    except AccountPlanGenerationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/api/account-planner/plans/{plan_id}/schedule")
async def schedule_account_plan_posts(plan_id: str, payload: AccountPlanScheduleRequest):
    """Schedule every generated unscheduled post in a StudyTok plan."""
    try:
        return schedule_generated_plan_posts(
            plan_id,
            session_id=payload.sessionId,
            platforms=[platform.model_dump() for platform in payload.platforms],
            profile_id=payload.profileId,
            timezone=payload.timezone or "UTC",
        )
    except AccountPlanGenerationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.patch("/api/account-planner/plans/{plan_id}/posts/{slot}")
async def update_account_plan_post(plan_id: str, slot: int, payload: AccountPlanPostPatchRequest):
    """Update per-post caption, schedule suggestion, review state, or schedule metadata."""
    updates = {
        key: value
        for key, value in payload.model_dump().items()
        if value is not None
    }
    if not updates:
        plan = account_plan_store.get(plan_id)
    else:
        plan = account_plan_store.update_post(plan_id, slot, **updates)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} slot {slot} not found.")
    return plan


@app.post("/api/account-planner/plans/{plan_id}/posts/{slot}/swap")
async def swap_account_plan_post(plan_id: str, slot: int):
    """Replace one planned post with a similar unused tagged source video."""
    try:
        return swap_studytok_plan_post(plan_id, slot)
    except AccountPlannerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# ---------------------------------------------------------------------------
# Video Library Endpoints
# ---------------------------------------------------------------------------

def _refresh_video_url(item: dict) -> dict:
    """Regenerate the signed URL for a stored video if needed."""
    refreshed = dict(item)
    bucket = item.get("bucket")
    object_name = item.get("object")
    if bucket and object_name:
        try:
            from storage_gcs import GcsStorage
            gcs = GcsStorage()
            if bucket == gcs.bucket_name:
                refreshed["url"] = gcs.generate_read_url(object_name)
        except Exception:
            pass  # keep existing url
    return refreshed


@app.get("/api/videos")
async def list_videos(
    limit: int = Query(0, ge=0, description="Max videos to return (0 = all)"),
    offset: int = Query(0, ge=0, description="Number of videos to skip"),
):
    """List previously generated videos that were uploaded to GCS."""
    items, total = video_metadata_store.list_all(limit=limit, offset=offset)
    refreshed = [_refresh_video_url(item) for item in items]
    return {"videos": refreshed, "total": total}


@app.get("/api/videos/{video_id}")
async def get_video(video_id: str):
    """Get metadata for a single generated video."""
    item = video_metadata_store.get(video_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found.")
    return _refresh_video_url(item)


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    """Delete a generated video from the video library."""
    if not video_metadata_store.delete(video_id):
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found.")
    return {"deleted": True, "videoId": video_id}


# ---------------------------------------------------------------------------
# Generation Center Endpoints
# ---------------------------------------------------------------------------

from job_manager import PIPELINE_STEPS as _PIPELINE_STEPS, EXTENDED_PIPELINE_STEPS as _EXTENDED_PIPELINE_STEPS


@app.post("/api/generations/video/no-trim")
@app.post("/api/generations/video")
async def generation_create_video(
    request: Request,
    image: Optional[UploadFile] = File(None, description="Model / identity reference image"),
    video: UploadFile = File(..., description="Reference video"),
    extended: bool = Form(False),
    additional_video: Optional[UploadFile] = File(None),
    modelId: Optional[str] = Form(None, description="Saved model ID (alternative to image upload)"),
    extensionVideoId: Optional[str] = Form(None, description="Saved extension video ID (alternative to additional_video upload)"),
):
    """Start a video generation job tracked in the Generation Center."""
    import requests as _requests

    skip_scene_detection = request.url.path.endswith("/no-trim")

    # Resolve model image: either from saved model or uploaded file
    has_image_upload = image is not None and image.filename
    if not has_image_upload and not modelId:
        raise HTTPException(status_code=400, detail="Either image file or modelId is required")
    if has_image_upload:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="image must be an image file")

    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="video must be a video file")

    # Resolve extension video source
    has_ext_upload = additional_video is not None and additional_video.filename
    if extended and not has_ext_upload and not extensionVideoId:
        raise HTTPException(status_code=400, detail="additional_video or extensionVideoId is required when extended=True")

    # Build step list for generation store
    step_defs = list(_PIPELINE_STEPS)
    if extended:
        step_defs = step_defs + list(_EXTENDED_PIPELINE_STEPS)
    steps = [{"key": s["key"], "label": s["label"], "status": "pending", "message": ""} for s in step_defs]

    gen = generation_store.create(
        gen_type="video",
        label=f"{video.filename or 'Video generation'}{' (no trim)' if skip_scene_detection else ''}",
        steps=steps,
    )
    gen_id = gen["generationId"]

    # Create legacy job (reuse existing infra)
    job = job_manager.create_job("", "", "", extended=extended)
    job_dir = os.path.join(JOBS_DIR, job.id)
    input_dir = os.path.join(job_dir, "input")
    output_dir = os.path.join(job_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Save model image
    if has_image_upload:
        image_ext = os.path.splitext(image.filename or "image.png")[1] or ".png"
        image_path = os.path.join(input_dir, f"model_image{image_ext}")
        _save_upload(image, image_path)
    else:
        # Download from saved model
        model_record = model_metadata_store.get(modelId)
        if not model_record:
            raise HTTPException(status_code=404, detail=f"Model {modelId} not found.")
        local_model_path = model_record.get("localPath", "")
        if local_model_path and os.path.isfile(local_model_path):
            image_ext = os.path.splitext(local_model_path)[1] or ".png"
            image_path = os.path.join(input_dir, f"model_image{image_ext}")
            shutil.copyfile(local_model_path, image_path)
        else:
            model_url = model_record.get("url", "")
            if not model_url:
                raise HTTPException(status_code=500, detail=f"Model {modelId} has no URL.")
            # Refresh signed URL
            bucket = model_record.get("bucket")
            obj = model_record.get("object")
            if bucket and obj:
                try:
                    from storage_gcs import GcsStorage
                    gcs = GcsStorage()
                    if bucket == gcs.bucket_name:
                        model_url = gcs.generate_read_url(obj)
                except Exception:
                    pass
            image_ext = os.path.splitext(obj or ".png")[1] or ".png"
            image_path = os.path.join(input_dir, f"model_image{image_ext}")
            resp = _requests.get(model_url, timeout=60)
            resp.raise_for_status()
            with open(image_path, "wb") as f:
                f.write(resp.content)

    video_ext = os.path.splitext(video.filename or "video.mp4")[1] or ".mp4"
    video_path = os.path.join(input_dir, f"reference_video{video_ext}")
    _save_upload(video, video_path)

    # Save extension video
    additional_video_path: Optional[str] = None
    if extended:
        if has_ext_upload:
            add_ext = os.path.splitext(additional_video.filename or "additional.mp4")[1] or ".mp4"
            additional_video_path = os.path.join(input_dir, f"additional_video{add_ext}")
            _save_upload(additional_video, additional_video_path)
        elif extensionVideoId:
            ext_record = extension_video_metadata_store.get(extensionVideoId)
            if not ext_record:
                raise HTTPException(status_code=404, detail=f"Extension video {extensionVideoId} not found.")
            local_ext_path = ext_record.get("localPath", "")
            if local_ext_path and os.path.isfile(local_ext_path):
                add_ext = os.path.splitext(local_ext_path)[1] or ".mp4"
                additional_video_path = os.path.join(input_dir, f"additional_video{add_ext}")
                shutil.copyfile(local_ext_path, additional_video_path)
            else:
                ext_url = ext_record.get("url", "")
                if not ext_url:
                    raise HTTPException(status_code=500, detail=f"Extension video {extensionVideoId} has no URL.")
                # Refresh signed URL
                bucket = ext_record.get("bucket")
                obj = ext_record.get("object")
                if bucket and obj:
                    try:
                        from storage_gcs import GcsStorage
                        gcs = GcsStorage()
                        if bucket == gcs.bucket_name:
                            ext_url = gcs.generate_read_url(obj)
                    except Exception:
                        pass
                add_ext = os.path.splitext(obj or ".mp4")[1] or ".mp4"
                additional_video_path = os.path.join(input_dir, f"additional_video{add_ext}")
                resp = _requests.get(ext_url, timeout=120)
                resp.raise_for_status()
                with open(additional_video_path, "wb") as f:
                    f.write(resp.content)

    job.video_path = video_path
    job.image_path = image_path
    job.output_dir = output_dir

    # Store the legacy jobId on the generation record for cross-reference
    generation_store.update(gen_id, jobId=job.id)

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(job.id, video_path, image_path, output_dir, extended, additional_video_path, gen_id, skip_scene_detection),
        daemon=True,
    )
    thread.start()

    return {"generationId": gen_id, "jobId": job.id}


@app.post("/api/generations/carousel")
async def generation_create_carousel(payload: CarouselCreateRequest):
    """Start an async carousel generation job tracked in the Generation Center."""
    steps = [{"key": "generating", "label": "Generating Carousel", "status": "pending", "message": ""}]
    gen = generation_store.create(
        gen_type="carousel",
        label=payload.prompt[:80],
        steps=steps,
    )
    gen_id = gen["generationId"]

    thread = threading.Thread(
        target=_run_carousel_thread,
        args=(gen_id, payload.prompt, payload.timezone, payload.hook_style, payload.carousel_style),
        daemon=True,
    )
    thread.start()

    return {"generationId": gen_id}


@app.post("/api/avatars")
async def generation_create_avatar(payload: AvatarCreateRequest):
    """Start an AI avatar generation job tracked in the Generation Center.

    The job calls ``avatar_service.create_avatar_model`` which builds a safe
    prompt from the user's visual selections, generates a portrait via Gemini
    or OpenAI, uploads it to GCS, and saves the result into model_metadata
    so it is immediately reusable in the existing video pipeline.
    """
    selections = dict(payload.selections or {})

    missing = validate_avatar_selections(selections)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required selections: {', '.join(missing)}",
        )

    steps = [
        {"key": "validate", "label": "Validating selections", "status": "pending", "message": ""},
        {"key": "prompt", "label": "Composing prompt", "status": "pending", "message": ""},
        {"key": "generate", "label": "Generating avatar image", "status": "pending", "message": ""},
        {"key": "upload", "label": "Uploading to library", "status": "pending", "message": ""},
        {"key": "save", "label": "Saving avatar", "status": "pending", "message": ""},
    ]
    label = (payload.label or "AI Avatar").strip()[:120]
    gen = generation_store.create(
        gen_type="avatar",
        label=label,
        steps=steps,
    )
    gen_id = gen["generationId"]

    thread = threading.Thread(
        target=_run_avatar_thread,
        args=(gen_id, selections, label, payload.promptSummary or ""),
        daemon=True,
    )
    thread.start()

    return {"generationId": gen_id}


@app.get("/api/generations")
async def list_generations(limit: int = Query(50, ge=1, le=200)):
    """List generation jobs for the Generation Center panel."""
    items = [_normalize_generation_record(item) for item in generation_store.list_all(limit=limit)]
    return {"generations": items}


@app.get("/api/generations/{generation_id}/result")
async def get_generation_result(generation_id: str):
    """Stream a persisted generation's final_output.mp4 from disk."""
    item = generation_store.get(generation_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} not found.")
    output = item.get("output") or {}
    result_path = str(output.get("resultPath") or "") if isinstance(output, dict) else ""
    if not _is_safe_result_path(result_path):
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} result not found.")
    return FileResponse(
        result_path,
        media_type="video/mp4",
        filename=f"{generation_id}_final_output.mp4",
    )


@app.get("/api/generations/{generation_id}")
async def get_generation(generation_id: str):
    """Get a single generation job's status and output."""
    item = generation_store.get(generation_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} not found.")
    return _normalize_generation_record(item)


class GenerationPatchRequest(BaseModel):
    scheduled: Optional[bool] = None


@app.patch("/api/generations/{generation_id}")
async def patch_generation(generation_id: str, payload: GenerationPatchRequest):
    """Update mutable fields on a generation (e.g. mark as scheduled)."""
    item = generation_store.get(generation_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} not found.")
    updates = {}
    if payload.scheduled is not None:
        updates["scheduled"] = payload.scheduled
    if not updates:
        return item
    updated = generation_store.update(generation_id, **updates)
    return updated


@app.post("/api/generations/{generation_id}/cancel")
async def cancel_generation(generation_id: str):
    """Cancel a generation that is queued or processing and signal its worker to stop."""
    item = generation_store.get(generation_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} not found.")
    status = item.get("status")
    if status in (GenerationStatus.COMPLETED, GenerationStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Generation is already {status}, cannot cancel.",
        )
    job_id = item.get("jobId")
    if job_id:
        job_manager.request_cancel(job_id, "Cancelled by user")
    generation_store.mark_failed(generation_id, "Cancelled by user")
    return {"generationId": generation_id, "status": "failed", "message": "Generation cancelled."}


@app.delete("/api/generations/{generation_id}")
async def delete_generation(generation_id: str):
    """Remove a finished generation from the Generation Center (completed or failed only)."""
    item = generation_store.get(generation_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} not found.")
    status = item.get("status")
    if status in (GenerationStatus.QUEUED, GenerationStatus.PROCESSING):
        raise HTTPException(
            status_code=400,
            detail="Cannot dismiss a running generation. Cancel it first, then dismiss.",
        )
    if status not in (GenerationStatus.COMPLETED, GenerationStatus.FAILED):
        raise HTTPException(status_code=400, detail=f"Cannot dismiss generation with status {status!r}.")
    generation_store.delete(generation_id)
    return {"generationId": generation_id, "dismissed": True}


# ---------------------------------------------------------------------------
# Hook Library Endpoints
# ---------------------------------------------------------------------------

def _refresh_hook_url(item: dict) -> dict:
    """Regenerate the signed URL for a stored hook if needed."""
    refreshed = dict(item)
    bucket = item.get("bucket")
    object_name = item.get("object")
    if bucket and object_name:
        try:
            from storage_gcs import GcsStorage
            gcs = GcsStorage()
            if bucket == gcs.bucket_name:
                refreshed["url"] = gcs.generate_read_url(object_name)
        except Exception:
            pass
    return refreshed


@app.get("/api/hooks")
async def list_hooks():
    """List saved hook videos for the remix studio."""
    items = hook_metadata_store.list_all()
    refreshed = [_refresh_hook_url(item) for item in items]
    return {"hooks": refreshed}


@app.get("/api/hooks/{hook_id}")
async def get_hook(hook_id: str):
    """Get metadata for a single hook video."""
    item = hook_metadata_store.get(hook_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Hook {hook_id} not found.")
    return _refresh_hook_url(item)


class HookLabelRequest(BaseModel):
    label: str = Field(max_length=200)


@app.post("/api/hooks/{hook_id}/label")
async def update_hook_label(hook_id: str, payload: HookLabelRequest):
    """Update a hook's user-assignable label."""
    item = hook_metadata_store.get(hook_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Hook {hook_id} not found.")
    updated = hook_metadata_store.update(hook_id, label=payload.label)
    return updated


@app.delete("/api/hooks/{hook_id}")
async def delete_hook(hook_id: str):
    """Delete a saved hook."""
    if not hook_metadata_store.delete(hook_id):
        raise HTTPException(status_code=404, detail=f"Hook {hook_id} not found.")
    return {"deleted": True, "hookId": hook_id}


# ---------------------------------------------------------------------------
# Sound Library Endpoints
# ---------------------------------------------------------------------------

def _refresh_sound_url(item: dict) -> dict:
    """Regenerate the signed URL for a stored sound if needed."""
    refreshed = dict(item)
    bucket = item.get("bucket")
    object_name = item.get("object")
    if bucket and object_name:
        try:
            from storage_gcs import GcsStorage
            gcs = GcsStorage()
            if bucket == gcs.bucket_name:
                refreshed["url"] = gcs.generate_read_url(object_name)
        except Exception:
            pass
    return refreshed


@app.get("/api/sounds")
async def list_sounds():
    """List saved sounds for the remix studio."""
    items = sound_metadata_store.list_all()
    refreshed = [_refresh_sound_url(item) for item in items]
    return {"sounds": refreshed}


@app.get("/api/sounds/{sound_id}")
async def get_sound(sound_id: str):
    """Get metadata for a single sound."""
    item = sound_metadata_store.get(sound_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Sound {sound_id} not found.")
    return _refresh_sound_url(item)


class SoundLabelRequest(BaseModel):
    label: str = Field(max_length=200)


@app.post("/api/sounds/{sound_id}/label")
async def update_sound_label(sound_id: str, payload: SoundLabelRequest):
    """Update a sound's user-assignable label."""
    item = sound_metadata_store.get(sound_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Sound {sound_id} not found.")
    updated = sound_metadata_store.update(sound_id, label=payload.label)
    return updated


# ---------------------------------------------------------------------------
# Remix Endpoints
# ---------------------------------------------------------------------------

REMIX_STEPS = [
    {"key": "download_hook", "label": "Download Hook Video"},
    {"key": "caption_overlay", "label": "Caption Overlay"},
    {"key": "video_concatenation", "label": "Video Concatenation"},
    {"key": "audio_replacement", "label": "Audio Replacement"},
]


def _run_remix_thread(
    generation_id: str,
    hook_id: str,
    output_dir: str,
    caption: Optional[str],
    sound_id: Optional[str],
    extension_video_path: Optional[str],
) -> None:
    """Background thread for the remix pipeline."""
    from remix_service import run_remix, RemixError

    generation_store.mark_processing(generation_id, current_step="download_hook")

    def cb(step_key: str, event: str, message: str = ""):
        if event == "progress":
            generation_store.update_step(generation_id, step_key, "running", message)
        else:
            step_status = {"start": "running", "complete": "completed", "fail": "failed"}.get(event, event)
            generation_store.update_step(generation_id, step_key, step_status, message)

    try:
        result = run_remix(
            hook_id=hook_id,
            output_dir=output_dir,
            caption=caption,
            sound_id=sound_id,
            extension_video_path=extension_video_path,
            on_step=cb,
        )

        # Upload final remix to GCS
        final_video = result.get("final_video", "")
        gcs_info = None
        if final_video and os.path.isfile(final_video):
            gcs_info = _upload_video_to_gcs(generation_id, final_video)

        video_url = (gcs_info or {}).get("url", "")

        # Also save to video metadata store so it appears in the video library
        if gcs_info:
            from datetime import datetime, timezone as _tz
            video_metadata_store.save(generation_id, {
                "videoId": generation_id,
                "url": video_url,
                "bucket": gcs_info.get("bucket", ""),
                "object": gcs_info.get("object", ""),
                "extended": bool(extension_video_path),
                "remix": True,
                "sourceHookId": hook_id,
                "createdAt": datetime.now(_tz.utc).isoformat(),
            })

        generation_store.mark_completed(generation_id, {
            "videoUrl": video_url,
            "resultPath": final_video,
            "videoGcs": gcs_info,
            "sourceHookId": hook_id,
        })
    except RemixError as exc:
        logger.exception(
            "remix pipeline FAILED generation_id=%s hook_id=%s error=%s",
            generation_id,
            hook_id,
            exc,
        )
        generation_store.mark_failed(generation_id, exc.message)
    except Exception as exc:
        logger.exception(
            "remix pipeline FAILED generation_id=%s hook_id=%s error=%s",
            generation_id,
            hook_id,
            exc,
        )
        generation_store.mark_failed(generation_id, str(exc))


@app.post("/api/remix")
async def create_remix(
    hookId: str = Form(..., description="ID of the hook video to remix"),
    caption: Optional[str] = Form(None, description="Caption text to overlay"),
    soundId: Optional[str] = Form(None, description="Sound ID to use (or __none__ to skip)"),
    extension_video: Optional[UploadFile] = File(None, description="Extension video to append"),
):
    """Start a remix job from a saved hook video."""
    # Validate hook exists
    hook = hook_metadata_store.get(hookId)
    if not hook:
        raise HTTPException(status_code=404, detail=f"Hook {hookId} not found.")

    # Validate sound exists if specified
    if soundId and soundId != "__none__":
        sound = sound_metadata_store.get(soundId)
        if not sound:
            raise HTTPException(status_code=404, detail=f"Sound {soundId} not found.")

    # Build step list based on what's requested
    steps = [{"key": "download_hook", "label": "Download Hook Video", "status": "pending", "message": ""}]
    if caption and caption.strip():
        steps.append({"key": "caption_overlay", "label": "Caption Overlay", "status": "pending", "message": ""})
    if extension_video and extension_video.filename:
        steps.append({"key": "video_concatenation", "label": "Video Concatenation", "status": "pending", "message": ""})
    resolved_sound = soundId or hook.get("originalSoundId")
    if resolved_sound and soundId != "__none__":
        steps.append({"key": "audio_replacement", "label": "Audio Replacement", "status": "pending", "message": ""})

    gen = generation_store.create(
        gen_type="remix",
        label=f"Remix of {hookId}",
        steps=steps,
    )
    gen_id = gen["generationId"]

    # Save extension video to disk if provided
    remix_dir = os.path.join(JOBS_DIR, gen_id)
    input_dir = os.path.join(remix_dir, "input")
    output_dir = os.path.join(remix_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    ext_video_path: Optional[str] = None
    if extension_video and extension_video.filename:
        ext_ext = os.path.splitext(extension_video.filename or "ext.mp4")[1] or ".mp4"
        ext_video_path = os.path.join(input_dir, f"extension_video{ext_ext}")
        _save_upload(extension_video, ext_video_path)

    thread = threading.Thread(
        target=_run_remix_thread,
        args=(gen_id, hookId, output_dir, caption, soundId, ext_video_path),
        daemon=True,
    )
    thread.start()

    return {"generationId": gen_id}


# ---------------------------------------------------------------------------
# Model Library Endpoints
# ---------------------------------------------------------------------------

def _refresh_model_url(item: dict) -> dict:
    """Regenerate the signed URL for a stored model image if needed."""
    refreshed = dict(item)
    bucket = item.get("bucket")
    object_name = item.get("object")
    if bucket and object_name:
        try:
            from storage_gcs import GcsStorage
            gcs = GcsStorage()
            if bucket == gcs.bucket_name:
                refreshed["url"] = gcs.generate_read_url(object_name)
        except Exception:
            pass
    elif item.get("localPath"):
        model_id = item.get("modelId")
        if model_id:
            refreshed["url"] = f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/models/{model_id}/image"
    return refreshed


@app.get("/api/models")
async def list_models():
    """List saved model / identity images."""
    items = model_metadata_store.list_all()
    refreshed = [_refresh_model_url(item) for item in items]
    return {"models": refreshed}


@app.get("/api/models/{model_id}/image")
async def get_model_image(model_id: str):
    """Serve a locally stored model image."""
    item = model_metadata_store.get(model_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")

    local_path = item.get("localPath", "")
    if not local_path or not os.path.isfile(local_path):
        raise HTTPException(status_code=404, detail=f"Model image {model_id} not found.")

    import mimetypes

    media_type, _ = mimetypes.guess_type(local_path)
    return FileResponse(
        local_path,
        media_type=media_type or "application/octet-stream",
        filename=item.get("filename") or os.path.basename(local_path),
    )


@app.post("/api/models")
async def upload_model(
    image: UploadFile = File(..., description="Model / identity image to save"),
    label: str = Form("", description="Optional label for the model"),
):
    """Upload and save a model image for reuse."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    import uuid
    from datetime import datetime, timezone as _tz

    model_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(image.filename or "model.png")[1] or ".png"

    # Save to a temp location, upload to GCS
    tmp_dir = os.path.join(JOBS_DIR, f"_model_{model_id}")
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, f"model{ext}")
    _save_upload(image, local_path)

    gcs_info: Optional[dict] = None
    try:
        from storage_gcs import GcsStorage
        gcs = GcsStorage()
        object_name = f"{GCS_MODELS_OBJECT_PREFIX.strip('/')}/{model_id}/model{ext}"
        gcs_info = gcs.upload_file_public(local_path, object_name)
    except Exception as exc:
        logger.warning("GCS model upload failed; using local model storage: %s", exc)

    now_iso = datetime.now(_tz.utc).isoformat()
    record = {
        "modelId": model_id,
        "url": (
            gcs_info.get("url", "")
            if gcs_info
            else f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/models/{model_id}/image"
        ),
        "bucket": gcs_info.get("bucket", "") if gcs_info else "",
        "object": gcs_info.get("object", "") if gcs_info else "",
        "localPath": local_path,
        "storage": "gcs" if gcs_info else "local",
        "label": label.strip() if label else "",
        "filename": image.filename or "",
        "createdAt": now_iso,
    }
    model_metadata_store.save(model_id, record)
    return _refresh_model_url(record)


class ModelLabelRequest(BaseModel):
    label: str = Field(max_length=200)


@app.post("/api/models/{model_id}/label")
async def update_model_label(model_id: str, payload: ModelLabelRequest):
    """Update a model's label."""
    item = model_metadata_store.get(model_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")
    updated = model_metadata_store.update(model_id, label=payload.label)
    return _refresh_model_url(updated)


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    """Delete a saved model."""
    if not model_metadata_store.delete(model_id):
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")
    return {"deleted": True, "modelId": model_id}


# ---------------------------------------------------------------------------
# Extension Video Library Endpoints
# ---------------------------------------------------------------------------

def _refresh_extension_video_url(item: dict) -> dict:
    """Regenerate the signed URL for a stored extension video if needed."""
    refreshed = dict(item)
    bucket = item.get("bucket")
    object_name = item.get("object")
    if bucket and object_name:
        try:
            from storage_gcs import GcsStorage
            gcs = GcsStorage()
            if bucket == gcs.bucket_name:
                refreshed["url"] = gcs.generate_read_url(object_name)
        except Exception:
            ext_id = item.get("extensionVideoId")
            if ext_id and item.get("localPath"):
                refreshed["url"] = f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/extension-videos/{ext_id}/video"
    elif item.get("localPath"):
        ext_id = item.get("extensionVideoId")
        if ext_id:
            refreshed["url"] = f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/extension-videos/{ext_id}/video"
    return refreshed


@app.get("/api/extension-videos")
async def list_extension_videos():
    """List saved extension videos."""
    items = extension_video_metadata_store.list_all()
    refreshed = [_refresh_extension_video_url(item) for item in items]
    return {"extensionVideos": refreshed}


@app.get("/api/extension-videos/{ext_id}/video")
async def get_extension_video(ext_id: str):
    """Serve a locally stored extension video."""
    item = extension_video_metadata_store.get(ext_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Extension video {ext_id} not found.")

    local_path = item.get("localPath", "")
    if not local_path or not os.path.isfile(local_path):
        raise HTTPException(status_code=404, detail=f"Extension video {ext_id} not found.")

    import mimetypes

    media_type, _ = mimetypes.guess_type(local_path)
    return FileResponse(
        local_path,
        media_type=media_type or "video/mp4",
        filename=item.get("filename") or os.path.basename(local_path),
    )


@app.post("/api/extension-videos")
async def upload_extension_video(
    video: UploadFile = File(..., description="Extension video to save"),
    label: str = Form("", description="Optional label"),
):
    """Upload and save an extension video for reuse."""
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video.")

    import uuid
    from datetime import datetime, timezone as _tz

    ext_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(video.filename or "extension.mp4")[1] or ".mp4"

    tmp_dir = os.path.join(JOBS_DIR, f"_ext_{ext_id}")
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, f"extension{ext}")
    _save_upload(video, local_path)

    gcs_info: Optional[dict] = None
    try:
        from storage_gcs import GcsStorage
        gcs = GcsStorage()
        object_name = f"{GCS_EXTENSION_VIDEOS_OBJECT_PREFIX.strip('/')}/{ext_id}/extension{ext}"
        gcs_info = gcs.upload_file_public(local_path, object_name)
    except Exception as exc:
        logger.warning("GCS extension video upload failed; using local storage: %s", exc)

    now_iso = datetime.now(_tz.utc).isoformat()
    record = {
        "extensionVideoId": ext_id,
        "url": (
            gcs_info.get("url", "")
            if gcs_info
            else f"{PUBLIC_BACKEND_BASE_URL.rstrip('/')}/api/extension-videos/{ext_id}/video"
        ),
        "bucket": gcs_info.get("bucket", "") if gcs_info else "",
        "object": gcs_info.get("object", "") if gcs_info else "",
        "localPath": local_path,
        "storage": "gcs" if gcs_info else "local",
        "label": label.strip() if label else "",
        "filename": video.filename or "",
        "createdAt": now_iso,
    }
    extension_video_metadata_store.save(ext_id, record)
    return _refresh_extension_video_url(record)


class ExtensionVideoLabelRequest(BaseModel):
    label: str = Field(max_length=200)


@app.post("/api/extension-videos/{ext_id}/label")
async def update_extension_video_label(ext_id: str, payload: ExtensionVideoLabelRequest):
    """Update an extension video's label."""
    item = extension_video_metadata_store.get(ext_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Extension video {ext_id} not found.")
    updated = extension_video_metadata_store.update(ext_id, label=payload.label)
    return _refresh_extension_video_url(updated)


@app.delete("/api/extension-videos/{ext_id}")
async def delete_extension_video(ext_id: str):
    """Delete a saved extension video."""
    if not extension_video_metadata_store.delete(ext_id):
        raise HTTPException(status_code=404, detail=f"Extension video {ext_id} not found.")
    return {"deleted": True, "extensionVideoId": ext_id}
