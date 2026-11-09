"""Deletion, stale entries, orphaned assets and media (SPEC §3.4, §3.5, §3.7)."""

from __future__ import annotations

import json

from PIL import Image

from cleanup import cleanup_orphaned_assets
from tests.conftest import Library, make_client

DOOMED = "globex-sam_lee-desert_road.mp4"


def test_delete_removes_everything_derived(populated: Library) -> None:
    sprite = populated.videos / "sprite"
    sprite.mkdir()
    for ext in ("jpg", "vtt"):
        (sprite / f"{DOOMED}_sprite.{ext}").write_text("x")
    (populated.videos / "cache.json").write_text(json.dumps({DOOMED: {"duration": 6}, "keep.mp4": {"duration": 1}}))
    populated.write_config({DOOMED: {"galleries": [], "excludedGalleries": [], "tags": [], "excludedTags": []}})
    client = make_client(populated)
    client.put("/api/filters", json={"studios": ["acme"]})

    result = client.post("/api/library/delete", json={"filenames": [DOOMED, "unknown.mp4"]}).json()

    assert result["deleted"] == 1
    assert result["errors"] == ["Rejected unknown filename: unknown.mp4"]
    assert not (populated.videos / DOOMED).exists()
    assert not (populated.videos / "img" / f"{DOOMED}.jpg").exists()
    assert not any(sprite.iterdir())
    assert DOOMED not in populated.read_config()["videoRelations"]
    assert json.loads((populated.videos / "cache.json").read_text()) == {"keep.mp4": {"duration": 1}}
    assert len(client.get("/api/library").json()["videos"]) == 3
    assert client.get("/api/filters").json()["isDefault"], "Filters reset after deletion"


def test_stale_preview_and_removal(populated: Library) -> None:
    populated.write_config({
        "gone-a-b.mp4": {"galleries": [], "excludedGalleries": [], "tags": [], "excludedTags": []},
        DOOMED: {"galleries": [], "excludedGalleries": ["Portraits"], "tags": [], "excludedTags": []},
    })
    client = make_client(populated)
    preview = client.get("/api/cleanup").json()
    assert preview == {"videosPath": str(populated.videos), "videoFileCount": 4, "relationCount": 2,
                       "staleEntries": ["gone-a-b.mp4"], "highRisk": False}

    assert client.post("/api/cleanup", json={"entries": ["gone-a-b.mp4", DOOMED]}).json() == {"removed": 1}
    assert list(populated.read_config()["videoRelations"]) == [DOOMED], "Only entries still stale are removed"


def test_stale_high_risk_when_no_videos_are_visible(populated: Library) -> None:
    populated.write_config({DOOMED: {"galleries": [], "excludedGalleries": [], "tags": [], "excludedTags": []}})
    client = make_client(populated)
    for p in populated.videos.iterdir():
        if p.is_file():
            p.unlink()
    preview = client.get("/api/cleanup").json()
    assert preview["videoFileCount"] == 0 and preview["highRisk"] is True


def test_startup_never_removes_stale_entries(populated: Library) -> None:
    populated.write_config({"gone-a-b.mp4": {"galleries": [], "excludedGalleries": [], "tags": [],
                                             "excludedTags": []}})
    make_client(populated)
    assert "gone-a-b.mp4" in populated.read_config()["videoRelations"]


def test_orphan_cleanup_touches_only_derived_assets(populated: Library) -> None:
    sprite = populated.videos / "sprite"
    sprite.mkdir()
    (sprite / "gone-a-b.mp4_sprite.jpg").write_text("x")
    (sprite / f"{DOOMED}_sprite.vtt").write_text("x")
    Image.new("RGB", (10, 10)).save(populated.videos / "img" / "gone-a-b.mp4.jpg")
    removed = cleanup_orphaned_assets(str(populated.videos), {
        "acme-jane_doe-harbor_lights.mp4", "acme-jane_doe-john_roe-mountain_pass.mp4", DOOMED,
        "initech-alex_kim-golden_hour.mkv"})
    assert removed == 2
    assert sorted(p.name for p in sprite.iterdir()) == [f"{DOOMED}_sprite.vtt"]
    assert len(list((populated.videos / "img").iterdir())) == 4
    assert len([p for p in populated.videos.iterdir() if p.is_file()]) == 4


def test_media_sizes_and_access(client, populated: Library) -> None:
    library = client.get("/api/library").json()
    card = client.get(library["videos"][0]["thumbUrl"])
    assert card.status_code == 200 and card.headers["content-type"] == "image/jpeg"
    from io import BytesIO
    assert max(Image.open(BytesIO(card.content)).size) == 720

    images = client.get("/api/viewer").json()["current"]["gallery"]["images"]
    assert client.get(images[0]).status_code == 200
    assert client.get("/api/media/sheet/..%2F..%2Fpvorg.json").status_code == 404
    assert client.get("/api/media/gallery/Portraits/..%2F..%2Fpvorg.json").status_code == 404
    assert client.get("/api/media/video/unknown.mp4").status_code == 404
