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
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query
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
from video_metadata_store import video_metadata_store
from generation_store import generation_store, GenerationStatus
from hook_metadata_store import hook_metadata_store
from sound_metadata_store import sound_metadata_store
from model_metadata_store import model_metadata_store
from extension_video_metadata_store import extension_video_metadata_store
from config import (
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
        "video pipeline thread started job_id=%s generation_id=%s video=%s image=%s extended=%s",
        job_id,
        generation_id or "-",
        os.path.basename(video_path),
        os.path.basename(image_path),
        extended,
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/generate")
async def generate(
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
        args=(job.id, video_path, image_path, output_dir, extended, additional_video_path),
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


# ---------------------------------------------------------------------------
# Generation Center Endpoints
# ---------------------------------------------------------------------------

from job_manager import PIPELINE_STEPS as _PIPELINE_STEPS, EXTENDED_PIPELINE_STEPS as _EXTENDED_PIPELINE_STEPS


@app.post("/api/generations/video")
async def generation_create_video(
    image: Optional[UploadFile] = File(None, description="Model / identity reference image"),
    video: UploadFile = File(..., description="Reference video"),
    extended: bool = Form(False),
    additional_video: Optional[UploadFile] = File(None),
    modelId: Optional[str] = Form(None, description="Saved model ID (alternative to image upload)"),
    extensionVideoId: Optional[str] = Form(None, description="Saved extension video ID (alternative to additional_video upload)"),
):
    """Start a video generation job tracked in the Generation Center."""
    import requests as _requests

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
        label=video.filename or "Video generation",
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
        args=(job.id, video_path, image_path, output_dir, extended, additional_video_path, gen_id),
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


@app.get("/api/generations")
async def list_generations(limit: int = Query(50, ge=1, le=200)):
    """List generation jobs for the Generation Center panel."""
    items = generation_store.list_all(limit=limit)
    return {"generations": items}


@app.get("/api/generations/{generation_id}")
async def get_generation(generation_id: str):
    """Get a single generation job's status and output."""
    item = generation_store.get(generation_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} not found.")
    return item


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
    return refreshed


@app.get("/api/models")
async def list_models():
    """List saved model / identity images."""
    items = model_metadata_store.list_all()
    refreshed = [_refresh_model_url(item) for item in items]
    return {"models": refreshed}


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

    try:
        from storage_gcs import GcsStorage
        gcs = GcsStorage()
        object_name = f"{GCS_MODELS_OBJECT_PREFIX.strip('/')}/{model_id}/model{ext}"
        gcs_info = gcs.upload_file_public(local_path, object_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GCS upload failed: {exc}") from exc

    now_iso = datetime.now(_tz.utc).isoformat()
    record = {
        "modelId": model_id,
        "url": gcs_info.get("url", ""),
        "bucket": gcs_info.get("bucket", ""),
        "object": gcs_info.get("object", ""),
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
            pass
    return refreshed


@app.get("/api/extension-videos")
async def list_extension_videos():
    """List saved extension videos."""
    items = extension_video_metadata_store.list_all()
    refreshed = [_refresh_extension_video_url(item) for item in items]
    return {"extensionVideos": refreshed}


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

    try:
        from storage_gcs import GcsStorage
        gcs = GcsStorage()
        object_name = f"{GCS_EXTENSION_VIDEOS_OBJECT_PREFIX.strip('/')}/{ext_id}/extension{ext}"
        gcs_info = gcs.upload_file_public(local_path, object_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GCS upload failed: {exc}") from exc

    now_iso = datetime.now(_tz.utc).isoformat()
    record = {
        "extensionVideoId": ext_id,
        "url": gcs_info.get("url", ""),
        "bucket": gcs_info.get("bucket", ""),
        "object": gcs_info.get("object", ""),
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
