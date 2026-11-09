"""Mapping saves (SPEC §3.3)."""

from __future__ import annotations

from config import AppConfig, VideoRelation
from relations import apply_mapping_changes
from tests.conftest import Library


def test_apply_preserves_unknown_values_and_the_other_pair() -> None:
    config = AppConfig(videosPath="/v", galleriesPath="/g", tags=["t1", "t2"], videoRelations={
        "a.mp4": VideoRelation(galleries=["Retired", "Café"], excludedGalleries=[], tags=["t2"], excludedTags=None),
    })
    apply_mapping_changes(config, "galleries", {
        "a.mp4": {"G2": "yes", "G1": "no", "Unknown": "yes"},
        "b.mp4": {"G1": "yes"},
    }, ["G1", "G2"])

    a = config.videoRelations["a.mp4"]
    assert a.galleries == ["G2", "Retired", "Café"], "Known names in vocabulary order, unknowns kept after"
    assert a.excludedGalleries == ["G1"]
    assert a.tags == ["t2"] and a.excludedTags == [], "The other pair untouched (missing becomes [])"
    assert config.videoRelations["b.mp4"].model_dump() == {"galleries": ["G1"], "excludedGalleries": [],
                                                          "tags": [], "excludedTags": []}


def test_undecided_removes_from_both() -> None:
    config = AppConfig(videosPath="/v", galleriesPath="/g", tags=[], videoRelations={
        "a.mp4": VideoRelation(galleries=["G1"], excludedGalleries=["G2"], tags=[], excludedTags=[]),
    })
    apply_mapping_changes(config, "galleries", {"a.mp4": {"G1": "undecided", "G2": "undecided"}}, ["G1", "G2"])
    assert config.videoRelations["a.mp4"].galleries == [] and config.videoRelations["a.mp4"].excludedGalleries == []


def test_api_rows_and_save(client, populated: Library) -> None:
    data = client.get("/api/mapping/tags").json()
    assert data["columns"] == ["4k", "night", "outdoor"]
    assert all(row["states"] == "uuu" for row in data["rows"])

    client.put("/api/filters", json={"studios": ["acme"]})
    saved = client.post("/api/mapping/tags", json={"changes": {
        "globex-sam_lee-desert_road.mp4": {"outdoor": "yes", "4k": "no"},
        "missing.mp4": {"4k": "yes"},
    }}).json()
    assert saved == {"saved": 2}, "Unknown videos are ignored"

    relation = populated.read_config()["videoRelations"]["globex-sam_lee-desert_road.mp4"]
    assert relation == {"galleries": [], "excludedGalleries": [], "tags": ["outdoor"], "excludedTags": ["4k"]}
    assert "missing.mp4" not in populated.read_config()["videoRelations"]

    rows = {r["filename"]: r["states"] for r in client.get("/api/mapping/tags").json()["rows"]}
    assert rows["globex-sam_lee-desert_road.mp4"] == "nuy"
    assert client.get("/api/filters").json()["sections"]["studios"]["selected"] == ["acme"], "Filters kept"
