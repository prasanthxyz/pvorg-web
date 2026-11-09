"""Startup preprocessing: TGP generation, sprite sheets, and metadata extraction."""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from cache import MetadataCache
from scanner import Video

logger = logging.getLogger(__name__)

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

TGP_COLS = 4
TGP_ROWS = 4
TGP_TILE_WIDTH = 480

SPRITE_INTERVAL_SECONDS = 2
SPRITE_COLS = 10
SPRITE_TILE_WIDTH = 160


def _get_video_duration(video_path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "error",
                "-select_streams", "v:0",
                # Matroska and WebM report no per-stream duration; fall back to the container's.
                "-show_entries", "stream=duration:format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.split():
            try:
                value = float(line)
            except ValueError:
                continue
            if math.isfinite(value) and value > 0:
                return value
        raise ValueError(f"no duration in ffprobe output {result.stdout.strip()!r}")
    except (ValueError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning("Could not get duration for %s: %s", video_path, e)
        return None


def _extract_metadata(video_path: Path) -> dict | None:
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration,width,height,r_frame_rate",
                "-show_entries", "format=size,duration",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        fmt = data.get("format", {})
        fps_str = stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = round(int(num) / int(den), 2) if int(den) != 0 else 0
        else:
            fps = round(float(fps_str), 2) if fps_str else 0

        duration = stream.get("duration") or fmt.get("duration") or 0
        return {
            "duration": float(duration),
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "fps": fps,
            "file_size": int(fmt.get("size", 0)),
        }
    except Exception as e:
        logger.warning("Metadata extraction failed for %s: %s", video_path, e)
        return None


def _get_media_dimensions(media_path: Path) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                str(media_path),
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        if width <= 0 or height <= 0:
            return None
        return width, height
    except Exception:
        return None


def generate_tgp(video_path: Path, output_path: Path) -> bool:
    """Generate a 4x4 contact sheet image (TGP)."""
    if output_path.exists():
        return True

    duration = _get_video_duration(video_path)
    if duration is None or duration < 1:
        return False

    num_tiles = TGP_COLS * TGP_ROWS
    interval = duration / num_tiles
    offset = interval / 2

    inputs = []
    stream_labels = []
    layout_parts = []

    for i in range(num_tiles):
        timestamp = offset + i * interval
        inputs.extend(["-ss", f"{timestamp:.2f}", "-i", str(video_path)])
        stream_labels.append(f"[{i}:v]")

        col = i % TGP_COLS
        row = i // TGP_COLS
        x = "+".join(["w0"] * col) if col > 0 else "0"
        y = "+".join(["h0"] * row) if row > 0 else "0"
        layout_parts.append(f"{x}_{y}")

    scale_w = TGP_COLS * TGP_TILE_WIDTH
    streams_str = "".join(stream_labels)
    layout_str = "|".join(layout_parts)
    filter_complex = (
        f"{streams_str}xstack=inputs={num_tiles}:layout={layout_str}[v];"
        f"[v]scale={scale_w}:-1[scaled]"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the target and rename, so an interrupted run never leaves a truncated sheet.
    partial = output_path.with_name(f".{output_path.stem}.partial.jpg")
    cmd = [FFMPEG] + inputs + [
        "-frames:v", "1", "-y",
        "-filter_complex", filter_complex,
        "-map", "[scaled]",
        str(partial),
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        partial.replace(output_path)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        partial.unlink(missing_ok=True)
        logger.error("TGP generation failed for %s: %s", video_path, e)
        return False


def generate_sprite(video_path: Path, sprite_dir: Path, video_name: str) -> bool:
    """Generate a scrubbing sprite sheet (1 frame every 2s) + VTT file."""
    sprite_path = sprite_dir / f"{video_name}_sprite.jpg"
    vtt_path = sprite_dir / f"{video_name}_sprite.vtt"

    if sprite_path.exists() and vtt_path.exists():
        return True

    duration = _get_video_duration(video_path)
    if duration is None or duration < 1:
        return False

    num_frames = max(1, int(math.floor(duration / SPRITE_INTERVAL_SECONDS)))
    rows = max(1, math.ceil(num_frames / SPRITE_COLS))

    sprite_dir.mkdir(parents=True, exist_ok=True)

    # Extract frames into a single sprite sheet using ffmpeg
    scale_w = SPRITE_TILE_WIDTH
    cmd = [
        FFMPEG, "-i", str(video_path),
        "-vf", f"fps=1/{SPRITE_INTERVAL_SECONDS},scale={scale_w}:-1,tile={SPRITE_COLS}x{rows}",
        "-frames:v", "1", "-y",
        str(sprite_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error("Sprite generation failed for %s: %s", video_path, e)
        return False

    # Generate VTT file for the sprite with exact tile coordinates.
    sprite_size = _get_media_dimensions(sprite_path)
    _generate_vtt(
        vtt_path=vtt_path,
        num_frames=num_frames,
        cols=SPRITE_COLS,
        sprite_filename=sprite_path.name,
        duration=duration,
        sprite_size=sprite_size,
    )
    return True


def _generate_vtt(
    vtt_path: Path,
    num_frames: int,
    cols: int,
    sprite_filename: str,
    duration: float,
    sprite_size: tuple[int, int] | None,
) -> None:
    rows = max(1, math.ceil(num_frames / cols))
    if sprite_size:
        sprite_width, sprite_height = sprite_size
        tile_width = max(1, sprite_width // cols)
        tile_height = max(1, sprite_height // rows)
    else:
        tile_width = SPRITE_TILE_WIDTH
        tile_height = round(tile_width * 9 / 16)

    lines = ["WEBVTT", ""]
    for i in range(num_frames):
        start_sec = i * SPRITE_INTERVAL_SECONDS
        end_sec = min((i + 1) * SPRITE_INTERVAL_SECONDS, duration)

        col = i % cols
        row = i // cols
        x = col * tile_width
        y = row * tile_height

        start_ts = _format_vtt_time(start_sec)
        end_ts = _format_vtt_time(end_sec)

        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(f"{sprite_filename}#xywh={x},{y},{tile_width},{tile_height}")
        lines.append("")

    vtt_path.write_text("\n".join(lines))


def _format_vtt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def run_preprocessing(
    videos: list[Video],
    videos_path: str,
    cache: MetadataCache,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[str]:
    """Generate missing contact sheets, sprites and metadata (SPEC §3.2 step 5).

    Failures for individual videos are logged and returned, never fatal: a video
    without a contact sheet still appears, with the "No Contact Sheet" state.
    """
    vpath = Path(videos_path)
    img_dir = vpath / "img"
    sprite_dir = vpath / "sprite"

    total = len(videos)
    failures: list[str] = []
    for idx, video in enumerate(videos):
        if progress_callback:
            progress_callback(idx, total, video.filename)
        video_file = vpath / video.filename
        if not video_file.exists():
            logger.warning("Video file not found, skipping: %s", video_file)
            continue

        if not generate_tgp(video_file, img_dir / f"{video.filename}.jpg"):
            failures.append(f"Contact sheet failed: {video.filename}")
        if not generate_sprite(video_file, sprite_dir, video.filename):
            failures.append(f"Sprite failed: {video.filename}")
        if not cache.has(video.filename):
            meta = _extract_metadata(video_file)
            if meta:
                cache.set(video.filename, meta)

    cache.save()
    for failure in failures:
        logger.warning(failure)
    logger.info("Preprocessing complete for %d videos (%d failures)", total, len(failures))
    return failures
