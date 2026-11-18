"""Parse Spotify share links and URIs into (kind, id) pairs."""

from __future__ import annotations

import re

KINDS: tuple[str, ...] = ("track", "playlist", "album")

_ID = r"(?P<id>[A-Za-z0-9]{22})"
_KIND = r"(?P<kind>track|playlist|album)"

_URL_RE = re.compile(
    r"^https?://open\.spotify\.com/"
    r"(?:intl-[A-Za-z]{2,3}(?:[-_][A-Za-z]{2,4})?/)?"
    rf"{_KIND}/{_ID}"
    r"/?(?:[?#].*)?$"
)
_URI_RE = re.compile(rf"^spotify:{_KIND}:{_ID}$")


def parse_spotify_link(url: str) -> tuple[str, str]:
    """Return (kind, id) for a Spotify track/playlist/album URL or URI.

    Raises ValueError if the input is not a recognised Spotify link.
    """
    candidate = url.strip()
    match = _URL_RE.match(candidate) or _URI_RE.match(candidate)
    if match is None:
        raise ValueError(f"Not a supported Spotify link: {url!r}")
    return match.group("kind"), match.group("id")
