"""
Generation Store
================
Persistent JSON-backed store for tracking generation jobs (video + carousel).

Each generation record contains:
    - generationId, type (video | carousel), status, progress (0-100),
      currentStep, steps, error, createdAt, completedAt, and output metadata.

Statuses: queued -> processing -> completed | failed
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from config import GENERATION_METADATA_FILE


class GenerationStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationStore:
    """Thread-safe, JSON-file-persisted generation tracker."""

    def __init__(self, metadata_file: str):
        self.metadata_file = metadata_file
        self._lock = threading.Lock()
        parent = os.path.dirname(self.metadata_file)
        if parent:
            os.makedirs(parent, exist_ok=True)

    # ---- low-level persistence ----

    def _read_all_unlocked(self) -> Dict[str, Any]:
        if not os.path.isfile(self.metadata_file):
            return {}
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _write_all_unlocked(self, payload: Dict[str, Any]) -> None:
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    # ---- public API ----

    def create(self, gen_type: str, label: str = "", steps: Optional[List[dict]] = None) -> Dict[str, Any]:
        """Create a new generation record and persist it. Returns the record dict."""
        gen_id = uuid.uuid4().hex[:12]
        now = time.time()
        record: Dict[str, Any] = {
            "generationId": gen_id,
            "type": gen_type,  # "video" or "carousel"
            "label": label,
            "status": GenerationStatus.QUEUED,
            "progress": 0,
            "currentStep": None,
            "steps": steps or [],
            "error": None,
            "createdAt": now,
            "completedAt": None,
            # Output metadata filled on completion
            "output": None,
        }
        with self._lock:
            all_items = self._read_all_unlocked()
            all_items[gen_id] = record
            self._write_all_unlocked(all_items)
        return record

    def get(self, gen_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            item = all_items.get(gen_id)
            return item if isinstance(item, dict) else None

    def list_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            values = [v for v in all_items.values() if isinstance(v, dict)]
            values.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
            return values[:limit]

    def update(self, gen_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Update arbitrary fields on a generation record and persist."""
        with self._lock:
            all_items = self._read_all_unlocked()
            record = all_items.get(gen_id)
            if not isinstance(record, dict):
                return None
            record.update(fields)
            all_items[gen_id] = record
            self._write_all_unlocked(all_items)
            return record

    # ---- convenience helpers ----

    def mark_processing(self, gen_id: str, current_step: Optional[str] = None) -> None:
        self.update(gen_id, status=GenerationStatus.PROCESSING, currentStep=current_step)

    def update_progress(self, gen_id: str, progress: int, current_step: Optional[str] = None,
                        steps: Optional[List[dict]] = None) -> None:
        fields: Dict[str, Any] = {"progress": progress}
        if current_step is not None:
            fields["currentStep"] = current_step
        if steps is not None:
            fields["steps"] = steps
        self.update(gen_id, **fields)

    def mark_completed(self, gen_id: str, output: Dict[str, Any]) -> None:
        self.update(
            gen_id,
            status=GenerationStatus.COMPLETED,
            progress=100,
            currentStep=None,
            completedAt=time.time(),
            output=output,
        )

    def mark_failed(self, gen_id: str, error: str) -> None:
        self.update(
            gen_id,
            status=GenerationStatus.FAILED,
            currentStep=None,
            completedAt=time.time(),
            error=error,
        )

    def update_step(self, gen_id: str, step_key: str, step_status: str, message: str = "") -> None:
        """Update a single step within the steps list."""
        with self._lock:
            all_items = self._read_all_unlocked()
            record = all_items.get(gen_id)
            if not isinstance(record, dict):
                return
            steps = record.get("steps", [])
            for step in steps:
                if step.get("key") == step_key:
                    step["status"] = step_status
                    step["message"] = message
                    break
            record["steps"] = steps
            # Auto-calculate progress from steps
            total = len(steps) if steps else 1
            completed = sum(1 for s in steps if s.get("status") == "completed")
            record["progress"] = int((completed / total) * 100)
            if step_status == "running":
                record["currentStep"] = step_key
            all_items[gen_id] = record
            self._write_all_unlocked(all_items)


# Singleton
generation_store = GenerationStore(GENERATION_METADATA_FILE)
