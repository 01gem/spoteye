"""Job/record state in the database: save results, finish, stop, and who owns a folder's reports."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, col, select

from app.models import Job, TrackRecord, now
from app.services.pipeline import TrackResult
from app.services.reports import write_reports

KEPT_STATUSES: frozenset[str] = frozenset({"done", "skipped", "manual"})


class JobStopped(Exception):
    """Raised by run_job after Ctrl+C: the job was saved as "stopped" and can be resumed."""

    def __init__(self, job_id: int) -> None:
        super().__init__(f"Job {job_id} stopped")
        self.job_id = job_id


def job_records(session: Session, job_id: int) -> list[TrackRecord]:
    query = select(TrackRecord).where(TrackRecord.job_id == job_id).order_by(TrackRecord.position)
    return list(session.exec(query))


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


def newer_job_for_folder(session: Session, job: Job) -> Job | None:
    """The newest later job writing to the same folder (it owns _missing.txt and the .m3u8)."""
    query = (
        select(Job)
        .where(Job.out_dir == job.out_dir, col(Job.id) > job.id)
        .order_by(col(Job.id).desc())
    )
    return session.exec(query).first()


def finish_job(session: Session, job: Job) -> list[TrackRecord]:
    """Set the final status; regenerate reports only if no newer job uses the same folder."""
    assert job.id is not None
    records = job_records(session, job.id)
    kept = sum(r.status in KEPT_STATUSES for r in records)
    job.status = "done" if kept == len(records) else ("failed" if kept == 0 else "partial")
    job.finished_at = now()
    session.add(job)
    session.commit()
    if job.kind == "playlist" and newer_job_for_folder(session, job) is None:
        write_reports(job, records, Path(job.out_dir))
    return records


def stop_job(session: Session, job: Job) -> bool:
    """Mark a running job "stopped" (no reports written). False if it was not running."""
    if job.status != "running":
        return False
    job.status, job.finished_at = "stopped", now()
    session.add(job)
    session.commit()
    return True
