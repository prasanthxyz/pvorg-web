#!/usr/bin/env python3
"""Remove orphaned TGP and sprite files that have no corresponding video.

Usage:
    python cleanup_orphans.py [--config path/to/pvorg.json]
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from cleanup import cleanup_orphaned_assets
from config import load_config
from scanner import VIDEO_EXTENSIONS, validate_video_filename


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove orphaned asset files")
    parser.add_argument("--config", type=Path, default=Path.home() / "pvorg.json")
    args = parser.parse_args()

    config = load_config(args.config)
    videos_dir = Path(config.videosPath)

    if not videos_dir.is_dir():
        print(f"Videos directory not found: {videos_dir}")
        sys.exit(1)

    valid_filenames: set[str] = set()
    for entry in sorted(videos_dir.iterdir()):
        if (
            entry.is_file()
            and entry.suffix.lower() in VIDEO_EXTENSIONS
            and not entry.name.startswith(".")
        ):
            is_valid, _ = validate_video_filename(entry.name)
            if is_valid:
                valid_filenames.add(entry.name)

    removed = cleanup_orphaned_assets(config.videosPath, valid_filenames)

    print(f"\nCleanup Report\n--------------")
    print(f"Orphan files removed: {removed}")


if __name__ == "__main__":
    main()
