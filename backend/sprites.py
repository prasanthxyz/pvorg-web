"""Seek-preview sprites (SPEC §14), made in the background once the library is ready.

Sprites are the web app's own extra: the viewer works without them (the scrubber just has no
frame preview), so they never hold up startup. A video whose sprite can't be made is
remembered by path, size and modification time, and isn't tried again until the file changes.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from pathlib import Path

import preprocessor
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


class SpriteWorker:
    """One background thread making missing sprites. `start` replaces any run in progress."""

    def __init__(self, failures_path: Path | None = None) -> None:
        self._failures_path = failures_path
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self, videos_path: str, filenames: list[str]) -> None:
        with self._lock:
            self._stop_locked()
            stop = threading.Event()
            self._stop = stop
            self._thread = threading.Thread(
                target=self._run, args=(Path(videos_path), list(filenames), stop),
                daemon=True, name="pvorg-sprites",
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Cancel the current run and wait for it; any running ffmpeg is killed."""
        with self._lock:
            self._stop_locked(timeout)

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _stop_locked(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None

    def _run(self, videos_dir: Path, filenames: list[str], stop: threading.Event) -> None:
        if not (shutil.which(preprocessor.FFMPEG) and shutil.which(preprocessor.FFPROBE)):
            logger.info("Skipping seek-preview sprites: ffmpeg or ffprobe isn't installed")
            return
        sprite_dir = videos_dir / "sprite"
        pending = [name for name in filenames
                   if not ((sprite_dir / f"{name}_sprite.jpg").is_file()
                           and (sprite_dir / f"{name}_sprite.vtt").is_file())]
        if not pending:
            return

        failures = FailureLog(self._failures_path or default_failures_path())
        made = failed = skipped = 0
        logger.info("Making seek-preview sprites for %d video(s) in the background", len(pending))
        try:
            for name in pending:
                if stop.is_set():
                    return
                video = videos_dir / name
                if not video.is_file():
                    continue
                if failures.known(video):
                    skipped += 1
                    continue
                try:
                    ok = preprocessor.generate_sprite(video, sprite_dir, name, stop=stop)
                except preprocessor.SpriteCancelled:
                    return
                except OSError as e:
                    logger.error("Stopping sprite generation: couldn't run ffmpeg: %s", e)
                    return
                if not video.exists():
                    # Deleted while its sprite was being made: don't leave an orphan behind.
                    for ext in ("jpg", "vtt"):
                        (sprite_dir / f"{name}_sprite.{ext}").unlink(missing_ok=True)
                    continue
                if ok:
                    made += 1
                    failures.forget(video)
                else:
                    failed += 1
                    failures.remember(video)
                    failures.save()
        finally:
            failures.save()
            logger.info("Sprites: %d made, %d failed, %d skipped after an earlier failure%s",
                        made, failed, skipped, " (stopped early)" if stop.is_set() else "")
