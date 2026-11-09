"""The same pvorg.json edits must produce the same content as pvorg-macos (SPEC §1.2).

`fixtures/compat` holds the input and expected outputs of a six-step sequence
first run against pvorg-macos: startup normalization, a gallery mapping save,
a tag mapping save, Exclude Pairing for a video without an entry, deleting a
video and stale-entry cleanup. `expected/5-cleanup.json` is the native app's
verbatim final output; steps 0–4 follow from the same rules. Content is
compared, not whitespace (§1.2 allows formatting to differ).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import Library, make_client

FIXTURES = Path(__file__).parent / "fixtures" / "compat"


def expected(name: str, root: Path) -> dict:
    text = (FIXTURES / "expected" / f"{name}.json").read_text(encoding="utf-8")
    return json.loads(text.replace("__ROOT__", str(root)))


@pytest.fixture
def compat_library(library: Library) -> Library:
    for video in ("acme-jane-one", "acme-jane-two", "globex-sam-three", "hooli-li-four"):
        (library.videos / f"{video}.mp4").write_bytes(b"")
    for gallery in ("G1", "G2", "G3"):
        (library.galleries / gallery).mkdir()
    text = (FIXTURES / "input.json").read_text(encoding="utf-8").replace("__ROOT__", str(library.root))
    library.config.write_text(text, encoding="utf-8")
    return library


def test_same_content_as_native(compat_library: Library) -> None:
    root = compat_library.root
    client = make_client(compat_library)
    assert compat_library.read_config() == expected("0-normalize", root)

    client.post("/api/mapping/galleries", json={"changes": {
        "acme-jane-one.mp4": {"G1": "yes", "G2": "no"},
        "acme-jane-two.mp4": {"G3": "no"},
        "globex-sam-three.mp4": {"G1": "undecided", "G2": "yes"},
    }}).raise_for_status()
    assert compat_library.read_config() == expected("1-gallery-mapping", root)

    client.post("/api/mapping/tags", json={"changes": {
        "acme-jane-one.mp4": {"t1": "yes", "t3": "no"},
        "globex-sam-three.mp4": {"t2": "no"},
    }}).raise_for_status()
    assert compat_library.read_config() == expected("2-tag-mapping", root)

    client.post("/api/pairings/exclude", json={"filename": "hooli-li-four.mp4", "gallery": "G2"}).raise_for_status()
    assert compat_library.read_config() == expected("3-exclude-pairing", root)

    client.post("/api/library/delete", json={"filenames": ["acme-jane-two.mp4"]}).raise_for_status()
    assert compat_library.read_config() == expected("4-delete", root)

    stale = client.get("/api/cleanup").json()["staleEntries"]
    assert stale == ["oldstudio-x-gone.mp4"]
    client.post("/api/cleanup", json={"entries": stale}).raise_for_status()
    assert compat_library.read_config() == expected("5-cleanup", root)
