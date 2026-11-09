"""Downsized images (SPEC §8.2, §11)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

import thumbnails


@pytest.fixture
def sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PVORG_CACHE_DIR", str(tmp_path / "cache"))
    path = tmp_path / "sheet.jpg"
    Image.new("RGB", (1920, 1080), (200, 40, 40)).save(path, "JPEG")
    return path


def test_nearest_size_covers_the_request() -> None:
    assert thumbnails.nearest_size(200) == 320
    assert thumbnails.nearest_size(720) == 720
    assert thumbnails.nearest_size(1000) == 1920
    assert thumbnails.nearest_size(4096) is None


def test_downsizes_and_caches_outside_the_library(sheet: Path) -> None:
    result = thumbnails.thumbnail(sheet, 300)
    assert result != sheet
    assert thumbnails.cache_dir() in result.parents
    with Image.open(result) as img:
        assert max(img.size) == 320
    assert thumbnails.thumbnail(sheet, 300) == result


def test_small_jpegs_are_served_as_is(sheet: Path) -> None:
    assert thumbnails.thumbnail(sheet, 1920) == sheet
    assert thumbnails.thumbnail(sheet, 5000) == sheet


def test_concurrent_requests_all_get_a_complete_image(sheet: Path) -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: thumbnails.thumbnail(sheet, 720), range(16)))
    assert len(set(results)) == 1
    with Image.open(results[0]) as img:
        img.load()
        assert max(img.size) == 720
    leftovers = [p for p in results[0].parent.iterdir() if p.suffix == ".partial"]
    assert leftovers == []
