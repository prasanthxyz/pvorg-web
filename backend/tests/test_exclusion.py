"""Exclude Pairing and its exact undo (SPEC §3.6)."""

from __future__ import annotations

import json

from tests.conftest import Library


def current(client) -> tuple[str, str, int]:
    v = client.get("/api/viewer").json()
    return v["current"]["video"]["filename"], v["current"]["gallery"]["name"], v["position"]


def order(client) -> list[tuple[str, str]]:
    state = client.app.state.pvorg
    return [(c.video.filename, c.gallery.name) for c in state.combinations]


def test_exclude_writes_no_and_shows_the_next_in_place(client, populated: Library) -> None:
    client.post("/api/viewer/move", json={"index": 2})
    filename, gallery, _ = current(client)
    before = order(client)

    result = client.post("/api/pairings/exclude", json={"filename": filename, "gallery": gallery}).json()

    assert order(client) == [p for p in before if p != (filename, gallery)], "No reshuffle"
    assert result["viewer"]["position"] == 2
    assert (result["viewer"]["current"]["video"]["filename"], result["viewer"]["current"]["gallery"]["name"]) \
        == before[3]
    assert result["viewer"]["total"] == len(before) - 1
    relation = populated.read_config()["videoRelations"][filename]
    assert relation == {"galleries": [], "excludedGalleries": [gallery], "tags": [], "excludedTags": []}


def test_undo_restores_the_file_exactly_and_the_position(client, populated: Library) -> None:
    original = populated.config.read_text()
    client.post("/api/viewer/move", json={"index": 1})
    filename, gallery, _ = current(client)
    before = order(client)

    exclusion = client.post("/api/pairings/exclude", json={"filename": filename, "gallery": gallery}).json()
    restored = client.post(f"/api/pairings/restore/{exclusion['exclusionId']}").json()["viewer"]

    assert order(client) == before
    assert restored["position"] == 1 and restored["current"]["video"]["filename"] == filename
    assert populated.read_config() == json.loads(original), "Entry the exclusion created is gone"
    assert client.post(f"/api/pairings/restore/{exclusion['exclusionId']}").status_code == 404


def test_undo_brings_back_an_earlier_yes(populated: Library) -> None:
    populated.write_config({"globex-sam_lee-desert_road.mp4": {"galleries": ["Beach Days"], "excludedGalleries": [],
                                                               "tags": ["night"], "excludedTags": []}})
    from tests.conftest import make_client
    client = make_client(populated)
    exclusion = client.post("/api/pairings/exclude", json={"filename": "globex-sam_lee-desert_road.mp4",
                                                           "gallery": "Beach Days"}).json()
    assert populated.read_config()["videoRelations"]["globex-sam_lee-desert_road.mp4"]["galleries"] == []
    client.post(f"/api/pairings/restore/{exclusion['exclusionId']}")
    assert populated.read_config()["videoRelations"]["globex-sam_lee-desert_road.mp4"] == {
        "galleries": ["Beach Days"], "excludedGalleries": [], "tags": ["night"], "excludedTags": []}


def test_last_wraps_to_first_and_earlier_keeps_current(client) -> None:
    pairs = order(client)
    client.post("/api/viewer/move", json={"index": len(pairs) - 1})
    filename, gallery, _ = current(client)
    after = client.post("/api/pairings/exclude", json={"filename": filename, "gallery": gallery}).json()["viewer"]
    assert after["position"] == 0 and after["current"]["video"]["filename"] == pairs[0][0]

    client.post("/api/viewer/move", json={"index": 3})
    keep = current(client)
    earlier = order(client)[0]
    after = client.post("/api/pairings/exclude", json={"filename": earlier[0], "gallery": earlier[1]}).json()
    assert (after["viewer"]["current"]["video"]["filename"], after["viewer"]["current"]["gallery"]["name"]) == keep[:2]


def test_restore_skips_pairings_the_filters_now_hide(client, populated: Library) -> None:
    filename, gallery, _ = current(client)
    exclusion = client.post("/api/pairings/exclude", json={"filename": filename, "gallery": gallery}).json()
    galleries = [g for g in ["Beach Days", "City Lights", "Portraits"] if g != gallery]
    client.put("/api/filters", json={"galleries": galleries})
    client.post(f"/api/pairings/restore/{exclusion['exclusionId']}")
    assert (filename, gallery) not in order(client)
    assert filename not in populated.read_config()["videoRelations"], "The decision is still restored"


def test_exclude_validates_names(client) -> None:
    assert client.post("/api/pairings/exclude", json={"filename": "nope.mp4", "gallery": "Portraits"}).status_code \
        == 404
    assert client.post("/api/pairings/exclude", json={"filename": "globex-sam_lee-desert_road.mp4",
                                                      "gallery": "Nope"}).status_code == 404
