"""`cache.json`: per-video metadata shared with the other apps (SPEC §1.5)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import atomic_write_text

logger = logging.getLogger(__name__)


class MetadataCache:
    def __init__(self, cache_path: Path) -> None:
        self.path = cache_path
        self._data: dict[str, Any] = {}
        if cache_path.exists():
            try:
                self._data = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load %s, starting fresh: %s", cache_path, e)

    def save(self) -> None:
        atomic_write_text(self.path, json.dumps(self._data, indent=2, sort_keys=True) + "\n")

    def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = value

    def has(self, key: str) -> bool:
        return key in self._data

    def remove(self, key: str) -> bool:
        return self._data.pop(key, None) is not None
