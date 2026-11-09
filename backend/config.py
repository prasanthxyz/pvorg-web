"""Load and validate ~/pvorg.json configuration."""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / "pvorg.json"


class VideoRelation(BaseModel):
    galleries: list[str] = Field(default_factory=list)
    excludedGalleries: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    excludedTags: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    videosPath: str
    galleriesPath: str
    tags: list[str] = Field(default_factory=list)
    videoRelations: dict[str, VideoRelation] = Field(default_factory=dict)


def load_config(path: Optional[Path] = None) -> AppConfig:
    path = path or CONFIG_PATH
    logger.info("Loading config from %s", path)
    with open(path, "r") as f:
        data = json.load(f)
    return AppConfig(**data)
