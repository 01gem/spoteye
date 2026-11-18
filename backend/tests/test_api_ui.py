"""Health extras and serving the built frontend at "/"."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import client, env  # noqa: F401  (pytest fixtures)

from app import main
from app.services import spotify_auth
from app.web import auth

HEALTH_KEYS = {"ffmpeg", "deno", "spotify_auth", "spotify_auth_expires", "output_dir",
               "yt_dlp_version", "cookies"}  # fmt: skip


def test_health_returns_seven_keys(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert set(body) == HEALTH_KEYS
    assert body["spotify_auth"] == "ok"


def test_health_reports_expired_sign_in_and_expiry(client: TestClient, tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    meta = tmp_path / "meta.json"
    meta.write_text('{"signed_in_at": "2026-05-01T10:00:00+00:00"}', encoding="utf-8")
    monkeypatch.setattr(spotify_auth, "SIGN_IN_META", meta)
    monkeypatch.setattr(auth, "token_status", lambda _settings: "expired")
    body = client.get("/api/health").json()
    assert body["spotify_auth"] == "expired"
    assert body["spotify_auth_expires"] == "2026-10-28T10:00:00Z"


def test_health_reports_offline(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "token_status", lambda _settings: "offline")
    assert client.get("/api/health").json()["spotify_auth"] == "offline"


def test_health_reports_yt_dlp_version_and_cookies(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert isinstance(body["yt_dlp_version"], str) and body["yt_dlp_version"]
    assert isinstance(body["cookies"], bool)


def test_built_ui_is_served_at_root(client: TestClient, tmp_path: Path,
                                    monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>spoteye ui</h1>", encoding="utf-8")
    # Drop any real frontend/dist mount; monkeypatch puts the original routes back afterwards.
    routes = [r for r in main.app.router.routes if getattr(r, "name", None) != "ui"]
    monkeypatch.setattr(main.app.router, "routes", routes)

    assert main.mount_ui(main.app, dist) is True
    res = client.get("/")
    assert res.status_code == 200
    assert "spoteye ui" in res.text
    assert client.get("/api/health").status_code == 200  # /api still wins over "/"


def test_mount_ui_skips_missing_build(tmp_path: Path) -> None:
    assert main.mount_ui(main.app, tmp_path / "nope") is False
