#!/usr/bin/env python3
"""Remove stale videoRelations entries (videos no longer in the videos folder) from pvorg.json.

Follows SPEC §3.5: shows what would be removed first, and refuses when no videos are
visible at all (a disconnected drive, say) unless --force is given.

Usage:
    python scripts/cleanup_pvorg.py [--config path/to/pvorg.json]          # preview
    python scripts/cleanup_pvorg.py [--config path/to/pvorg.json] --yes    # remove
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import load_config, save_config
from relations import stale_preview
from scanner import VIDEO_EXTENSIONS


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean stale pvorg.json entries")
    parser.add_argument("--config", type=Path, default=None, help="pvorg.json (default: $PVORG_CONFIG or ~/pvorg.json)")
    parser.add_argument("--yes", action="store_true", help="remove the entries instead of only listing them")
    parser.add_argument("--force", action="store_true", help="allow removal even when no videos are visible")
    args = parser.parse_args()

    config = load_config(args.config)
    preview = stale_preview(config, VIDEO_EXTENSIONS)

    print(f"Videos folder:         {preview.videos_path}")
    print(f"Videos on disk:        {preview.video_file_count}")
    print(f"Entries in pvorg.json: {preview.relation_count}")
    print(f"Stale entries:         {len(preview.stale_entries)}")
    for name in preview.stale_entries:
        print(f"  {name}")

    if not preview.stale_entries:
        return 0
    if preview.high_risk and not args.force:
        print("\nNo videos are visible in the videos folder. If a drive is disconnected, removing these")
        print("entries would permanently delete your mapping decisions. Re-run with --force to remove anyway.")
        return 1
    if not args.yes:
        print("\nPreview only. Re-run with --yes to remove these entries.")
        return 0

    for name in preview.stale_entries:
        del config.videoRelations[name]
    save_config(config, args.config)
    print(f"\nRemoved {len(preview.stale_entries)} stale entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
