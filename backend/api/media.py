"""Media: contact sheets, gallery images, videos and sprites, addressed by library names.

Only files that belong to the scanned library are served, so arbitrary paths
can't be requested. Images are downsized to the requested standard size.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api.common import require_ready, sheet_path
from state import AppState
from thumbnails import thumbnail

IMAGE_CACHE = "private, max-age=31536000, immutable"  # URLs carry a version token


def _image_response(source: Path, size: int | None) -> FileResponse:
    target = thumbnail(source, size) if size else source
    media_type = "image/jpeg" if target != source else (mimetypes.guess_type(source.name)[0] or "image/jpeg")
    return FileResponse(target, media_type=media_type, headers={"Cache-Control": IMAGE_CACHE})


def create_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api/media", tags=["media"])

    def known_video(filename: str) -> None:
        if filename not in {v.filename for v in state.videos}:
            raise HTTPException(status_code=404, detail="Unknown video")

    @router.get("/sheet/{filename}")
    def sheet(filename: str, size: int | None = Query(None, ge=16, le=8192)) -> FileResponse:
        require_ready(state)
        known_video(filename)
        path = sheet_path(state, filename)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="No contact sheet")
        return _image_response(path, size)

    @router.get("/gallery/{gallery}/{image}")
    def gallery_image(gallery: str, image: str, size: int | None = Query(None, ge=16, le=8192)) -> FileResponse:
        require_ready(state)
        match = next((g for g in state.galleries if g.name == gallery), None)
        path = next((Path(p) for p in match.image_files if Path(p).name == image), None) if match else None
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="Unknown image")
        return _image_response(path, size)

    @router.get("/video/{filename}")
    def video(filename: str) -> FileResponse:
        """Range requests are supported, so the browser can seek."""
        require_ready(state)
        known_video(filename)
        assert state.config is not None
        path = Path(state.config.videosPath) / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Video file missing")
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    @router.get("/sprite/{name}")
    def sprite(name: str) -> FileResponse:
        require_ready(state)
        filename, _, ext = name.rpartition(".")
        if ext not in ("jpg", "vtt"):
            raise HTTPException(status_code=404, detail="Unknown sprite")
        known_video(filename)
        assert state.config is not None
        path = Path(state.config.videosPath) / "sprite" / f"{filename}_sprite.{ext}"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="No sprite")
        return FileResponse(path, media_type="image/jpeg" if ext == "jpg" else "text/vtt")

    return router
