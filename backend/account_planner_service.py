"""Deterministic account planner for StudyTok scheduling workflows."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from account_plan_store import account_plan_store
from organizer_store import organizer_store


ARCHETYPES = [
    {
        "id": "studytok",
        "label": "StudyTok",
        "description": "Study tips, relatable student life, app promos, routines, and study tool demos.",
        "defaultPostCount": 30,
    }
]

RELATABLE_RULE = {
    "purpose": "relatable",
    "label": "Relatable study video",
    "durationTargetSec": {"min": 3, "max": 10},
    "creativeNotes": "Recreate short single-scene student-life relatable content. Prefer clips under 10 seconds because they are easiest to replicate.",
    "targetTags": {
        "study_content_type": ["relatable_student_problem"],
        "cta_strength": ["none", "light"],
    },
}

HOOK_DEMO_RULE = {
    "purpose": "hook_demo",
    "label": "Hook + demo video",
    "durationTargetSec": {"min": 10, "max": 25},
    "creativeNotes": "Use the source as the hook/reference, then append the account demo extension in the generation pipeline.",
    "targetTags": {
        "is_hook_then_demo": [True],
        "creative_template": ["hook_then_demo"],
        "funnel_stage": ["consideration", "conversion"],
    },
}

DEFAULT_DAILY_TIMES = ["09:00", "12:30", "16:30", "20:00"]


class AccountPlannerError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def list_archetypes() -> Dict[str, Any]:
    return {"archetypes": ARCHETYPES}


def create_studytok_simple_plan(
    *,
    post_count: int = 30,
    relatable_per_day: int = 3,
    hook_demo_per_day: int = 1,
    start_date: str = "",
    daily_times: Optional[List[str]] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    relatable_count = max(0, min(int(relatable_per_day or 3), 12))
    hook_count = max(0, min(int(hook_demo_per_day or 1), 12))
    if relatable_count + hook_count <= 0:
        raise AccountPlannerError("At least one daily content slot is required.", 400)

    target_count = max(1, min(int(post_count or 30), 60))
    times = _normalize_daily_times(daily_times, relatable_count + hook_count)
    schedule_start = _parse_start_date(start_date)
    videos = _tagged_videos()
    planned_posts = _build_ordered_posts(
        videos=videos,
        post_count=target_count,
        relatable_per_day=relatable_count,
        hook_demo_per_day=hook_count,
        start=schedule_start,
        daily_times=times,
        timezone=timezone or "UTC",
    )

    plan = account_plan_store.create({
        "archetype": "studytok",
        "mode": "studytok_daily",
        "status": "draft",
        "settings": {
            "postCount": target_count,
            "relatablePerDay": relatable_count,
            "hookDemoPerDay": hook_count,
            "startDate": schedule_start.isoformat(),
            "dailyTimes": times,
            "timezone": timezone or "UTC",
        },
        "source": {
            "taggedVideoCount": len(videos),
            "relatableCandidates": sum(1 for video in videos if _score_for_purpose(video, "relatable")[0] >= 2),
            "hookDemoCandidates": sum(1 for video in videos if _score_for_purpose(video, "hook_demo")[0] >= 2),
        },
        "contentMix": _content_mix(planned_posts),
        "plannedPosts": planned_posts,
    })
    return plan


def generate_account_plan(archetype: str, post_count: int = 30, batch_id: str = "") -> Dict[str, Any]:
    """Backward-compatible wrapper for the original planner endpoint."""
    del batch_id
    if archetype != "studytok":
        raise AccountPlannerError("Only the StudyTok archetype is available in this MVP.", 400)
    return create_studytok_simple_plan(post_count=post_count)


def swap_studytok_plan_post(plan_id: str, slot: int) -> Dict[str, Any]:
    plan = account_plan_store.get(plan_id)
    if not plan:
        raise AccountPlannerError(f"Plan {plan_id} not found.", 404)

    posts = [post for post in plan.get("plannedPosts", []) if isinstance(post, dict)]
    current = next((post for post in posts if int(post.get("slot") or 0) == int(slot)), None)
    if not current:
        raise AccountPlannerError(f"Plan {plan_id} slot {slot} not found.", 404)
    if current.get("status") == "generating":
        raise AccountPlannerError("This post is currently generating and cannot be swapped yet.", 409)

    purpose = current.get("purpose") or "relatable"
    current_video_id = current.get("videoReferenceId") or ""
    used_ids = {
        post.get("videoReferenceId")
        for post in posts
        if post is not current and post.get("videoReferenceId")
    }
    if current_video_id:
        used_ids.add(current_video_id)

    videos = _tagged_videos()
    replacement = _select_similar_video_for_post(videos, current, purpose, used_ids)
    if not replacement:
        raise AccountPlannerError("No similar unused tagged video is available for this slot.", 404)

    swapped = _planned_post_payload(
        slot=int(slot),
        purpose=purpose,
        match=replacement,
        weak_match=replacement["score"] < 2,
        scheduled_for=current.get("suggestedScheduledFor", ""),
        timezone=current.get("timezone") or (plan.get("settings") or {}).get("timezone") or "UTC",
    )
    swapped["swapHistory"] = (current.get("swapHistory") or []) + [{
        "fromVideoReferenceId": current_video_id,
        "toVideoReferenceId": swapped.get("videoReferenceId", ""),
        "fromStatus": current.get("status", ""),
        "swappedAt": datetime.utcnow().isoformat(),
    }]

    updated = account_plan_store.update_post(
        plan_id,
        int(slot),
        **{key: value for key, value in swapped.items() if key != "slot"},
    )
    if not updated:
        raise AccountPlannerError(f"Plan {plan_id} slot {slot} not found.", 404)

    if updated.get("status") in {"generated", "generation_failed"}:
        return account_plan_store.update(plan_id, status="approved") or updated
    return updated


def _tagged_videos(batch_id: str = "") -> List[Dict[str, Any]]:
    if batch_id:
        batch = organizer_store.get_batch(batch_id)
        if not batch:
            raise AccountPlannerError(f"Organizer batch {batch_id} not found.", 404)
        candidates = batch.get("videos") or []
    else:
        refs = organizer_store.video_references.all()
        tags = organizer_store.video_ai_tags.all()
        candidates = []
        for ref_id, ref in refs.items():
            if not isinstance(ref, dict):
                continue
            tag = tags.get(ref_id)
            if isinstance(tag, dict):
                candidates.append({**ref, "aiTag": tag})

    tagged = []
    for video in candidates:
        ai_tag = video.get("aiTag") or {}
        if ai_tag.get("status") != "tagged":
            continue
        tags = ai_tag.get("normalizedTags") or {}
        if not tags:
            continue
        if not _looks_study_related(tags, video):
            continue
        tagged.append(video)
    return tagged


def _build_ordered_posts(
    *,
    videos: List[Dict[str, Any]],
    post_count: int,
    relatable_per_day: int,
    hook_demo_per_day: int,
    start: date,
    daily_times: List[str],
    timezone: str,
) -> List[Dict[str, Any]]:
    pattern = (["relatable"] * relatable_per_day) + (["hook_demo"] * hook_demo_per_day)
    used_ids = set()
    planned_posts = []
    for idx in range(post_count):
        purpose = pattern[idx % len(pattern)]
        selected, weak = _select_video_for_purpose(videos, purpose, used_ids)
        selected_video_id = (selected or {}).get("video", {}).get("id", "")
        if selected_video_id:
            used_ids.add(selected_video_id)
        scheduled_for = _scheduled_datetime(start, daily_times, idx)
        planned_posts.append(_planned_post_payload(
            slot=idx + 1,
            purpose=purpose,
            match=selected,
            weak_match=weak,
            scheduled_for=scheduled_for,
            timezone=timezone,
        ))
    return planned_posts


def _select_video_for_purpose(
    videos: List[Dict[str, Any]],
    purpose: str,
    used_ids: set,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    scored = []
    for video in videos:
        score, reasons = _score_for_purpose(video, purpose)
        if score <= 0:
            continue
        if video.get("id") in used_ids:
            score -= 4
        scored.append({"video": video, "score": score, "selectionReasons": reasons})
    scored.sort(key=lambda item: item["score"], reverse=True)
    fresh = [item for item in scored if item["video"].get("id") not in used_ids]
    if fresh:
        item = fresh[0]
        return item, item["score"] < 2
    return None, True


def _select_similar_video_for_post(
    videos: List[Dict[str, Any]],
    current_post: Dict[str, Any],
    purpose: str,
    used_ids: set,
) -> Optional[Dict[str, Any]]:
    scored = []
    for video in videos:
        video_id = video.get("id")
        if not video_id or video_id in used_ids:
            continue
        score, reasons = _score_for_purpose(video, purpose)
        if score <= 0:
            continue
        similarity_score, similarity_reasons = _similarity_to_post(video, current_post)
        scored.append({
            "video": video,
            "score": score + similarity_score,
            "selectionReasons": (similarity_reasons + reasons)[:5],
        })
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[0] if scored else None


def _similarity_to_post(video: Dict[str, Any], current_post: Dict[str, Any]) -> Tuple[float, List[str]]:
    current_tags = current_post.get("keyTags") or {}
    tags = (video.get("aiTag") or {}).get("normalizedTags") or {}
    score = 0.0
    reasons: List[str] = []
    weighted_fields = [
        ("study_content_type", 2.0),
        ("creative_template", 1.5),
        ("format", 1.25),
        ("funnel_stage", 1.0),
        ("cta_strength", 0.75),
        ("primary_product_name", 0.75),
    ]
    for field, weight in weighted_fields:
        current_value = current_tags.get(field)
        if current_value and tags.get(field) == current_value:
            score += weight
            reasons.append(f"same {field.replace('_', ' ')}")

    if bool(tags.get("is_hook_then_demo")) == bool(current_tags.get("is_hook_then_demo")):
        score += 1.0
        if current_tags.get("is_hook_then_demo"):
            reasons.append("same hook/demo structure")

    current_duration = 0.0
    try:
        current_duration = float((current_post.get("sourceVideo") or {}).get("durationSec") or 0)
    except (TypeError, ValueError):
        current_duration = 0.0
    candidate_duration = _duration(video, tags)
    if current_duration and candidate_duration:
        delta = abs(candidate_duration - current_duration)
        if delta <= 3:
            score += 1.0
            reasons.append("similar duration")
        elif delta <= 7:
            score += 0.5

    current_scene_count = 0
    try:
        current_scene_count = int(float(current_tags.get("scene_count") or (current_post.get("sourceVideo") or {}).get("sceneCount") or 0))
    except (TypeError, ValueError):
        current_scene_count = 0
    candidate_scene_count = _scene_count(video)
    if current_scene_count and candidate_scene_count == current_scene_count:
        score += 1.0
        if candidate_scene_count == 1:
            reasons.append("same single-scene structure")
    return score, reasons[:3]


def _score_for_purpose(video: Dict[str, Any], purpose: str) -> Tuple[float, List[str]]:
    tags = (video.get("aiTag") or {}).get("normalizedTags") or {}
    duration = _duration(video, tags)
    scene_count = _scene_count(video)
    reasons: List[str] = []
    score = 0.0

    if purpose == "relatable":
        if duration and duration <= 10:
            score += 3
            reasons.append(f"{round(duration)}s under 10s")
        elif duration:
            score -= 3
            reasons.append(f"{round(duration)}s longer than target")

        if scene_count == 1:
            score += 3
            reasons.append("single scene")
        elif scene_count > 1:
            score -= min(4, scene_count - 1)
            reasons.append(f"{scene_count} scenes")

        if tags.get("study_content_type") == "relatable_student_problem":
            score += 4
            reasons.append("relatable student problem")
        if tags.get("cta_strength") in {"", "none", "light"}:
            score += 1
            reasons.append("no or light CTA")
        if tags.get("primary_product_name") and tags.get("product_integration_type") == "demo_core":
            score -= 2
    else:
        if tags.get("is_hook_then_demo"):
            score += 4
            reasons.append("hook then demo structure")
        if tags.get("creative_template") == "hook_then_demo" or tags.get("script_structure") == "hook_then_demo":
            score += 2
            reasons.append("hook/demo template")
        if tags.get("study_content_type") in {"app_demo", "app_promo", "ai_study_tool"}:
            score += 2
            reasons.append(f"study app content: {tags.get('study_content_type')}")
        if tags.get("funnel_stage") in {"consideration", "conversion"}:
            score += 1
            reasons.append(f"{tags.get('funnel_stage')} funnel")
        if tags.get("primary_product_name"):
            score += 0.75
            reasons.append(f"mentions {tags.get('primary_product_name')}")

    if tags.get("repeatability_score"):
        score += min(0.75, float(tags.get("repeatability_score") or 0) * 0.75)
    if not reasons and _looks_study_related(tags, video):
        score = 0.5
        reasons.append("nearby study content fallback")
    return score, reasons[:5]


def _looks_study_related(tags: Dict[str, Any], video: Dict[str, Any]) -> bool:
    hashtags = " ".join(video.get("hashtags") or []).lower()
    text = f"{video.get('caption', '')} {hashtags}".lower()
    return (
        tags.get("niche") in {"education", "productivity", "tech_apps"}
        or tags.get("study_content_type") not in {"", "not_study", None}
        or tags.get("account_archetype") in {"study_productivity_creator", "education_app_creator"}
        or any(term in text for term in ["study", "student", "exam", "finals", "college", "flashcard"])
    )


def _duration(video: Dict[str, Any], tags: Dict[str, Any]) -> float:
    for value in (tags.get("duration_sec"), video.get("durationSec"), (video.get("aiTag") or {}).get("motionMetrics", {}).get("duration_sec")):
        try:
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _scene_count(video: Dict[str, Any]) -> int:
    ai_tag = video.get("aiTag") or {}
    metrics = ai_tag.get("motionMetrics") or {}
    tags = ai_tag.get("normalizedTags") or {}
    for value in (metrics.get("scene_count"), tags.get("scene_count"), video.get("sceneCount")):
        try:
            if value not in (None, ""):
                return int(float(value))
        except (TypeError, ValueError):
            continue
    timeline = metrics.get("scene_timeline") or []
    if isinstance(timeline, list) and timeline:
        return len(timeline)
    return 0


def _planned_post_payload(
    *,
    slot: int,
    purpose: str,
    match: Optional[Dict[str, Any]],
    weak_match: bool,
    scheduled_for: str,
    timezone: str,
) -> Dict[str, Any]:
    rule = RELATABLE_RULE if purpose == "relatable" else HOOK_DEMO_RULE
    item = match or {}
    video = item.get("video") or {}
    ai_tag = video.get("aiTag") or {}
    tags = ai_tag.get("normalizedTags") or {}
    caption = (video.get("caption") or "").strip()
    return {
        "slot": slot,
        "purpose": purpose,
        "label": rule["label"],
        "targetTags": rule["targetTags"],
        "durationTargetSec": rule["durationTargetSec"],
        "creativeNotes": rule["creativeNotes"],
        "videoReferenceId": video.get("id", ""),
        "sourceVideo": {
            "id": video.get("id", ""),
            "url": video.get("url", ""),
            "thumbnailUrl": video.get("thumbnailUrl", ""),
            "creatorHandle": video.get("creatorHandle", ""),
            "caption": caption,
            "durationSec": _duration(video, tags),
            "sceneCount": _scene_count(video),
        },
        "selectionReasons": item.get("selectionReasons") or ["needs more matching study videos"],
        "weakMatch": bool(weak_match),
        "needsSource": not bool(video.get("id")),
        "captionDraft": caption or "Generated with nflncr.ai",
        "suggestedScheduledFor": scheduled_for,
        "timezone": timezone,
        "status": "planned",
        "reviewStatus": "pending",
        "generationId": "",
        "jobId": "",
        "generatedMediaUrl": "",
        "error": "",
        "keyTags": {
            "study_content_type": tags.get("study_content_type", ""),
            "study_pain_point": tags.get("study_pain_point", ""),
            "study_outcome_promise": tags.get("study_outcome_promise", ""),
            "format": tags.get("format", ""),
            "creative_template": tags.get("creative_template", ""),
            "funnel_stage": tags.get("funnel_stage", ""),
            "cta_strength": tags.get("cta_strength", ""),
            "primary_product_name": tags.get("primary_product_name", ""),
            "is_hook_then_demo": tags.get("is_hook_then_demo", False),
            "scene_count": _scene_count(video),
        },
    }


def _content_mix(planned_posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    total = len(planned_posts) or 1
    counts: Dict[str, int] = {}
    for post in planned_posts:
        counts[post["purpose"]] = counts.get(post["purpose"], 0) + 1
    return [
        {
            "purpose": purpose,
            "count": count,
            "percentage": round((count / total) * 100),
        }
        for purpose, count in counts.items()
    ]


def _parse_start_date(raw: str) -> date:
    if raw:
        try:
            return datetime.fromisoformat(raw[:10]).date()
        except ValueError:
            raise AccountPlannerError("startDate must use YYYY-MM-DD format.", 400)
    return date.today()


def _normalize_daily_times(values: Optional[List[str]], slots_per_day: int) -> List[str]:
    cleaned = []
    for value in values or []:
        text = str(value or "").strip()
        try:
            parsed = time.fromisoformat(text)
        except ValueError:
            continue
        cleaned.append(parsed.strftime("%H:%M"))
    if cleaned:
        while len(cleaned) < slots_per_day:
            cleaned.append(cleaned[-1])
        return cleaned[:slots_per_day]
    return DEFAULT_DAILY_TIMES[:slots_per_day] if slots_per_day <= len(DEFAULT_DAILY_TIMES) else DEFAULT_DAILY_TIMES


def _scheduled_datetime(start: date, daily_times: List[str], idx: int) -> str:
    slot_count = len(daily_times) or 1
    day_offset = idx // slot_count
    time_value = daily_times[idx % slot_count]
    parsed_time = time.fromisoformat(time_value)
    scheduled = datetime.combine(start + timedelta(days=day_offset), parsed_time)
    return scheduled.isoformat()
