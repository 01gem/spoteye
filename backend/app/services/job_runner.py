"""Run download jobs: skip existing files, match (cached), download concurrently, record results.

All database writes happen here, in the main thread.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from sqlmodel import Session, select

from app.config import Settings
from app.models import Job, TrackRecord, now
from app.services.matcher import Matcher
from app.services.pipeline import TrackResult, WorkItem, Worker, cleanup_tmp, download_all
from app.services.pipeline import download_track, existing_output, match_all
from app.services.presets import Preset
from app.services.reports import write_reports
from app.services.spotify_client import TrackMeta

KEPT_STATUSES: frozenset[str] = frozenset({"done", "skipped", "manual"})
ProgressFn = Callable[[Iterable[Any], str, int], Iterable[Any]]


class TrackFetcher(Protocol):
    def get_track(self, track_id: str) -> TrackMeta: ...


def no_progress(items: Iterable[Any], description: str, total: int) -> Iterable[Any]:
    return items


def job_records(session: Session, job_id: int) -> list[TrackRecord]:
    query = select(TrackRecord).where(TrackRecord.job_id == job_id).order_by(TrackRecord.position)
    return list(session.exec(query))


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


def save_result(session: Session, record: TrackRecord, result: TrackResult) -> None:
    record.status = result.status
    record.file_name = result.path.name if result.path else None
    record.source = result.source or None
    record.output = result.output or None
    record.upscaled = result.upscaled
    record.error = result.error
    record.updated_at = now()
    session.add(record)
    session.commit()


def finish_job(session: Session, job: Job) -> list[TrackRecord]:
    """Set the job's final status and regenerate its reports (playlist jobs only)."""
    assert job.id is not None
    records = job_records(session, job.id)
    kept = sum(r.status in KEPT_STATUSES for r in records)
    job.status = "done" if kept == len(records) else ("failed" if kept == 0 else "partial")
    job.finished_at = now()
    session.add(job)
    session.commit()
    if job.kind == "playlist":
        write_reports(job, records, Path(job.out_dir))
    return records


def run_job(
    session: Session, job: Job, pairs: Sequence[tuple[TrackRecord, TrackMeta]],
    matcher: Matcher, settings: Settings, *, accept_review: bool, rematch: bool = False,
    max_workers: int | None = None, progress: ProgressFn = no_progress,
    worker: Worker = download_track, sleep: Callable[[float], None] = time.sleep,
) -> list[TrackRecord]:  # fmt: skip
    """Process the given records of a job and return all of the job's records afterwards."""
    preset, out_dir = Preset(job.preset), Path(job.out_dir)
    numbered = job.kind == "playlist"
    to_match: list[tuple[TrackRecord, TrackMeta]] = []
    for record, track in pairs:
        existing = existing_output(track, preset, out_dir, record.position if numbered else None)
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
    results = download_all(items, preset, out_dir, settings, workers, worker=worker, sleep=sleep)
    for item, result in progress(results, "Downloading...", len(items)):
        save_result(session, by_key[item.key], result)
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
