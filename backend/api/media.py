"""Serve media files from absolute paths with directory allowlist validation."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from state import AppState

router = APIRouter(prefix="/api/media", tags=["media"])


def _is_path_allowed(file_path: Path, allowed_roots: list[Path]) -> bool:
    resolved = file_path.resolve()
    return any(
        resolved == root or root in resolved.parents
        for root in allowed_roots
    )


def create_router(app_state: AppState) -> APIRouter:
    @router.get("")
    def serve_media(path: str = Query(..., description="Base64url-encoded absolute file path")):
        try:
            decoded = base64.urlsafe_b64decode(path.encode()).decode()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid path encoding")

        file_path = Path(decoded)
        if not file_path.is_absolute():
            raise HTTPException(status_code=400, detail="Path must be absolute")

        allowed_roots: list[Path] = []
        if app_state.config:
            allowed_roots.append(Path(app_state.config.videosPath).resolve())
            allowed_roots.append(Path(app_state.config.galleriesPath).resolve())

        if not _is_path_allowed(file_path, allowed_roots):
            raise HTTPException(status_code=403, detail="Access denied")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        return FileResponse(
            str(file_path),
            media_type=content_type,
            filename=file_path.name,
        )

    return router
