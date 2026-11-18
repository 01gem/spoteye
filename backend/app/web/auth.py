"""Spotify sign-in check for the API.

SpotifyClient opens a browser and waits for input when no token is cached, which would hang
the server. So the API checks the cached token first and answers 401 instead.
"""

from __future__ import annotations

import json

from fastapi import HTTPException

from app.config import CACHE_PATH, Settings
from app.services.spotify_client import SpotifyClient

NEED_TOKEN_MSG: str = (
    "Spotify sign-in needed: run  python cli.py info <any spotify url>  once in the terminal."
)


def has_spotify_token() -> bool:
    """True only if the token cache exists, is valid JSON and has a non-empty refresh_token."""
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and bool(data.get("refresh_token"))


def require_spotify_client(settings: Settings) -> SpotifyClient:
    """SpotifyClient for a request, or HTTP 401 when there is no cached sign-in."""
    if not has_spotify_token():
        raise HTTPException(status_code=401, detail=NEED_TOKEN_MSG)
    return SpotifyClient(settings)
