"""
Persistent discovery jobs and ranked TikTok account suggestions.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from config import ORGANIZER_ACCOUNT_DISCOVERY_FILE


class OrganizerDiscoveryStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OrganizerAccountDiscoveryStore:
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

    def create(self, *, niche: str, limit: int, videos_per_source: int) -> Dict[str, Any]:
        discovery_id = f"disc_{uuid.uuid4().hex[:12]}"
        now = time.time()
        record = {
            "discoveryId": discovery_id,
            "status": OrganizerDiscoveryStatus.QUEUED,
            "progress": 0,
            "currentStep": "queued",
            "niche": niche,
            "limit": max(1, min(int(limit or 25), 50)),
            "videosPerSource": max(1, min(int(videos_per_source or 20), 50)),
            "accounts": [],
            "counts": {
                "providerItems": 0,
                "videos": 0,
                "accounts": 0,
            },
            "error": "",
            "createdAt": now,
            "updatedAt": now,
            "completedAt": None,
        }
        with self._lock:
            all_items = self._read_all_unlocked()
            all_items[discovery_id] = record
            self._write_all_unlocked(all_items)
        return record

    def get(self, discovery_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._read_all_unlocked().get(discovery_id)
            return item if isinstance(item, dict) else None

    def delete(self, discovery_id: str) -> bool:
        with self._lock:
            all_items = self._read_all_unlocked()
            if discovery_id not in all_items:
                return False
            del all_items[discovery_id]
            self._write_all_unlocked(all_items)
            return True

    def list_all(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._lock:
            items = [item for item in self._read_all_unlocked().values() if isinstance(item, dict)]
        items.sort(key=lambda item: item.get("createdAt", 0), reverse=True)
        return items[:limit] if limit else items

    def latest_for_niche(self, niche: str) -> Optional[Dict[str, Any]]:
        niche_key = (niche or "").strip().lower()
        matches = [
            item for item in self.list_all(limit=250)
            if item.get("niche") == niche_key and item.get("status") == OrganizerDiscoveryStatus.COMPLETED
        ]
        return matches[0] if matches else None

    def update(self, discovery_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            record = all_items.get(discovery_id)
            if not isinstance(record, dict):
                return None
            record.update(fields)
            record["updatedAt"] = time.time()
            all_items[discovery_id] = record
            self._write_all_unlocked(all_items)
            return record

    def mark_processing(self, discovery_id: str, current_step: str, progress: int = 10) -> None:
        self.update(
            discovery_id,
            status=OrganizerDiscoveryStatus.PROCESSING,
            currentStep=current_step,
            progress=max(0, min(int(progress), 99)),
        )

    def mark_completed(
        self,
        discovery_id: str,
        *,
        accounts: List[Dict[str, Any]],
        counts: Dict[str, Any],
    ) -> None:
        self.update(
            discovery_id,
            status=OrganizerDiscoveryStatus.COMPLETED,
            progress=100,
            currentStep=None,
            accounts=accounts,
            counts=counts,
            completedAt=time.time(),
            error="",
        )

    def mark_failed(self, discovery_id: str, error: str) -> None:
        self.update(
            discovery_id,
            status=OrganizerDiscoveryStatus.FAILED,
            currentStep=None,
            completedAt=time.time(),
            error=error,
        )


organizer_account_discovery_store = OrganizerAccountDiscoveryStore(ORGANIZER_ACCOUNT_DISCOVERY_FILE)
