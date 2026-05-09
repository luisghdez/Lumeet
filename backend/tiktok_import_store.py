"""
Lightweight JSON store for TikTok account import scans.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

from config import TIKTOK_IMPORT_METADATA_FILE


class TikTokImportStore:
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
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _write_all_unlocked(self, payload: Dict[str, Any]) -> None:
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def save(self, scan_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            scans = self._read_all_unlocked()
            scans[scan_id] = payload
            self._write_all_unlocked(scans)

    def get(self, scan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            scans = self._read_all_unlocked()
            item = scans.get(scan_id)
            return item if isinstance(item, dict) else None

    def list_all(self, *, limit: int = 25) -> list[Dict[str, Any]]:
        with self._lock:
            scans = [
                scan for scan in self._read_all_unlocked().values()
                if isinstance(scan, dict)
            ]
            scans.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
            return scans[:limit] if limit else scans


tiktok_import_store = TikTokImportStore(TIKTOK_IMPORT_METADATA_FILE)
