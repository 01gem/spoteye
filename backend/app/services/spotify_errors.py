"""Turn Spotify trouble into short, plain messages (API 401/502/503, CLI, job log)."""

from __future__ import annotations

import logging

import requests
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOauthError

from app.services.hints import hint

OFFLINE_MSG: str = "Can't reach Spotify. Check your internet connection and try again."
RATE_LIMIT_MSG: str = "Spotify is rate-limiting requests. Wait a minute and try again."
EXPIRED_MSG: str = hint("expired")
EXPIRED_ERRORS: frozenset[str] = frozenset({"invalid_grant", "invalid_client"})  # Spotify refused
# Catch these around any Spotify call: spotipy raises SpotifyException for HTTP errors and
# exhausted retries, SpotifyOauthError when the token refresh is refused, and a lost
# connection surfaces as a plain requests exception.
SPOTIFY_ERRORS: tuple[type[Exception], ...] = (
    requests.RequestException, SpotifyException, SpotifyOauthError,
)  # fmt: skip
MAX_CHAIN: int = 5  # how many __cause__/__context__ links to follow


def _chain(exc: BaseException) -> list[BaseException]:
    """exc and the exceptions it was raised from (at most MAX_CHAIN levels)."""
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and len(chain) <= MAX_CHAIN:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _status(exc: BaseException) -> int:
    status = getattr(exc, "http_status", None)
    return status if isinstance(status, int) else 0


def _unreachable(exc: BaseException) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    return isinstance(exc, SpotifyException) and (_status(exc) == 429 or _status(exc) >= 500)


def is_spotify_unreachable(exc: BaseException) -> bool:
    """No connection, a timeout, rate limiting (429) or a Spotify server error (5xx)."""
    return any(_unreachable(e) for e in _chain(exc))


def is_rate_limited(exc: BaseException) -> bool:
    return any(isinstance(e, SpotifyException) and _status(e) == 429 for e in _chain(exc))


def is_sign_in_expired(exc: BaseException) -> bool:
    """Spotify refused the refresh token: only `python cli.py login` helps."""
    return any(isinstance(e, SpotifyOauthError) and e.error in EXPIRED_ERRORS for e in _chain(exc))


def spotify_error_status(exc: BaseException) -> int:
    """HTTP status for the API: 401 expired sign-in, 502 Spotify's own error, 503 the rest."""
    if is_sign_in_expired(exc):
        return 401
    if isinstance(exc, SpotifyException) and not is_spotify_unreachable(exc):
        return 502
    return 503


def spotify_error_message(exc: BaseException) -> str:
    """Message for the user: expired, rate limit, Spotify's own error, or offline for the rest."""
    if is_sign_in_expired(exc):
        return EXPIRED_MSG
    if is_rate_limited(exc):
        return RATE_LIMIT_MSG
    if isinstance(exc, SpotifyException) and not is_spotify_unreachable(exc):
        return f"Spotify error {exc.http_status}: {exc.msg}"
    return OFFLINE_MSG


def log_failure(logger: logging.Logger, exc: BaseException, what: str) -> None:
    """A lost connection or expired sign-in is one warning line; anything else keeps its traceback."""
    if is_spotify_unreachable(exc) or is_sign_in_expired(exc):
        logger.warning("%s: %s (%s)", what, spotify_error_message(exc), type(exc).__name__)
    else:
        logger.error("%s", what, exc_info=exc)
