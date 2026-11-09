"""Filters: vocabularies, selections, and the preview with Up Next (SPEC §6.1)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from api.common import require_ready, sheet_url
from state import AppState

UP_NEXT = 10


class FiltersUpdate(BaseModel):
    galleries: list[str] | None = None
    studios: list[str] | None = None
    tags: list[str] | None = None
    cast: list[str] | None = None


def filters_payload(state: AppState) -> dict:
    f = state.filters
    total = len(state.combinations)
    up_next = []
    for offset in range(min(UP_NEXT, total)):
        index = (state.position + offset) % total
        c = state.combinations[index]
        up_next.append({
            "index": index,
            "title": c.video.display_title,
            "gallery": c.gallery.name,
            "thumbUrl": sheet_url(state, c.video.filename, 320),
        })
    return {
        "sections": {
            "galleries": {"items": state.label_sorted(state.gallery_names(), False), "selected": sorted(f.galleries)},
            "studios": {"items": state.label_sorted(state.all_studios(), True), "selected": sorted(f.studios)},
            "tags": {"items": state.label_sorted(state.all_tags(), False), "selected": sorted(f.tags)},
            "cast": {"items": state.label_sorted(state.all_cast(), True), "selected": sorted(f.cast)},
        },
        "isDefault": state.filters_are_default(),
        "count": total,
        "videoCount": len({c.video.filename for c in state.combinations}),
        "galleryCount": len({c.gallery.name for c in state.combinations}),
        "upNext": up_next,
        "revision": state.revision,
    }


def create_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api/filters", tags=["filters"])

    @router.get("")
    def get_filters() -> dict:
        require_ready(state)
        return filters_payload(state)

    @router.put("")
    def update_filters(body: FiltersUpdate) -> dict:
        require_ready(state)
        state.set_filters(galleries=body.galleries, studios=body.studios, tags=body.tags, cast=body.cast)
        return filters_payload(state)

    @router.post("/reset")
    def reset_filters() -> dict:
        require_ready(state)
        state.reset_filters()
        return filters_payload(state)

    return router
