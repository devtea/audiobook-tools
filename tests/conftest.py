from pathlib import Path

import pytest


@pytest.fixture
def test_book() -> Path:
    """Path to the committed sample .m4b fixture."""
    return Path(__file__).parent / "data" / "test_book.m4b"
