"""Resolve links and manage jobs: create, list, detail, resume, stop, delete."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, col, select

from app.config import Settings, load_settings
from app.db import get_session
from app.models import Job
from app.services.job_runner import create_job
from app.services.job_setup import LoadedTracks, job_name, job_target, load_tracks, previous_folder
from app.services.job_state import delete_job, job_records
from app.services.spotify_client import PlaylistNotAccessible, SpotifyConfigError
from app.web import auth
from app.web.job_queue import JobQueue
from app.web.schemas import JobCreated, JobDetail, JobIn, JobSummary, Resolved, ResolvedTrack
from app.web.schemas import ResolveIn, ResumeIn, StopOut, job_detail, job_summary

router = APIRouter(prefix="/api")
BUSY_STATUSES: frozenset[str] = frozenset({"queued", "running"})
RECENT_JOBS: int = 50


def job_queue(request: Request) -> JobQueue:
    queue: JobQueue = request.app.state.job_queue
    return queue


def get_job_or_404(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job


def is_busy(request: Request, job: Job) -> bool:
    assert job.id is not None
    return job.status in BUSY_STATUSES or job_queue(request).is_active(job.id)


def load_detail(job_id: int) -> JobDetail:
    with get_session() as session:
        job = get_job_or_404(session, job_id)
        return job_detail(job, job_records(session, job_id))


def _fetch(url: str) -> tuple[LoadedTracks, Settings]:
    settings = load_settings()
    client = auth.require_spotify_client(settings)  # 401 before any browser could open
    return load_tracks(url, None, client), settings


async def _load(url: str) -> tuple[LoadedTracks, Settings]:
    try:
        return await run_in_threadpool(_fetch, url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlaylistNotAccessible as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SpotifyConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _target(settings: Settings, loaded: LoadedTracks) -> Path:
    """Same folder for the preview and create(): the playlist's earlier folder, else a new one."""
    with get_session() as session:
        previous = previous_folder(session, loaded.kind, loaded.spotify_id)
    return previous or job_target(settings.output_dir, loaded.playlist_name)


@router.post("/resolve", response_model=Resolved)
async def resolve(body: ResolveIn) -> Resolved:
    loaded, settings = await _load(body.url)
    tracks = [
        ResolvedTrack(spotify_id=t.spotify_id, position=i, title=t.title, artists=t.artists,
                      album=t.album, duration_ms=t.duration_ms, isrc=t.isrc, cover_url=t.cover_url)
        for i, t in enumerate(loaded.tracks, start=1)
    ]  # fmt: skip
    name = job_name(loaded.playlist_name, loaded.tracks, loaded.spotify_id)
    target = await run_in_threadpool(_target, settings, loaded)  # same folder create() uses
    return Resolved(kind=loaded.kind, name=name, target_dir=str(target), tracks=tracks)


@router.post("/jobs", status_code=201, response_model=JobCreated)
async def create(body: JobIn, request: Request) -> JobCreated:
    loaded, settings = await _load(body.url)
    target = await run_in_threadpool(_target, settings, loaded)  # never a client-given path
    name = job_name(loaded.playlist_name, loaded.tracks, loaded.spotify_id)

    def insert() -> int:
        with get_session() as session:
            job, _ = create_job(session, body.url, loaded.kind, loaded.spotify_id, name,
                                body.preset, target, loaded.tracks)  # fmt: skip
            assert job.id is not None
            return job.id

    job_id = await run_in_threadpool(insert)
    await run_in_threadpool(job_queue(request).submit_new, job_id, loaded.tracks,
                            body.accept_review)  # fmt: skip
    return JobCreated(job_id=job_id)


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs() -> list[JobSummary]:
    with get_session() as session:
        recent = session.exec(select(Job).order_by(col(Job.id).desc()).limit(RECENT_JOBS)).all()
        return [job_summary(job, job_records(session, job.id or 0)) for job in recent]


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int) -> JobDetail:
    return load_detail(job_id)


@router.post("/jobs/{job_id}/resume", status_code=202, response_model=JobCreated)
def resume(job_id: int, request: Request, body: ResumeIn | None = None) -> JobCreated:
    with get_session() as session:
        job = get_job_or_404(session, job_id)
    if is_busy(request, job):
        raise HTTPException(status_code=409, detail=f"Job {job_id} is already {job.status}.")
    auth.require_spotify_auth(load_settings())
    job_queue(request).submit_resume(job_id, (body or ResumeIn()).accept_review)
    return JobCreated(job_id=job_id)


@router.post("/jobs/{job_id}/stop", status_code=202, response_model=StopOut)
def stop(job_id: int, request: Request) -> StopOut:
    with get_session() as session:
        get_job_or_404(session, job_id)
    result = job_queue(request).stop(job_id)
    if result is None:
        raise HTTPException(status_code=409, detail=f"Job {job_id} is not queued or running.")
    return StopOut(result=result)


@router.delete("/jobs/{job_id}", status_code=204, response_class=Response)
def delete(job_id: int, request: Request) -> Response:
    """Forget the job and its track list; files and the match cache stay."""
    with get_session() as session:
        job = get_job_or_404(session, job_id)
        if is_busy(request, job):
            raise HTTPException(status_code=409, detail=f"Job {job_id} is {job.status}; stop it first.")
        delete_job(session, job)
    return Response(status_code=204)
