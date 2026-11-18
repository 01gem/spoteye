"""Sign-in state without network: a fake SpotifyPKCE, or the real one with a patched refresh."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import requests
from spotipy.oauth2 import SpotifyOauthError, SpotifyPKCE

from app.config import Settings
from app.services import spotify_auth
from app.services.spotify_client import SCOPE

SETTINGS = Settings("client", "http://127.0.0.1:8765/callback", Path("out"), None)


class FakePKCE:
    """Records how often it is built; validate_token returns or raises `result`."""

    built = 0
    result: Any = {"access_token": "a", "refresh_token": "r"}

    def __init__(self, **kwargs: Any) -> None:
        assert kwargs["open_browser"] is False
        FakePKCE.built += 1
        self.cache_handler = kwargs["cache_handler"]

    def validate_token(self, token_info: Any) -> Any:
        if isinstance(FakePKCE.result, Exception):
            raise FakePKCE.result
        return FakePKCE.result

    def get_access_token(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("token_status must never start an interactive sign-in")


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".cache"
    monkeypatch.setattr(spotify_auth, "CACHE_PATH", path)
    monkeypatch.setattr(spotify_auth, "SIGN_IN_META", tmp_path / ".cache-meta.json")
    monkeypatch.setattr(spotify_auth, "SpotifyPKCE", FakePKCE)
    monkeypatch.setattr(spotify_auth, "_ok_until", 0.0)
    monkeypatch.setattr(FakePKCE, "built", 0)
    monkeypatch.setattr(FakePKCE, "result", {"access_token": "a", "refresh_token": "r"})
    return path


def write_cache(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_missing_without_cache_file(cache: Path) -> None:
    assert spotify_auth.token_status(SETTINGS) == "missing"


@pytest.mark.parametrize("content", ["not json", '{"access_token": "a"}', '{"refresh_token": ""}'])
def test_missing_with_invalid_cache(cache: Path, content: str) -> None:
    cache.write_text(content, encoding="utf-8")
    assert spotify_auth.token_status(SETTINGS) == "missing"
    assert FakePKCE.built == 0


@pytest.mark.parametrize("result", [None, SpotifyOauthError("revoked", error="invalid_grant")])
def test_expired_when_spotify_refuses(cache: Path, monkeypatch: pytest.MonkeyPatch,
                                      result: Any) -> None:  # fmt: skip
    write_cache(cache, {"refresh_token": "r"})
    monkeypatch.setattr(FakePKCE, "result", result)
    assert spotify_auth.token_status(SETTINGS) == "expired"
    assert spotify_auth.token_status(SETTINGS) == "expired"
    assert FakePKCE.built == 2  # "expired" is not cached


def test_ok_is_cached(cache: Path) -> None:
    write_cache(cache, {"refresh_token": "r"})
    assert spotify_auth.token_status(SETTINGS) == "ok"
    assert spotify_auth.token_status(SETTINGS) == "ok"
    assert FakePKCE.built == 1


def test_deleted_cache_is_missing_even_after_ok(cache: Path) -> None:
    write_cache(cache, {"refresh_token": "r"})
    assert spotify_auth.token_status(SETTINGS) == "ok"
    cache.unlink()
    assert spotify_auth.token_status(SETTINGS) == "missing"


def test_sign_in_expiry_is_180_days_after_sign_in(cache: Path) -> None:
    assert spotify_auth.sign_in_expires_at() is None
    spotify_auth.mark_signed_in(datetime(2026, 11, 18, 12, 0, tzinfo=UTC))
    assert spotify_auth.signed_in_at() == datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
    assert spotify_auth.sign_in_expires_at() == datetime(2027, 5, 17, 12, 0, tzinfo=UTC)


def expired_access_token(path: Path) -> None:
    """A real-looking cache whose access token has run out, so validate_token must refresh."""
    write_cache(path, {"access_token": "a", "token_type": "Bearer", "expires_in": 3600,
                       "refresh_token": "r", "scope": SCOPE, "expires_at": 0})  # fmt: skip


@pytest.mark.parametrize(("error", "expected"), [
    (SpotifyOauthError("revoked", error="invalid_grant"), "expired"),
    (SpotifyOauthError("bad app", error="invalid_client"), "expired"),
    (requests.ConnectionError("no network"), "offline"),
    (requests.Timeout("slow"), "offline"),
    (SpotifyOauthError("oops", error="server_error"), "offline"),
    (RuntimeError("unexpected"), "offline"),
])  # fmt: skip
def test_refresh_error_maps_to_status(cache: Path, monkeypatch: pytest.MonkeyPatch,
                                      error: Exception, expected: str) -> None:  # fmt: skip
    calls: list[str] = []

    def refresh(self: SpotifyPKCE, refresh_token: str) -> Any:
        calls.append(refresh_token)
        raise error

    monkeypatch.setattr(spotify_auth, "SpotifyPKCE", SpotifyPKCE)  # the real one
    monkeypatch.setattr(SpotifyPKCE, "refresh_access_token", refresh)
    expired_access_token(cache)
    assert spotify_auth.token_status(SETTINGS) == expected
    assert spotify_auth.token_status(SETTINGS) == expected
    assert calls == ["r", "r"]  # neither "expired" nor "offline" is cached
