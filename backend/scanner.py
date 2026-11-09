"""Scan filesystem to discover videos and galleries."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from config import AppConfig, VideoRelation

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


@dataclass
class Gallery:
    name: str
    image_files: list[str] = field(default_factory=list)


def validate_video_filename(filename: str) -> tuple[bool, list[str]]:
    """Check filename is lowercase, no spaces, and has studio-cast-title structure."""
    reasons: list[str] = []
    if filename != filename.lower():
        reasons.append("uppercase characters")
    if " " in filename:
        reasons.append("spaces")
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) < 3:
        reasons.append("fewer than 3 dash-separated fields (need studio-cast-title)")
    return (len(reasons) == 0, reasons)


def parse_video_filename(filename: str) -> tuple[str, list[str], str]:
    """Parse 'studio-cast1-cast2-...-title.ext' into components."""
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) < 3:
        return parts[0] if parts else "unknown", [], stem

    studio = parts[0]
    actors = list(parts[1:-1])
    title = parts[-1]
    return studio, actors, title


def scan_videos(
    config: AppConfig, gallery_names: list[str],
) -> tuple[list[Video], list[tuple[str, list[str]]]]:
    """Returns (valid_videos, skipped_files) where skipped_files is [(filename, reasons)]."""
    videos_dir = Path(config.videosPath)
    if not videos_dir.is_dir():
        logger.error("Videos directory does not exist: %s", videos_dir)
        return [], []

    all_tags = config.tags
    videos: list[Video] = []
    skipped: list[tuple[str, list[str]]] = []

    for entry in sorted(videos_dir.iterdir()):
        if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS and not entry.name.startswith("."):
            valid, reasons = validate_video_filename(entry.name)
            if not valid:
                logger.warning("Invalid filename skipped: %s  Reason: %s", entry.name, ", ".join(reasons))
                skipped.append((entry.name, reasons))
                continue

            studio, actors, title = parse_video_filename(entry.name)
            relation: VideoRelation = config.videoRelations.get(
                entry.name,
                VideoRelation(galleries=gallery_names, tags=all_tags),
            )
            excluded_galleries = set(relation.excludedGalleries)
            excluded_tags = set(relation.excludedTags)
            videos.append(Video(
                filename=entry.name,
                studio=studio,
                actors=actors,
                title=title,
                related_galleries=[g for g in gallery_names if g not in excluded_galleries],
                tags=[t for t in all_tags if t not in excluded_tags],
            ))

    logger.info("Scanned %d videos (%d skipped) from %s", len(videos), len(skipped), videos_dir)
    return videos, skipped


def scan_galleries(config: AppConfig) -> list[Gallery]:
    galleries_dir = Path(config.galleriesPath)
    if not galleries_dir.is_dir():
        logger.error("Galleries directory does not exist: %s", galleries_dir)
        return []

    galleries: list[Gallery] = []

    for entry in sorted(galleries_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            images = [
                str(img)
                for img in sorted(entry.iterdir())
                if img.is_file()
                and img.suffix.lower() in IMAGE_EXTENSIONS
                and not img.name.startswith(".")
            ]
            galleries.append(Gallery(name=entry.name, image_files=images))

    logger.info("Scanned %d galleries from %s", len(galleries), galleries_dir)
    return galleries
