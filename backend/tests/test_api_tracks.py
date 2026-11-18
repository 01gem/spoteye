"""Manual match picker: candidates and choose."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import FakeMatcher, FakeSpotify, add_job, client, env, run_playlist  # noqa: F401

from app.db import get_session
from app.models import MatchCache
from app.web import api_tracks, job_queue

VIDEO_ID = "abcDEF_12-x"  # 11 characters


def test_candidates_lists_url_and_delta(client: TestClient, env: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(api_tracks, "Matcher", lambda **_kw: FakeMatcher())
    job_id = add_job("partial", env / "music" / "Mix")
    record_id = client.get(f"/api/jobs/{job_id}").json()["records"][0]["id"]
    res = client.get(f"/api/jobs/{job_id}/tracks/{record_id}/candidates")
    assert res.status_code == 200
    [candidate] = res.json()
    assert candidate["url"] == "https://music.youtube.com/watch?v=vid-sp1"
    assert candidate["delta_s"] == 0.0
    assert candidate["score"] == 0.95


def test_candidates_for_unknown_record_is_404(client: TestClient, env: Path) -> None:
    job_id = add_job("partial", env / "music" / "Mix")
    assert client.get(f"/api/jobs/{job_id}/tracks/9999/candidates").status_code == 404


def test_choose_rejects_bad_video_id(client: TestClient, env: Path) -> None:
    job_id = add_job("partial", env / "music" / "Mix")
    record_id = client.get(f"/api/jobs/{job_id}").json()["records"][0]["id"]
    res = client.post(f"/api/jobs/{job_id}/tracks/{record_id}/choose", json={"video_id": "bad"})
    assert res.status_code == 422


def test_choose_downloads_the_picked_video(client: TestClient,
                                           monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(job_queue, "SpotifyClient", FakeSpotify)
    detail = run_playlist(client)
    record = next(r for r in detail["records"] if r["status"] == "not_found")
    url = f"/api/jobs/{detail['id']}/tracks/{record['id']}/choose"
    res = client.post(url, json={"video_id": VIDEO_ID})
    assert (res.status_code, res.json()) == (202, {"job_id": detail["id"]})

    with get_session() as session:
        cached = session.get(MatchCache, record["spotify_id"])
        assert cached is not None
        assert (cached.video_id, cached.score, cached.status) == (VIDEO_ID, 1.0, "matched")

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        after = client.get(f"/api/jobs/{detail['id']}").json()
        mine = next(r for r in after["records"] if r["id"] == record["id"])
        if mine["status"] == "done" and after["status"] == "done":
            assert mine["video_id"] == VIDEO_ID
            return
        time.sleep(0.05)
    pytest.fail(f"track ended {mine['status']}, job {after['status']}")


def test_choose_on_downloaded_track_is_409(client: TestClient) -> None:
    detail = run_playlist(client)
    record = next(r for r in detail["records"] if r["status"] == "done")
    url = f"/api/jobs/{detail['id']}/tracks/{record['id']}/choose"
    assert client.post(url, json={"video_id": VIDEO_ID}).status_code == 409
