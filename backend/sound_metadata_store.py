"""
Lightweight JSON metadata store for extracted audio / sound files uploaded to GCS.

Each sound record tracks an audio file (typically extracted from the original
reference video) that can be selected when remixing hook videos.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from config import SOUND_METADATA_FILE


class SoundMetadataStore:
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

    def save(self, sound_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            all_items = self._read_all_unlocked()
            all_items[sound_id] = payload
            self._write_all_unlocked(all_items)

    def get(self, sound_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            item = all_items.get(sound_id)
            return item if isinstance(item, dict) else None

    def update(self, sound_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Update arbitrary fields on a sound record and persist."""
        with self._lock:
            all_items = self._read_all_unlocked()
            record = all_items.get(sound_id)
            if not isinstance(record, dict):
                return None
            record.update(fields)
            all_items[sound_id] = record
            self._write_all_unlocked(all_items)
            return record

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            values = [v for v in all_items.values() if isinstance(v, dict)]
            return sorted(values, key=lambda x: x.get("createdAt", ""), reverse=True)


sound_metadata_store = SoundMetadataStore(SOUND_METADATA_FILE)
