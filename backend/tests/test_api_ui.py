"""Health extras and serving the built frontend at "/"."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import client, env  # noqa: F401  (pytest fixtures)

from app import main


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
