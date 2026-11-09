"""Viewer: the current combination, navigation, and Exclude Pairing with undo (SPEC §5, §3.6)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.common import gallery_image_url, require_ready, sheet_url
from state import AppState


class MoveRequest(BaseModel):
    delta: int | None = None
    index: int | None = None


class ExcludeRequest(BaseModel):
    filename: str
    gallery: str


def viewer_payload(state: AppState) -> dict:
    assert state.config is not None
    total = len(state.combinations)
    current = state.current()
    payload: dict = {"position": state.position, "total": total, "revision": state.revision,
                     "current": None, "nextSheetUrl": None, "empty": None}
    if current is None:
        if not state.videos:
            reason = "noVideos"
        elif not state.galleries:
            reason = "noGalleries"
        elif not state.filters_are_default():
            reason = "filters"
        else:
            reason = "mappings"
        payload["empty"] = {
            "reason": reason,
            "videosPath": state.config.videosPath,
            "galleriesPath": state.config.galleriesPath,
            "tagsRequired": bool(state.filters.tags),
        }
        return payload

    video, gallery = current.video, current.gallery
    sprite_dir = Path(state.config.videosPath) / "sprite"
    has_sprite = (sprite_dir / f"{video.filename}_sprite.jpg").is_file() and \
        (sprite_dir / f"{video.filename}_sprite.vtt").is_file()
    payload["current"] = {
        "video": {
            "filename": video.filename,
            "title": video.display_title,
            "credits": video.credits,
            "extension": Path(video.filename).suffix.lstrip(".").lower(),
            "sheetUrl": sheet_url(state, video.filename, None),
            "videoUrl": f"/api/media/video/{quote(video.filename)}",
            "spriteUrl": f"/api/media/sprite/{quote(video.filename)}.jpg" if has_sprite else None,
            "vttUrl": f"/api/media/sprite/{quote(video.filename)}.vtt" if has_sprite else None,
        },
        "gallery": {
            "name": gallery.name,
            "images": [gallery_image_url(gallery.name, image, 1920) for image in gallery.image_files],
        },
    }
    if total > 1:
        upcoming = state.combinations[(state.position + 1) % total]
        payload["nextSheetUrl"] = sheet_url(state, upcoming.video.filename, None)
    return payload


def create_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["viewer"])

    @router.get("/viewer")
    def get_viewer() -> dict:
        require_ready(state)
        return viewer_payload(state)

    @router.post("/viewer/move")
    def move(body: MoveRequest) -> dict:
        require_ready(state)
        if body.index is not None:
            state.goto(body.index)
        elif body.delta:
            state.move(body.delta)
        return viewer_payload(state)

    @router.post("/pairings/exclude")
    def exclude(body: ExcludeRequest) -> dict:
        """Exclude a specific pairing. The client names it, so it excludes exactly what it shows."""
        require_ready(state)
        if body.filename not in {v.filename for v in state.videos}:
            raise HTTPException(status_code=404, detail=f"Unknown video: {body.filename}")
        if body.gallery not in set(state.gallery_names()):
            raise HTTPException(status_code=404, detail=f"Unknown gallery: {body.gallery}")
        exclusion = state.exclude_pairing(body.filename, body.gallery)
        return {"exclusionId": exclusion.id, "viewer": viewer_payload(state)}

    @router.post("/pairings/restore/{exclusion_id}")
    def restore(exclusion_id: str) -> dict:
        require_ready(state)
        exclusion = state.exclusions.get(exclusion_id)
        if exclusion is None:
            raise HTTPException(status_code=404, detail="That change can no longer be undone.")
        state.restore_pairing(exclusion)
        return {"viewer": viewer_payload(state)}

    return router
