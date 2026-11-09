"""Startup preprocessing: contact sheets (TGP), seek-preview sprites and metadata."""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from cache import MetadataCache
from config import atomic_write_text
from scanner import Video
from sprites import FailureLog

logger = logging.getLogger(__name__)

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

TGP_COLS = 4
TGP_ROWS = 4
TGP_TILE_WIDTH = 480

SPRITE_INTERVAL_SECONDS = 2
SPRITE_COLS = 10
SPRITE_TILE_WIDTH = 160
# Keyframe-only decoding rarely needs more than seconds; the margin covers slow or network drives.
# A timeout is remembered as a failure, so it's paid once per file, not on every launch.
SPRITE_TIMEOUT_SECONDS = 300


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


class SpriteCancelled(Exception):
    """Sprite generation was stopped because the server is stopping."""


def generate_sprite(video_path: Path, sprite_dir: Path, video_name: str, *,
                    stop: threading.Event | None = None,
                    timeout: float = SPRITE_TIMEOUT_SECONDS) -> bool:
    """Generate a scrubbing sprite sheet (one tile every 2 s) and its VTT index.

    Only keyframes are decoded (`-skip_frame nokey`): each tile shows the nearest earlier
    keyframe, which is plenty for a scrubber preview and tens of times cheaper than decoding
    every frame of a long video. Raises SpriteCancelled when `stop` is set, and OSError when
    ffmpeg can't be started.
    """
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
    # Written beside the target and renamed. The partial name ends in "_sprite.jpg" but names no
    # video, so the startup orphan cleanup removes it if a run is ever killed mid-write.
    partial = sprite_dir / f".{video_name}.partial_sprite.jpg"
    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
        "-skip_frame", "nokey", "-i", str(video_path),
        "-an", "-sn", "-dn",
        # tpad holds the last keyframe to the end, so the tiles after it (and a clip with a
        # single keyframe) aren't left blank by the fps filter.
        "-vf", (f"tpad=stop_mode=clone:stop_duration={duration:.3f},fps=1/{SPRITE_INTERVAL_SECONDS},"
                f"scale={SPRITE_TILE_WIDTH}:-1,tile={SPRITE_COLS}x{rows}"),
        "-frames:v", "1", "-y",
        str(partial),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + timeout
    done = False
    try:
        while True:
            try:
                _, err = proc.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                if stop is not None and stop.is_set():
                    raise SpriteCancelled from None
                if time.monotonic() > deadline:
                    logger.error("Sprite generation timed out after %ds for %s", timeout, video_path)
                    return False
        if proc.returncode != 0:
            logger.error("Sprite generation failed for %s: %s", video_path, (err or "").strip()[-500:])
            return False
        try:
            partial.replace(sprite_path)
        except OSError as e:
            logger.error("Sprite generation produced no image for %s: %s", video_path, e)
            return False
        done = True
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()  # reap it and close its stderr pipe
        if not done:
            partial.unlink(missing_ok=True)

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

    atomic_write_text(vtt_path, "\n".join(lines))


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
    *,
    sprite_failures: FailureLog | None = None,
    stop: threading.Event | None = None,
) -> list[str]:
    """Generate missing contact sheets, seek-preview sprites and metadata (SPEC §3.2 step 5).

    Failures for individual videos are logged and returned, never fatal: a video without a
    contact sheet still appears, with the "No Contact Sheet" state, and one without a sprite has
    no scrubber preview. A video whose sprite failed before is skipped until its file changes
    (`sprite_failures`). Raises SpriteCancelled if `stop` is set while a sprite is being made.
    """
    vpath = Path(videos_path)
    img_dir = vpath / "img"
    sprite_dir = vpath / "sprite"
    can_make_sprites = bool(shutil.which(FFMPEG) and shutil.which(FFPROBE))

    total = len(videos)
    failures: list[str] = []
    try:
        for idx, video in enumerate(videos):
            if progress_callback:
                progress_callback(idx, total, video.filename)
            video_file = vpath / video.filename
            if not video_file.exists():
                logger.warning("Video file not found, skipping: %s", video_file)
                continue

            if not generate_tgp(video_file, img_dir / f"{video.filename}.jpg"):
                failures.append(f"Contact sheet failed: {video.filename}")
            if can_make_sprites:
                _prepare_sprite(video_file, sprite_dir, video.filename, failures, sprite_failures, stop)
            if not cache.has(video.filename):
                meta = _extract_metadata(video_file)
                if meta:
                    cache.set(video.filename, meta)
    finally:
        cache.save()
        if sprite_failures is not None:
            sprite_failures.save()

    for failure in failures:
        logger.warning(failure)
    logger.info("Preprocessing complete for %d videos (%d failures)", total, len(failures))
    return failures


def _prepare_sprite(video_file: Path, sprite_dir: Path, filename: str, failures: list[str],
                    known_failures: FailureLog | None, stop: threading.Event | None) -> None:
    if (sprite_dir / f"{filename}_sprite.jpg").is_file() and (sprite_dir / f"{filename}_sprite.vtt").is_file():
        return
    if known_failures is not None and known_failures.known(video_file):
        logger.debug("Skipping sprite for %s: it failed before and the file hasn't changed", filename)
        return
    try:
        ok = generate_sprite(video_file, sprite_dir, filename, stop=stop)
    except OSError as e:
        # ffmpeg couldn't be started: a problem with the tools, not with this video.
        failures.append(f"Sprite failed: {filename}: {e}")
        return
    if ok:
        if known_failures is not None:
            known_failures.forget(video_file)
    else:
        failures.append(f"Sprite failed: {filename}")
        if known_failures is not None:
            known_failures.remember(video_file)
            known_failures.save()
