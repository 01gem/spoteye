"""In-process event bus: the job worker publishes, SSE connections subscribe per job."""

from __future__ import annotations

import queue
import threading
from collections.abc import Sequence
from typing import Any

from app.models import Job, TrackRecord
from app.services.job_state import KEPT_STATUSES

Event = dict[str, Any]
FINAL_JOB_STATUSES: frozenset[str] = frozenset({"done", "partial", "failed", "stopped"})


class EventBus:
    """Thread-safe fan-out of events to every subscriber of a job.

    Also keeps each running track's latest "progress" event, so a new subscriber (page reload)
    starts from the current bars instead of empty ones.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[int, list[queue.Queue[Event]]] = {}
        self._progress: dict[int, dict[int, Event]] = {}  # job_id -> record_id -> latest

    def subscribe(self, job_id: int) -> queue.Queue[Event]:
        q: queue.Queue[Event] = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: int, q: queue.Queue[Event]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(job_id, [])
            if q in subscribers:
                subscribers.remove(q)
            if not subscribers:
                self._subscribers.pop(job_id, None)

    def publish(self, job_id: int, event: Event) -> None:
        """Deliver to every current subscriber; no subscribers -> only the progress is kept."""
        with self._lock:
            self._remember(job_id, event)
            targets = list(self._subscribers.get(job_id, []))
        for q in targets:
            q.put_nowait(dict(event))

    def progress(self, job_id: int) -> dict[int, Event]:
        """Latest progress event per record of a job (copies)."""
        with self._lock:
            return {record_id: dict(e) for record_id, e in self._progress.get(job_id, {}).items()}

    def _remember(self, job_id: int, event: Event) -> None:
        """Keep the latest progress; a finished track or a finished job drops it (lock held)."""
        kind = event.get("type")
        if kind == "progress":
            self._progress.setdefault(job_id, {})[int(event["record_id"])] = dict(event)
        elif kind == "track" and event.get("status") != "pending":
            self._progress.get(job_id, {}).pop(int(event["record_id"]), None)
        elif kind == "job" and event.get("status") in FINAL_JOB_STATUSES:
            self._progress.pop(job_id, None)


def job_callbacks(bus: EventBus, job_id: int) -> dict[str, Any]:
    """run_job callbacks that publish a job's record, job and progress (+ job_id) events."""

    def on_record(record: TrackRecord) -> None:
        bus.publish(job_id, record_event(record))

    def on_job(job: Job, records: list[TrackRecord]) -> None:
        bus.publish(job_id, job_event(job, records))

    def on_progress(event: Event) -> None:
        bus.publish(job_id, {**event, "job_id": job_id})

    return {"on_record": on_record, "on_job": on_job, "on_progress": on_progress}


def record_event(record: TrackRecord) -> Event:
    return {
        "type": "track",
        "job_id": record.job_id,
        "record_id": record.id,
        "position": record.position,
        "status": record.status,
        "score": record.score,
        "source": record.source,
        "output": record.output,
        "upscaled": record.upscaled,
        "file_name": record.file_name,
        "error": record.error,
    }


def job_event(job: Job, records: Sequence[TrackRecord]) -> Event:
    return {
        "type": "job",
        "job_id": job.id,
        "status": job.status,
        "done": sum(r.status in KEPT_STATUSES for r in records),
        "total": len(records),
    }
