"""Startup and reload (SPEC §3.2): named steps, determinate preview progress, recoverable errors."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from cache import MetadataCache
from cleanup import cleanup_orphaned_assets
from config import ConfigError, config_path, load_config, normalize_relations, save_config
from preprocessor import SpriteCancelled, run_preprocessing
from scanner import scan_galleries, scan_videos
from sprites import FailureLog, default_failures_path
from state import AppState, Startup

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, state: AppState, *, preprocess: bool = True, sprite_failures_path: Path | None = None) -> None:
        self.state = state
        self.preprocess = preprocess
        self.sprite_failures_path = sprite_failures_path
        self._stop = threading.Event()
        self._running = threading.Lock()

    def start(self) -> bool:
        """Start a run in the background. Returns False if one is already running."""
        if not self._running.acquire(blocking=False):
            return False
        self.state.startup = Startup()
        threading.Thread(target=self._run_and_release, daemon=True, name="pvorg-startup").start()
        return True

    def run_blocking(self) -> None:
        with self._running:
            self.state.startup = Startup()
            self._run()

    def _run_and_release(self) -> None:
        try:
            self._run()
        finally:
            self._running.release()

    def _step(self, title: str, detail: str | None = None, fraction: float | None = None) -> None:
        self.state.startup = Startup(phase="loading", step=title, detail=detail, fraction=fraction)

    def shutdown(self, timeout: float = 5.0) -> None:
        """When the server stops: cancel a run in progress, and wait so its ffmpeg is killed, not orphaned."""
        self._stop.set()
        if self._running.acquire(timeout=timeout):
            self._running.release()

    def _run(self) -> None:
        try:
            self._step("Loading Configuration", str(config_path()))
            config = load_config()

            self._step("Scanning Library", config.videosPath)
            galleries = scan_galleries(config)
            videos, skipped = scan_videos(config, [g.name for g in galleries])

            self._step("Updating pvorg.json")
            if normalize_relations(config):
                save_config(config)

            self._step("Cleaning Up Previews")
            cleanup_orphaned_assets(config.videosPath, {v.filename for v in videos})

            if self.preprocess:
                self._step("Preparing Previews", fraction=0)

                def progress(done: int, total: int, filename: str) -> None:
                    self._step("Preparing Previews", f"{done + 1} of {total} · {filename}", done / max(total, 1))

                run_preprocessing(videos, config.videosPath, MetadataCache(Path(config.videosPath) / "cache.json"),
                                  progress,
                                  sprite_failures=FailureLog(self.sprite_failures_path or default_failures_path()),
                                  stop=self._stop)

            self.state.apply_library(config, galleries, videos, skipped, reset_filters=True)
            self.state.startup = Startup(phase="ready", step="Ready")
            logger.info("Library ready: %d videos, %d galleries, %d skipped", len(videos), len(galleries),
                        len(skipped))
        except SpriteCancelled:
            logger.info("Startup stopped: the server is shutting down")
        except ConfigError as e:
            logger.error("Startup failed: %s", e)
            self.state.startup = Startup(phase="error", step="Error", error=str(e))
        except Exception as e:  # noqa: BLE001 — any failure must reach the error screen
            logger.exception("Startup failed")
            self.state.startup = Startup(phase="error", step="Error", error=str(e) or e.__class__.__name__)
