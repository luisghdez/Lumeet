"""
JSON-backed organizer entities for the cheap-first bulk video MVP.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import (
    ORGANIZER_CREATORS_FILE,
    ORGANIZER_REVIEW_ACTIONS_FILE,
    ORGANIZER_SOURCE_BATCHES_FILE,
    ORGANIZER_VIDEO_AI_TAGS_FILE,
    ORGANIZER_VIDEO_REFERENCES_FILE,
)


APPROVAL_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "saved_hook_only",
    "saved_format_only",
    "needs_deep_analysis",
}

AI_TAG_STATUSES = {"not_tagged", "tagging", "tagged", "tag_failed"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_url_id(url: str) -> str:
    return hashlib.sha1((url or "").strip().lower().encode("utf-8")).hexdigest()[:16]


class JsonEntityStore:
    def __init__(self, metadata_file: str):
        self.metadata_file = metadata_file
        self._lock = threading.Lock()
        parent = os.path.dirname(self.metadata_file)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _read_all_unlocked(self) -> Dict[str, Any]:
        if not os.path.isfile(self.metadata_file):
            return {}
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_all_unlocked(self, payload: Dict[str, Any]) -> None:
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def save(self, entity_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            all_items = self._read_all_unlocked()
            all_items[entity_id] = payload
            self._write_all_unlocked(all_items)

    def get(self, entity_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._read_all_unlocked().get(entity_id)
            return item if isinstance(item, dict) else None

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return self._read_all_unlocked()


class OrganizerStore:
    def __init__(self):
        self.source_batches = JsonEntityStore(ORGANIZER_SOURCE_BATCHES_FILE)
        self.video_references = JsonEntityStore(ORGANIZER_VIDEO_REFERENCES_FILE)
        self.creators = JsonEntityStore(ORGANIZER_CREATORS_FILE)
        self.review_actions = JsonEntityStore(ORGANIZER_REVIEW_ACTIONS_FILE)
        self.video_ai_tags = JsonEntityStore(ORGANIZER_VIDEO_AI_TAGS_FILE)

    def create_batch_from_scan(self, scan: Dict[str, Any], niche_hint: str = "") -> Dict[str, Any]:
        now = utc_now_iso()
        scan_id = scan.get("scanId") or ""
        creator_handle = (scan.get("creatorHandle") or "").strip().lstrip("@")
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        videos = [video for video in scan.get("videos", []) if isinstance(video, dict)]

        creator_id = ""
        if creator_handle:
            creator_id = f"tiktok_{creator_handle.lower()}"
            existing_creator = self.creators.get(creator_id) or {}
            self.creators.save(creator_id, {
                **existing_creator,
                "id": creator_id,
                "platform": "tiktok",
                "handle": creator_handle,
                "displayName": existing_creator.get("displayName") or "",
                "sourceScanIds": sorted(set((existing_creator.get("sourceScanIds") or []) + [scan_id])),
                "updatedAt": now,
                "createdAt": existing_creator.get("createdAt") or now,
            })

        existing_refs = self.video_references.all()
        existing_url_to_id = {
            (item.get("normalizedUrl") or item.get("url")): ref_id
            for ref_id, item in existing_refs.items()
            if isinstance(item, dict) and (item.get("normalizedUrl") or item.get("url"))
        }

        reference_ids: List[str] = []
        created_count = 0
        duplicate_count = 0
        for video in videos:
            normalized_url = video.get("normalizedUrl") or video.get("url")
            if not normalized_url:
                continue
            ref_id = existing_url_to_id.get(normalized_url) or f"vidref_{stable_url_id(normalized_url)}"
            if ref_id in reference_ids:
                duplicate_count += 1
                continue
            existing_ref = self.video_references.get(ref_id) or {}
            batch_ids = sorted(set((existing_ref.get("sourceBatchIds") or []) + [batch_id]))
            reference = {
                **existing_ref,
                "id": ref_id,
                "platform": "tiktok",
                "url": video.get("url") or normalized_url,
                "normalizedUrl": normalized_url,
                "creatorId": creator_id,
                "creatorHandle": video.get("creatorHandle") or creator_handle,
                "caption": video.get("caption") or "",
                "hashtags": video.get("hashtags") or [],
                "durationSec": video.get("durationSec"),
                "thumbnailUrl": video.get("thumbnailUrl") or "",
                "sourceMediaUrl": video.get("sourceMediaUrl") or existing_ref.get("sourceMediaUrl") or "",
                "postedAt": video.get("postedAt"),
                "metrics": video.get("metrics") or {},
                "sourceBatchIds": batch_ids,
                "sourceScanId": existing_ref.get("sourceScanId") or scan_id,
                "providerVideoId": video.get("providerVideoId") or existing_ref.get("providerVideoId") or "",
                "approvalStatus": existing_ref.get("approvalStatus") or "pending",
                "processingStatus": existing_ref.get("processingStatus") or "imported",
                "aiTagStatus": existing_ref.get("aiTagStatus") or "not_tagged",
                "updatedAt": now,
                "createdAt": existing_ref.get("createdAt") or now,
            }
            self.video_references.save(ref_id, reference)

            if not self.video_ai_tags.get(ref_id):
                self.video_ai_tags.save(ref_id, {
                    "videoReferenceId": ref_id,
                    "status": "not_tagged",
                    "normalizedTags": {},
                    "motionMetrics": {},
                    "sampledFrames": [],
                    "rawAiOutput": None,
                    "error": "",
                    "createdAt": now,
                    "updatedAt": now,
                })

            reference_ids.append(ref_id)
            existing_url_to_id[normalized_url] = ref_id
            if existing_ref:
                duplicate_count += 1
            else:
                created_count += 1

        batch = {
            "id": batch_id,
            "sourceType": "tiktok_account",
            "platform": "tiktok",
            "sourceScanId": scan_id,
            "creatorId": creator_id,
            "creatorHandle": creator_handle,
            "nicheHint": niche_hint.strip(),
            "status": "imported",
            "counts": {
                "total": len(reference_ids),
                "imported": len(reference_ids),
                "enriched": 0,
                "failed": 0,
                "aiTagged": 0,
                "created": created_count,
                "duplicates": duplicate_count,
            },
            "videoReferenceIds": reference_ids,
            "createdAt": now,
            "updatedAt": now,
        }
        self.source_batches.save(batch_id, batch)
        return self.get_batch(batch_id) or batch

    def list_batches(self, limit: int = 25) -> List[Dict[str, Any]]:
        batches = [
            item for item in self.source_batches.all().values()
            if isinstance(item, dict)
        ]
        batches.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
        return batches[:limit] if limit else batches

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        batch = self.source_batches.get(batch_id)
        if not batch:
            return None

        videos = []
        ai_tags = self.video_ai_tags.all()
        for ref_id in batch.get("videoReferenceIds", []):
            video = self.video_references.get(ref_id)
            if not video:
                continue
            tag = ai_tags.get(ref_id) if isinstance(ai_tags.get(ref_id), dict) else None
            videos.append({
                **video,
                "aiTag": tag or {"videoReferenceId": ref_id, "status": "not_tagged", "rawAiOutput": None},
            })
        return {**batch, "videos": videos}

    def get_video_reference(self, video_reference_id: str) -> Optional[Dict[str, Any]]:
        return self.video_references.get(video_reference_id)

    def get_video_analysis(self, video_reference_id: str) -> Optional[Dict[str, Any]]:
        tag = self.video_ai_tags.get(video_reference_id)
        return tag if isinstance(tag, dict) else None

    def set_video_analysis_status(self, video_reference_id: str, status: str, error: str = "") -> Dict[str, Any]:
        if status not in AI_TAG_STATUSES:
            raise ValueError(f"Unsupported AI tag status: {status}")
        video = self.video_references.get(video_reference_id)
        if not video:
            raise KeyError(video_reference_id)
        now = utc_now_iso()
        updated_video = {
            **video,
            "aiTagStatus": status,
            "processingStatus": "analyzing" if status == "tagging" else ("analysis_failed" if status == "tag_failed" else video.get("processingStatus", "imported")),
            "updatedAt": now,
        }
        self.video_references.save(video_reference_id, updated_video)

        existing_tag = self.video_ai_tags.get(video_reference_id) or {}
        self.video_ai_tags.save(video_reference_id, {
            **existing_tag,
            "videoReferenceId": video_reference_id,
            "status": status,
            "error": error,
            "updatedAt": now,
            "createdAt": existing_tag.get("createdAt") or now,
        })
        return updated_video

    def save_video_analysis_result(self, video_reference_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        video = self.video_references.get(video_reference_id)
        if not video:
            raise KeyError(video_reference_id)
        now = utc_now_iso()
        tags = result.get("normalizedTags") or {}
        metrics = result.get("motionMetrics") or {}
        existing_tag = self.video_ai_tags.get(video_reference_id) or {}
        tag_record = {
            **existing_tag,
            "videoReferenceId": video_reference_id,
            "analysisId": result.get("analysisId", ""),
            "status": "tagged",
            "niche": tags.get("niche", ""),
            "sub_niche": tags.get("sub_niche", ""),
            "format": tags.get("format", ""),
            "hook_type": tags.get("hook_type", ""),
            "camera_movement": tags.get("camera_movement", ""),
            "visual_pattern": tags.get("visual_pattern", ""),
            "motion_amount": tags.get("motion_amount", ""),
            "recreation_difficulty": tags.get("recreation_difficulty", ""),
            "motion_difficulty": tags.get("motion_difficulty", ""),
            "content_pillar": tags.get("content_pillar", ""),
            "account_archetype": tags.get("account_archetype", ""),
            "funnel_stage": tags.get("funnel_stage", ""),
            "campaign_use": tags.get("campaign_use", ""),
            "creative_template": tags.get("creative_template", ""),
            "script_structure": tags.get("script_structure", ""),
            "is_hook_then_demo": tags.get("is_hook_then_demo", False),
            "hook_scene_count": tags.get("hook_scene_count", 0),
            "demo_scene_count": tags.get("demo_scene_count", 0),
            "cta_scene_count": tags.get("cta_scene_count", 0),
            "demo_start_sec": tags.get("demo_start_sec", 0),
            "product_integration_type": tags.get("product_integration_type", ""),
            "primary_product_name": tags.get("primary_product_name", ""),
            "primary_product_type": tags.get("primary_product_type", ""),
            "product_mention_type": tags.get("product_mention_type", ""),
            "cta_strength": tags.get("cta_strength", ""),
            "conversion_intent": tags.get("conversion_intent", ""),
            "production_complexity": tags.get("production_complexity", ""),
            "campaign_fit_score": tags.get("campaign_fit_score", 0),
            "account_fit_score": tags.get("account_fit_score", 0),
            "repeatability_score": tags.get("repeatability_score", 0),
            "conversion_potential_score": tags.get("conversion_potential_score", 0),
            "normalizedTags": tags,
            "motionMetrics": metrics,
            "sampledFrames": result.get("sampledFrames") or [],
            "rawAiOutput": result.get("rawAiOutput"),
            "error": "",
            "updatedAt": now,
            "createdAt": existing_tag.get("createdAt") or now,
        }
        self.video_ai_tags.save(video_reference_id, tag_record)

        updated_video = {
            **video,
            "aiTagStatus": "tagged",
            "processingStatus": "analyzed",
            "niche": tags.get("niche", ""),
            "sub_niche": tags.get("sub_niche", ""),
            "format": tags.get("format", ""),
            "visualPattern": tags.get("visual_pattern", ""),
            "contentPillar": tags.get("content_pillar", ""),
            "accountArchetype": tags.get("account_archetype", ""),
            "funnelStage": tags.get("funnel_stage", ""),
            "campaignUse": tags.get("campaign_use", ""),
            "creativeTemplate": tags.get("creative_template", ""),
            "scriptStructure": tags.get("script_structure", ""),
            "isHookThenDemo": tags.get("is_hook_then_demo", False),
            "hookSceneCount": tags.get("hook_scene_count", 0),
            "demoSceneCount": tags.get("demo_scene_count", 0),
            "ctaSceneCount": tags.get("cta_scene_count", 0),
            "demoStartSec": tags.get("demo_start_sec", 0),
            "productIntegrationType": tags.get("product_integration_type", ""),
            "primaryProductName": tags.get("primary_product_name", ""),
            "primaryProductType": tags.get("primary_product_type", ""),
            "productMentionType": tags.get("product_mention_type", ""),
            "ctaStrength": tags.get("cta_strength", ""),
            "conversionIntent": tags.get("conversion_intent", ""),
            "productionComplexity": tags.get("production_complexity", ""),
            "motionDifficulty": tags.get("motion_difficulty", ""),
            "motionAmount": tags.get("motion_amount", ""),
            "recreationDifficulty": tags.get("recreation_difficulty", ""),
            "durationSec": metrics.get("duration_sec") or video.get("durationSec"),
            "updatedAt": now,
        }
        self.video_references.save(video_reference_id, updated_video)
        self._refresh_batches_for_video(video_reference_id)
        return self.get_video_analysis(video_reference_id) or tag_record

    def save_video_analysis_failure(self, video_reference_id: str, error: str) -> Dict[str, Any]:
        self.set_video_analysis_status(video_reference_id, "tag_failed", error=error)
        self._refresh_batches_for_video(video_reference_id)
        return self.get_video_analysis(video_reference_id) or {}

    def _refresh_batches_for_video(self, video_reference_id: str) -> None:
        all_refs = self.video_references.all()
        for batch in self.source_batches.all().values():
            if not isinstance(batch, dict):
                continue
            if video_reference_id not in (batch.get("videoReferenceIds") or []):
                continue
            ref_ids = batch.get("videoReferenceIds") or []
            refs = [all_refs.get(ref_id) for ref_id in ref_ids if isinstance(all_refs.get(ref_id), dict)]
            counts = dict(batch.get("counts") or {})
            counts["total"] = len(ref_ids)
            counts["imported"] = len(ref_ids)
            counts["aiTagged"] = sum(1 for ref in refs if ref.get("aiTagStatus") == "tagged")
            counts["failed"] = sum(1 for ref in refs if ref.get("aiTagStatus") == "tag_failed" or ref.get("processingStatus") == "analysis_failed")
            counts["enriched"] = counts["aiTagged"]
            status = "analyzed" if counts["total"] and counts["aiTagged"] == counts["total"] else batch.get("status", "imported")
            self.source_batches.save(batch["id"], {
                **batch,
                "counts": counts,
                "status": status,
                "updatedAt": utc_now_iso(),
            })

    def update_review_status(
        self,
        video_reference_id: str,
        approval_status: str,
        notes: str = "",
        action: str = "status_update",
    ) -> Dict[str, Any]:
        if approval_status not in APPROVAL_STATUSES:
            raise ValueError(f"Unsupported approval status: {approval_status}")
        video = self.video_references.get(video_reference_id)
        if not video:
            raise KeyError(video_reference_id)

        now = utc_now_iso()
        updated = {
            **video,
            "approvalStatus": approval_status,
            "updatedAt": now,
        }
        self.video_references.save(video_reference_id, updated)

        action_id = f"review_{uuid.uuid4().hex[:12]}"
        self.review_actions.save(action_id, {
            "id": action_id,
            "videoReferenceId": video_reference_id,
            "action": action,
            "approvalStatus": approval_status,
            "notes": notes.strip(),
            "createdAt": now,
        })
        return updated


organizer_store = OrganizerStore()
