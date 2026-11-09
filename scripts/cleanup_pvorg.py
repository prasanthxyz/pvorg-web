#!/usr/bin/env python3
"""Remove stale videoRelations entries from pvorg.json where the video no longer exists.

Usage:
    python cleanup_pvorg.py [--config path/to/pvorg.json]
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from cleanup import cleanup_config_entries
from config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean stale pvorg.json entries")
    parser.add_argument("--config", type=Path, default=Path.home() / "pvorg.json")
    args = parser.parse_args()

    config = load_config(args.config)
    removed = cleanup_config_entries(args.config, config.videosPath)

    print(f"\nCleanup Report\n--------------")
    print(f"Stale entries removed: {removed}")


if __name__ == "__main__":
    main()
