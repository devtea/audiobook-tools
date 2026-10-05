import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def test_book() -> Path:
    """Path to the committed sample .m4b fixture."""
    return Path(__file__).parent / "data" / "test_book.m4b"


@pytest.fixture
def make_mp3():
    """Factory that writes a short sine-wave mp3 with optional tags."""

    def _make(path: Path, bitrate: str = "128k", **tags: str) -> Path:
        cmd = ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=2"]
        cmd += ["-b:a", bitrate]
        for key, value in tags.items():
            cmd += ["-metadata", f"{key}={value}"]
        subprocess.run([*cmd, str(path)], check=True)
        return path

    return _make
