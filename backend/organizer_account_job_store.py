"""
Persistent job tracking for one-tap TikTok account processing.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from config import ORGANIZER_ACCOUNT_JOBS_FILE


class OrganizerAccountJobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


DEFAULT_COUNTS = {
    "scanned": 0,
    "imported": 0,
    "eligible": 0,
    "tagged": 0,
    "failed": 0,
    "skipped": 0,
    "skippedDuration": 0,
    "skippedAlreadyTagged": 0,
    "skippedFailed": 0,
    "total": 0,
}


class OrganizerAccountJobStore:
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

    def create(
        self,
        *,
        account: str,
        max_items: int,
        niche_hint: str = "",
        analyze: bool = True,
        retry_failed: bool = False,
        max_duration_sec: int = 30,
        tag_concurrency: int = 2,
        max_analysis_frames: int = 12,
    ) -> Dict[str, Any]:
        job_id = f"orgjob_{uuid.uuid4().hex[:12]}"
        now = time.time()
        record = {
            "jobId": job_id,
            "status": OrganizerAccountJobStatus.QUEUED,
            "progress": 0,
            "currentStep": "queued",
            "account": account,
            "creatorHandle": "",
            "maxItems": max(1, min(int(max_items or 100), 100)),
            "nicheHint": niche_hint.strip(),
            "analyze": analyze,
            "retryFailed": retry_failed,
            "maxDurationSec": max(1, min(int(max_duration_sec or 30), 300)),
            "tagConcurrency": max(1, min(int(tag_concurrency or 2), 3)),
            "maxAnalysisFrames": max(1, min(int(max_analysis_frames or 12), 45)),
            "counts": dict(DEFAULT_COUNTS),
            "scanId": "",
            "batchId": "",
            "batch": None,
            "error": "",
            "createdAt": now,
            "updatedAt": now,
            "completedAt": None,
        }
        with self._lock:
            all_items = self._read_all_unlocked()
            all_items[job_id] = record
            self._write_all_unlocked(all_items)
        return record

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._read_all_unlocked().get(job_id)
            return item if isinstance(item, dict) else None

    def delete(self, job_id: str) -> bool:
        with self._lock:
            all_items = self._read_all_unlocked()
            if job_id not in all_items:
                return False
            del all_items[job_id]
            self._write_all_unlocked(all_items)
            return True

    def list_all(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._lock:
            items = [item for item in self._read_all_unlocked().values() if isinstance(item, dict)]
        items.sort(key=lambda item: item.get("createdAt", 0), reverse=True)
        return items[:limit] if limit else items

    def update(self, job_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            record = all_items.get(job_id)
            if not isinstance(record, dict):
                return None
            record.update(fields)
            record["updatedAt"] = time.time()
            all_items[job_id] = record
            self._write_all_unlocked(all_items)
            return record

    def mark_processing(self, job_id: str, current_step: str, progress: Optional[int] = None) -> None:
        fields: Dict[str, Any] = {
            "status": OrganizerAccountJobStatus.PROCESSING,
            "currentStep": current_step,
        }
        if progress is not None:
            fields["progress"] = max(0, min(int(progress), 99))
        self.update(job_id, **fields)

    def update_counts(
        self,
        job_id: str,
        *,
        counts: Optional[Dict[str, Any]] = None,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        **fields: Any,
    ) -> None:
        existing = self.get(job_id) or {}
        next_counts = dict(DEFAULT_COUNTS)
        next_counts.update(existing.get("counts") or {})
        if counts:
            next_counts.update(counts)
        update_fields = {**fields, "counts": next_counts}
        if progress is not None:
            update_fields["progress"] = max(0, min(int(progress), 99))
        if current_step is not None:
            update_fields["currentStep"] = current_step
        self.update(job_id, **update_fields)

    def mark_completed(self, job_id: str, **fields: Any) -> None:
        self.update(
            job_id,
            **fields,
            status=OrganizerAccountJobStatus.COMPLETED,
            progress=100,
            currentStep=None,
            completedAt=time.time(),
            error="",
        )

    def mark_failed(self, job_id: str, error: str) -> None:
        self.update(
            job_id,
            status=OrganizerAccountJobStatus.FAILED,
            currentStep=None,
            completedAt=time.time(),
            error=error,
        )


organizer_account_job_store = OrganizerAccountJobStore(ORGANIZER_ACCOUNT_JOBS_FILE)
