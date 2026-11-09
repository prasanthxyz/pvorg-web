"""Gallery and Tag Mapping (SPEC §6.3).

Every row is returned with its saved states; the client keeps pending changes,
the Undecided/All scope and search locally, so none of them round-trip.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from api.common import require_ready, video_payload
from relations import tri_state
from state import AppState

Kind = Literal["galleries", "tags"]
CODES = {"yes": "y", "no": "n", "undecided": "u"}


class SaveRequest(BaseModel):
    changes: dict[str, dict[str, Literal["yes", "no", "undecided"]]]


def create_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api/mapping", tags=["mapping"])

    @router.get("/{kind}")
    def get_mapping(kind: Kind) -> dict:
        require_ready(state)
        assert state.config is not None
        columns = state.columns(kind)
        rows = []
        for video in state.videos:
            relation = state.config.videoRelations.get(video.filename)
            states = "".join(CODES[tri_state(relation, kind, column)] for column in columns)
            rows.append({**video_payload(state, video, card=320), "states": states})
        return {
            "kind": kind,
            "columns": columns,
            "rows": rows,
            "galleriesPath": state.config.galleriesPath,
            "revision": state.revision,
        }

    @router.post("/{kind}")
    def save_mapping(kind: Kind, body: SaveRequest) -> dict:
        require_ready(state)
        return {"saved": state.save_mappings(kind, body.changes)}

    return router
