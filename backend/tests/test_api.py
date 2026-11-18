"""API tests without network: fake Spotify client, fake matcher and fake download worker."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.db import get_engine, get_session, init_db
from app.models import Job
from app.services.filenames import build_filename
from app.services.job_runner import create_job
from app.services.matcher import Candidate, MatchResult
from app.services.pipeline import TrackResult, WorkItem
from app.services.presets import Preset
from app.services.spotify_client import TrackMeta
from app.web import auth, job_queue

PLAYLIST_URL = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
TRACKS = [TrackMeta(spotify_id=f"sp{i}", title=f"Song {i}", artists=["Artist"], album="Album",
                    duration_ms=180_000) for i in (1, 2, 3)]  # fmt: skip


class FakeSpotify:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def get_track(self, track_id: str) -> TrackMeta:
        return next(t for t in TRACKS if t.spotify_id == track_id)

    def get_playlist_name(self, playlist_id: str) -> str:
        return "Mix"

    def get_playlist_tracks(self, playlist_id: str) -> list[TrackMeta]:
        return list(TRACKS)


class FakeMatcher:
    def match(self, track: TrackMeta) -> MatchResult:
        if track.spotify_id == "sp3":
            return MatchResult("not_found", None, 0.0, [])
        best = Candidate(f"vid-{track.spotify_id}", track.title, track.artists, None, 180, "song")
        return MatchResult("matched", best, 0.95, [(best, 0.95)])


def fake_worker(item: WorkItem, preset: Preset, out_dir: Path, settings: Settings) -> TrackResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / build_filename(item.track, "opus", item.index)
    path.write_bytes(b"fake audio")
    return TrackResult(item.track, "done", path=path, source="opus 130k", output="opus copy")


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "music"))
    monkeypatch.setattr(auth, "has_spotify_token", lambda: True)
    monkeypatch.setattr(auth, "SpotifyClient", FakeSpotify)
    monkeypatch.setattr(job_queue, "Matcher", FakeMatcher)
    monkeypatch.setattr(main, "RUN_OPTIONS", {"worker": fake_worker, "sleep": lambda _s: None})
    yield tmp_path
    get_engine().dispose()


@pytest.fixture
def client(env: Path) -> Iterator[TestClient]:
    with TestClient(main.app) as test_client:
        yield test_client


def run_playlist(client: TestClient) -> dict[str, Any]:
    res = client.post("/api/jobs", json={"url": PLAYLIST_URL, "preset": "best"})
    assert res.status_code == 201
    job_id = res.json()["job_id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        detail: dict[str, Any] = client.get(f"/api/jobs/{job_id}").json()
        if detail["status"] == "partial":
            return detail
        time.sleep(0.05)
    pytest.fail(f"job {job_id} did not finish: {detail['status']}")


def add_job(status: str, out_dir: Path) -> int:
    with get_session() as session:
        job, _ = create_job(session, PLAYLIST_URL, "playlist", "pl", "Mix", Preset.BEST, out_dir,
                            TRACKS)  # fmt: skip
        job.status = status
        session.add(job)
        session.commit()
        assert job.id is not None
        return job.id


def test_health_returns_four_keys(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert set(body) == {"ffmpeg", "deno", "spotify_auth", "output_dir"}
    assert body["spotify_auth"] is True


def test_resolve_rejects_non_spotify_url(client: TestClient) -> None:
    assert client.post("/api/resolve", json={"url": "https://example.com/x"}).status_code == 422


def test_resolve_without_token_is_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "has_spotify_token", lambda: False)
    res = client.post("/api/resolve", json={"url": PLAYLIST_URL})
    assert res.status_code == 401
    assert "python cli.py info" in res.json()["detail"]


def test_job_runs_to_partial_with_track_3_not_found(client: TestClient) -> None:
    detail = run_playlist(client)
    assert {r["position"]: r["status"] for r in detail["records"]} == {
        1: "done", 2: "done", 3: "not_found"}  # fmt: skip
    assert (detail["done"], detail["total"]) == (2, 3)
    assert detail["created_at"].endswith("Z")


def test_missing_returns_only_track_3(client: TestClient) -> None:
    job_id = run_playlist(client)["id"]
    missing = client.get(f"/api/jobs/{job_id}/missing").json()
    assert [(r["position"], r["spotify_id"]) for r in missing] == [(3, "sp3")]


def test_attach_rejects_txt_upload(client: TestClient) -> None:
    detail = run_playlist(client)
    record_id = next(r["id"] for r in detail["records"] if r["position"] == 3)
    res = client.post(f"/api/jobs/{detail['id']}/tracks/{record_id}/attach",
                      files={"file": ("notes.txt", b"hello", "text/plain")})  # fmt: skip
    assert res.status_code == 400


def test_resume_running_job_is_409(client: TestClient, env: Path) -> None:
    job_id = add_job("running", env / "music" / "Mix")
    assert client.post(f"/api/jobs/{job_id}/resume", json={"accept_review": False}).status_code == 409


def test_startup_marks_running_job_stopped(env: Path) -> None:
    init_db(env / "api.db")
    job_id = add_job("running", env / "music" / "Mix")
    with TestClient(main.app) as test_client:
        assert test_client.get(f"/api/jobs/{job_id}").json()["status"] == "stopped"
