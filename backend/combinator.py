"""Combinations and the filter rules (SPEC §3.1)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from scanner import Gallery, Video


@dataclass
class Combination:
    video: Video
    gallery: Gallery

    @property
    def id(self) -> str:
        return f"{self.video.filename}\u0000{self.gallery.name}"


@dataclass
class Filters:
    galleries: set[str] = field(default_factory=set)
    studios: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)
    cast: set[str] = field(default_factory=set)


def video_passes(video: Video, filters: Filters) -> bool:
    """Studio included, every required tag marked yes, every required cast member present."""
    if video.studio not in filters.studios:
        return False
    if filters.cast and not filters.cast.issubset(video.actors):
        return False
    if filters.tags and not filters.tags.issubset(video.tags):
        return False
    return True


def gallery_passes(gallery: Gallery, video: Video, filters: Filters) -> bool:
    """Gallery included, and the video isn't excluded from it."""
    return gallery.name in filters.galleries and gallery.name in video.related_galleries


def generate_combinations(
    videos: list[Video],
    galleries: list[Gallery],
    filters: Filters,
    rng: random.Random | None = None,
) -> list[Combination]:
    combinations = [
        Combination(video, gallery)
        for video in videos
        if video_passes(video, filters)
        for gallery in galleries
        if gallery_passes(gallery, video, filters)
    ]
    (rng or random).shuffle(combinations)
    return combinations
