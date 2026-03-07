"""
Job Manager
===========
Thread-safe in-memory job store for tracking pipeline runs.

Each job moves through: queued -> processing -> completed | failed
Individual pipeline steps are tracked for progress reporting.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


PIPELINE_STEPS = [
    {"key": "scene_detection", "label": "Scene Detection"},
    {"key": "frame_extraction", "label": "Frame Extraction"},
    {"key": "caption_detection", "label": "Caption Detection"},
    {"key": "scene_recreation", "label": "Scene Recreation"},
    {"key": "motion_control", "label": "Motion Control (Kling AI)"},
    {"key": "caption_overlay", "label": "Caption Overlay"},
]

EXTENDED_PIPELINE_STEPS = [
    {"key": "audio_extraction", "label": "Audio Extraction"},
    {"key": "video_concatenation", "label": "Video Concatenation"},
    {"key": "audio_replacement", "label": "Audio Replacement"},
]


@dataclass
class StepInfo:
    key: str
    label: str
    status: StepStatus = StepStatus.PENDING
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status.value,
            "message": self.message,
        }


@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.QUEUED
    current_step: Optional[str] = None
    steps: list[StepInfo] = field(default_factory=list)
    result_path: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    # Paths to uploaded files (set by the API layer)
    video_path: Optional[str] = None
    image_path: Optional[str] = None
    output_dir: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "current_step": self.current_step,
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class JobManager:
    """Thread-safe in-memory job store."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        video_path: str,
        image_path: str,
        output_dir: str,
        extended: bool = False,
    ) -> Job:
        """
        Create a new job with pending steps.
        
        Args:
            video_path: Path to input video.
            image_path: Path to model image.
            output_dir: Output directory.
            extended: If True, include extended pipeline steps.
        """
        job_id = uuid.uuid4().hex[:12]
        steps = [StepInfo(key=s["key"], label=s["label"]) for s in PIPELINE_STEPS]
        
        # Add extended steps if enabled
        if extended:
            extended_steps = [
                StepInfo(key=s["key"], label=s["label"]) for s in EXTENDED_PIPELINE_STEPS
            ]
            steps.extend(extended_steps)
        
        job = Job(
            id=job_id,
            steps=steps,
            video_path=video_path,
            image_path=image_path,
            output_dir=output_dir,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def _find_step(self, job: Job, step_key: str) -> Optional[StepInfo]:
        for s in job.steps:
            if s.key == step_key:
                return s
        return None

    # -- Callbacks used by the pipeline runner --

    def mark_processing(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = JobStatus.PROCESSING

    def step_start(self, job_id: str, step_key: str, message: str = "") -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.current_step = step_key
            step = self._find_step(job, step_key)
            if step:
                step.status = StepStatus.RUNNING
                step.message = message or f"Running {step.label}..."

    def step_complete(self, job_id: str, step_key: str, message: str = "") -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            step = self._find_step(job, step_key)
            if step:
                step.status = StepStatus.COMPLETED
                step.message = message or "Done"

    def step_fail(self, job_id: str, step_key: str, message: str = "") -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            step = self._find_step(job, step_key)
            if step:
                step.status = StepStatus.FAILED
                step.message = message

    def mark_completed(self, job_id: str, result_path: str, result: dict) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = JobStatus.COMPLETED
                job.result_path = result_path
                job.result = result
                job.completed_at = time.time()

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error = error
                job.completed_at = time.time()

    def make_step_callback(self, job_id: str) -> Callable:
        """
        Return a callback function for the pipeline to report step progress.

        The callback signature: callback(step_key, event, message)
        where event is 'start', 'complete', or 'fail'.
        """
        def callback(step_key: str, event: str, message: str = ""):
            if event == "start":
                self.step_start(job_id, step_key, message)
            elif event == "complete":
                self.step_complete(job_id, step_key, message)
            elif event == "fail":
                self.step_fail(job_id, step_key, message)

        return callback


# Singleton instance
job_manager = JobManager()
