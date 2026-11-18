"""One background worker thread that runs queued jobs one at a time (FIFO)."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Sequence
from typing import Any

from app.config import load_settings
from app.db import get_session
from app.models import Job, TrackRecord, now
from app.services.job_runner import resume_job, run_job
from app.services.job_state import job_records
from app.services.matcher import Matcher
from app.services.spotify_client import SpotifyClient, TrackMeta
from app.web import auth
from app.web.events import EventBus, job_event, record_event

log = logging.getLogger(__name__)

Task = tuple[int, str, dict[str, Any]]  # (job_id, "new" | "resume", options)


class JobQueue:
    """FIFO of jobs for a single daemon worker; extra run_options go to run_job (tests)."""

    def __init__(self, bus: EventBus, **run_options: Any) -> None:
        self.bus = bus
        self.run_options = run_options
        self._tasks: queue.Queue[Task | None] = queue.Queue()
        self._active: set[int] = set()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, name="spoteye-jobs", daemon=True)
        self._thread.start()

    def submit_new(self, job_id: int, tracks: Sequence[TrackMeta], accept_review: bool) -> None:
        self._submit(job_id, "new", {"tracks": list(tracks), "accept_review": accept_review})

    def submit_resume(self, job_id: int, accept_review: bool) -> None:
        self._submit(job_id, "resume", {"accept_review": accept_review})

    def is_active(self, job_id: int) -> bool:
        with self._lock:
            return job_id in self._active

    def shutdown(self) -> None:
        """Stop after the current job; a job cut off here is marked "stopped" on next startup."""
        self._tasks.put(None)
        self._thread.join(timeout=2)

    def _submit(self, job_id: int, kind: str, options: dict[str, Any]) -> None:
        with self._lock:
            self._active.add(job_id)
        self._set_status(job_id, "queued", finished=False)
        self._tasks.put((job_id, kind, options))

    def _set_status(self, job_id: int, status: str, *, finished: bool) -> None:
        with get_session() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            job.status, job.finished_at = status, (now() if finished else None)
            session.add(job)
            session.commit()
            self.bus.publish(job_id, job_event(job, job_records(session, job_id)))

    def _loop(self) -> None:
        while True:
            task = self._tasks.get()
            if task is None:
                return
            job_id, kind, options = task
            try:
                self._run(job_id, kind, options)
            except Exception:
                log.exception("Job %s crashed", job_id)
                try:
                    self._set_status(job_id, "failed", finished=True)
                except Exception:
                    log.exception("Could not mark job %s as failed", job_id)
            finally:
                with self._lock:
                    self._active.discard(job_id)

    def _run(self, job_id: int, kind: str, options: dict[str, Any]) -> None:
        def on_record(record: TrackRecord) -> None:
            self.bus.publish(job_id, record_event(record))

        def on_job(job: Job, records: list[TrackRecord]) -> None:
            self.bus.publish(job_id, job_event(job, records))

        callbacks: dict[str, Any] = {"on_record": on_record, "on_job": on_job, **self.run_options}
        settings = load_settings()
        with get_session() as session:
            job = session.get(Job, job_id)
            if job is None:
                log.warning("Job %s disappeared before it ran", job_id)
                return
            accept_review = bool(options["accept_review"])
            if kind == "new":
                records = job_records(session, job_id)
                pairs = list(zip(records, options["tracks"], strict=True))
                job.status, job.finished_at = "running", None
                session.add(job)
                session.commit()
                run_job(session, job, pairs, Matcher(), settings, accept_review=accept_review,
                        **callbacks)  # fmt: skip
            else:
                if not auth.has_spotify_token():
                    raise RuntimeError(auth.NEED_TOKEN_MSG)
                client = SpotifyClient(settings)
                resume_job(session, job, client, Matcher(), settings, accept_review=accept_review,
                           **callbacks)  # fmt: skip
