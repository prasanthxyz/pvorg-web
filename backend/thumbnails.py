"""Downsized images at the spec's decode sizes (SPEC §8.2), cached on disk outside the library.

Grids would otherwise download 1920 px contact sheets for 300 px cards. Pillow
decodes JPEGs in draft mode (DCT scaling), so a cold 1920→720 resize takes a few
milliseconds; results are cached keyed by path, size and modification time.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

SIZES = (320, 720, 1920)


def cache_root() -> Path:
    """`PVORG_CACHE_DIR`, else `~/.cache/pvorg-web`: the web app's own, disposable files."""
    override = os.environ.get("PVORG_CACHE_DIR")
    return Path(override).expanduser() if override else Path.home() / ".cache" / "pvorg-web"


def cache_dir() -> Path:
    """`<cache root>/thumbnails`."""
    return cache_root() / "thumbnails"


def nearest_size(requested: int) -> int | None:
    """The smallest standard size covering the request, or None for full resolution."""
    for size in SIZES:
        if requested <= size:
            return size
    return None


def thumbnail(source: Path, requested: int) -> Path:
    """A JPEG of `source` whose longest edge is at most the standard size for `requested`."""
    size = nearest_size(requested)
    if size is None:
        return source
    stat = source.stat()
    key = hashlib.sha1(f"{source}|{stat.st_mtime_ns}|{stat.st_size}|{size}".encode()).hexdigest()
    target = cache_dir() / key[:2] / f"{key}.jpg"
    if target.exists():
        return target

    with Image.open(source) as img:
        if max(img.size) <= size and img.format == "JPEG":
            return source
        img.draft("RGB", (size, size))
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        target.parent.mkdir(parents=True, exist_ok=True)
        # A unique temporary name, so concurrent requests for the same image never
        # write into each other's file; the last atomic replace wins.
        fd, partial = tempfile.mkstemp(prefix=f".{key}.", suffix=".partial", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as out:
                img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
            os.replace(partial, target)
        except BaseException:
            Path(partial).unlink(missing_ok=True)
            raise
    return target
