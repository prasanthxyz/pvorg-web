"""Seek-preview sprite failures (SPEC §14), remembered so they aren't retried on every launch.

A video whose sprite can't be made is remembered by path, size and modification time, and
isn't tried again until the file changes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from config import atomic_write_text
from thumbnails import cache_root

logger = logging.getLogger(__name__)


def default_failures_path() -> Path:
    return cache_root() / "sprite-failures.json"


class FailureLog:
    """Videos whose sprite failed, keyed by absolute path, with the file's size and mtime."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, dict[str, int]] = {}
        self._dirty = False
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._data = data
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Ignoring unreadable %s: %s", path, e)

    @staticmethod
    def _stamp(video: Path) -> dict[str, int] | None:
        try:
            st = video.stat()
        except OSError:
            return None
        return {"size": st.st_size, "mtimeNs": st.st_mtime_ns}

    def known(self, video: Path) -> bool:
        """True if this exact file (same size and mtime) failed before."""
        entry = self._data.get(str(video.resolve()))
        return entry is not None and entry == self._stamp(video)

    def remember(self, video: Path) -> None:
        stamp = self._stamp(video)
        if stamp is not None:
            self._data[str(video.resolve())] = stamp
            self._dirty = True

    def forget(self, video: Path) -> None:
        if self._data.pop(str(video.resolve()), None) is not None:
            self._dirty = True

    def save(self) -> None:
        if self._dirty:
            atomic_write_text(self.path, json.dumps(self._data, indent=2, sort_keys=True) + "\n")
            self._dirty = False
