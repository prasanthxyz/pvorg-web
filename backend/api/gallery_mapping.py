"""Gallery mapping API: view and update video-gallery associations."""

from __future__ import annotations

import base64
import json
import logging
import math
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from config import CONFIG_PATH, VideoRelation
from state import AppState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gallery-mapping", tags=["gallery-mapping"])


def _media_url(absolute_path: str) -> str:
    encoded = base64.urlsafe_b64encode(absolute_path.encode()).decode()
    return f"/api/media?path={encoded}"


class SaveMappingRequest(BaseModel):
    mappings: dict[str, dict[str, str]]


def create_router(app_state: AppState) -> APIRouter:
    @router.get("")
    def get_gallery_mapping(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        hide_decided: bool = Query(True),
    ) -> dict[str, Any]:
        if not app_state.config:
            return {
                "total": 0,
                "page": 1,
                "page_size": page_size,
                "galleries": [],
                "videos": [],
            }

        videos_path = app_state.config.videosPath
        gallery_names = sorted(g.name for g in app_state.galleries)
        if not gallery_names:
            return {
                "total": 0,
                "page": 1,
                "page_size": page_size,
                "galleries": [],
                "videos": [],
            }

        video_rows: list[dict[str, Any]] = []
        for v in app_state.videos:
            relation: VideoRelation = app_state.config.videoRelations.get(
                v.filename,
                VideoRelation(),
            )

            gallery_map: dict[str, str] = {}
            for g in gallery_names:
                if g in relation.galleries:
                    gallery_map[g] = "yes"
                elif g in relation.excludedGalleries:
                    gallery_map[g] = "no"
                else:
                    gallery_map[g] = "undecided"

            if hide_decided and all(s != "undecided" for s in gallery_map.values()):
                continue

            video_rows.append(
                {
                    "filename": v.filename,
                    "title": v.title,
                    "studio": v.studio,
                    "tgp_url": _media_url(
                        str(Path(videos_path) / "img" / f"{v.filename}.jpg")
                    ),
                    "gallery_map": gallery_map,
                }
            )

        total = len(video_rows)
        total_pages = max(1, math.ceil(total / page_size))
        page = min(page, total_pages)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "galleries": gallery_names,
            "videos": video_rows[start:end],
        }

    @router.post("")
    def save_gallery_mapping(body: SaveMappingRequest) -> dict[str, Any]:
        if not app_state.config:
            return {"updated": 0}

        with open(CONFIG_PATH, "r") as f:
            config_data = json.load(f)

        relations = config_data.setdefault("videoRelations", {})
        gallery_names = sorted(g.name for g in app_state.galleries)
        gallery_name_set = set(gallery_names)
        updated = 0

        for filename, gallery_map in body.mappings.items():
            rel = relations.get(filename)
            if isinstance(rel, dict):
                yes_galleries = set(rel.get("galleries") or [])
                no_galleries = set(rel.get("excludedGalleries") or [])
                tags = rel.get("tags") or []
                excluded_tags = rel.get("excludedTags") or []
            else:
                # Missing relation defaults to undecided for mapper state.
                yes_galleries = set()
                no_galleries = set()
                tags = []
                excluded_tags = []

            # Apply only provided gallery updates; do not overwrite unrelated decisions.
            for gallery_name, state in gallery_map.items():
                if gallery_name not in gallery_name_set:
                    continue
                if state == "yes":
                    yes_galleries.add(gallery_name)
                    no_galleries.discard(gallery_name)
                elif state == "no":
                    no_galleries.add(gallery_name)
                    yes_galleries.discard(gallery_name)
                elif state == "undecided":
                    yes_galleries.discard(gallery_name)
                    no_galleries.discard(gallery_name)

            relations[filename] = {
                "galleries": [g for g in gallery_names if g in yes_galleries],
                "excludedGalleries": [g for g in gallery_names if g in no_galleries],
                "tags": tags if isinstance(tags, list) else list(app_state.config.tags),
                "excludedTags": excluded_tags if isinstance(excluded_tags, list) else list(excluded_tags),
            }
            updated += 1

        with open(CONFIG_PATH, "w") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        app_state.load()

        return {"updated": updated}

    return router
