"""Run download jobs: skip existing files, match (cached), download concurrently, record results.

All database writes happen in the main thread (here and in job_state). Ctrl+C -> job "stopped".
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from sqlmodel import Session

from app.config import Settings
from app.models import Job, TrackRecord
from app.services.job_state import JobStopped, finish_job, job_records, save_result, stop_job
from app.services.matcher import Matcher
from app.services.pipeline import TrackResult, WorkItem, Worker, cleanup_tmp, download_all
from app.services.pipeline import download_track, existing_output, match_all
from app.services.presets import Preset
from app.services.spotify_client import TrackMeta

ProgressFn = Callable[[Iterable[Any], str, int], Iterable[Any]]


class TrackFetcher(Protocol):
    def get_track(self, track_id: str) -> TrackMeta: ...


def no_progress(items: Iterable[Any], description: str, total: int) -> Iterable[Any]:
    return items


def create_job(
    session: Session, url: str, kind: str, spotify_id: str, name: str,
    preset: Preset, out_dir: Path, tracks: Sequence[TrackMeta],
) -> tuple[Job, list[TrackRecord]]:  # fmt: skip
    """Insert a running Job and one pending TrackRecord per track (positions are 1-based)."""
    job = Job(url=url, kind=kind, spotify_id=spotify_id, name=name, preset=preset.value,
              out_dir=str(out_dir))  # fmt: skip
    session.add(job)
    session.commit()
    session.refresh(job)
    assert job.id is not None
    records = [
        TrackRecord(job_id=job.id, spotify_id=t.spotify_id, position=i, title=t.title,
                    artists=", ".join(t.artists), isrc=t.isrc, duration_ms=t.duration_ms)
        for i, t in enumerate(tracks, start=1)
    ]  # fmt: skip
    session.add_all(records)
    session.commit()
    return job, records


def run_job(
    session: Session, job: Job, pairs: Sequence[tuple[TrackRecord, TrackMeta]],
    matcher: Matcher, settings: Settings, *, accept_review: bool, rematch: bool = False,
    max_workers: int | None = None, progress: ProgressFn = no_progress,
    worker: Worker = download_track, sleep: Callable[[float], None] = time.sleep,
) -> list[TrackRecord]:  # fmt: skip
    """Process the given records of a job and return all of its records afterwards.

    Ctrl+C: the job is saved as "stopped" and JobStopped is raised (resume picks it up).
    """
    preset, out_dir = Preset(job.preset), Path(job.out_dir)
    try:
        numbered = job.kind == "playlist"
        to_match: list[tuple[TrackRecord, TrackMeta]] = []
        for record, track in pairs:
            index = record.position if numbered else None
            existing = existing_output(track, preset, out_dir, index)
            if existing is not None:
                save_result(session, record, TrackResult(track, "skipped", path=existing))
            else:
                to_match.append((record, track))

        tracks = [track for _, track in to_match]
        matches = match_all(progress(tracks, "Matching...", len(tracks)), matcher, session, rematch)
        items: list[WorkItem] = []
        by_key: dict[int, TrackRecord] = {}
        for record, track in to_match:
            cached = matches[track.spotify_id]
            record.video_id, record.score = cached.video_id, cached.score
            if cached.status == "not_found" or not cached.video_id:
                save_result(session, record, TrackResult(track, "not_found"))
            elif cached.status == "review" and not accept_review:
                save_result(session, record, TrackResult(track, "review_skipped"))
            else:
                assert record.id is not None
                by_key[record.id] = record
                index = record.position if numbered else None
                items.append(WorkItem(record.id, track, cached.video_id, index))

        workers = max_workers or settings.max_workers
        results = download_all(items, preset, out_dir, settings, workers, worker=worker,
                               sleep=sleep)  # fmt: skip
        for item, result in progress(results, "Downloading...", len(items)):
            save_result(session, by_key[item.key], result)
    except KeyboardInterrupt:
        session.rollback()  # an interrupted commit must not poison the session
        stop_job(session, job)
        assert job.id is not None
        raise JobStopped(job.id) from None
    finally:
        cleanup_tmp(out_dir)
    return finish_job(session, job)


def resume_job(
    session: Session, job: Job, client: TrackFetcher, matcher: Matcher, settings: Settings,
    *, accept_review: bool, **options: Any,
) -> list[TrackRecord]:  # fmt: skip
    """Re-process pending/failed records (and review_skipped with accept_review)."""
    assert job.id is not None
    wanted = {"pending", "failed"} | ({"review_skipped"} if accept_review else set())
    records = [r for r in job_records(session, job.id) if r.status in wanted]
    pairs = [(r, client.get_track(r.spotify_id)) for r in records]
    job.status, job.finished_at = "running", None
    session.add(job)
    session.commit()
    return run_job(session, job, pairs, matcher, settings, accept_review=accept_review, **options)
