"""Server-side application state for single-user local app."""

from __future__ import annotations

import logging
from typing import Any

from combinator import Combination, generate_combinations
from config import AppConfig, load_config
from scanner import Gallery, Video, scan_galleries, scan_videos

logger = logging.getLogger(__name__)


class AppState:
    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.videos: list[Video] = []
        self.galleries: list[Gallery] = []
        self.combinations: list[Combination] = []
        self.combination_index: int = 0

        self.selected_galleries: set[str] = set()
        self.selected_studios: set[str] = set()
        self.selected_tags: set[str] = set()
        self.selected_cast: set[str] = set()

        self.ready: bool = False
        self.preprocessing_progress: str = ""
        self.skipped_files: list[tuple[str, list[str]]] = []
        self.startup_report: dict[str, Any] = {}

    def load(self) -> None:
        self.config = load_config()
        self.galleries = scan_galleries(self.config)
        gallery_names = [g.name for g in self.galleries]
        self.videos, self.skipped_files = scan_videos(self.config, gallery_names)

        self.selected_galleries = set(gallery_names)
        self.selected_studios = {v.studio for v in self.videos}
        self.selected_tags = set()
        self.selected_cast = set()

        self.regenerate_combinations()
        logger.info(
            "State loaded: %d videos, %d galleries, %d combinations",
            len(self.videos), len(self.galleries), len(self.combinations),
        )

    def regenerate_combinations(self) -> None:
        self.combinations = generate_combinations(
            videos=self.videos,
            galleries=self.galleries,
            selected_galleries=self.selected_galleries,
            selected_studios=self.selected_studios,
            selected_tags=self.selected_tags,
            selected_cast=self.selected_cast,
        )
        self.combination_index = 0

    def shuffle_combinations(self) -> None:
        import random
        random.shuffle(self.combinations)
        self.combination_index = 0

    def current_combination(self) -> Combination | None:
        if not self.combinations:
            return None
        return self.combinations[self.combination_index]

    def next_combination(self) -> None:
        if not self.combinations:
            return
        self.combination_index = (self.combination_index + 1) % len(self.combinations)

    def prev_combination(self) -> None:
        if not self.combinations:
            return
        self.combination_index = (self.combination_index - 1) % len(self.combinations)

    # ---- Derived data for the config page ----

    def all_studios(self) -> list[str]:
        return sorted({v.studio for v in self.videos})

    def all_tags(self) -> list[str]:
        return sorted(self.config.tags) if self.config else []

    def all_cast(self) -> list[str]:
        actors: set[str] = set()
        for v in self.videos:
            actors.update(v.actors)
        return sorted(actors)

    def all_gallery_names(self) -> list[str]:
        return sorted(g.name for g in self.galleries)
