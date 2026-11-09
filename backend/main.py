"""FastAPI application entry point."""

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.combinations import create_router as combinations_router
from api.config_api import create_router as config_router
from api.gallery_mapping import create_router as gallery_mapping_router
from api.media import create_router as media_router
from api.tag_mapping import create_router as tag_mapping_router
from api.videos import create_router as videos_router
from cache import MetadataCache
from cleanup import (
    cleanup_config_entries,
    cleanup_orphaned_assets,
    normalize_config_entries,
)
from config import CONFIG_PATH
from preprocessor import run_preprocessing
from state import AppState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app_state = AppState()
pipeline_lock = threading.Lock()
pipeline_state_lock = threading.Lock()
pipeline_running = threading.Event()


def _startup_pipeline() -> None:
    """Full startup: validate, cleanup, preprocess, report."""
    with pipeline_lock:
        if not app_state.config:
            return

        videos_path = app_state.config.videosPath
        gallery_names = [g.name for g in app_state.galleries]
        valid_filenames = {v.filename for v in app_state.videos}

        entries_normalized = normalize_config_entries(CONFIG_PATH)

        orphans_removed = cleanup_orphaned_assets(videos_path, valid_filenames)

        config_entries_removed = cleanup_config_entries(CONFIG_PATH, videos_path)

        if config_entries_removed > 0 or entries_normalized > 0:
            app_state.load()

        cache = MetadataCache(Path(videos_path) / "cache.json")
        run_preprocessing(
            videos=app_state.videos,
            videos_path=videos_path,
            cache=cache,
            progress_callback=lambda msg: setattr(app_state, "preprocessing_progress", msg),
            fail_on_error=True,
        )

        report = {
            "invalid_filenames_skipped": len(app_state.skipped_files),
            "entries_normalized": entries_normalized,
            "orphan_assets_removed": orphans_removed,
            "stale_config_entries_removed": config_entries_removed,
        }
        app_state.startup_report = report

        logger.info(
            "\nStartup Cleanup Summary\n"
            "-----------------------\n"
            "Invalid filenames skipped:    %d\n"
            "Entries normalized:           %d\n"
            "Orphan assets removed:        %d\n"
            "Stale config entries removed: %d",
            report["invalid_filenames_skipped"],
            report["entries_normalized"],
            report["orphan_assets_removed"],
            report["stale_config_entries_removed"],
        )

        app_state.ready = True


def _run_pipeline_or_die() -> None:
    try:
        _startup_pipeline()
    except Exception:
        logger.exception("Startup pipeline failed. Terminating process.")
        os._exit(1)
    finally:
        pipeline_running.clear()


def _claim_pipeline_slot() -> bool:
    with pipeline_state_lock:
        if pipeline_running.is_set():
            return False
        pipeline_running.set()
        return True


def _start_pipeline_worker() -> None:
    startup_thread = threading.Thread(target=_run_pipeline_or_die, daemon=True)
    startup_thread.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.load()
    if _claim_pipeline_slot():
        _start_pipeline_worker()
    else:
        logger.warning("Startup pipeline already running; skipped duplicate start")

    yield


app = FastAPI(title="pvorg", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def get_status():
    return {
        "ready": app_state.ready,
        "progress": app_state.preprocessing_progress,
        "video_count": len(app_state.videos),
        "gallery_count": len(app_state.galleries),
        "combination_count": len(app_state.combinations),
        "startup_report": app_state.startup_report,
    }


@app.post("/api/shuffle")
def shuffle():
    app_state.shuffle_combinations()
    return {"total": len(app_state.combinations)}


@app.post("/api/reload")
def reload_config():
    if not _claim_pipeline_slot():
        return {"status": "already_running"}
    try:
        app_state.load()
        app_state.ready = False
        app_state.preprocessing_progress = "Reloading preprocessing..."
        _start_pipeline_worker()
        return {"status": "reloading"}
    except Exception:
        pipeline_running.clear()
        raise


def run() -> None:
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000)


app.include_router(combinations_router(app_state))
app.include_router(config_router(app_state))
app.include_router(media_router(app_state))
app.include_router(videos_router(app_state))
app.include_router(gallery_mapping_router(app_state))
app.include_router(tag_mapping_router(app_state))

# Serve the React build if it exists
frontend_build = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_build.is_dir():
    app.mount(
        "/", StaticFiles(directory=str(frontend_build), html=True), name="frontend"
    )
