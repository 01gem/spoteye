"""Sign-in state without network: a fake SpotifyPKCE stands in for spotipy."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.services import spotify_auth

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


@pytest.mark.parametrize("result", [None, RuntimeError("invalid_grant: Refresh token revoked")])
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
