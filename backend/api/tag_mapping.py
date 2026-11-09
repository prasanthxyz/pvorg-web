"""Tag mapping API: view and update video-tag associations."""

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
router = APIRouter(prefix="/api/tag-mapping", tags=["tag-mapping"])


def _media_url(absolute_path: str) -> str:
    encoded = base64.urlsafe_b64encode(absolute_path.encode()).decode()
    return f"/api/media?path={encoded}"


class SaveTagMappingRequest(BaseModel):
    mappings: dict[str, dict[str, str]]


def create_router(app_state: AppState) -> APIRouter:
    @router.get("")
    def get_tag_mapping(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        hide_decided: bool = Query(True),
    ) -> dict[str, Any]:
        if not app_state.config:
            return {
                "total": 0,
                "page": 1,
                "page_size": page_size,
                "tags": [],
                "videos": [],
            }

        videos_path = app_state.config.videosPath
        all_tags = sorted(app_state.config.tags)
        if not all_tags:
            return {
                "total": 0,
                "page": 1,
                "page_size": page_size,
                "tags": [],
                "videos": [],
            }

        video_rows: list[dict[str, Any]] = []
        for v in app_state.videos:
            relation: VideoRelation = app_state.config.videoRelations.get(
                v.filename,
                VideoRelation(),
            )

            tag_map: dict[str, str] = {}
            for t in all_tags:
                if t in relation.tags:
                    tag_map[t] = "yes"
                elif t in relation.excludedTags:
                    tag_map[t] = "no"
                else:
                    tag_map[t] = "undecided"

            if hide_decided and all(s != "undecided" for s in tag_map.values()):
                continue

            video_rows.append(
                {
                    "filename": v.filename,
                    "title": v.title,
                    "studio": v.studio,
                    "tgp_url": _media_url(
                        str(Path(videos_path) / "img" / f"{v.filename}.jpg")
                    ),
                    "tag_map": tag_map,
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
            "tags": all_tags,
            "videos": video_rows[start:end],
        }

    @router.post("")
    def save_tag_mapping(body: SaveTagMappingRequest) -> dict[str, Any]:
        if not app_state.config:
            return {"updated": 0}

        with open(CONFIG_PATH, "r") as f:
            config_data = json.load(f)

        relations = config_data.setdefault("videoRelations", {})
        all_tags = sorted(app_state.config.tags)
        tag_set = set(all_tags)
        gallery_names = sorted(g.name for g in app_state.galleries)
        updated = 0

        for filename, tag_map in body.mappings.items():
            rel = relations.get(filename)
            if isinstance(rel, dict):
                yes_tags = set(rel.get("tags") or [])
                no_tags = set(rel.get("excludedTags") or [])
                galleries = rel.get("galleries") or []
                excluded_galleries = rel.get("excludedGalleries") or []
            else:
                # Missing relation defaults to undecided for mapper state.
                yes_tags = set()
                no_tags: set[str] = set()
                galleries = []
                excluded_galleries: list[str] = []

            for tag_name, state in tag_map.items():
                if tag_name not in tag_set:
                    continue
                if state == "yes":
                    yes_tags.add(tag_name)
                    no_tags.discard(tag_name)
                elif state == "no":
                    no_tags.add(tag_name)
                    yes_tags.discard(tag_name)
                elif state == "undecided":
                    yes_tags.discard(tag_name)
                    no_tags.discard(tag_name)

            relations[filename] = {
                "galleries": galleries if isinstance(galleries, list) else list(galleries),
                "excludedGalleries": excluded_galleries if isinstance(excluded_galleries, list) else list(excluded_galleries),
                "tags": [t for t in all_tags if t in yes_tags],
                "excludedTags": [t for t in all_tags if t in no_tags],
            }
            updated += 1

        with open(CONFIG_PATH, "w") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        app_state.load()

        return {"updated": updated}

    return router
