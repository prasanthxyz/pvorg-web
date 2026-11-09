"""Helpers shared by the API routers: readiness, media URLs and video payloads."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException

from scanner import Video
from state import AppState


def require_ready(state: AppState) -> None:
    if state.startup.phase != "ready" or state.config is None:
        raise HTTPException(status_code=503, detail="The library is still loading.")


def _version(path: Path) -> str:
    """Cache-busting token: changes whenever the file is regenerated."""
    try:
        return str(path.stat().st_mtime_ns)
    except OSError:
        return "0"


def sheet_path(state: AppState, filename: str) -> Path:
    assert state.config is not None
    return Path(state.config.videosPath) / "img" / f"{filename}.jpg"


def sheet_url(state: AppState, filename: str, size: int | None) -> str | None:
    path = sheet_path(state, filename)
    if not path.is_file():
        return None
    query = f"v={_version(path)}" + (f"&size={size}" if size else "")
    return f"/api/media/sheet/{quote(filename)}?{query}"


def gallery_image_url(gallery: str, image_path: str, size: int | None) -> str:
    path = Path(image_path)
    query = f"v={_version(path)}" + (f"&size={size}" if size else "")
    return f"/api/media/gallery/{quote(gallery)}/{quote(path.name)}?{query}"


def video_payload(state: AppState, video: Video, *, card: int = 720, preview: int = 1920) -> dict:
    return {
        "filename": video.filename,
        "title": video.display_title,
        "credits": video.credits,
        "studio": video.studio,
        "actors": video.actors,
        "thumbUrl": sheet_url(state, video.filename, card),
        "previewUrl": sheet_url(state, video.filename, preview),
    }
