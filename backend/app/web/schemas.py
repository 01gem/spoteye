"""Pydantic request/response models. Datetimes go out as ISO 8601 UTC with a "Z" suffix."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer

from app.models import Job, TrackRecord
from app.services.job_state import KEPT_STATUSES
from app.services.presets import Preset
from app.services.spotify_auth import TokenStatus


def iso_utc(value: datetime) -> str:
    """Naive DB datetimes are UTC; always emit e.g. 2026-11-18T09:30:00.123456Z."""
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(iso_utc, return_type=str)]


class ResolveIn(BaseModel):
    url: str


class ResolvedTrack(BaseModel):
    spotify_id: str
    position: int
    title: str
    artists: list[str]
    album: str
    duration_ms: int
    isrc: str | None
    cover_url: str | None


class Resolved(BaseModel):
    kind: str
    name: str
    target_dir: str
    tracks: list[ResolvedTrack]


class JobIn(BaseModel):
    url: str
    preset: Preset = Preset.BEST
    accept_review: bool = False


class JobCreated(BaseModel):
    job_id: int


class PresetOut(BaseModel):
    value: str
    label: str


class JobSummary(BaseModel):
    id: int
    name: str
    kind: str
    preset: str
    status: str
    created_at: UtcDatetime
    done: int
    total: int


class RecordOut(BaseModel):
    id: int
    position: int
    spotify_id: str
    title: str
    artists: str
    isrc: str | None
    duration_ms: int
    status: str
    video_id: str | None
    score: float | None
    source: str | None
    output: str | None
    upscaled: bool
    file_name: str | None
    error: str | None
    updated_at: UtcDatetime


class JobDetail(JobSummary):
    url: str
    out_dir: str
    finished_at: UtcDatetime | None
    records: list[RecordOut]


class StopOut(BaseModel):
    result: Literal["cancelled", "stopping"]


class ResumeIn(BaseModel):
    accept_review: bool = False


class Health(BaseModel):
    app: Literal["spoteye"]  # lets a second launch recognise a running Spoteye
    frozen: bool
    ffmpeg: bool
    deno: bool
    spotify_auth: TokenStatus
    spotify_auth_expires: UtcDatetime | None  # about 6 months after the last sign-in
    output_dir: str
    yt_dlp_version: str
    yt_dlp_mode: Literal["binary", "library"]
    cookies: bool


def record_out(record: TrackRecord) -> RecordOut:
    return RecordOut.model_validate(record, from_attributes=True)


def job_summary(job: Job, records: Sequence[TrackRecord]) -> JobSummary:
    assert job.id is not None
    done = sum(r.status in KEPT_STATUSES for r in records)
    return JobSummary(id=job.id, name=job.name, kind=job.kind, preset=job.preset,
                      status=job.status, created_at=job.created_at, done=done,
                      total=len(records))  # fmt: skip


def job_detail(job: Job, records: Sequence[TrackRecord]) -> JobDetail:
    summary = dict(job_summary(job, records))  # raw field values (model_dump would serialize)
    return JobDetail(**summary, url=job.url, out_dir=job.out_dir, finished_at=job.finished_at,
                     records=[record_out(r) for r in records])  # fmt: skip
