"""The single-user library state the API serves (SPEC Part I).

The server owns the ordered combination list and the viewer position, so
excluding a pairing can remove it in place and the Filters page can show
"Up Next" from where the viewer is.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from cache import MetadataCache
from combinator import Combination, Filters, gallery_passes, generate_combinations, video_passes
from config import AppConfig, VideoRelation, save_config
from display import fold, humanize
from relations import Kind, State, StalePreview, apply_mapping_changes, stale_preview, tri_state
from scanner import VIDEO_EXTENSIONS, Gallery, SkippedFile, Video, scan_galleries, scan_videos

logger = logging.getLogger(__name__)


@dataclass
class PairingExclusion:
    """What's needed to undo one Exclude Pairing exactly (SPEC §3.6)."""

    id: str
    filename: str
    gallery: str
    previous_state: State
    had_relation: bool
    index: int | None


@dataclass
class Startup:
    phase: str = "loading"  # loading | ready | error
    step: str = "Starting Up"
    detail: str | None = None
    fraction: float | None = None
    error: str | None = None


@dataclass
class DeletionResult:
    deleted: int
    errors: list[str] = field(default_factory=list)


class AppState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.config: AppConfig | None = None
        self.galleries: list[Gallery] = []
        self.videos: list[Video] = []
        self.skipped: list[SkippedFile] = []
        self.filters = Filters()
        self.combinations: list[Combination] = []
        self.position = 0
        self.revision = 0
        self.exclusions: dict[str, PairingExclusion] = {}
        self.startup = Startup()

    # ---- Loading ----

    def apply_library(self, config: AppConfig, galleries: list[Gallery], videos: list[Video],
                      skipped: list[SkippedFile], *, reset_filters: bool) -> None:
        with self.lock:
            self.config, self.galleries, self.videos, self.skipped = config, galleries, videos, skipped
            if reset_filters:
                self.filters = self.default_filters()
            else:
                self._intersect_filters()
            self.regenerate()

    def rescan(self, *, reset_filters: bool) -> None:
        assert self.config is not None
        galleries = scan_galleries(self.config)
        videos, skipped = scan_videos(self.config, [g.name for g in galleries])
        self.apply_library(self.config, galleries, videos, skipped, reset_filters=reset_filters)

    def default_filters(self) -> Filters:
        return Filters(
            galleries={g.name for g in self.galleries},
            studios={v.studio for v in self.videos},
        )

    def _intersect_filters(self) -> None:
        f = self.filters
        galleries, studios = set(self.gallery_names()), set(self.all_studios())
        f.galleries = (f.galleries & galleries) or galleries
        f.studios = (f.studios & studios) or studios
        f.tags &= set(self.all_tags())
        f.cast &= set(self.all_cast())

    def regenerate(self) -> None:
        with self.lock:
            self.combinations = generate_combinations(self.videos, self.galleries, self.filters)
            self.position = 0
            self.revision += 1

    # ---- Vocabularies ----

    def gallery_names(self) -> list[str]:
        return sorted(g.name for g in self.galleries)

    def all_studios(self) -> list[str]:
        return sorted({v.studio for v in self.videos})

    def all_tags(self) -> list[str]:
        return sorted(self.config.tags) if self.config else []

    def all_cast(self) -> list[str]:
        return sorted({a for v in self.videos for a in v.actors})

    def columns(self, kind: Kind) -> list[str]:
        return self.gallery_names() if kind == "galleries" else self.all_tags()

    # ---- Filters ----

    def filters_are_default(self) -> bool:
        d = self.default_filters()
        f = self.filters
        return f.galleries == d.galleries and f.studios == d.studios and not f.tags and not f.cast

    def set_filters(self, *, galleries=None, studios=None, tags=None, cast=None) -> None:
        with self.lock:
            if galleries is not None:
                self.filters.galleries = set(galleries)
            if studios is not None:
                self.filters.studios = set(studios)
            if tags is not None:
                self.filters.tags = set(tags)
            if cast is not None:
                self.filters.cast = set(cast)
            self.regenerate()

    def reset_filters(self) -> None:
        with self.lock:
            self.filters = self.default_filters()
            self.regenerate()

    # ---- Viewer ----

    def current(self) -> Combination | None:
        if not self.combinations:
            return None
        return self.combinations[self.position % len(self.combinations)]

    def move(self, delta: int) -> None:
        with self.lock:
            if self.combinations:
                self.position = (self.position + delta) % len(self.combinations)

    def goto(self, index: int) -> None:
        with self.lock:
            if 0 <= index < len(self.combinations):
                self.position = index

    def exclude_pairing(self, filename: str, gallery: str) -> PairingExclusion:
        """Write No for the gallery and drop just that pairing, keeping order and position."""
        with self.lock:
            config = self._config()
            relation = config.videoRelations.get(filename)
            exclusion = PairingExclusion(
                id=uuid.uuid4().hex,
                filename=filename,
                gallery=gallery,
                previous_state=tri_state(relation, "galleries", gallery),
                had_relation=relation is not None,
                index=None,
            )
            apply_mapping_changes(config, "galleries", {filename: {gallery: "no"}}, self.gallery_names())
            save_config(config)
            self._refresh_related_galleries(filename)

            index = self._index_of(filename, gallery)
            if index is not None:
                del self.combinations[index]
                if index < self.position:
                    self.position -= 1
                if self.position >= len(self.combinations):
                    self.position = 0
            exclusion.index = index
            self.revision += 1
            self.exclusions[exclusion.id] = exclusion
            return exclusion

    def restore_pairing(self, exclusion: PairingExclusion) -> None:
        """Undo an exclusion exactly, and put the pairing back if the filters allow it."""
        with self.lock:
            config = self._config()
            apply_mapping_changes(
                config, "galleries", {exclusion.filename: {exclusion.gallery: exclusion.previous_state}},
                self.gallery_names(),
            )
            relation = config.videoRelations.get(exclusion.filename)
            if not exclusion.had_relation and relation is not None and relation.is_empty():
                del config.videoRelations[exclusion.filename]
            save_config(config)
            self._refresh_related_galleries(exclusion.filename)

            video = next((v for v in self.videos if v.filename == exclusion.filename), None)
            gallery = next((g for g in self.galleries if g.name == exclusion.gallery), None)
            if (video and gallery and self._index_of(video.filename, gallery.name) is None
                    and video_passes(video, self.filters) and gallery_passes(gallery, video, self.filters)):
                index = min(exclusion.index if exclusion.index is not None else self.position, len(self.combinations))
                self.combinations.insert(index, Combination(video, gallery))
                self.position = index
            self.exclusions.pop(exclusion.id, None)
            self.revision += 1

    def _index_of(self, filename: str, gallery: str) -> int | None:
        return next(
            (i for i, c in enumerate(self.combinations) if c.video.filename == filename and c.gallery.name == gallery),
            None,
        )

    def _refresh_related_galleries(self, filename: str) -> None:
        """Recompute a video's galleries from config the way the scanner does."""
        assert self.config is not None
        relation = self.config.videoRelations.get(filename)
        excluded = set(relation.no_galleries) if relation else set()
        for video in self.videos:
            if video.filename == filename:
                video.related_galleries = [g.name for g in self.galleries if g.name not in excluded]

    # ---- Mapping ----

    def save_mappings(self, kind: Kind, changes: dict[str, dict[str, State]]) -> int:
        with self.lock:
            config = self._config()
            known = {v.filename for v in self.videos}
            changes = {f: cells for f, cells in changes.items() if f in known and cells}
            count = sum(len(cells) for cells in changes.values())
            if not count:
                return 0
            apply_mapping_changes(config, kind, changes, self.columns(kind))
            save_config(config)
            self.rescan(reset_filters=False)
            return count

    # ---- Library ----

    def delete_videos(self, filenames: list[str]) -> DeletionResult:
        """Permanently remove videos and everything derived from them (SPEC §3.7)."""
        with self.lock:
            config = self._config()
            videos_dir = Path(config.videosPath)
            known = {v.filename for v in self.videos}
            cache = MetadataCache(videos_dir / "cache.json")
            result = DeletionResult(deleted=0)
            cache_changed = False

            for filename in sorted(set(filenames)):
                if filename not in known:
                    result.errors.append(f"Rejected unknown filename: {filename}")
                    continue
                removed_something = False
                for target in (
                    videos_dir / filename,
                    videos_dir / "img" / f"{filename}.jpg",
                    videos_dir / "sprite" / f"{filename}_sprite.jpg",
                    videos_dir / "sprite" / f"{filename}_sprite.vtt",
                ):
                    if target.is_file():
                        try:
                            target.unlink()
                            removed_something = True
                        except OSError as e:
                            result.errors.append(f"Couldn’t delete {target}: {e.strerror}")
                if config.videoRelations.pop(filename, None) is not None:
                    removed_something = True
                if cache.remove(filename):
                    cache_changed = removed_something = True
                result.deleted += removed_something

            save_config(config)
            if cache_changed:
                cache.save()
            self.rescan(reset_filters=True)
            return result

    # ---- Stale entries ----

    def stale_preview(self) -> StalePreview:
        with self.lock:
            return stale_preview(self._config(), VIDEO_EXTENSIONS)

    def remove_stale(self, entries: list[str]) -> int:
        """Remove previewed entries whose video is still missing; nothing else."""
        with self.lock:
            config = self._config()
            still_stale = set(stale_preview(config, VIDEO_EXTENSIONS).stale_entries)
            removed = 0
            for key in entries:
                if key in still_stale and config.videoRelations.pop(key, None) is not None:
                    removed += 1
            if removed:
                save_config(config)
                self.rescan(reset_filters=False)
            return removed

    def _config(self) -> AppConfig:
        if self.config is None:
            raise RuntimeError("The library isn’t loaded yet.")
        return self.config

    # ---- Search helpers ----

    @staticmethod
    def label_sorted(values: list[str], humanized: bool) -> list[dict[str, str]]:
        items = [{"value": v, "label": humanize(v) if humanized else v} for v in values]
        return sorted(items, key=lambda i: (fold(i["label"]), i["value"]))


# Kept for type hints in API modules.
__all__ = ["AppState", "PairingExclusion", "Startup", "DeletionResult", "VideoRelation"]
