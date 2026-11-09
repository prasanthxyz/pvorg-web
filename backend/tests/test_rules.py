"""Library scanning, filter rules and presentation (SPEC §1.3, §2, §3.1)."""

from __future__ import annotations

from combinator import Filters, generate_combinations
from config import load_config
from display import credits, fold, humanize
from scanner import scan_galleries, scan_videos, validate_video_filename
from tests.conftest import Library, make_client


def scan(lib: Library):
    config = load_config()
    galleries = scan_galleries(config)
    videos, skipped = scan_videos(config, [g.name for g in galleries])
    return config, galleries, videos, skipped


def test_tags_are_opt_in_and_galleries_opt_out(populated: Library) -> None:
    populated.write_config({
        "acme-jane_doe-harbor_lights.mp4": {
            "galleries": [], "excludedGalleries": ["Portraits"], "tags": ["outdoor"], "excludedTags": ["night"],
        },
        "globex-sam_lee-desert_road.mp4": {"galleries": [], "excludedGalleries": [], "tags": [], "excludedTags": []},
    })
    _, _, videos, _ = scan(populated)
    by_name = {v.filename: v for v in videos}

    harbor = by_name["acme-jane_doe-harbor_lights.mp4"]
    assert harbor.related_galleries == ["Beach Days", "City Lights"]
    assert harbor.tags == ["outdoor"], "Only tags marked yes count; undecided 4k doesn't"
    assert by_name["globex-sam_lee-desert_road.mp4"].tags == [], "An entry with no decisions has no tags"
    untouched = by_name["initech-alex_kim-golden_hour.mkv"]
    assert untouched.tags == [] and untouched.related_galleries == ["Beach Days", "City Lights", "Portraits"]


def test_filter_rules(populated: Library) -> None:
    populated.write_config({
        "acme-jane_doe-harbor_lights.mp4": {"galleries": [], "excludedGalleries": [], "tags": ["outdoor", "night"],
                                            "excludedTags": []},
        "globex-sam_lee-desert_road.mp4": {"galleries": [], "excludedGalleries": ["City Lights"],
                                           "tags": ["outdoor"], "excludedTags": ["night"]},
    })
    _, galleries, videos, _ = scan(populated)
    every = Filters(galleries={g.name for g in galleries}, studios={v.studio for v in videos})

    def shown(**kw) -> set[str]:
        f = Filters(galleries=kw.get("galleries", every.galleries), studios=kw.get("studios", every.studios),
                    tags=set(kw.get("tags", ())), cast=set(kw.get("cast", ())))
        return {c.video.filename for c in generate_combinations(videos, galleries, f)}

    assert shown() == {v.filename for v in videos}, "No required tags: tagged and untagged videos alike"
    assert shown(tags=["outdoor"]) == {"acme-jane_doe-harbor_lights.mp4", "globex-sam_lee-desert_road.mp4"}
    assert shown(tags=["outdoor", "night"]) == {"acme-jane_doe-harbor_lights.mp4"}, "Every required tag must be yes"
    assert shown(cast=["jane_doe", "john_roe"]) == {"acme-jane_doe-john_roe-mountain_pass.mp4"}
    assert shown(studios={"globex"}) == {"globex-sam_lee-desert_road.mp4"}

    pairs = generate_combinations(videos, galleries, every)
    assert len(pairs) == 4 * 3 - 1, "Each video with every gallery it isn't excluded from"
    only_city = {c.gallery.name for c in generate_combinations(videos, galleries, Filters(
        galleries={"City Lights"}, studios=every.studios))}
    assert only_city == {"City Lights"}


def test_skipped_files_and_reasons(populated: Library) -> None:
    populated.add_video("Bad Name.mp4", sheet=False)
    populated.add_video("nodashes.mp4", sheet=False)
    (populated.videos / ".hidden-x-y.mp4").write_bytes(b"")
    (populated.videos / "notes.txt").write_text("x")
    _, _, videos, skipped = scan(populated)
    assert len(videos) == 4
    assert [s.filename for s in skipped] == ["Bad Name.mp4", "nodashes.mp4"]
    assert skipped[0].reasons == ["Contains uppercase characters", "Contains spaces",
                                  "Fewer than 3 dash-separated parts (need studio-cast-title)"]
    assert validate_video_filename("unknown-unknown-party.time.mp4") == (True, [])


def test_videos_sort_by_humanized_title(populated: Library) -> None:
    _, _, videos, _ = scan(populated)
    assert [v.display_title for v in videos] == ["Desert Road", "Golden Hour", "Harbor Lights", "Mountain Pass"]


def test_presentation() -> None:
    assert humanize("jane_doe") == "Jane Doe"
    assert humanize("4k__clip") == "4k Clip"
    assert credits("acme", ["jane_doe"]) == "Acme · Jane Doe"
    assert credits("acme", ["jane_doe", "john_roe"]) == "Acme · Jane Doe and John Roe"
    assert credits("acme", ["a", "b", "c"]) == "Acme · A, B, and C"
    assert credits("acme", []) == "Acme"
    assert fold("Café") == fold("cafe")


def test_viewer_empty_reasons(library: Library) -> None:
    library.write_config()
    client = make_client(library)
    assert client.get("/api/viewer").json()["empty"]["reason"] == "noVideos"

    library.add_video("acme-jane-one.mp4")
    client = make_client(library)
    assert client.get("/api/viewer").json()["empty"]["reason"] == "noGalleries"

    library.add_gallery("G1", 1)
    library.write_config({"acme-jane-one.mp4": {"galleries": [], "excludedGalleries": ["G1"], "tags": [],
                                                "excludedTags": []}})
    client = make_client(library)
    assert client.get("/api/viewer").json()["empty"]["reason"] == "mappings"

    library.write_config()
    client = make_client(library)
    client.put("/api/filters", json={"tags": ["4k"]})
    empty = client.get("/api/viewer").json()["empty"]
    assert empty["reason"] == "filters" and empty["tagsRequired"] is True
