from __future__ import annotations

import pytest

from app.services.link_parser import parse_spotify_link


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://open.spotify.com/track/3D110t9ctcoOoylXsc3iR8?si=07da54340502418e",
            ("track", "3D110t9ctcoOoylXsc3iR8"),
        ),
        (
            "https://open.spotify.com/playlist/0FeBuGJJDqiFwbzeB2YDeZ?si=M4TcqmJhT7eJuHewsEc7wg",
            ("playlist", "0FeBuGJJDqiFwbzeB2YDeZ"),
        ),
        (
            "https://open.spotify.com/intl-fil/track/3D110t9ctcoOoylXsc3iR8",
            ("track", "3D110t9ctcoOoylXsc3iR8"),
        ),
        (
            "spotify:track:3D110t9ctcoOoylXsc3iR8",
            ("track", "3D110t9ctcoOoylXsc3iR8"),
        ),
    ],
)
def test_parse_valid_links(url: str, expected: tuple[str, str]) -> None:
    assert parse_spotify_link(url) == expected


def test_parse_rejects_non_spotify_url() -> None:
    with pytest.raises(ValueError):
        parse_spotify_link("https://example.com/track/abc")
