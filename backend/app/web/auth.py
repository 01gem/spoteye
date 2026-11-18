"""Spotify sign-in check for the API.

SpotifyClient opens a browser and waits for input when no token is usable, which would hang
the server. So the API checks the cached sign-in first and answers 401 instead.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.config import Settings, load_settings
from app.services.hints import hint
from app.services.spotify_auth import TokenStatus, token_status
from app.services.spotify_client import SpotifyClient
from app.services.spotify_errors import EXPIRED_MSG, OFFLINE_MSG

NEED_TOKEN_MSG: str = hint("need_token")
SIGN_IN_ERRORS: dict[str, tuple[int, str]] = {
    "missing": (401, NEED_TOKEN_MSG),
    "expired": (401, EXPIRED_MSG),
    "offline": (503, OFFLINE_MSG),
}


def sign_in_message(status: TokenStatus) -> str:
    return SIGN_IN_ERRORS[status][1]


def has_spotify_token() -> bool:
    return token_status(load_settings()) == "ok"


def require_spotify_auth(settings: Settings) -> None:
    """HTTP 401 (missing/expired) or 503 (offline) unless the sign-in is usable; never opens a browser."""
    status = token_status(settings)
    if status != "ok":
        code, message = SIGN_IN_ERRORS[status]
        raise HTTPException(status_code=code, detail=message)


def require_spotify_client(settings: Settings) -> SpotifyClient:
    """SpotifyClient for a request, or HTTP 401/503 (see require_spotify_auth)."""
    require_spotify_auth(settings)
    return SpotifyClient(settings)
