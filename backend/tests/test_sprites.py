"""Background seek-preview sprites: they never hold up startup, failures aren't retried, and they stop cleanly."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from PIL import Image

import preprocessor
from cache import MetadataCache
from pipeline import Pipeline
from preprocessor import run_preprocessing
from scanner import Video
from sprites import FailureLog, SpriteWorker
from state import AppState

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

CLIP = "studio-cast-clip.mp4"


def make_clip(path: Path, seconds: int = 6) -> Path:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=s=320x180:r=24:d={seconds}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-g", "48", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


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


def sprite_files(videos: Path, name: str = CLIP) -> list[Path]:
    return [videos / "sprite" / f"{name}_sprite.{ext}" for ext in ("jpg", "vtt")]


def test_startup_preprocessing_makes_no_sprites(videos: Path) -> None:
    run_preprocessing([Video(filename=CLIP, studio="studio", actors=["cast"], title="clip", related_galleries=[], tags=[])],
                      str(videos), MetadataCache(videos / "cache.json"))
    assert (videos / "img" / f"{CLIP}.jpg").is_file()
    assert not (videos / "sprite").exists()


def test_worker_makes_sprites_in_the_background(videos: Path, tmp_path: Path) -> None:
    worker = SpriteWorker(failures_path=tmp_path / "failures.json")
    worker.start(str(videos), [CLIP])
    worker.join(30)
    assert not worker.running
    jpg, vtt = sprite_files(videos)
    assert jpg.is_file() and vtt.read_text().startswith("WEBVTT")
    assert vtt.read_text().count("#xywh=") == 3, "One cue every 2 s of a 6 s clip"
    assert not list((videos / "sprite").glob(".*")), "No partial file left behind"


def test_a_failed_video_is_not_retried_until_it_changes(videos: Path, tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    damaged = videos / "studio-cast-damaged.mp4"
    damaged.write_bytes(b"not a video" * 1000)
    failures = tmp_path / "failures.json"

    worker = SpriteWorker(failures_path=failures)
    worker.start(str(videos), [damaged.name])
    worker.join(30)
    assert not any(p.exists() for p in sprite_files(videos, damaged.name))
    assert FailureLog(failures).known(damaged)

    calls: list[str] = []
    real = preprocessor.generate_sprite
    def counting(video: Path, *args, **kwargs) -> bool:
        calls.append(video.name)
        return real(video, *args, **kwargs)

    monkeypatch.setattr(preprocessor, "generate_sprite", counting)
    worker.start(str(videos), [damaged.name])
    worker.join(30)
    assert calls == [], "Skipped while the file is unchanged"

    damaged.write_bytes(b"still not a video, but different")
    worker.start(str(videos), [damaged.name])
    worker.join(30)
    assert calls == [damaged.name], "Retried once the file changed"


def test_stop_kills_a_running_ffmpeg(videos: Path, tmp_path: Path, hanging_ffmpeg: Path) -> None:
    worker = SpriteWorker(failures_path=tmp_path / "failures.json")
    worker.start(str(videos), [CLIP])
    time.sleep(0.5)
    assert worker.running
    started = time.monotonic()
    worker.stop()
    assert time.monotonic() - started < 3
    assert not worker.running
    assert not (videos / "sprite").exists() or not any((videos / "sprite").iterdir())
    assert not FailureLog(tmp_path / "failures.json").known(videos / CLIP), "Cancelling isn't a failure"


def test_the_library_is_ready_while_sprites_are_still_running(videos: Path, tmp_path: Path,
                                                              hanging_ffmpeg: Path,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    # The contact sheet already exists, so only sprites would need the (hanging) ffmpeg.
    (videos / "img").mkdir()
    Image.new("RGB", (1920, 1080)).save(videos / "img" / f"{CLIP}.jpg")
    galleries = tmp_path / "galleries"
    (galleries / "Beach").mkdir(parents=True)
    Image.new("RGB", (40, 60)).save(galleries / "Beach" / "a.jpg")
    config = tmp_path / "pvorg.json"
    config.write_text(json.dumps({"videosPath": str(videos), "galleriesPath": str(galleries),
                                  "tags": [], "videoRelations": {}}) + "\n")
    monkeypatch.setenv("PVORG_CONFIG", str(config))
    monkeypatch.setenv("PVORG_CACHE_DIR", str(tmp_path / "cache"))

    pipeline = Pipeline(AppState(), sprites=SpriteWorker(failures_path=tmp_path / "failures.json"))
    started = time.monotonic()
    pipeline.run_blocking()
    try:
        assert pipeline.state.startup.phase == "ready"
        assert time.monotonic() - started < 30
        assert pipeline.sprites.running, "Sprites carry on after the library opened"
    finally:
        pipeline.shutdown()
    assert not pipeline.sprites.running
