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
from late_service import late_service, LateServiceError
from carousel_service import carousel_service, CarouselServiceError
from video_metadata_store import video_metadata_store
from generation_store import generation_store, GenerationStatus
from config import GCS_VIDEO_OBJECT_PREFIX

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
    job_manager.mark_processing(job_id)
    if generation_id:
        generation_store.mark_processing(generation_id, current_step="pipeline")

    # Build a callback that updates both the legacy job_manager AND generation_store
    jm_cb = job_manager.make_step_callback(job_id)

    def cb(step_key: str, event: str, message: str = ""):
        jm_cb(step_key, event, message)
        if generation_id:
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
        )

        # Attempt to upload final video to GCS for stable public URL.
        gcs_info = _upload_video_to_gcs(job_id, result["final_video"])
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

        # Update generation store with completed output
        if generation_id:
            video_url = (gcs_info or {}).get("url", "") if gcs_info else ""
            generation_store.mark_completed(generation_id, {
                "jobId": job_id,
                "videoUrl": video_url,
                "resultPath": result.get("final_video", ""),
                "videoGcs": gcs_info,
            })
    except Exception as exc:
        job_manager.mark_failed(job_id, str(exc))
        if generation_id:
            generation_store.mark_failed(generation_id, str(exc))


def _run_carousel_thread(generation_id: str, prompt: str, timezone_name: str) -> None:
    """Background thread that generates a carousel and updates the generation store."""
    generation_store.mark_processing(generation_id, current_step="generating")
    generation_store.update_step(generation_id, "generating", "running", "Generating carousel slides...")

    try:
        result = carousel_service.create_carousel(
            prompt=prompt,
            timezone_name=timezone_name,
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
    logger.info("Carousel create requested timezone=%s", payload.timezone)
    try:
        return carousel_service.create_carousel(
            prompt=payload.prompt,
            timezone_name=payload.timezone,
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
async def list_videos():
    """List previously generated videos that were uploaded to GCS."""
    items = video_metadata_store.list_all()
    refreshed = [_refresh_video_url(item) for item in items]
    return {"videos": refreshed}


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
    image: UploadFile = File(..., description="Model / identity reference image"),
    video: UploadFile = File(..., description="Reference video"),
    extended: bool = Form(False),
    additional_video: Optional[UploadFile] = File(None),
):
    """Start a video generation job tracked in the Generation Center."""
    # Validation (same as /api/generate)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="image must be an image file")
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="video must be a video file")
    if extended:
        if additional_video is None or not additional_video.filename:
            raise HTTPException(status_code=400, detail="additional_video is required when extended=True")

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

    image_ext = os.path.splitext(image.filename or "image.png")[1] or ".png"
    video_ext = os.path.splitext(video.filename or "video.mp4")[1] or ".mp4"
    image_path = os.path.join(input_dir, f"model_image{image_ext}")
    video_path = os.path.join(input_dir, f"reference_video{video_ext}")
    _save_upload(image, image_path)
    _save_upload(video, video_path)

    additional_video_path: Optional[str] = None
    if extended and additional_video is not None:
        add_ext = os.path.splitext(additional_video.filename or "additional.mp4")[1] or ".mp4"
        additional_video_path = os.path.join(input_dir, f"additional_video{add_ext}")
        _save_upload(additional_video, additional_video_path)

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
        args=(gen_id, payload.prompt, payload.timezone),
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
