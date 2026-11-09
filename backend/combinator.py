"""Generate video+gallery combinations with filter logic."""

import random
from dataclasses import dataclass

from scanner import Gallery, Video


@dataclass
class Combination:
    video: Video
    gallery: Gallery


def generate_combinations(
    videos: list[Video],
    galleries: list[Gallery],
    selected_galleries: set[str],
    selected_studios: set[str],
    selected_tags: set[str],
    selected_cast: set[str],
) -> list[Combination]:
    """Replicate the SwiftUI generateCombinations() logic.

    - Filter videos by studio, cast (subset), tags (subset)
    - Pair each passing video with galleries that are both selected AND in video.related_galleries
    - Shuffle the result
    """
    combinations: list[Combination] = []

    for video in videos:
        if video.studio not in selected_studios:
            continue
        if selected_cast and not selected_cast.issubset(set(video.actors)):
            continue
        if selected_tags and not selected_tags.issubset(set(video.tags)):
            continue

        for gallery in galleries:
            if gallery.name in selected_galleries and gallery.name in video.related_galleries:
                combinations.append(Combination(video=video, gallery=gallery))

    random.shuffle(combinations)
    return combinations
