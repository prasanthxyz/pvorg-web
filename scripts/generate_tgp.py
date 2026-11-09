#!/usr/bin/env python3
"""Generate TGP (4x4 contact sheet) thumbnails for all videos.

Usage:
    python generate_tgp.py [--config path/to/pvorg.json]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import load_config
from preprocessor import generate_tgp
from scanner import VIDEO_EXTENSIONS, validate_video_filename


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TGP contact sheets")
    parser.add_argument("--config", type=Path, default=Path.home() / "pvorg.json")
    args = parser.parse_args()

    config = load_config(args.config)
    videos_dir = Path(config.videosPath)

    if not videos_dir.is_dir():
        print(f"Videos directory not found: {videos_dir}")
        sys.exit(1)

    img_dir = videos_dir / "img"
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
        tgp_out = img_dir / f"{vf.name}.jpg"
        if tgp_out.exists():
            skipped += 1
            continue
        print(f"[{i}/{total}] {vf.name}")
        if generate_tgp(vf, tgp_out):
            generated += 1

    print(f"\nTGP Report\n----------")
    print(f"Generated: {generated}")
    print(f"Skipped (existing): {skipped}")
    if skipped_invalid:
        print(f"Skipped (invalid name): {skipped_invalid}")


if __name__ == "__main__":
    main()
