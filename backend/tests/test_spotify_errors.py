"""Which errors mean "Spotify unreachable", and the message the user sees."""

from __future__ import annotations

import logging

import pytest
import requests
from spotipy.exceptions import SpotifyException

from app.services.spotify_errors import OFFLINE_MSG, RATE_LIMIT_MSG, is_spotify_unreachable
from app.services.spotify_errors import log_failure, spotify_error_message


def spotify_error(status: int, msg: str = "error") -> SpotifyException:
    return SpotifyException(status, -1, msg)


def caused_by(cause: BaseException, depth: int = 1) -> BaseException:
    """A ValueError chain `depth` levels above cause (raise ... from ...)."""
    exc = cause
    for _ in range(depth):
        try:
            raise ValueError("wrapped") from exc
        except ValueError as wrapped:
            exc = wrapped
    return exc


@pytest.mark.parametrize("exc", [
    requests.ConnectionError("no network"), requests.Timeout("slow"),
    spotify_error(429), spotify_error(503), caused_by(requests.ConnectionError("no network")),
])  # fmt: skip
def test_unreachable(exc: BaseException) -> None:
    assert is_spotify_unreachable(exc)


@pytest.mark.parametrize("exc", [spotify_error(404), ValueError("bad link"), requests.HTTPError("x")])
def test_not_unreachable(exc: BaseException) -> None:
    assert not is_spotify_unreachable(exc)


def test_chain_is_followed_at_most_five_levels() -> None:
    assert is_spotify_unreachable(caused_by(requests.Timeout(), depth=5))
    assert not is_spotify_unreachable(caused_by(requests.Timeout(), depth=6))


@pytest.mark.parametrize(("exc", "message"), [
    (requests.ConnectionError(), OFFLINE_MSG),
    (spotify_error(429), RATE_LIMIT_MSG),
    (spotify_error(502), OFFLINE_MSG),
    (spotify_error(404, "Not found"), "Spotify error 404: Not found"),
    (requests.HTTPError("other"), OFFLINE_MSG),
])  # fmt: skip
def test_message(exc: BaseException, message: str) -> None:
    assert spotify_error_message(exc) == message


def test_log_failure_has_no_traceback_for_lost_connection(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test")
    with caplog.at_level(logging.WARNING):
        log_failure(logger, requests.ConnectionError(), "Job 1 failed")
        log_failure(logger, RuntimeError("bug"), "Job 2 failed")
    first, second = caplog.records
    assert first.levelno == logging.WARNING and first.exc_info is None
    assert OFFLINE_MSG in first.getMessage()
    assert second.levelno == logging.ERROR and second.exc_info is not None
