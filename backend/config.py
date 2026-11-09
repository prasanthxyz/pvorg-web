"""pvorg.json: location, schema, loading, normalization and atomic saving (SPEC §1.2)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


def config_path() -> Path:
    """`~/pvorg.json`, or the file named by `PVORG_CONFIG` (read on every call so tests can set it)."""
    override = os.environ.get("PVORG_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / "pvorg.json"


class VideoRelation(BaseModel):
    """Tri-state decisions for one video. `None` means the array is missing from the file."""

    galleries: list[str] | None = None
    excludedGalleries: list[str] | None = None
    tags: list[str] | None = None
    excludedTags: list[str] | None = None

    @property
    def yes_galleries(self) -> list[str]:
        return self.galleries or []

    @property
    def no_galleries(self) -> list[str]:
        return self.excludedGalleries or []

    @property
    def yes_tags(self) -> list[str]:
        return self.tags or []

    @property
    def no_tags(self) -> list[str]:
        return self.excludedTags or []

    def is_empty(self) -> bool:
        return not any([self.galleries, self.excludedGalleries, self.tags, self.excludedTags])


class AppConfig(BaseModel):
    videosPath: str
    galleriesPath: str
    tags: list[str]
    videoRelations: dict[str, VideoRelation]


class ConfigError(Exception):
    """pvorg.json is missing, unreadable or doesn't match the schema."""


def load_config(path: Path | None = None) -> AppConfig:
    path = path or config_path()
    logger.info("Loading config from %s", path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"The file “{path.name}” couldn’t be found.") from e
    except OSError as e:
        raise ConfigError(f"The file “{path.name}” couldn’t be read: {e.strerror}.") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path.name} isn’t valid JSON: {e.msg} (line {e.lineno}, column {e.colno}).") from e
    try:
        return AppConfig.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"{path.name} isn’t valid: {_describe(e)}") from e


def _describe(error: ValidationError) -> str:
    first = error.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    if first["type"] == "missing":
        return f"the required key “{location}” is missing."
    return f"{first['msg'].rstrip('.')} (at “{location}”)."


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """UTF-8, pretty-printed, keys sorted, trailing newline, written atomically.

    Only schema keys are written (SPEC §1.2: unknown keys are not preserved), and
    arrays missing from a relation stay missing, matching the other apps.
    """
    path = path or config_path()
    data = config.model_dump(exclude_none=True)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    atomic_write_text(path, text)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def normalize_relations(config: AppConfig) -> int:
    """Turn missing or null arrays into `[]` (SPEC §1.2). Returns how many relations changed."""
    changed = 0
    for relation in config.videoRelations.values():
        touched = False
        for field in ("galleries", "excludedGalleries", "tags", "excludedTags"):
            if getattr(relation, field) is None:
                setattr(relation, field, [])
                touched = True
        changed += touched
    return changed
