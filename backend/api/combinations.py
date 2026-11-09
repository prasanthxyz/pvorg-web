"""Combination API endpoints."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from state import AppState

router = APIRouter(prefix="/api/combinations", tags=["combinations"])


def _media_url(absolute_path: str) -> str:
    encoded = base64.urlsafe_b64encode(absolute_path.encode()).decode()
    return f"/api/media?path={encoded}"


def _combination_summary(app: AppState, idx: int) -> dict[str, Any]:
    c = app.combinations[idx]
    videos_path = app.config.videosPath if app.config else ""
    tgp_path = str(Path(videos_path) / "img" / f"{c.video.filename}.jpg")

    return {
        "index": idx,
        "video": {
            "filename": c.video.filename,
            "studio": c.video.studio,
            "actors": c.video.actors,
            "title": c.video.title,
        },
        "gallery": {
            "name": c.gallery.name,
        },
        "tgp_url": _media_url(tgp_path),
    }


def _combination_detail(app: AppState, idx: int) -> dict[str, Any]:
    c = app.combinations[idx]
    videos_path = app.config.videosPath if app.config else ""
    video_file = str(Path(videos_path) / c.video.filename)
    tgp_path = str(Path(videos_path) / "img" / f"{c.video.filename}.jpg")
    sprite_path = str(Path(videos_path) / "sprite" / f"{c.video.filename}_sprite.jpg")
    sprite_vtt_path = str(Path(videos_path) / "sprite" / f"{c.video.filename}_sprite.vtt")

    return {
        "index": idx,
        "total": len(app.combinations),
        "video": {
            "filename": c.video.filename,
            "studio": c.video.studio,
            "actors": c.video.actors,
            "title": c.video.title,
            "url": _media_url(video_file),
            "tgp_url": _media_url(tgp_path),
            "sprite_url": _media_url(sprite_path),
            "sprite_vtt_url": _media_url(sprite_vtt_path),
        },
        "gallery": {
            "name": c.gallery.name,
            "images": [_media_url(img) for img in c.gallery.image_files],
        },
    }


def create_router(app_state: AppState) -> APIRouter:
    @router.get("")
    def list_combinations():
        return {
            "total": len(app_state.combinations),
            "combinations": [
                _combination_summary(app_state, i)
                for i in range(len(app_state.combinations))
            ],
        }

    @router.get("/{index}")
    def get_combination(index: int):
        if not app_state.combinations or index < 0 or index >= len(app_state.combinations):
            raise HTTPException(status_code=404, detail="Combination not found")
        return _combination_detail(app_state, index)

    return router
