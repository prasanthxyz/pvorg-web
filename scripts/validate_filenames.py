#!/usr/bin/env python3
"""Validate video filenames against naming conventions.

Usage:
    python validate_filenames.py [--config path/to/pvorg.json]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import load_config
from scanner import VIDEO_EXTENSIONS, validate_video_filename


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate video filenames")
    parser.add_argument("--config", type=Path, default=None, help="pvorg.json (default: $PVORG_CONFIG or ~/pvorg.json)")
    args = parser.parse_args()

    config = load_config(args.config)
    videos_dir = Path(config.videosPath)

    if not videos_dir.is_dir():
        print(f"Videos directory not found: {videos_dir}")
        sys.exit(1)

    invalid_count = 0
    valid_count = 0

    for entry in sorted(videos_dir.iterdir()):
        if (
            entry.is_file()
            and entry.suffix.lower() in VIDEO_EXTENSIONS
            and not entry.name.startswith(".")
        ):
            is_valid, reasons = validate_video_filename(entry.name)
            if not is_valid:
                print(f"  INVALID: {entry.name}  ({', '.join(reasons)})")
                invalid_count += 1
            else:
                valid_count += 1

    print(f"\nValidation Report\n-----------------")
    print(f"Valid:   {valid_count}")
    print(f"Invalid: {invalid_count}")


if __name__ == "__main__":
    main()
