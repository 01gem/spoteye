"""Job history commands: `jobs`, `job`, `resume`, `stop`, `missing`, `forget`."""

from __future__ import annotations

import typer
from rich.markup import escape
from rich.table import Table
from sqlmodel import Session, col, select

from app.commands import app, console, fail, rich_progress, stopped_exit, styled
from app.commands.download import print_job_summary
from app.config import load_settings
from app.db import get_session
from app.models import Job, to_local
from app.services.job_runner import resume_job
from app.services.job_state import KEPT_STATUSES, JobStopped, job_records
from app.services.job_state import delete_job, newer_job_for_folder, stop_job
from app.services.matcher import Matcher
from app.services.reports import missing_lines
from app.services.spotify_client import SpotifyClient, SpotifyConfigError
from app.services.spotify_errors import SPOTIFY_ERRORS, spotify_error_message
from app.services.transcoder import ensure_ffmpeg

RECENT_JOBS: int = 20


def _get_job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise fail(f"Job {job_id} not found.")
    return job


@app.command()
def jobs() -> None:
    """List the most recent download jobs."""
    with get_session() as session:
        recent = session.exec(select(Job).order_by(col(Job.id).desc()).limit(RECENT_JOBS)).all()
        table = Table(title=f"Last {RECENT_JOBS} jobs")
        for name in ("Id", "Name", "Preset", "Created", "Done/Total", "Status"):
            table.add_column(name, justify="right" if name in ("Id", "Done/Total") else "left")
        for job in recent:
            assert job.id is not None
            records = job_records(session, job.id)
            kept = sum(r.status in KEPT_STATUSES for r in records)
            table.add_row(
                str(job.id), escape(job.name), job.preset,
                to_local(job.created_at).strftime("%Y-%m-%d %H:%M"), f"{kept}/{len(records)}",
                styled(job.status),
            )  # fmt: skip
    console.print(table)


@app.command()
def job(job_id: int = typer.Argument(..., help="Job id (see `jobs`).")) -> None:
    """Show every track of one job."""
    with get_session() as session:
        found = _get_job(session, job_id)
        records = job_records(session, job_id)
    table = Table(title=f"Job {job_id}: {escape(found.name)} [{found.status}]")
    for name in ("No", "Title", "Artists", "Status", "Score", "Source", "Output"):
        table.add_column(name, justify="right" if name in ("No", "Score") else "left")
    table.add_column("File name", overflow="fold")
    for r in records:
        table.add_row(
            str(r.position), escape(r.title), escape(r.artists), styled(r.status),
            f"{r.score:.2f}" if r.score is not None else "-",
            r.source or "-", r.output or "-", escape(r.file_name or "-"),
        )  # fmt: skip
    console.print(table)


@app.command()
def resume(
    job_id: int = typer.Argument(..., help="Job id (see `jobs`)."),
    accept_review: bool = typer.Option(
        False, "--accept-review", help="Also retry tracks skipped for review."
    ),
    workers: int | None = typer.Option(
        None, "--workers", min=1, help="Parallel downloads (default: MAX_WORKERS)."
    ),
    rematch: bool = typer.Option(False, "--rematch", help="Ignore the match cache."),
) -> None:
    """Retry a job's pending and failed tracks with its original preset and folder."""
    try:
        ensure_ffmpeg()
        settings = load_settings()
        client = SpotifyClient(settings)
    except (RuntimeError, SpotifyConfigError) as exc:
        raise fail(str(exc)) from exc
    with get_session() as session:
        found = _get_job(session, job_id)
        try:
            records = resume_job(
                session, found, client, Matcher(), settings, accept_review=accept_review,
                rematch=rematch, max_workers=workers, progress=rich_progress,
            )  # fmt: skip
        except JobStopped as exc:
            raise stopped_exit(exc.job_id) from None
        except SPOTIFY_ERRORS as exc:  # fetching the tracks happens before the job is "running"
            raise fail(spotify_error_message(exc)) from exc
        print_job_summary(found, records)
        newer = newer_job_for_folder(session, found) if found.kind == "playlist" else None
        if newer is not None:
            console.print(f"[dim]Reports not rewritten: job {newer.id} is newer for this folder.[/dim]")


@app.command()
def stop(job_id: int = typer.Argument(..., help="Job id (see `jobs`).")) -> None:
    """Mark a job stuck at "running" (closed terminal, killed process) as stopped.

    It does not kill anything: for a job running in another terminal, press Ctrl+C there.
    """
    with get_session() as session:
        found = _get_job(session, job_id)
        if not stop_job(session, found):
            raise fail(f"Job {job_id} is not running (status: {found.status}).")
    console.print(f"Job {job_id}: {styled(found.status)}. Continue with: python cli.py resume {job_id}")


@app.command()
def missing(job_id: int = typer.Argument(..., help="Job id (see `jobs`).")) -> None:
    """Print the tracks of a job that were not downloaded (same as _missing.txt)."""
    with get_session() as session:
        _get_job(session, job_id)
        lines = missing_lines(job_records(session, job_id))
    if not lines:
        console.print("[green]Nothing missing.[/green]")
    for line in lines:
        console.print(line, markup=False, highlight=False)


@app.command()
def forget(job_id: int = typer.Argument(..., help="Job id (see `jobs`).")) -> None:
    """Remove a job and its track list from the history. Files and the match cache stay."""
    with get_session() as session:
        found = _get_job(session, job_id)
        if found.status in ("queued", "running"):
            raise fail(f"Job {job_id} is {found.status}; stop it first: python cli.py stop {job_id}")
        out_dir = found.out_dir
        delete_job(session, found)
    console.print(f"Job {job_id} forgotten. Files in {escape(out_dir)} were not touched.")
