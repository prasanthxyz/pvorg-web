"""pvorg.json reading and writing rules (SPEC §1.2)."""

from __future__ import annotations

import json

import pytest

from config import AppConfig, ConfigError, load_config, normalize_relations, save_config
from tests.conftest import Library, make_client


def test_save_format(library: Library) -> None:
    library.write_config({"z.mp4": {"galleries": ["Café"]}, "a.mp4": {"tags": []}}, notes="unknown")
    config = load_config()
    save_config(config)
    text = library.config.read_text(encoding="utf-8")

    assert text.endswith("}\n")
    assert "Café" in text, "UTF-8, not escaped"
    data = json.loads(text)
    assert "notes" not in data, "Keys outside the schema are not preserved"
    assert list(data) == sorted(data), "Keys sorted"
    assert list(data["videoRelations"]) == ["a.mp4", "z.mp4"]
    assert data["videoRelations"]["z.mp4"] == {"galleries": ["Café"]}, "Missing arrays stay missing"
    assert text.splitlines()[1].startswith('  "galleriesPath"'), "Two-space indent"
    assert [p.name for p in library.root.iterdir() if p.name.startswith(".")] == [], "Atomic write leaves no temp"


def test_normalization(library: Library) -> None:
    library.write_config({"a.mp4": {"galleries": ["G"], "tags": None}, "b.mp4": {
        "galleries": [], "excludedGalleries": [], "tags": [], "excludedTags": []}})
    config = load_config()
    assert normalize_relations(config) == 1
    assert config.videoRelations["a.mp4"].model_dump() == {"galleries": ["G"], "excludedGalleries": [], "tags": [],
                                                          "excludedTags": []}
    assert normalize_relations(config) == 0


def test_startup_normalizes_and_saves_only_when_needed(populated: Library) -> None:
    populated.write_config({"acme-jane_doe-harbor_lights.mp4": {"galleries": ["Beach Days"]}})
    make_client(populated)
    assert populated.read_config()["videoRelations"]["acme-jane_doe-harbor_lights.mp4"] == {
        "galleries": ["Beach Days"], "excludedGalleries": [], "tags": [], "excludedTags": []}

    before = populated.config.stat().st_mtime_ns
    make_client(populated)
    assert populated.config.stat().st_mtime_ns == before, "Nothing to normalize: no write"


@pytest.mark.parametrize(("content", "message"), [
    (None, "couldn’t be found"),
    ("{not json", "isn’t valid JSON"),
    ('{"videosPath": "/x", "tags": [], "videoRelations": {}}', "the required key “galleriesPath” is missing"),
])
def test_config_errors(library: Library, content: str | None, message: str) -> None:
    if content is not None:
        library.config.write_text(content)
    with pytest.raises(ConfigError, match=message):
        load_config()


def test_startup_error_is_recoverable(library: Library) -> None:
    client = make_client(library)
    status = client.get("/api/status").json()
    assert status["phase"] == "error"
    assert "couldn’t be found" in status["error"]
    assert status["configExists"] is False
    assert client.get("/api/viewer").status_code == 503

    library.add_video("acme-jane-one.mp4")
    library.add_gallery("G1", 1)
    library.write_config()
    client.app.state.pipeline.run_blocking()
    assert client.get("/api/status").json()["phase"] == "ready"


def test_schema_requires_all_fields() -> None:
    with pytest.raises(Exception):
        AppConfig.model_validate({"videosPath": "/v", "galleriesPath": "/g", "videoRelations": {}})
