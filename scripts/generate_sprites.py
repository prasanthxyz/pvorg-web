#!/usr/bin/env python3
"""Generate scrubbing sprite sheets + VTT files for all videos.

Usage:
    python generate_sprites.py [--config path/to/pvorg.json]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import load_config
from preprocessor import generate_sprite
from scanner import VIDEO_EXTENSIONS, validate_video_filename


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate scrubbing sprite sheets")
    parser.add_argument("--config", type=Path, default=None, help="pvorg.json (default: $PVORG_CONFIG or ~/pvorg.json)")
    args = parser.parse_args()

    config = load_config(args.config)
    videos_dir = Path(config.videosPath)

    if not videos_dir.is_dir():
        print(f"Videos directory not found: {videos_dir}")
        sys.exit(1)

    sprite_dir = videos_dir / "sprite"
    video_files = []
    skipped_invalid = 0
    for entry in sorted(videos_dir.iterdir()):
        if (
            entry.is_file()
            and entry.suffix.lower() in VIDEO_EXTENSIONS
            and not entry.name.startswith(".")
        ):
            is_valid, reasons = validate_video_filename(entry.name)
            if not is_valid:
                print(f"  Skipping invalid filename: {entry.name}  ({', '.join(reasons)})")
                skipped_invalid += 1
            else:
                video_files.append(entry)

    total = len(video_files)
    generated = 0
    skipped = 0
    print(f"Processing {total} valid videos...")

    for i, vf in enumerate(video_files, 1):
        sprite_path = sprite_dir / f"{vf.name}_sprite.jpg"
        vtt_path = sprite_dir / f"{vf.name}_sprite.vtt"
        if sprite_path.exists() and vtt_path.exists():
            skipped += 1
            continue
        print(f"[{i}/{total}] {vf.name}")
        if generate_sprite(vf, sprite_dir, vf.name):
            generated += 1

    print(f"\nSprite Report\n-------------")
    print(f"Generated: {generated}")
    print(f"Skipped (existing): {skipped}")
    if skipped_invalid:
        print(f"Skipped (invalid name): {skipped_invalid}")


if __name__ == "__main__":
    main()
