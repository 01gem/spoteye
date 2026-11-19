"""EventBus keeps the latest progress per running track; the SSE snapshot carries it."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import Session

from app.db import init_db
from app.services.job_runner import create_job
from app.services.presets import Preset
from app.services.progress import event as progress_event
from app.services.spotify_client import TrackMeta
from app.web.api_stream import snapshot_data
from app.web.events import EventBus, job_callbacks
from app.web.schemas import job_detail

TRACKS = [TrackMeta(spotify_id=f"sp{i}", title=f"Song {i}", artists=["Artist"], duration_ms=1000)
          for i in (1, 2)]  # fmt: skip


def progress(record_id: int, percent: float | None) -> dict[str, Any]:
    return {**progress_event(record_id, "downloading", percent), "job_id": 1}


def test_latest_progress_is_kept_and_delivered() -> None:
    bus = EventBus()
    q = bus.subscribe(1)
    bus.publish(1, progress(5, 10.0))
    bus.publish(1, progress(5, 40.0))
    bus.publish(2, progress(6, 1.0))
    assert bus.progress(1) == {5: progress(5, 40.0)}
    assert [q.get_nowait()["percent"], q.get_nowait()["percent"]] == [10.0, 40.0]


def test_finished_track_and_final_job_events_drop_progress() -> None:
    bus = EventBus()  # no subscribers: progress is still kept for the next one
    bus.publish(1, progress(5, 10.0))
    bus.publish(1, progress(6, 20.0))
    bus.publish(1, {"type": "track", "record_id": 5, "status": "pending"})
    assert set(bus.progress(1)) == {5, 6}
    bus.publish(1, {"type": "track", "record_id": 5, "status": "done"})
    assert set(bus.progress(1)) == {6}
    bus.publish(1, {"type": "job", "status": "running"})
    assert set(bus.progress(1)) == {6}
    bus.publish(1, {"type": "job", "status": "stopped"})
    assert bus.progress(1) == {}


def test_job_callbacks_add_the_job_id_to_progress() -> None:
    bus = EventBus()
    job_callbacks(bus, 3)["on_progress"](progress_event(8, "waiting"))
    assert bus.progress(3)[8]["job_id"] == 3


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = init_db(tmp_path / "jobs.db")
    with Session(engine, expire_on_commit=False) as s:
        yield s
    engine.dispose()


def test_snapshot_includes_progress(session: Session, tmp_path: Path) -> None:
    job, records = create_job(session, "url", "playlist", "pl", "Mix", Preset.BEST, tmp_path, TRACKS)
    assert job.id is not None and records[1].id is not None
    bus = EventBus()
    bus.publish(job.id, {**progress_event(records[1].id, "converting"), "job_id": job.id})
    detail = job_detail(job, records)

    data = json.loads(snapshot_data(detail, bus))

    assert data == {**json.loads(detail.model_dump_json()), "progress": {
        str(records[1].id): {**progress_event(records[1].id, "converting"), "job_id": job.id}}}  # fmt: skip
