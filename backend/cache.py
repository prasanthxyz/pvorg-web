"""Simple JSON file cache for video metadata."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MetadataCache:
    def __init__(self, cache_path: Path) -> None:
        self.path = cache_path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    self._data = json.load(f)
                logger.info("Loaded cache with %d entries from %s", len(self._data), self.path)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load cache, starting fresh: %s", e)
                self._data = {}
        else:
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = value

    def has(self, key: str) -> bool:
        return key in self._data
