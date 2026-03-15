"""
Lightweight JSON metadata store for generated carousels.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

from config import CAROUSEL_METADATA_FILE


class CarouselMetadataStore:
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

    def save(self, carousel_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            all_items = self._read_all_unlocked()
            all_items[carousel_id] = payload
            self._write_all_unlocked(all_items)

    def get(self, carousel_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            item = all_items.get(carousel_id)
            return item if isinstance(item, dict) else None

    def list_all(self) -> list[Dict[str, Any]]:
        with self._lock:
            all_items = self._read_all_unlocked()
            values = [v for v in all_items.values() if isinstance(v, dict)]
            return sorted(values, key=lambda x: x.get("createdAt", ""), reverse=True)


carousel_metadata_store = CarouselMetadataStore(CAROUSEL_METADATA_FILE)
