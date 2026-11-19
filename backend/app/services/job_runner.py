"""Run download jobs: skip existing files, match (cached), download concurrently, record results.

All database writes happen in the main thread (here and in job_state). Ctrl+C or should_stop() -> "stopped".
"""

from __future__ import annotations

import time
from datetime import timedelta
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any, Protocol

from sqlmodel import Session

from app.config import Settings
from app.models import Job, TrackRecord
from app.services.job_state import JobStopped, StopFn, StopRequested, finish_job, job_records
from app.services.job_state import save_result, stop_job, until_stopped
from app.services.job_state import create_job as create_job  # re-exported for callers
from app.services.matcher import Matcher
from app.services.pipeline import TrackResult, WorkItem, Worker, cleanup_tmp, download_all
from app.services.pipeline import download_track, existing_output, match_all
from app.services.presets import Preset
from app.services.progress import ProgressFn as OnProgress
from app.services.progress import announce
from app.services.spotify_client import TrackMeta

ProgressFn = Callable[[Iterable[Any], str, int], Iterable[Any]]
OnRecord = Callable[[TrackRecord], None]
OnJob = Callable[[Job, list[TrackRecord]], None]


class TrackFetcher(Protocol):
    def get_track(self, track_id: str) -> TrackMeta: ...


def no_progress(items: Iterable[Any], description: str, total: int) -> Iterable[Any]:
    return items


def _announced(pairs: Iterable[tuple[TrackRecord, TrackMeta]], on_progress: OnProgress | None,
               ) -> Iterator[TrackMeta]:  # fmt: skip
    """Tracks for match_all; "matching" is sent as match_all asks for each one."""
    for record, track in pairs:
        announce(on_progress, record.id, "matching")
        yield track


def run_job(
    session: Session, job: Job, pairs: Sequence[tuple[TrackRecord, TrackMeta]],
    matcher: Matcher, settings: Settings, *, accept_review: bool, rematch: bool = False,
    max_workers: int | None = None, progress: ProgressFn = no_progress,
    worker: Worker = download_track, sleep: Callable[[float], None] = time.sleep,
    on_record: OnRecord | None = None, on_job: OnJob | None = None,
    should_stop: StopFn | None = None, on_progress: OnProgress | None = None,
) -> list[TrackRecord]:  # fmt: skip
    """Process the given records of a job and return all of its records afterwards.

    Ctrl+C or should_stop(): the job is saved as "stopped" and JobStopped is raised.
    on_record runs after every saved result, on_job at the start and after finish_job,
    on_progress for live per-track phases (matching, waiting, then from the download workers).
    """
    preset, out_dir = Preset(job.preset), Path(job.out_dir)

    def save(record: TrackRecord, result: TrackResult) -> None:
        save_result(session, record, result)
        if on_record is not None:
            on_record(record)

    if on_job is not None:
        assert job.id is not None
        on_job(job, job_records(session, job.id))
    try:
        numbered = job.kind == "playlist"
        to_match: list[tuple[TrackRecord, TrackMeta]] = []
        for record, track in pairs:
            index = record.position if numbered else None
            existing = existing_output(track, preset, out_dir, index)
            if existing is not None:
                save(record, TrackResult(track, "skipped", path=existing))
            else:
                to_match.append((record, track))

        pending = _announced(until_stopped(to_match, should_stop), on_progress)
        matches = match_all(progress(pending, "Matching...", len(to_match)), matcher, session,
                            rematch, timedelta(days=settings.match_retry_days))  # fmt: skip
        if should_stop is not None and should_stop():
            raise StopRequested
        items: list[WorkItem] = []
        by_key: dict[int, TrackRecord] = {}
        for record, track in to_match:
            cached = matches[track.spotify_id]
            record.video_id, record.score = cached.video_id, cached.score
            if cached.status == "not_found" or not cached.video_id:
                save(record, TrackResult(track, "not_found"))
            elif cached.status == "review" and not accept_review:
                save(record, TrackResult(track, "review_skipped"))
            else:
                assert record.id is not None
                by_key[record.id] = record
                index = record.position if numbered else None
                items.append(WorkItem(record.id, track, cached.video_id, index))

        for item in items:
            announce(on_progress, item.key, "waiting")
        workers = max_workers or settings.max_workers
        results = download_all(items, preset, out_dir, settings, workers, worker=worker,
                               sleep=sleep, on_progress=on_progress)  # fmt: skip
        for item, result in progress(results, "Downloading...", len(items)):
            save(by_key[item.key], result)
            if should_stop is not None and should_stop():
                results.close()  # its finally drops queued tracks and waits for running ones
                raise StopRequested
    except (KeyboardInterrupt, StopRequested):
        session.rollback()  # an interrupted commit must not poison the session
        stop_job(session, job)
        assert job.id is not None
        raise JobStopped(job.id) from None
    finally:
        cleanup_tmp(out_dir)
    records = finish_job(session, job)
    if on_job is not None:
        on_job(job, records)
    return records


def resume_job(
    session: Session, job: Job, client: TrackFetcher, matcher: Matcher, settings: Settings,
    *, accept_review: bool, **options: Any,
) -> list[TrackRecord]:  # fmt: skip
    """Re-run pending/failed records (+ review_skipped if accept_review); options go to run_job."""
    assert job.id is not None
    wanted = {"pending", "failed"} | ({"review_skipped"} if accept_review else set())
    records = [r for r in job_records(session, job.id) if r.status in wanted]
    pairs = [(r, client.get_track(r.spotify_id)) for r in records]
    job.status, job.finished_at = "running", None
    session.add(job)
    session.commit()
    return run_job(session, job, pairs, matcher, settings, accept_review=accept_review, **options)
