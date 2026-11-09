"""Video listing and batch deletion API."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from config import CONFIG_PATH
from state import AppState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["videos"])


def _media_url(absolute_path: str) -> str:
    encoded = base64.urlsafe_b64encode(absolute_path.encode()).decode()
    return f"/api/media?path={encoded}"


class DeleteRequest(BaseModel):
    filenames: list[str]


def create_router(app_state: AppState) -> APIRouter:
    @router.get("")
    def list_videos(
        page: int = Query(1, ge=1),
        page_size: int = Query(24, ge=1, le=100),
    ) -> dict[str, Any]:
        videos_path = app_state.config.videosPath if app_state.config else ""
        all_videos = [
            {
                "filename": v.filename,
                "studio": v.studio,
                "title": v.title,
                "actors": v.actors,
                "tgp_url": _media_url(
                    str(Path(videos_path) / "img" / f"{v.filename}.jpg")
                ),
            }
            for v in app_state.videos
        ]

        total = len(all_videos)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "videos": all_videos[start:end],
        }

    @router.delete("")
    def delete_videos(body: DeleteRequest) -> dict[str, Any]:
        if not app_state.config:
            return {"deleted": 0, "errors": ["No config loaded"]}

        videos_path = Path(app_state.config.videosPath)
        known_filenames = {v.filename for v in app_state.videos}
        deleted = 0
        errors: list[str] = []

        with open(CONFIG_PATH, "r") as f:
            config_data = json.load(f)
        relations = config_data.get("videoRelations", {})

        cache_path = videos_path / "cache.json"
        cache_data: dict = {}
        if cache_path.exists():
            with open(cache_path, "r") as f:
                cache_data = json.load(f)

        config_changed = False
        cache_changed = False

        for filename in sorted(set(body.filenames)):
            if filename not in known_filenames:
                errors.append(f"Rejected unknown filename: {filename}")
                continue

            targets = [
                videos_path / filename,
                videos_path / "img" / f"{filename}.jpg",
                videos_path / "sprite" / f"{filename}_sprite.jpg",
                videos_path / "sprite" / f"{filename}_sprite.vtt",
            ]

            file_deleted = False
            for target in targets:
                if target.is_file():
                    target.unlink()
                    logger.info("Deleted: %s", target)
                    file_deleted = True

            relation_removed = False
            if filename in relations:
                del relations[filename]
                config_changed = True
                relation_removed = True

            cache_removed = False
            if filename in cache_data:
                del cache_data[filename]
                cache_changed = True
                cache_removed = True

            if file_deleted or relation_removed or cache_removed:
                deleted += 1

        if config_changed:
            with open(CONFIG_PATH, "w") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
                f.write("\n")

        if cache_changed:
            with open(cache_path, "w") as f:
                json.dump(cache_data, f, indent=2)

        app_state.load()

        return {"deleted": deleted, "errors": errors}

    return router
