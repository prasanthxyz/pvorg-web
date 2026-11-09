"""Shared fixtures: an isolated library on disk and an app that serves it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import create_app  # noqa: E402

DEFAULT_VIDEOS = [
    "acme-jane_doe-harbor_lights.mp4",
    "acme-jane_doe-john_roe-mountain_pass.mp4",
    "globex-sam_lee-desert_road.mp4",
    "initech-alex_kim-golden_hour.mkv",
]
DEFAULT_GALLERIES = {"Beach Days": 3, "City Lights": 2, "Portraits": 1}


class Library:
    """A throwaway library: videos (empty files), contact sheets, galleries, pvorg.json."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.videos = root / "videos"
        self.galleries = root / "galleries"
        self.config = root / "pvorg.json"
        self.videos.mkdir(parents=True)
        self.galleries.mkdir(parents=True)

    def add_video(self, name: str, *, sheet: bool = True) -> None:
        (self.videos / name).write_bytes(b"")
        if sheet:
            (self.videos / "img").mkdir(exist_ok=True)
            Image.new("RGB", (1920, 1080), (40, 90, 160)).save(self.videos / "img" / f"{name}.jpg")

    def add_gallery(self, name: str, images: int) -> None:
        folder = self.galleries / name
        folder.mkdir()
        for i in range(images):
            Image.new("RGB", (800, 1200), (i * 40, 120, 80)).save(folder / f"image_{i:02d}.jpg")

    def write_config(self, relations: dict | None = None, tags: list[str] | None = None, **extra) -> None:
        data = {
            "videosPath": str(self.videos),
            "galleriesPath": str(self.galleries),
            "tags": tags if tags is not None else ["4k", "night", "outdoor"],
            "videoRelations": relations or {},
            **extra,
        }
        self.config.write_text(json.dumps(data, indent=2) + "\n")

    def read_config(self) -> dict:
        return json.loads(self.config.read_text())


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Library:
    lib = Library(tmp_path / "library")
    monkeypatch.setenv("PVORG_CONFIG", str(lib.config))
    monkeypatch.setenv("PVORG_CACHE_DIR", str(tmp_path / "cache"))
    return lib


@pytest.fixture
def populated(library: Library) -> Library:
    for name in DEFAULT_VIDEOS:
        library.add_video(name)
    for name, count in DEFAULT_GALLERIES.items():
        library.add_gallery(name, count)
    library.write_config()
    return library


def make_client(library: Library) -> TestClient:
    """An app over `library`, loaded synchronously and without ffmpeg preprocessing."""
    app = create_app(start_pipeline=False, preprocess=False)
    app.state.pipeline.run_blocking()
    return TestClient(app)


@pytest.fixture
def client(populated: Library) -> TestClient:
    return make_client(populated)
