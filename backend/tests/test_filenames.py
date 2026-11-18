from __future__ import annotations

import pytest

from app.services.filenames import build_filename, safe_filename
from app.services.spotify_client import TrackMeta


@pytest.mark.parametrize("name", ["CON", "nul", "COM1", "LPT9", "Aux.mp3"])
def test_reserved_names_are_prefixed(name: str) -> None:
    assert safe_filename(name) == f"_{name}"


def test_non_reserved_lookalike_is_untouched() -> None:
    assert safe_filename("CONTROL") == "CONTROL"


def test_illegal_characters_are_removed() -> None:
    assert safe_filename('a<b>c:d"e/f\\g|h?i*j\x01k') == "abcdefghijk"


@pytest.mark.parametrize(("raw", "expected"), [("Hello...", "Hello"), ("Hello. . ", "Hello")])
def test_trailing_dots_and_spaces_are_stripped(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected


def test_whitespace_is_collapsed() -> None:
    assert safe_filename("  a \t  b\n c  ") == "a b c"


def test_length_is_truncated() -> None:
    assert len(safe_filename("x" * 300)) == 150
    assert safe_filename("abcdefghijkl", max_len=5) == "abcde"


def make_track(title: str = "Song") -> TrackMeta:
    return TrackMeta(spotify_id="id", title=title, artists=["Artist", "Guest"])


def test_numbered_filename() -> None:
    assert build_filename(make_track(), "mp3", 3) == "03 - Artist - Song.mp3"


def test_unnumbered_filename() -> None:
    assert build_filename(make_track(), "opus", None) == "Artist - Song.opus"


def test_long_filename_keeps_extension() -> None:
    name = build_filename(make_track("T" * 400), "m4a", 12)
    assert name.endswith(".m4a")
    assert len(name) <= 150
