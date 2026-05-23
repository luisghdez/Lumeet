"""
Deterministic account planner for building creator account content mixes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from organizer_store import organizer_store


ARCHETYPES = [
    {
        "id": "studytok",
        "label": "StudyTok",
        "description": "Study tips, relatable student life, app promos, routines, and study tool demos.",
        "defaultPostCount": 10,
    }
]


STUDYTOK_SLOTS = [
    {
        "purpose": "relatable",
        "label": "Relatable student pain",
        "count": 3,
        "durationTargetSec": {"min": 6, "max": 12},
        "targetTags": {
            "study_content_type": ["relatable_student_problem"],
            "cta_strength": ["none", "light"],
            "content_pillar": ["relatable_lifestyle"],
        },
        "creativeNotes": "Single-room text overlay or face-to-camera student pain point. Keep it native and low-pressure.",
    },
    {
        "purpose": "study_tip",
        "label": "Study tip / productivity",
        "count": 2,
        "durationTargetSec": {"min": 8, "max": 20},
        "targetTags": {
            "study_content_type": ["study_tip", "productivity_hack", "note_taking", "flashcards"],
            "funnel_stage": ["awareness", "consideration"],
        },
        "creativeNotes": "Quick useful study framework, memorization tip, note-taking tactic, or productivity hack.",
    },
    {
        "purpose": "routine",
        "label": "Study routine / aesthetic",
        "count": 1,
        "durationTargetSec": {"min": 10, "max": 25},
        "targetTags": {
            "study_content_type": ["routine", "study_aesthetic", "motivation"],
        },
        "creativeNotes": "Routine, desk setup, focus session, or aesthetic study montage to make the account feel real.",
    },
    {
        "purpose": "soft_app_mention",
        "label": "Soft app/product mention",
        "count": 2,
        "durationTargetSec": {"min": 6, "max": 15},
        "targetTags": {
            "product_integration_type": ["mentioned_only", "shown_briefly"],
            "cta_strength": ["light", "medium"],
        },
        "creativeNotes": "Relatable or useful content where the app/product is mentioned naturally, not fully demoed.",
    },
    {
        "purpose": "direct_app_demo",
        "label": "Direct app demo / CTA",
        "count": 2,
        "durationTargetSec": {"min": 12, "max": 25},
        "targetTags": {
            "study_content_type": ["app_demo", "app_promo", "ai_study_tool"],
            "is_hook_then_demo": [True],
            "funnel_stage": ["conversion", "consideration"],
        },
        "creativeNotes": "Hook first, then show app/interface steps and a clear CTA or payoff.",
    },
]


class AccountPlannerError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def list_archetypes() -> Dict[str, Any]:
    return {"archetypes": ARCHETYPES}


def generate_account_plan(archetype: str, post_count: int = 10, batch_id: str = "") -> Dict[str, Any]:
    if archetype != "studytok":
        raise AccountPlannerError("Only the StudyTok archetype is available in this MVP.", 400)

    videos = _tagged_videos(batch_id=batch_id.strip())
    slots = _expand_slots(post_count)
    used_video_ids = set()
    planned_posts = []

    for idx, slot in enumerate(slots, start=1):
        matches = _rank_videos_for_slot(videos, slot, used_video_ids)
        selected = matches[:5]
        if len(selected) >= 2:
            used_video_ids.update(item["video"]["id"] for item in selected[:2] if item["video"].get("id"))
        planned_posts.append({
            "slot": idx,
            "purpose": slot["purpose"],
            "label": slot["label"],
            "targetTags": slot["targetTags"],
            "durationTargetSec": slot["durationTargetSec"],
            "creativeNotes": slot["creativeNotes"],
            "inspoVideos": [_inspo_payload(item) for item in selected],
            "needsMoreInspo": len(selected) < 2,
            "fallbackNote": "" if len(selected) >= 2 else "Not enough strong matches yet. Import/analyze more study videos for this slot.",
        })

    return {
        "archetype": "studytok",
        "postCount": len(planned_posts),
        "source": {
            "batchId": batch_id,
            "taggedVideoCount": len(videos),
        },
        "contentMix": _content_mix(planned_posts),
        "plannedPosts": planned_posts,
    }


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


def _looks_study_related(tags: Dict[str, Any], video: Dict[str, Any]) -> bool:
    hashtags = " ".join(video.get("hashtags") or []).lower()
    text = f"{video.get('caption', '')} {hashtags}".lower()
    return (
        tags.get("niche") in {"education", "productivity", "tech_apps"}
        or tags.get("study_content_type") not in {"", "not_study", None}
        or tags.get("account_archetype") in {"study_productivity_creator", "education_app_creator"}
        or any(term in text for term in ["study", "student", "exam", "finals", "college", "flashcard"])
    )


def _expand_slots(post_count: int) -> List[Dict[str, Any]]:
    target_count = max(1, min(int(post_count or 10), 20))
    expanded = []
    for slot in STUDYTOK_SLOTS:
        for _ in range(slot["count"]):
            expanded.append(slot)
    if target_count <= len(expanded):
        return expanded[:target_count]
    idx = 0
    while len(expanded) < target_count:
        expanded.append(STUDYTOK_SLOTS[idx % len(STUDYTOK_SLOTS)])
        idx += 1
    return expanded


def _rank_videos_for_slot(videos: List[Dict[str, Any]], slot: Dict[str, Any], used_video_ids: set) -> List[Dict[str, Any]]:
    scored = []
    for video in videos:
        score, reasons = _score_video(video, slot)
        if video.get("id") in used_video_ids:
            score -= 1.5
            reasons.append("already used in an earlier slot")
        if score <= 0:
            continue
        scored.append({"video": video, "score": round(score, 2), "reasons": reasons})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored


def _score_video(video: Dict[str, Any], slot: Dict[str, Any]) -> tuple:
    tags = (video.get("aiTag") or {}).get("normalizedTags") or {}
    duration = _duration(video, tags)
    reasons = []
    score = 0.0

    for key, wanted_values in (slot.get("targetTags") or {}).items():
        actual = tags.get(key)
        if key == "is_hook_then_demo":
            if bool(actual) in wanted_values:
                score += 2.0
                reasons.append("matches hook + demo structure")
            continue
        if actual in wanted_values:
            score += 2.0
            reasons.append(f"{key} is {actual}")

    min_sec = slot["durationTargetSec"]["min"]
    max_sec = slot["durationTargetSec"]["max"]
    if duration and min_sec <= duration <= max_sec:
        score += 1.0
        reasons.append(f"duration {round(duration)}s fits target")
    elif duration:
        distance = min(abs(duration - min_sec), abs(duration - max_sec))
        if distance <= 6:
            score += 0.35
            reasons.append(f"duration {round(duration)}s is near target")

    if slot["purpose"] == "soft_app_mention" and tags.get("primary_product_name"):
        score += 1.5
        reasons.append(f"mentions {tags.get('primary_product_name')}")
    if slot["purpose"] == "direct_app_demo" and tags.get("product_integration_type") == "demo_core":
        score += 1.25
        reasons.append("product is core to the demo")
    if slot["purpose"] == "relatable" and tags.get("content_pillar") == "relatable_lifestyle":
        score += 1.0
        reasons.append("relatable content pillar")
    if tags.get("repeatability_score"):
        score += min(0.75, float(tags.get("repeatability_score") or 0) * 0.75)
    if tags.get("production_ease_score"):
        score += min(0.5, float(tags.get("production_ease_score") or 0) * 0.5)

    return score, reasons[:5] or ["nearby study content match"]


def _duration(video: Dict[str, Any], tags: Dict[str, Any]) -> float:
    for value in (tags.get("duration_sec"), video.get("durationSec"), (video.get("aiTag") or {}).get("motionMetrics", {}).get("duration_sec")):
        try:
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _inspo_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    video = item["video"]
    ai_tag = video.get("aiTag") or {}
    tags = ai_tag.get("normalizedTags") or {}
    return {
        "videoReferenceId": video.get("id", ""),
        "url": video.get("url", ""),
        "thumbnailUrl": video.get("thumbnailUrl", ""),
        "creatorHandle": video.get("creatorHandle", ""),
        "caption": video.get("caption", ""),
        "durationSec": _duration(video, tags),
        "score": item["score"],
        "selectionReasons": item["reasons"],
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
