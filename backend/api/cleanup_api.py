"""Clean Up Stale Entries: preview first, then remove (SPEC §3.5, §6.4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.common import require_ready
from state import AppState


class RemoveRequest(BaseModel):
    entries: list[str]


def create_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api/cleanup", tags=["cleanup"])

    @router.get("")
    def preview() -> dict:
        require_ready(state)
        try:
            p = state.stale_preview()
        except FileNotFoundError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return {
            "videosPath": p.videos_path,
            "videoFileCount": p.video_file_count,
            "relationCount": p.relation_count,
            "staleEntries": p.stale_entries,
            "highRisk": p.high_risk,
        }

    @router.post("")
    def remove(body: RemoveRequest) -> dict:
        require_ready(state)
        return {"removed": state.remove_stale(body.entries)}

    return router
