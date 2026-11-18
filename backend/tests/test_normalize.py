from __future__ import annotations

import pytest

from app.services.normalize import normalize_artist, normalize_title, penalty_words_in


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hey Jude - Remastered 2015", "hey jude"),
        ("Song (feat. Someone)", "song"),
        ("Café del Mar", "cafe del mar"),
        ("Title [Official Audio]", "title"),
    ],
)
def test_normalize_title(raw: str, expected: str) -> None:
    assert normalize_title(raw) == expected


def test_normalize_title_keeps_version_words() -> None:
    assert normalize_title("Song (Live)") == "song live"


def test_normalize_artist_drops_the_prefix() -> None:
    assert normalize_artist("The  Beatles") == "beatles"


def test_penalty_word_only_in_candidate() -> None:
    assert penalty_words_in("Song (Live)", "Song") == ["live"]


def test_penalty_word_also_in_spotify_title() -> None:
    assert penalty_words_in("Song (Live)", "Song - Live") == []
