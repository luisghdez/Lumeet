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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_upload(upload: UploadFile, dest: str) -> None:
    """Save an UploadFile to disk."""
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)


def _run_pipeline_thread(
    job_id: str, video_path: str, image_path: str, output_dir: str, extended: bool = False
) -> None:
    """Target for the background thread that runs the pipeline."""
    job_manager.mark_processing(job_id)
    cb = job_manager.make_step_callback(job_id)

    try:
        result = run_full_pipeline(
            video_path=video_path,
            model_image_path=image_path,
            output_dir=output_dir,
            on_step=cb,
            extended=extended,
        )
        job_manager.mark_completed(job_id, result["final_video"], result)
    except Exception as exc:
        job_manager.mark_failed(job_id, str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/generate")
async def generate(
    image: UploadFile = File(..., description="Model / identity reference image"),
    video: UploadFile = File(..., description="Reference video"),
    extended: bool = Form(False, description="Enable extended pipeline (concatenate additional video and replace audio)"),
):
    """
    Start a new video generation pipeline job.

    Accepts multipart form data with:
      - ``image``: the model/identity reference image (PNG/JPG)
      - ``video``: the reference video (MP4)
      - ``extended``: optional boolean to enable extended pipeline (default: False)

    Returns the ``job_id`` which can be used to poll progress and
    download the result.
    """
    # Basic validation
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="image must be an image file (PNG, JPG, etc.)")
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="video must be a video file (MP4, etc.)")

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

    # Update job with real paths
    job.video_path = video_path
    job.image_path = image_path
    job.output_dir = output_dir

    # Launch pipeline in background thread
    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(job.id, video_path, image_path, output_dir, extended),
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


@app.post("/api/late/posts")
async def create_late_post(payload: LateCreatePostRequest):
    """Create/schedule a social post via Late."""
    logger.info(
        "Late post create requested session=%s targets=%d includeResultVideo=%s",
        payload.sessionId,
        len(payload.platforms),
        payload.includeResultVideo,
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
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return result
