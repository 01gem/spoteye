"""In-process event bus: the job worker publishes, SSE connections subscribe per job."""

from __future__ import annotations

import queue
import threading
from collections.abc import Sequence
from typing import Any

from app.models import Job, TrackRecord
from app.services.job_state import KEPT_STATUSES

Event = dict[str, Any]


class EventBus:
    """Thread-safe fan-out of events to every subscriber of a job."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[int, list[queue.Queue[Event]]] = {}

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
        """Deliver to every current subscriber; no subscribers -> nothing happens."""
        with self._lock:
            targets = list(self._subscribers.get(job_id, []))
        for q in targets:
            q.put_nowait(dict(event))


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
