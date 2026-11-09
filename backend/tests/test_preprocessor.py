"""Preview generation with real media (skipped without ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from preprocessor import _get_video_duration, generate_sprite, generate_tgp

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


@pytest.fixture
def mkv(tmp_path: Path) -> Path:
    path = tmp_path / "studio-cast-clip.mkv"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=320x180:r=24:d=3", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_matroska_duration_falls_back_to_the_container(mkv: Path) -> None:
    duration = _get_video_duration(mkv)
    assert duration is not None and 2.5 < duration < 3.5


def test_contact_sheet_and_sprite(mkv: Path, tmp_path: Path) -> None:
    sheet = tmp_path / "img" / f"{mkv.name}.jpg"
    assert generate_tgp(mkv, sheet)
    assert sheet.is_file() and not list(sheet.parent.glob(".*")), "No partial file left behind"
    assert generate_sprite(mkv, tmp_path / "sprite", mkv.name)
    vtt = (tmp_path / "sprite" / f"{mkv.name}_sprite.vtt").read_text()
    assert vtt.startswith("WEBVTT") and "#xywh=" in vtt
