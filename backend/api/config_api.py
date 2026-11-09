"""Config API: get/update filter selections."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from state import AppState

router = APIRouter(prefix="/api/config", tags=["config"])


class SelectionsUpdate(BaseModel):
    selected_galleries: list[str] | None = None
    selected_studios: list[str] | None = None
    selected_tags: list[str] | None = None
    selected_cast: list[str] | None = None


def _config_response(app: AppState) -> dict[str, Any]:
    return {
        "galleries": app.all_gallery_names(),
        "studios": app.all_studios(),
        "tags": app.all_tags(),
        "cast": app.all_cast(),
        "selected_galleries": sorted(app.selected_galleries),
        "selected_studios": sorted(app.selected_studios),
        "selected_tags": sorted(app.selected_tags),
        "selected_cast": sorted(app.selected_cast),
        "combination_count": len(app.combinations),
        "sample_combinations": [
            {
                "video": c.video.filename,
                "gallery": c.gallery.name,
            }
            for c in app.combinations[:10]
        ],
    }


def create_router(app_state: AppState) -> APIRouter:
    @router.get("")
    def get_config():
        return _config_response(app_state)

    @router.post("")
    def update_config(body: SelectionsUpdate):
        if body.selected_galleries is not None:
            app_state.selected_galleries = set(body.selected_galleries)
        if body.selected_studios is not None:
            app_state.selected_studios = set(body.selected_studios)
        if body.selected_tags is not None:
            app_state.selected_tags = set(body.selected_tags)
        if body.selected_cast is not None:
            app_state.selected_cast = set(body.selected_cast)

        app_state.regenerate_combinations()
        return _config_response(app_state)

    return router
