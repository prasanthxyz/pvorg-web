"""Scan the filesystem for videos and galleries (SPEC §1.3, §1.4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from config import AppConfig
from display import credits, display_title, sort_key

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"}


@dataclass
class Video:
    filename: str
    studio: str
    actors: list[str]
    title: str
    related_galleries: list[str]
    tags: list[str]

    @property
    def display_title(self) -> str:
        return display_title(self.title, self.filename)

    @property
    def credits(self) -> str:
        return credits(self.studio, self.actors)

    @property
    def sort_key(self) -> tuple[str, str, str]:
        return sort_key(self.display_title, self.filename)


@dataclass
class Gallery:
    name: str
    image_files: list[str] = field(default_factory=list)


@dataclass
class SkippedFile:
    filename: str
    reasons: list[str]


def validate_video_filename(filename: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if filename != filename.lower():
        reasons.append("Contains uppercase characters")
    if " " in filename:
        reasons.append("Contains spaces")
    if len(Path(filename).stem.split("-")) < 3:
        reasons.append("Fewer than 3 dash-separated parts (need studio-cast-title)")
    return (not reasons, reasons)


def parse_video_filename(filename: str) -> tuple[str, list[str], str]:
    """`studio-cast1-cast2-…-title.ext` → (studio, cast, title)."""
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) < 3:
        return (parts[0] if parts else "unknown"), [], stem
    return parts[0], parts[1:-1], parts[-1]


def scan_videos(config: AppConfig, gallery_names: list[str]) -> tuple[list[Video], list[SkippedFile]]:
    """Valid videos sorted for display, plus files skipped for their names."""
    videos_dir = Path(config.videosPath)
    if not videos_dir.is_dir():
        logger.warning("Videos directory does not exist: %s", videos_dir)
        return [], []

    videos: list[Video] = []
    skipped: list[SkippedFile] = []

    for entry in sorted(videos_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_file() or entry.name.startswith(".") or entry.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        valid, reasons = validate_video_filename(entry.name)
        if not valid:
            logger.warning("Invalid filename skipped: %s (%s)", entry.name, ", ".join(reasons))
            skipped.append(SkippedFile(entry.name, reasons))
            continue

        studio, actors, title = parse_video_filename(entry.name)
        relation = config.videoRelations.get(entry.name)
        excluded = set(relation.no_galleries) if relation else set()
        videos.append(Video(
            filename=entry.name,
            studio=studio,
            actors=actors,
            title=title,
            # Galleries are opt-out: every gallery the video isn't excluded from.
            related_galleries=[g for g in gallery_names if g not in excluded],
            # Tags are opt-in: only tags explicitly marked yes (SPEC §3.1).
            tags=list(relation.yes_tags) if relation else [],
        ))

    videos.sort(key=lambda v: v.sort_key)
    logger.info("Scanned %d videos (%d skipped) from %s", len(videos), len(skipped), videos_dir)
    return videos, skipped


def scan_galleries(config: AppConfig) -> list[Gallery]:
    galleries_dir = Path(config.galleriesPath)
    if not galleries_dir.is_dir():
        logger.warning("Galleries directory does not exist: %s", galleries_dir)
        return []

    galleries: list[Gallery] = []
    for entry in sorted(galleries_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        images = [
            str(img)
            for img in sorted(entry.iterdir(), key=lambda p: p.name)
            if img.is_file() and not img.name.startswith(".") and img.suffix.lower() in IMAGE_EXTENSIONS
        ]
        galleries.append(Gallery(name=entry.name, image_files=images))

    logger.info("Scanned %d galleries from %s", len(galleries), galleries_dir)
    return galleries
