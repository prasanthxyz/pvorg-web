#!/usr/bin/env python3
"""Re-encode videos for optimal web playback using ffmpeg.

Usage:
    python reencode_videos.py [--config path/to/pvorg.json]

Reads the config to find the videos directory, then re-encodes each video
in-place (backup created with .bak extension) using H264 with fast-start.
Only processes videos with valid filenames.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import load_config
from scanner import VIDEO_EXTENSIONS, validate_video_filename

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


def reencode_video(input_path: Path, output_path: Path) -> bool:
    cmd = [
        FFMPEG,
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=3600)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  FAILED: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-encode videos for web playback")
    parser.add_argument("--config", type=Path, default=None, help="pvorg.json (default: $PVORG_CONFIG or ~/pvorg.json)")
    args = parser.parse_args()

    config = load_config(args.config)
    videos_dir = Path(config.videosPath)

    if not videos_dir.is_dir():
        print(f"Videos directory not found: {videos_dir}")
        sys.exit(1)

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

    print(f"Found {len(video_files)} valid videos in {videos_dir}")
    if skipped_invalid:
        print(f"Skipped {skipped_invalid} videos with invalid filenames")

    encoded = 0
    failed = 0
    for i, video in enumerate(video_files, 1):
        print(f"[{i}/{len(video_files)}] Re-encoding: {video.name}")

        temp_output = video.with_suffix(".reencoded.mp4")
        if not reencode_video(video, temp_output):
            if temp_output.exists():
                temp_output.unlink()
            failed += 1
            continue

        backup = video.with_suffix(video.suffix + ".bak")
        video.rename(backup)
        temp_output.rename(video.with_suffix(".mp4"))
        encoded += 1
        print(f"  Done. Backup: {backup.name}")

    print(f"\nRe-encode Report\n----------------")
    print(f"Re-encoded: {encoded}")
    print(f"Failed:     {failed}")
    if skipped_invalid:
        print(f"Skipped (invalid name): {skipped_invalid}")


if __name__ == "__main__":
    main()
