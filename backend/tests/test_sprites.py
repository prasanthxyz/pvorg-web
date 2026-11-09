"""Seek-preview sprites during Preparing Previews: keyframe-only, failures not retried, stoppable."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

import preprocessor
from cache import MetadataCache
from pipeline import Pipeline
from preprocessor import SpriteCancelled, run_preprocessing
from scanner import Video
from sprites import FailureLog
from state import AppState

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

CLIP = "studio-cast-clip.mp4"


def make_clip(path: Path, seconds: int = 6) -> Path:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=s=320x180:r=24:d={seconds}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-g", "48", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def video(name: str) -> Video:
    return Video(filename=name, studio="studio", actors=["cast"], title="clip", related_galleries=[], tags=[])


@pytest.fixture
def videos(tmp_path: Path) -> Path:
    folder = tmp_path / "videos"
    folder.mkdir()
    make_clip(folder / CLIP)
    return folder


@pytest.fixture
def hanging_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An "ffmpeg" that never finishes, standing in for a very long video."""
    fake = tmp_path / "bin" / "ffmpeg"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\nexec sleep 60\n")
    fake.chmod(0o755)
    monkeypatch.setattr(preprocessor, "FFMPEG", str(fake))
    return fake


def with_contact_sheet(videos: Path, name: str = CLIP) -> None:
    """So only the sprite would need ffmpeg."""
    (videos / "img").mkdir(exist_ok=True)
    Image.new("RGB", (1920, 1080)).save(videos / "img" / f"{name}.jpg")


def sprite_files(videos: Path, name: str = CLIP) -> list[Path]:
    return [videos / "sprite" / f"{name}_sprite.{ext}" for ext in ("jpg", "vtt")]


def test_preparing_previews_makes_the_sheet_sprite_and_metadata(videos: Path, tmp_path: Path) -> None:
    cache = MetadataCache(videos / "cache.json")
    failures = run_preprocessing([video(CLIP)], str(videos), cache,
                                 sprite_failures=FailureLog(tmp_path / "failures.json"))
    assert failures == []
    assert (videos / "img" / f"{CLIP}.jpg").is_file()
    jpg, vtt = sprite_files(videos)
    assert jpg.is_file() and vtt.read_text().startswith("WEBVTT")
    assert vtt.read_text().count("#xywh=") == 3, "One cue every 2 s of a 6 s clip"
    assert not list((videos / "sprite").glob(".*")), "No partial file left behind"
    assert cache.has(CLIP)


def test_a_failed_video_is_not_retried_until_it_changes(videos: Path, tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    damaged = videos / "studio-cast-damaged.mp4"
    damaged.write_bytes(b"not a video" * 1000)
    failures_path = tmp_path / "failures.json"

    def run() -> list[str]:
        return run_preprocessing([video(damaged.name)], str(videos), MetadataCache(videos / "cache.json"),
                                 sprite_failures=FailureLog(failures_path))

    assert f"Sprite failed: {damaged.name}" in run()
    assert not any(p.exists() for p in sprite_files(videos, damaged.name))
    assert FailureLog(failures_path).known(damaged)

    calls: list[str] = []
    real = preprocessor.generate_sprite

    def counting(path: Path, *args, **kwargs) -> bool:
        calls.append(path.name)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(preprocessor, "generate_sprite", counting)
    run()
    assert calls == [], "Skipped while the file is unchanged"

    damaged.write_bytes(b"still not a video, but different")
    run()
    assert calls == [damaged.name], "Retried once the file changed"


def test_stop_kills_a_running_ffmpeg(videos: Path, tmp_path: Path, hanging_ffmpeg: Path) -> None:
    with_contact_sheet(videos)
    stop = threading.Event()
    outcome: list[BaseException | None] = []

    def run() -> None:
        try:
            run_preprocessing([video(CLIP)], str(videos), MetadataCache(videos / "cache.json"),
                              sprite_failures=FailureLog(tmp_path / "failures.json"), stop=stop)
            outcome.append(None)
        except BaseException as e:  # noqa: BLE001
            outcome.append(e)

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.5)
    assert thread.is_alive(), "Still making the sprite"
    started = time.monotonic()
    stop.set()
    thread.join(5)
    assert not thread.is_alive() and time.monotonic() - started < 3
    assert len(outcome) == 1 and isinstance(outcome[0], SpriteCancelled)
    assert not (videos / "sprite").exists() or not any((videos / "sprite").iterdir())
    assert not FailureLog(tmp_path / "failures.json").known(videos / CLIP), "Cancelling isn't a failure"


def test_the_library_opens_only_after_sprites_and_shutdown_stops_them(videos: Path, tmp_path: Path,
                                                                     hanging_ffmpeg: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    with_contact_sheet(videos)
    galleries = tmp_path / "galleries"
    (galleries / "Beach").mkdir(parents=True)
    Image.new("RGB", (40, 60)).save(galleries / "Beach" / "a.jpg")
    config = tmp_path / "pvorg.json"
    config.write_text(json.dumps({"videosPath": str(videos), "galleriesPath": str(galleries),
                                  "tags": [], "videoRelations": {}}) + "\n")
    monkeypatch.setenv("PVORG_CONFIG", str(config))
    monkeypatch.setenv("PVORG_CACHE_DIR", str(tmp_path / "cache"))

    pipeline = Pipeline(AppState(), sprite_failures_path=tmp_path / "failures.json")
    assert pipeline.start()
    deadline = time.monotonic() + 10
    while pipeline.state.startup.step != "Preparing Previews" and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.5)
    assert pipeline.state.startup.phase == "loading", "Not ready while a sprite is still being made"

    started = time.monotonic()
    pipeline.shutdown()
    assert time.monotonic() - started < 3, "Shutdown kills ffmpeg instead of waiting for it"
    assert pipeline.state.startup.phase != "error"
