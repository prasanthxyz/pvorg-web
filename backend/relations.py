"""Pure rules for changing relations in pvorg.json (SPEC §3.3, §3.5, §3.6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from config import AppConfig, VideoRelation

Kind = Literal["galleries", "tags"]
State = Literal["yes", "no", "undecided"]

_FIELDS: dict[Kind, tuple[str, str]] = {
    "galleries": ("galleries", "excludedGalleries"),
    "tags": ("tags", "excludedTags"),
}
_OTHER: dict[Kind, Kind] = {"galleries": "tags", "tags": "galleries"}


def tri_state(relation: VideoRelation | None, kind: Kind, column: str) -> State:
    if relation is None:
        return "undecided"
    yes_field, no_field = _FIELDS[kind]
    if column in (getattr(relation, yes_field) or []):
        return "yes"
    if column in (getattr(relation, no_field) or []):
        return "no"
    return "undecided"


def apply_mapping_changes(
    config: AppConfig,
    kind: Kind,
    changes: dict[str, dict[str, State]],
    ordered_columns: list[str],
) -> None:
    """Apply pending cell changes exactly as the other apps do.

    Known names are written in vocabulary order; unknown values already present are
    kept after them; the other relation pair is left as it was (missing arrays become []).
    """
    known = set(ordered_columns)
    yes_field, no_field = _FIELDS[kind]
    other_yes, other_no = _FIELDS[_OTHER[kind]]

    for filename, cells in changes.items():
        relation = config.videoRelations.get(filename) or VideoRelation(
            galleries=[], excludedGalleries=[], tags=[], excludedTags=[]
        )
        original_yes = list(getattr(relation, yes_field) or [])
        original_no = list(getattr(relation, no_field) or [])
        yes, no = set(original_yes), set(original_no)

        for column, state in cells.items():
            if column not in known:
                continue
            if state == "yes":
                yes.add(column)
                no.discard(column)
            elif state == "no":
                no.add(column)
                yes.discard(column)
            else:
                yes.discard(column)
                no.discard(column)

        setattr(relation, yes_field,
                [c for c in ordered_columns if c in yes] + [c for c in original_yes if c not in known and c in yes])
        setattr(relation, no_field,
                [c for c in ordered_columns if c in no] + [c for c in original_no if c not in known and c in no])
        for field in (other_yes, other_no):
            if getattr(relation, field) is None:
                setattr(relation, field, [])
        config.videoRelations[filename] = relation


@dataclass
class StalePreview:
    videos_path: str
    video_file_count: int
    relation_count: int
    stale_entries: list[str]

    @property
    def high_risk(self) -> bool:
        """No videos visible while entries exist — a disconnected drive, say."""
        return self.video_file_count == 0 and self.relation_count > 0


def stale_preview(config: AppConfig, video_extensions: set[str]) -> StalePreview:
    videos_dir = Path(config.videosPath)
    if not videos_dir.is_dir():
        raise FileNotFoundError(f"Videos directory is missing: {config.videosPath}")
    files = [p for p in videos_dir.iterdir() if p.is_file() and not p.name.startswith(".")]
    video_count = sum(1 for p in files if p.suffix.lower() in video_extensions)
    stale = sorted(name for name in config.videoRelations if not (videos_dir / name).exists())
    return StalePreview(config.videosPath, video_count, len(config.videoRelations), stale)
