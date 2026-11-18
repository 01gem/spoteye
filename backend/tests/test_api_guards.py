"""Local-server guards (Host and Origin checks) and the expired Spotify sign-in."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import PLAYLIST_URL, add_job, client, env  # noqa: F401  (pytest fixtures)

from app import main
from app.web import auth

EVIL = "https://evil.example"


def test_foreign_host_is_rejected(client: TestClient) -> None:
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_cross_site_post_is_blocked(client: TestClient) -> None:
    res = client.post("/api/resolve", json={"url": PLAYLIST_URL}, headers={"origin": EVIL})
    assert res.status_code == 403
    assert res.json() == {"detail": "Cross-site request blocked."}


@pytest.mark.parametrize("origin", ["http://127.0.0.1", "http://localhost:5173"])
def test_same_site_post_is_allowed(client: TestClient, origin: str) -> None:
    res = client.post("/api/resolve", json={"url": PLAYLIST_URL},
                      headers={"origin": origin, "host": "127.0.0.1"})  # fmt: skip
    assert res.status_code == 200


def test_get_with_foreign_origin_is_allowed(client: TestClient) -> None:
    assert client.get("/api/health", headers={"origin": EVIL}).status_code == 200


def test_expired_sign_in_is_401_with_login_hint(client: TestClient,
                                                monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(auth, "token_status", lambda _settings: "expired")
    res = client.post("/api/resolve", json={"url": PLAYLIST_URL})
    assert res.status_code == 401
    assert "python cli.py login" in res.json()["detail"]


def test_resolve_while_offline_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "token_status", lambda _settings: "offline")
    res = client.post("/api/resolve", json={"url": PLAYLIST_URL})
    assert res.status_code == 503
    assert res.json() == {"detail": "Can't reach Spotify. Check your internet connection and try again."}


def test_queued_resume_with_expired_sign_in_fails_the_job(client: TestClient, env: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    job_id = add_job("partial", env / "music" / "Mix")
    monkeypatch.setattr(auth, "token_status", lambda _settings: "expired")
    main.app.state.job_queue.submit_resume(job_id, accept_review=False)
    deadline, status = time.monotonic() + 10, ""
    while time.monotonic() < deadline:
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status == "failed":
            break
        time.sleep(0.05)
    assert status == "failed"
