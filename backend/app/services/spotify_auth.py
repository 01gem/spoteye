"""Spotify sign-in state: is the cached token still usable, and when does the sign-in run out.

Spotify ends a sign-in (its refresh token) after about 6 months. The server must then answer 401
instead of opening a browser, so only `login` (CLI) is interactive here.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyPKCE

from app.config import BACKEND_DIR, CACHE_PATH, Settings
from app.services.spotify_client import MISSING_CLIENT_ID_MSG, SCOPE, SpotifyConfigError

TokenStatus = Literal["ok", "missing", "expired"]

SIGN_IN_META: Path = BACKEND_DIR / ".cache-meta.json"  # {"signed_in_at": ISO UTC}
SIGN_IN_DAYS: int = 180
OK_CACHE_S: float = 300  # a good token is re-checked at most every 5 minutes
TOKEN_TIMEOUT_S: float = 10
_ok_until: float = 0.0


def _has_refresh_token() -> bool:
    """True only if the token cache exists, is valid JSON and has a non-empty refresh_token."""
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and bool(data.get("refresh_token"))


def _auth_manager(settings: Settings, open_browser: bool) -> SpotifyPKCE:
    return SpotifyPKCE(
        client_id=settings.spotify_client_id,
        redirect_uri=settings.spotify_redirect_uri,
        scope=SCOPE,
        cache_handler=CacheFileHandler(cache_path=str(CACHE_PATH)),
        open_browser=open_browser,
        requests_timeout=TOKEN_TIMEOUT_S,
    )


def token_status(settings: Settings) -> TokenStatus:
    """"ok", "missing" (never signed in) or "expired" (Spotify refused the cached sign-in).

    Never opens a browser or reads stdin: validate_token only refreshes the token over HTTP.
    """
    global _ok_until
    if not settings.spotify_client_id or not _has_refresh_token():
        return "missing"
    if time.monotonic() < _ok_until:
        return "ok"
    try:
        auth = _auth_manager(settings, open_browser=False)
        valid = auth.validate_token(auth.cache_handler.get_cached_token())
    except Exception:
        valid = None
    if valid is None:
        return "expired"
    _ok_until = time.monotonic() + OK_CACHE_S
    return "ok"


def signed_in_at() -> datetime | None:
    """When the current sign-in happened (from SIGN_IN_META), or None if unknown."""
    try:
        value = datetime.fromisoformat(json.loads(SIGN_IN_META.read_text(encoding="utf-8"))["signed_in_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def mark_signed_in(when: datetime | None = None) -> None:
    stamp = (when or datetime.now(UTC)).astimezone(UTC).isoformat()
    SIGN_IN_META.write_text(json.dumps({"signed_in_at": stamp}), encoding="utf-8")


def sign_in_expires_at() -> datetime | None:
    """About when Spotify will ask for a new sign-in (signed_in_at + 180 days)."""
    start = signed_in_at()
    return start + timedelta(days=SIGN_IN_DAYS) if start else None


def login(settings: Settings) -> None:
    """Interactive sign-in for the CLI only: opens the browser and waits for Spotify's redirect."""
    if not settings.spotify_client_id:
        raise SpotifyConfigError(MISSING_CLIENT_ID_MSG)
    _auth_manager(settings, open_browser=True).get_access_token(check_cache=False)
    mark_signed_in()
