"""SQLModel tables: job history, per-track records and the match cache.

Timestamps are stored in UTC (sqlmodel requires timezone-aware datetimes); the CLI shows local time.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

JOB_STATUSES = ("running", "done", "partial", "failed")
RECORD_STATUSES = (
    "pending", "done", "skipped", "not_found", "review_skipped", "failed", "manual",
)  # fmt: skip
MATCH_STATUSES = ("matched", "review", "not_found")


def now() -> datetime:
    return datetime.now(UTC)


def to_local(value: datetime) -> datetime:
    """UTC timestamp from the DB -> local time (naive values are treated as UTC)."""
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone()


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    url: str
    kind: str  # "track" | "playlist"
    spotify_id: str
    name: str
    preset: str
    out_dir: str
    status: str = "running"  # see JOB_STATUSES
    created_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None


class TrackRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    spotify_id: str = Field(index=True)
    position: int  # 1-based
    title: str
    artists: str  # comma-joined
    isrc: str | None = None
    duration_ms: int = 0
    status: str = "pending"  # see RECORD_STATUSES
    video_id: str | None = None
    score: float | None = None
    file_name: str | None = None
    source: str | None = None
    output: str | None = None
    upscaled: bool = False
    error: str | None = None
    updated_at: datetime = Field(default_factory=now)


class MatchCache(SQLModel, table=True):
    spotify_id: str = Field(primary_key=True)
    video_id: str | None = None
    score: float = 0.0
    status: str = "not_found"  # see MATCH_STATUSES
    matched_at: datetime = Field(default_factory=now)
