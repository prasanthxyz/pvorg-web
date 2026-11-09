"""Filesystem and config cleanup: orphan assets and stale pvorg.json entries."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_orphaned_assets(videos_path: str, valid_filenames: set[str]) -> int:
    """Delete TGP thumbnails and sprite files that have no matching valid video.

    Never touches original video files. Returns the count of files removed.
    """
    base = Path(videos_path)
    removed = 0

    img_dir = base / "img"
    if img_dir.is_dir():
        for f in sorted(img_dir.iterdir()):
            if f.suffix.lower() == ".jpg" and f.is_file():
                # TGP files are named {video.filename}.jpg, so f.stem is the full video filename
                if f.stem not in valid_filenames:
                    logger.info("Removing orphan TGP: %s", f)
                    f.unlink()
                    removed += 1

    sprite_dir = base / "sprite"
    if sprite_dir.is_dir():
        for f in sorted(sprite_dir.iterdir()):
            if f.is_file() and f.name.endswith(("_sprite.jpg", "_sprite.vtt")):
                # Sprite files are named {video.filename}_sprite.{ext}
                video_filename = f.name.rsplit("_sprite", 1)[0]
                if video_filename not in valid_filenames:
                    logger.info("Removing orphan sprite asset: %s", f)
                    f.unlink()
                    removed += 1

    logger.info("Orphan cleanup: removed %d file(s)", removed)
    return removed


def normalize_config_entries(config_path: Path) -> int:
    """Normalize null/missing relation lists without changing tri-state intent.

    Important: empty lists are preserved as-is. Runtime processing interprets them as
    effective "all included unless explicitly excluded".
    """
    with open(config_path, "r") as f:
        data = json.load(f)

    relations = data.get("videoRelations", {})
    if not relations:
        return 0

    normalized = 0
    for key, rel in relations.items():
        if not isinstance(rel, dict):
            continue
        changed = False
        if "tags" not in rel or rel["tags"] is None:
            rel["tags"] = []
            changed = True
        if "galleries" not in rel or rel["galleries"] is None:
            rel["galleries"] = []
            changed = True
        if "excludedTags" not in rel or rel["excludedTags"] is None:
            rel["excludedTags"] = []
            changed = True
        if "excludedGalleries" not in rel or rel["excludedGalleries"] is None:
            rel["excludedGalleries"] = []
            changed = True
        if changed:
            logger.info("Normalized missing/null mapping fields for: %s", key)
            normalized += 1

    if normalized > 0:
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    logger.info("Normalization: updated %d videoRelation(s)", normalized)
    return normalized


def cleanup_config_entries(config_path: Path, videos_path: str) -> int:
    """Remove videoRelations entries from pvorg.json where the video no longer exists on disk."""
    with open(config_path, "r") as f:
        data = json.load(f)

    relations = data.get("videoRelations", {})
    if not relations:
        return 0

    videos_dir = Path(videos_path)
    stale_keys: list[str] = []

    for key in list(relations.keys()):
        if not (videos_dir / key).is_file():
            logger.info("Removing stale pvorg.json entry: %s", key)
            stale_keys.append(key)

    if not stale_keys:
        return 0

    for key in stale_keys:
        del relations[key]

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.info("Config cleanup: removed %d stale videoRelation(s)", len(stale_keys))
    return len(stale_keys)
