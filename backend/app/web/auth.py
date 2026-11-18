"""Spotify sign-in check for the API.

SpotifyClient opens a browser and waits for input when no token is usable, which would hang
the server. So the API checks the cached sign-in first and answers 401 instead.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.config import Settings, load_settings
from app.services.spotify_auth import TokenStatus, token_status
from app.services.spotify_client import SpotifyClient

NEED_TOKEN_MSG: str = (
    "Spotify sign-in needed: run  python cli.py info <any spotify url>  once in the terminal."
)
EXPIRED_MSG: str = (
    "Spotify sign-in expired (Spotify limits sign-ins to 6 months). Run: python cli.py login"
)


def sign_in_message(status: TokenStatus) -> str:
    return EXPIRED_MSG if status == "expired" else NEED_TOKEN_MSG


def has_spotify_token() -> bool:
    return token_status(load_settings()) == "ok"


def require_spotify_auth(settings: Settings) -> None:
    """HTTP 401 unless the cached sign-in is usable (never opens a browser)."""
    status = token_status(settings)
    if status != "ok":
        raise HTTPException(status_code=401, detail=sign_in_message(status))


def require_spotify_client(settings: Settings) -> SpotifyClient:
    """SpotifyClient for a request, or HTTP 401 when the sign-in is missing or expired."""
    require_spotify_auth(settings)
    return SpotifyClient(settings)
