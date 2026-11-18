"""Per-track actions: list missing tracks, show match candidates, pick a match by hand."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.config import load_settings
from app.db import get_session
from app.models import MatchCache, TrackRecord, now
from app.services.job_state import KEPT_STATUSES, job_records
from app.services.matcher import Matcher
from app.services.reports import MISSING_STATUSES
from app.services.spotify_client import SpotifyConfigError
from app.web import auth
from app.web.api_jobs import get_job_or_404, is_busy, job_queue
from app.web.events import record_event
from app.web.schemas import JobCreated, RecordOut, record_out

router = APIRouter(prefix="/api")
CANDIDATE_LIMIT: int = 5
VIDEO_ID_PATTERN: str = r"^[A-Za-z0-9_-]{11}$"
YTM_WATCH: str = "https://music.youtube.com/watch?v="


class CandidateOut(BaseModel):
    video_id: str
    title: str
    artists: list[str]
    album: str | None
    duration_s: int | None
    delta_s: float | None  # candidate minus Spotify duration, seconds
    score: float
    url: str


class ChooseIn(BaseModel):
    video_id: str = Field(pattern=VIDEO_ID_PATTERN)


def record_or_404(session: Session, job_id: int, record_id: int) -> TrackRecord:
    get_job_or_404(session, job_id)
    record = session.get(TrackRecord, record_id)
    if record is None or record.job_id != job_id:
        raise HTTPException(status_code=404, detail=f"Track {record_id} is not in job {job_id}.")
    return record


@router.get("/jobs/{job_id}/missing", response_model=list[RecordOut])
def missing(job_id: int) -> list[RecordOut]:
    with get_session() as session:
        get_job_or_404(session, job_id)
        return [record_out(r) for r in job_records(session, job_id) if r.status in MISSING_STATUSES]


def _candidates(job_id: int, record_id: int) -> list[CandidateOut]:
    """Fresh search (the match cache is ignored) scored like the automatic match."""
    with get_session() as session:
        spotify_id = record_or_404(session, job_id, record_id).spotify_id
    try:
        track = auth.require_spotify_client(load_settings()).get_track(spotify_id)
    except SpotifyConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    result = Matcher(top_n=CANDIDATE_LIMIT).match(track)
    spotify_s = track.duration_ms / 1000
    return [
        CandidateOut(video_id=c.video_id, title=c.title, artists=c.artists, album=c.album,
                     duration_s=c.duration_s, score=round(score, 3), url=YTM_WATCH + c.video_id,
                     delta_s=None if c.duration_s is None else round(c.duration_s - spotify_s, 1))
        for c, score in result.candidates
    ]  # fmt: skip


@router.get("/jobs/{job_id}/tracks/{record_id}/candidates", response_model=list[CandidateOut])
async def candidates(job_id: int, record_id: int) -> list[CandidateOut]:
    return await run_in_threadpool(_candidates, job_id, record_id)


@router.post("/jobs/{job_id}/tracks/{record_id}/choose", status_code=202, response_model=JobCreated)
def choose(job_id: int, record_id: int, body: ChooseIn, request: Request) -> JobCreated:
    """Pin the chosen video in the match cache, reset the track, and resume the job."""
    with get_session() as session:
        job = get_job_or_404(session, job_id)
        if is_busy(request, job):
            raise HTTPException(status_code=409, detail=f"Job {job_id} is {job.status}.")
        record = record_or_404(session, job_id, record_id)
        if record.status in KEPT_STATUSES:
            raise HTTPException(status_code=409, detail=f"Track {record_id} already has a file.")
        session.merge(MatchCache(spotify_id=record.spotify_id, video_id=body.video_id, score=1.0,
                                 status="matched", matched_at=now()))  # fmt: skip
        record.status, record.error, record.video_id, record.score = "pending", None, body.video_id, 1.0
        record.updated_at = now()
        session.add(record)
        session.commit()
        session.refresh(record)
        request.app.state.bus.publish(job_id, record_event(record))
    job_queue(request).submit_resume(job_id, accept_review=False)
    return JobCreated(job_id=job_id)
