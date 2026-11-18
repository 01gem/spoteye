"""Stop jobs from the API (running and queued) and delete jobs from the history."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import PLAYLIST_URL, add_job, client, env, fake_worker  # noqa: F401  (fixtures)

from app import main
from app.config import Settings
from app.db import get_session
from app.services.job_state import job_records
from app.services.pipeline import TrackResult, WorkItem
from app.services.presets import Preset

WAIT_S: float = 10


@pytest.fixture
def gate() -> Iterator[threading.Event]:
    event = threading.Event()
    yield event
    event.set()  # never leave the worker thread blocked


@pytest.fixture
def blocking_client(env: Path, gate: threading.Event,
                    monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:  # fmt: skip
    def blocked_worker(item: WorkItem, preset: Preset, out_dir: Path, s: Settings) -> TrackResult:
        gate.wait(WAIT_S)
        return fake_worker(item, preset, out_dir, s)

    monkeypatch.setattr(main, "RUN_OPTIONS", {"worker": blocked_worker, "sleep": lambda _s: None})
    with TestClient(main.app) as test_client:
        yield test_client
    gate.set()


def start_job(client: TestClient) -> int:
    res = client.post("/api/jobs", json={"url": PLAYLIST_URL, "preset": "best"})
    assert res.status_code == 201
    job_id: int = res.json()["job_id"]
    return job_id


def wait_status(client: TestClient, job_id: int, *statuses: str) -> str:
    deadline = time.monotonic() + WAIT_S
    status = ""
    while time.monotonic() < deadline:
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status in statuses:
            return status
        time.sleep(0.02)
    pytest.fail(f"job {job_id} stayed {status!r}, wanted {statuses}")


def test_stop_running_job(blocking_client: TestClient, gate: threading.Event) -> None:
    job_id = start_job(blocking_client)
    wait_status(blocking_client, job_id, "running")
    res = blocking_client.post(f"/api/jobs/{job_id}/stop")
    assert (res.status_code, res.json()) == (202, {"result": "stopping"})
    gate.set()
    assert wait_status(blocking_client, job_id, "stopped", "done", "partial") == "stopped"


def test_stop_queued_job_cancels_it(blocking_client: TestClient, gate: threading.Event) -> None:
    first = start_job(blocking_client)
    wait_status(blocking_client, first, "running")
    second = start_job(blocking_client)
    res = blocking_client.post(f"/api/jobs/{second}/stop")
    assert (res.status_code, res.json()) == (202, {"result": "cancelled"})
    gate.set()
    assert wait_status(blocking_client, second, "stopped", "done", "partial") == "stopped"
    detail = blocking_client.get(f"/api/jobs/{second}").json()
    assert {r["status"] for r in detail["records"]} == {"pending"}  # never ran


def test_stop_done_job_is_409(client: TestClient, env: Path) -> None:
    job_id = add_job("done", env / "music" / "Mix")
    assert client.post(f"/api/jobs/{job_id}/stop").status_code == 409


def test_delete_done_job_removes_it_and_its_records(client: TestClient, env: Path) -> None:
    job_id = add_job("done", env / "music" / "Mix")
    assert client.delete(f"/api/jobs/{job_id}").status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    with get_session() as session:
        assert job_records(session, job_id) == []


def test_delete_running_job_is_409(client: TestClient, env: Path) -> None:
    job_id = add_job("running", env / "music" / "Mix")
    assert client.delete(f"/api/jobs/{job_id}").status_code == 409
