"""Orphaned asset cleanup (SPEC §3.4). Stale config entries are removed only on request (§3.5)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_orphaned_assets(videos_path: str, valid_filenames: set[str]) -> int:
    """Delete contact sheets and sprite files whose video no longer exists. Never touches videos."""
    base = Path(videos_path)
    removed = 0

    img_dir = base / "img"
    if img_dir.is_dir():
        for f in sorted(img_dir.iterdir()):
            # Contact sheets are named `<video filename>.jpg`.
            if f.is_file() and f.suffix.lower() == ".jpg" and f.stem not in valid_filenames:
                logger.info("Removing orphan contact sheet: %s", f)
                f.unlink()
                removed += 1

    sprite_dir = base / "sprite"
    if sprite_dir.is_dir():
        for f in sorted(sprite_dir.iterdir()):
            if f.is_file() and f.name.endswith(("_sprite.jpg", "_sprite.vtt")):
                if f.name.rsplit("_sprite", 1)[0] not in valid_filenames:
                    logger.info("Removing orphan sprite asset: %s", f)
                    f.unlink()
                    removed += 1

    logger.info("Orphan cleanup: removed %d file(s)", removed)
    return removed
