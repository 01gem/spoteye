"""Spotify sign-in from the UI: start, replace a pending attempt, cancel, errors (no network)."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_api import client, env  # noqa: F401  (pytest fixtures)

from app.config import Settings
from app.services import spotify_auth
from app.services.spotify_login import LoginCancelled
from app.web import login_task

CLIENT_ID = "0123456789abcdef0123456789abcdef"


def test_login_without_client_id_is_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "")
    assert client.post("/api/auth/login").status_code == 400


def wait_until_idle(client: TestClient) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while (status := client.get("/api/auth/status").json())["running"] and time.monotonic() < deadline:
        time.sleep(0.02)
    result: dict[str, Any] = status
    return result


def test_second_login_replaces_the_first(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[threading.Event] = []

    def fake_login(settings: Settings, cancel: threading.Event | None = None) -> None:
        assert cancel is not None
        events.append(cancel)
        if not cancel.wait(5):
            raise AssertionError("never cancelled")
        raise LoginCancelled("Sign-in cancelled.")

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(spotify_auth, "login", fake_login)
    assert client.post("/api/auth/login").status_code == 202
    assert client.post("/api/auth/login").status_code == 202
    assert [e.is_set() for e in events] == [True, False]
    assert client.get("/api/auth/status").json() == {"running": True, "last_error": None}
    assert client.post("/api/auth/cancel").status_code == 204
    assert client.get("/api/auth/status").json() == {"running": False, "last_error": None}
    assert events[1].is_set()


def test_success_clears_token_cache(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    cleared: list[bool] = []
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(spotify_auth, "login", lambda settings, cancel=None: None)
    monkeypatch.setattr(spotify_auth, "clear_status_cache", lambda: cleared.append(True))
    assert client.post("/api/auth/login").status_code == 202
    assert wait_until_idle(client) == {"running": False, "last_error": None}
    assert cleared == [True]


def test_cancel_without_sign_in_is_204(client: TestClient) -> None:
    assert client.post("/api/auth/cancel").status_code == 204
    assert client.get("/api/auth/status").json() == {"running": False, "last_error": None}


def test_login_is_409_while_old_attempt_is_still_closing(client: TestClient,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    release = threading.Event()
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(spotify_auth, "login", lambda settings, cancel=None: release.wait(5))
    monkeypatch.setattr(login_task, "JOIN_S", 0.1)
    assert client.post("/api/auth/login").status_code == 202
    res = client.post("/api/auth/login")
    assert res.status_code == 409 and "still closing" in res.json()["detail"]
    release.set()


def test_failed_login_reports_last_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_login(settings: Settings, cancel: threading.Event | None = None) -> None:
        raise RuntimeError("Port 8765 is in use")

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(spotify_auth, "login", fake_login)
    assert client.post("/api/auth/login").status_code == 202
    assert wait_until_idle(client) == {"running": False, "last_error": "Port 8765 is in use"}
