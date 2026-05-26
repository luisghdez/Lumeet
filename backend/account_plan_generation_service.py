"""
Controlled generation queue for StudyTok account plans.
"""

from __future__ import annotations

import os
import shutil
import threading
import uuid
from typing import Any, Dict, List, Optional

import requests

from account_plan_store import account_plan_store
from config import GCS_VIDEO_OBJECT_PREFIX
from generation_store import generation_store
from job_manager import EXTENDED_PIPELINE_STEPS, PIPELINE_STEPS, job_manager
from late_service import LateServiceError, late_service
from model_metadata_store import model_metadata_store
from extension_video_metadata_store import extension_video_metadata_store
from organizer_store import organizer_store
from pipeline import run_full_pipeline
from video_analysis_service import _download_video


JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")
_active_plans = set()
_active_lock = threading.Lock()


class AccountPlanGenerationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def start_plan_generation(
    plan_id: str,
    dry_run: bool = False,
    limit: int = 0,
    model_id: Optional[str] = None,
    extension_video_id: Optional[str] = None,
) -> Dict[str, Any]:
    plan = account_plan_store.get(plan_id)
    if not plan:
        raise AccountPlanGenerationError(f"Plan {plan_id} not found.", 404)
    if plan.get("status") not in {"approved", "generating", "generation_dry_run"}:
        raise AccountPlanGenerationError("Approve the plan before starting generation.", 400)

    posts = [
        post for post in (plan.get("plannedPosts") or [])
        if isinstance(post, dict) and post.get("videoReferenceId") and post.get("status") in {"planned", "queued", "failed"}
    ]
    if limit:
        posts = posts[:max(0, int(limit))]
    if not posts:
        raise AccountPlanGenerationError("No planned posts with source videos are available to generate.", 400)

    if dry_run:
        for post in posts:
            account_plan_store.update_post(plan_id, post["slot"], status="queued", error="")
        return account_plan_store.update(plan_id, status="generation_dry_run") or plan

    model = _select_model(model_id)
    selected_model_id = model.get("modelId", "")
    needs_extension = any((post.get("purpose") or "relatable") == "hook_demo" for post in posts)
    extension_video = _select_extension_video(extension_video_id) if needs_extension else None
    if needs_extension and not extension_video:
        raise AccountPlanGenerationError("No default demo/extension video is available for hook + demo posts.", 400)
    selected_extension_video_id = (extension_video or {}).get("extensionVideoId", "")

    with _active_lock:
        if plan_id in _active_plans:
            raise AccountPlanGenerationError("This plan is already generating.", 409)
        _active_plans.add(plan_id)

    try:
        bulk_run_id = f"planrun_{uuid.uuid4().hex[:12]}"
        account_plan_store.update(plan_id, status="generating", activeBulkRunId=bulk_run_id)
        slots = []
        for post in posts:
            _precreate_post_generation(
                plan_id=plan_id,
                post=post,
                model_id=selected_model_id,
                extension_video_id=selected_extension_video_id,
                bulk_run_id=bulk_run_id,
            )
            slots.append(post.get("slot"))

        thread = threading.Thread(
            target=_run_plan_queue,
            args=(plan_id, slots, selected_model_id, selected_extension_video_id, bulk_run_id),
            daemon=True,
        )
        thread.start()
    except Exception:
        with _active_lock:
            _active_plans.discard(plan_id)
        raise
    return account_plan_store.get(plan_id) or plan


def _run_plan_queue(
    plan_id: str,
    slots: list,
    model_id: Optional[str] = None,
    extension_video_id: Optional[str] = None,
    bulk_run_id: str = "",
) -> None:
    try:
        for slot in slots:
            plan = account_plan_store.get(plan_id)
            if not plan:
                return
            post = next(
                (item for item in plan.get("plannedPosts", []) if isinstance(item, dict) and item.get("slot") == slot),
                None,
            )
            if not post:
                continue
            try:
                _generate_post(
                    plan_id,
                    post,
                    model_id=model_id,
                    extension_video_id=extension_video_id,
                    generation_id=post.get("generationId", ""),
                    bulk_run_id=bulk_run_id,
                )
            except Exception as exc:
                gen_id = (post or {}).get("generationId", "")
                if gen_id:
                    generation_store.mark_failed(gen_id, str(exc))
                account_plan_store.update_post(plan_id, slot, status="failed", error=str(exc))
        _finish_plan(plan_id)
    finally:
        with _active_lock:
            _active_plans.discard(plan_id)


def _finish_plan(plan_id: str) -> None:
    plan = account_plan_store.get(plan_id)
    if not plan:
        return
    posts = [post for post in plan.get("plannedPosts", []) if isinstance(post, dict)]
    if any(post.get("status") == "generating" for post in posts):
        return
    if any(post.get("status") == "failed" for post in posts):
        account_plan_store.update(plan_id, status="generation_failed")
    else:
        account_plan_store.update(plan_id, status="generated")


def _generate_post(
    plan_id: str,
    post: Dict[str, Any],
    model_id: Optional[str] = None,
    extension_video_id: Optional[str] = None,
    generation_id: str = "",
    bulk_run_id: str = "",
) -> None:
    slot = int(post.get("slot") or 0)
    purpose = post.get("purpose") or "relatable"
    extended = purpose == "hook_demo"
    account_plan_store.update_post(plan_id, slot, status="generating", error="")

    video_ref = organizer_store.get_video_reference(post.get("videoReferenceId", ""))
    if not video_ref:
        raise AccountPlanGenerationError(f"Video reference {post.get('videoReferenceId')} not found.", 404)

    model = _select_model(model_id)
    extension_video = _select_extension_video(extension_video_id) if extended else None
    if extended and not extension_video:
        raise AccountPlanGenerationError("No default demo/extension video is available for hook + demo posts.", 400)

    gen_id = generation_id or _create_generation_record(
        plan_id=plan_id,
        slot=slot,
        purpose=purpose,
        extended=extended,
        model_id=model.get("modelId", ""),
        extension_video_id=(extension_video or {}).get("extensionVideoId", ""),
        bulk_run_id=bulk_run_id,
    )

    job = job_manager.create_job("", "", "", extended=extended)
    job_dir = os.path.join(JOBS_DIR, job.id)
    input_dir = os.path.join(job_dir, "input")
    output_dir = os.path.join(job_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    generation_store.update(
        gen_id,
        jobId=job.id,
        plannerPlanId=plan_id,
        plannerSlot=slot,
        bulkRunId=bulk_run_id,
        modelId=model.get("modelId", ""),
        extensionVideoId=(extension_video or {}).get("extensionVideoId", ""),
    )
    account_plan_store.update_post(
        plan_id,
        slot,
        status="generating",
        generationId=gen_id,
        jobId=job.id,
        bulkRunId=bulk_run_id,
        modelId=model.get("modelId", ""),
        extensionVideoId=(extension_video or {}).get("extensionVideoId", ""),
    )

    model_path = _materialize_model(model, input_dir)
    source_path = os.path.join(input_dir, "reference_video")
    source_download = _download_video(video_ref, source_path)
    source_path = source_download.get("path") or source_path
    extension_path = _materialize_extension_video(extension_video, input_dir) if extension_video else None

    job.video_path = source_path
    job.image_path = model_path
    job.output_dir = output_dir
    job_manager.mark_processing(job.id)
    generation_store.mark_processing(gen_id, current_step="scene_detection")

    def callback(step_key: str, event: str, message: str = ""):
        job_manager.make_step_callback(job.id)(step_key, event, message)
        status = {"start": "running", "complete": "completed", "fail": "failed", "progress": "running"}.get(event, event)
        generation_store.update_step(gen_id, step_key, status, message)

    result = run_full_pipeline(
        video_path=source_path,
        model_image_path=model_path,
        output_dir=output_dir,
        extended=extended,
        additional_video_path=extension_path,
        skip_scene_detection=False,
        on_step=callback,
        cancel_check=lambda: job_manager.is_cancel_requested(job.id),
    )
    final_video = result.get("final_video", "")
    gcs_info = _upload_video_to_gcs(job.id, final_video)
    media_url = (gcs_info or {}).get("url", "")
    output = {
        "jobId": job.id,
        "videoUrl": media_url,
        "videoGcs": gcs_info,
        "resultPath": final_video,
        "plannerPlanId": plan_id,
        "plannerSlot": slot,
        "bulkRunId": bulk_run_id,
        "modelId": model.get("modelId", ""),
        "extensionVideoId": (extension_video or {}).get("extensionVideoId", ""),
    }
    job.video_gcs = gcs_info
    job_manager.mark_completed(job.id, final_video, result)
    generation_store.mark_completed(gen_id, output)
    account_plan_store.update_post(
        plan_id,
        slot,
        status="generated",
        generatedMediaUrl=media_url,
        generationId=gen_id,
        jobId=job.id,
        bulkRunId=bulk_run_id,
        modelId=model.get("modelId", ""),
        extensionVideoId=(extension_video or {}).get("extensionVideoId", ""),
        error="",
    )


def schedule_generated_plan_posts(
    plan_id: str,
    *,
    session_id: str,
    platforms: List[Dict[str, str]],
    profile_id: Optional[str] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    plan = account_plan_store.get(plan_id)
    if not plan:
        raise AccountPlanGenerationError(f"Plan {plan_id} not found.", 404)
    if not platforms:
        raise AccountPlanGenerationError("Select at least one connected account before scheduling.", 400)

    posts = [
        post for post in (plan.get("plannedPosts") or [])
        if isinstance(post, dict)
        and (post.get("status") == "generated" or post.get("generatedMediaUrl"))
        and post.get("reviewStatus") != "scheduled"
    ]
    if not posts:
        raise AccountPlanGenerationError("No generated unscheduled posts are ready to schedule.", 400)

    results = []
    for post in posts:
        slot = int(post.get("slot") or 0)
        try:
            response = late_service.create_post(
                session_id=session_id,
                content=post.get("captionDraft") or "Generated with nflncr.ai",
                platforms=platforms,
                profile_id=profile_id,
                scheduled_for=post.get("suggestedScheduledFor"),
                publish_now=False,
                timezone=post.get("timezone") or timezone or "UTC",
                media_urls=[post.get("generatedMediaUrl")] if post.get("generatedMediaUrl") else [],
                include_result_video=bool(post.get("jobId")),
                job_id=post.get("jobId") or None,
            )
            late_post_id = (
                (response.get("post") or {}).get("_id")
                or response.get("_id")
                or response.get("id")
                or "created"
            )
            account_plan_store.update_post(
                plan_id,
                slot,
                reviewStatus="scheduled",
                status="scheduled",
                latePostId=late_post_id,
                scheduleError="",
            )
            if post.get("generationId"):
                generation_store.update(post["generationId"], scheduled=True)
            results.append({"slot": slot, "ok": True, "latePostId": late_post_id})
        except LateServiceError as exc:
            account_plan_store.update_post(plan_id, slot, scheduleError=exc.message)
            results.append({"slot": slot, "ok": False, "error": exc.message})
        except Exception as exc:
            account_plan_store.update_post(plan_id, slot, scheduleError=str(exc))
            results.append({"slot": slot, "ok": False, "error": str(exc)})

    updated = account_plan_store.get(plan_id) or plan
    return {
        "plan": updated,
        "attempted": len(results),
        "scheduled": sum(1 for result in results if result.get("ok")),
        "results": results,
    }


def _precreate_post_generation(
    *,
    plan_id: str,
    post: Dict[str, Any],
    model_id: str,
    extension_video_id: str,
    bulk_run_id: str,
) -> str:
    slot = int(post.get("slot") or 0)
    purpose = post.get("purpose") or "relatable"
    extended = purpose == "hook_demo"
    gen_id = _create_generation_record(
        plan_id=plan_id,
        slot=slot,
        purpose=purpose,
        extended=extended,
        model_id=model_id,
        extension_video_id=extension_video_id if extended else "",
        bulk_run_id=bulk_run_id,
    )
    account_plan_store.update_post(
        plan_id,
        slot,
        status="queued",
        generationId=gen_id,
        jobId="",
        bulkRunId=bulk_run_id,
        modelId=model_id,
        extensionVideoId=extension_video_id if extended else "",
        generatedMediaUrl="",
        latePostId="",
        error="",
        scheduleError="",
    )
    return gen_id


def _create_generation_record(
    *,
    plan_id: str,
    slot: int,
    purpose: str,
    extended: bool,
    model_id: str,
    extension_video_id: str,
    bulk_run_id: str,
) -> str:
    generation = generation_store.create(
        gen_type="video",
        label=f"StudyTok slot {slot}: {purpose}",
        steps=_step_records(extended),
    )
    gen_id = generation["generationId"]
    generation_store.update(
        gen_id,
        plannerPlanId=plan_id,
        plannerSlot=slot,
        bulkRunId=bulk_run_id,
        modelId=model_id,
        extensionVideoId=extension_video_id,
    )
    return gen_id


def _step_records(extended: bool) -> List[Dict[str, str]]:
    steps = list(PIPELINE_STEPS) + (list(EXTENDED_PIPELINE_STEPS) if extended else [])
    return [
        {"key": step["key"], "label": step["label"], "status": "pending", "message": ""}
        for step in steps
    ]


def _select_model(model_id: Optional[str] = None) -> Dict[str, Any]:
    requested_id = (model_id or "").strip()
    if requested_id:
        model = model_metadata_store.get(requested_id)
        if not model:
            raise AccountPlanGenerationError(f"Model {requested_id} not found.", 404)
        return model
    return _default_model()


def _default_model() -> Dict[str, Any]:
    models = model_metadata_store.list_all()
    if not models:
        raise AccountPlanGenerationError("No saved account model is available. Create or upload a model first.", 400)
    return models[0]


def _select_extension_video(extension_video_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    requested_id = (extension_video_id or "").strip()
    if requested_id:
        video = extension_video_metadata_store.get(requested_id)
        if not video:
            raise AccountPlanGenerationError(f"Extension video {requested_id} not found.", 404)
        return video
    return _default_extension_video()


def _default_extension_video() -> Optional[Dict[str, Any]]:
    videos = extension_video_metadata_store.list_all()
    return videos[0] if videos else None


def _materialize_model(model: Dict[str, Any], input_dir: str) -> str:
    local_path = model.get("localPath") or ""
    ext = os.path.splitext(local_path or model.get("object") or ".png")[1] or ".png"
    dest = os.path.join(input_dir, f"model_image{ext}")
    if local_path and os.path.isfile(local_path):
        shutil.copyfile(local_path, dest)
        return dest
    url = model.get("url") or ""
    if not url:
        raise AccountPlanGenerationError(f"Model {model.get('modelId', '')} has no downloadable URL.", 500)
    _download_url(url, dest, timeout=120)
    return dest


def _materialize_extension_video(video: Dict[str, Any], input_dir: str) -> str:
    local_path = video.get("localPath") or ""
    ext = os.path.splitext(local_path or video.get("object") or ".mp4")[1] or ".mp4"
    dest = os.path.join(input_dir, f"additional_video{ext}")
    if local_path and os.path.isfile(local_path):
        shutil.copyfile(local_path, dest)
        return dest
    url = video.get("url") or ""
    if not url:
        raise AccountPlanGenerationError(f"Extension video {video.get('extensionVideoId', '')} has no downloadable URL.", 500)
    _download_url(url, dest, timeout=300)
    return dest


def _download_url(url: str, dest: str, timeout: int = 120) -> None:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


def _upload_video_to_gcs(job_id: str, local_video_path: str) -> Optional[dict]:
    if not local_video_path or not os.path.isfile(local_video_path):
        return None
    try:
        from storage_gcs import GcsStorage

        gcs = GcsStorage()
        ext = os.path.splitext(local_video_path)[1] or ".mp4"
        object_name = f"{GCS_VIDEO_OBJECT_PREFIX.strip('/')}/{job_id}/final_output{ext}"
        return gcs.upload_file_public(local_video_path, object_name)
    except Exception:
        return None
