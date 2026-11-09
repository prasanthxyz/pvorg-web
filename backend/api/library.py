"""Library: every valid video, skipped files, and permanent deletion (SPEC §6.2, §3.7)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from api.common import require_ready, video_payload
from state import AppState


class DeleteRequest(BaseModel):
    filenames: list[str]


def create_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api/library", tags=["library"])

    @router.get("")
    def get_library() -> dict:
        require_ready(state)
        assert state.config is not None
        return {
            "videos": [video_payload(state, v) for v in state.videos],
            "skipped": [{"filename": s.filename, "reasons": s.reasons} for s in state.skipped],
            "videosPath": state.config.videosPath,
            "revision": state.revision,
        }

    @router.post("/delete")
    def delete(body: DeleteRequest) -> dict:
        require_ready(state)
        result = state.delete_videos(body.filenames)
        return {"deleted": result.deleted, "errors": result.errors}

    return router
