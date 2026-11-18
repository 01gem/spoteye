"""A playlist downloaded before goes back into its existing folder, even after a rename."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from test_api import PLAYLIST_URL, add_job, client, env  # noqa: F401  (pytest fixtures)

from app.db import get_session
from app.models import Job
from app.services.job_setup import previous_folder

PLAYLIST_ID = "37i9dQZF1DXcBWIGoYBM5M"  # from PLAYLIST_URL; the fake Spotify calls it "Mix"


def set_playlist_id(job_id: int, spotify_id: str) -> None:
    with get_session() as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.spotify_id, job.status = spotify_id, "done"
        session.add(job)
        session.commit()


def resolve_target(client: TestClient) -> str:
    res = client.post("/api/resolve", json={"url": PLAYLIST_URL})
    assert res.status_code == 200
    target: str = res.json()["target_dir"]
    return target


def wait_detail(client: TestClient, job_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        detail: dict[str, Any] = client.get(f"/api/jobs/{job_id}").json()
        if detail["status"] not in ("queued", "running"):
            return detail
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def test_same_playlist_reuses_folder_after_rename(client: TestClient, env: Path) -> None:
    old = env / "music" / "Old Name"
    old.mkdir(parents=True)
    set_playlist_id(add_job("done", old), PLAYLIST_ID)

    assert resolve_target(client) == str(old)
    res = client.post("/api/jobs", json={"url": PLAYLIST_URL, "preset": "best"})
    assert res.status_code == 201
    assert wait_detail(client, res.json()["job_id"])["out_dir"] == str(old)


def test_deleted_folder_falls_back_to_playlist_name(client: TestClient, env: Path) -> None:
    set_playlist_id(add_job("done", env / "music" / "Gone"), PLAYLIST_ID)  # never created
    assert resolve_target(client) == str(env / "music" / "Mix")


def test_other_playlist_with_same_name_gets_its_own_target(client: TestClient, env: Path) -> None:
    other = env / "music" / "Somewhere"
    other.mkdir(parents=True)
    set_playlist_id(add_job("done", other), "another-playlist")
    assert resolve_target(client) == str(env / "music" / "Mix")


def test_single_tracks_never_reuse_a_folder(env: Path) -> None:
    with get_session() as session:
        assert previous_folder(session, "track", PLAYLIST_ID) is None
