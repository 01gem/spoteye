"""Turn Spotify network trouble into short, plain messages (API 503/502, CLI, job log)."""

from __future__ import annotations

import logging

import requests
from spotipy.exceptions import SpotifyException

OFFLINE_MSG: str = "Can't reach Spotify. Check your internet connection and try again."
RATE_LIMIT_MSG: str = "Spotify is rate-limiting requests. Wait a minute and try again."
# Catch these around any Spotify call (spotipy raises SpotifyException for HTTP errors and
# exhausted retries; a lost connection surfaces as a plain requests exception).
SPOTIFY_ERRORS: tuple[type[Exception], ...] = (requests.RequestException, SpotifyException)
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


def spotify_error_message(exc: BaseException) -> str:
    """Message for the user: rate limit / offline, Spotify's own error, or offline for the rest."""
    if is_rate_limited(exc):
        return RATE_LIMIT_MSG
    if not is_spotify_unreachable(exc) and isinstance(exc, SpotifyException):
        return f"Spotify error {exc.http_status}: {exc.msg}"
    return OFFLINE_MSG


def log_failure(logger: logging.Logger, exc: BaseException, what: str) -> None:
    """A lost connection is one warning line; anything else keeps its full traceback."""
    if is_spotify_unreachable(exc):
        logger.warning("%s: %s (%s)", what, spotify_error_message(exc), type(exc).__name__)
    else:
        logger.error("%s", what, exc_info=exc)
