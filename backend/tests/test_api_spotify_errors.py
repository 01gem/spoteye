"""Spotify network errors become 503/502 in the API, a failed job in the queue, one line in the CLI."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient
from spotipy.exceptions import SpotifyException
from test_api import PLAYLIST_URL, FakeSpotify, add_job, client, env  # noqa: F401
from typer.testing import CliRunner

from app.commands import app as cli
from app.commands import attach, info, match
from app.services.spotify_client import TrackMeta
from app.services.spotify_errors import OFFLINE_MSG, RATE_LIMIT_MSG
from app.web import auth, job_queue

TRACK_URL = "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC"


def raising(error: Exception) -> type[FakeSpotify]:
    """A fake Spotify client whose every call raises error."""

    class Broken(FakeSpotify):
        def get_track(self, track_id: str) -> TrackMeta:
            raise error

        def get_playlist_tracks(self, playlist_id: str) -> list[TrackMeta]:
            raise error

    return Broken


@pytest.mark.parametrize(("error", "status", "detail"), [
    (requests.ConnectionError("no network"), 503, OFFLINE_MSG),
    (SpotifyException(429, -1, "too many requests"), 503, RATE_LIMIT_MSG),
    (SpotifyException(404, -1, "Not found"), 502, "Spotify error 404: Not found"),
])  # fmt: skip
def test_resolve_maps_spotify_errors(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                     error: Exception, status: int, detail: str) -> None:  # fmt: skip
    monkeypatch.setattr(auth, "SpotifyClient", raising(error))
    res = client.post("/api/resolve", json={"url": PLAYLIST_URL})
    assert (res.status_code, res.json()) == (status, {"detail": detail})


def test_create_job_offline_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "SpotifyClient", raising(requests.ConnectionError()))
    res = client.post("/api/jobs", json={"url": PLAYLIST_URL, "preset": "best"})
    assert (res.status_code, res.json()["detail"]) == (503, OFFLINE_MSG)


def test_candidates_and_attach_offline_are_503(client: TestClient, env: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    job_id = add_job("partial", env / "music" / "Mix")
    record_id = client.get(f"/api/jobs/{job_id}").json()["records"][0]["id"]
    monkeypatch.setattr(auth, "SpotifyClient", raising(requests.Timeout()))
    base = f"/api/jobs/{job_id}/tracks/{record_id}"
    res = client.get(f"{base}/candidates")
    assert (res.status_code, res.json()["detail"]) == (503, OFFLINE_MSG)
    res = client.post(f"{base}/attach", files={"file": ("song.mp3", b"fake mp3", "audio/mpeg")})
    assert (res.status_code, res.json()["detail"]) == (503, OFFLINE_MSG)


def test_resume_offline_fails_the_job(client: TestClient, env: Path,
                                      monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    job_id = add_job("partial", env / "music" / "Mix")
    monkeypatch.setattr(job_queue, "SpotifyClient", raising(requests.ConnectionError()))
    assert client.post(f"/api/jobs/{job_id}/resume", json={"accept_review": False}).status_code == 202
    deadline, status = time.monotonic() + 10, ""
    while time.monotonic() < deadline and status != "failed":
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        time.sleep(0.05)
    assert status == "failed"


@pytest.mark.parametrize(("module", "args"), [
    (info, ["info", TRACK_URL]),
    (match, ["match", TRACK_URL]),
    (attach, ["attach", TRACK_URL, "song.mp3"]),
])  # fmt: skip
def test_cli_prints_offline_message(module: object, args: list[str], tmp_path: Path,
                                    monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    broken = raising(requests.ConnectionError("no network"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "song.mp3").write_bytes(b"fake mp3")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "cli.db"))
    if module is attach:
        monkeypatch.setattr("app.services.attach.SpotifyClient", broken)
    else:
        monkeypatch.setattr(module, "SpotifyClient", broken)
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 1
    assert OFFLINE_MSG in " ".join(result.output.split())
