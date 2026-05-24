"""
JSON-backed persistence for StudyTok account plans.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import ACCOUNT_PLAN_METADATA_FILE


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AccountPlanStore:
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

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        plan = {
            **payload,
            "id": plan_id,
            "status": payload.get("status") or "draft",
            "createdAt": now,
            "updatedAt": now,
        }
        with self._lock:
            all_items = self._read_all_unlocked()
            all_items[plan_id] = plan
            self._write_all_unlocked(all_items)
        return plan

    def get(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._read_all_unlocked().get(plan_id)
            return item if isinstance(item, dict) else None

    def list_all(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._lock:
            values = [item for item in self._read_all_unlocked().values() if isinstance(item, dict)]
        values.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
        return values[:limit] if limit else values

    def update(self, plan_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            plan = all_items.get(plan_id)
            if not isinstance(plan, dict):
                return None
            plan.update(fields)
            plan["updatedAt"] = utc_now_iso()
            all_items[plan_id] = plan
            self._write_all_unlocked(all_items)
            return plan

    def update_post(self, plan_id: str, slot: int, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            plan = all_items.get(plan_id)
            if not isinstance(plan, dict):
                return None
            posts = plan.get("plannedPosts") or []
            found = False
            for post in posts:
                if isinstance(post, dict) and int(post.get("slot") or 0) == int(slot):
                    post.update(fields)
                    post["updatedAt"] = utc_now_iso()
                    found = True
                    break
            if not found:
                return None
            plan["plannedPosts"] = posts
            plan["updatedAt"] = utc_now_iso()
            all_items[plan_id] = plan
            self._write_all_unlocked(all_items)
            return plan


account_plan_store = AccountPlanStore(ACCOUNT_PLAN_METADATA_FILE)
