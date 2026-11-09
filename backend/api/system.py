"""Startup status, reload and library settings."""

from __future__ import annotations

from fastapi import APIRouter

from config import config_path
from pipeline import Pipeline
from state import AppState


def create_router(state: AppState, pipeline: Pipeline) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["system"])

    @router.get("/status")
    def status() -> dict:
        s = state.startup
        path = config_path()
        return {
            "phase": s.phase,
            "step": s.step,
            "detail": s.detail,
            "fraction": s.fraction,
            "error": s.error,
            "configPath": str(path),
            "configExists": path.is_file(),
            "revision": state.revision,
            "library": {"videos": len(state.videos), "galleries": len(state.galleries)},
        }

    @router.post("/reload")
    def reload() -> dict:
        return {"started": pipeline.start()}

    @router.get("/settings")
    def settings() -> dict:
        config = state.config
        return {
            "configPath": str(config_path()),
            "videosPath": config.videosPath if config else None,
            "galleriesPath": config.galleriesPath if config else None,
        }

    return router
