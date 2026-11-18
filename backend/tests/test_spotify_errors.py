"""Which errors mean "Spotify unreachable", and the message the user sees."""

from __future__ import annotations

import logging

import pytest
import requests
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOauthError

from app.services.spotify_errors import EXPIRED_MSG, OFFLINE_MSG, RATE_LIMIT_MSG
from app.services.spotify_errors import is_sign_in_expired, is_spotify_unreachable, log_failure
from app.services.spotify_errors import spotify_error_message, spotify_error_status


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


def oauth_error(error: str) -> SpotifyOauthError:
    return SpotifyOauthError(f"error: {error}", error=error)


@pytest.mark.parametrize(("exc", "status", "message"), [
    (oauth_error("invalid_grant"), 401, EXPIRED_MSG),
    (oauth_error("invalid_client"), 401, EXPIRED_MSG),
    (caused_by(oauth_error("invalid_grant")), 401, EXPIRED_MSG),
    (oauth_error("server_error"), 503, OFFLINE_MSG),
    (spotify_error(404, "Not found"), 502, "Spotify error 404: Not found"),
    (spotify_error(429), 503, RATE_LIMIT_MSG),
    (requests.ConnectionError(), 503, OFFLINE_MSG),
])  # fmt: skip
def test_status_and_message(exc: BaseException, status: int, message: str) -> None:
    assert (spotify_error_status(exc), spotify_error_message(exc)) == (status, message)


def test_only_refused_refresh_counts_as_expired() -> None:
    assert is_sign_in_expired(oauth_error("invalid_grant"))
    assert not is_sign_in_expired(oauth_error("server_error"))
    assert not is_sign_in_expired(spotify_error(401))


def test_log_failure_expired_sign_in_is_one_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger("test"), oauth_error("invalid_grant"), "Job 3 failed")
    [record] = caplog.records
    assert record.levelno == logging.WARNING and record.exc_info is None
    assert "python cli.py login" in record.getMessage()


def test_log_failure_has_no_traceback_for_lost_connection(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test")
    with caplog.at_level(logging.WARNING):
        log_failure(logger, requests.ConnectionError(), "Job 1 failed")
        log_failure(logger, RuntimeError("bug"), "Job 2 failed")
    first, second = caplog.records
    assert first.levelno == logging.WARNING and first.exc_info is None
    assert OFFLINE_MSG in first.getMessage()
    assert second.levelno == logging.ERROR and second.exc_info is not None
