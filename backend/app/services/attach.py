"""Attach an audio file you obtained yourself to a Spotify track (and optionally a job)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from sqlmodel import Session, select

from app.config import Settings, load_settings
from app.models import Job, TrackRecord, now
from app.services.filenames import build_filename
from app.services.job_runner import TrackFetcher
from app.services.job_state import finish_job
from app.services.pipeline import fetch_cover
from app.services.spotify_client import SpotifyClient
from app.services.tagger import tag_file

ALLOWED_EXTS: frozenset[str] = frozenset({".mp3", ".m4a", ".opus", ".flac", ".ogg"})


def _is_same_file(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and a.samefile(b)


def attach_file(
    src: Path,
    spotify_track_id: str,
    job: Job | None,
    session: Session,
    copy: bool,
    *,
    force: bool = False,
    client: TrackFetcher | None = None,
    settings: Settings | None = None,
    cover_fetcher: Callable[[str | None], bytes | None] = fetch_cover,
) -> tuple[Path, TrackRecord | None]:
    """Copy/move src to its Spotify-based name, tag it, and mark the job record "manual".

    The file is never re-encoded. Returns (target path, updated record or None).
    Your original file is only removed (move mode) after tagging succeeded.
    """
    ext = src.suffix.lower()
    if not src.is_file():
        raise ValueError(f"File not found: {src}")
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported file type {ext or '(none)'}; use one of {sorted(ALLOWED_EXTS)}")

    settings = settings or load_settings()
    track = (client or SpotifyClient(settings)).get_track(spotify_track_id)

    record: TrackRecord | None = None
    if job is not None:
        query = select(TrackRecord).where(
            TrackRecord.job_id == job.id, TrackRecord.spotify_id == spotify_track_id
        )
        record = session.exec(query).first()
        if record is None:
            raise ValueError(f"Track {spotify_track_id} is not part of job {job.id}")
        index = record.position if job.kind == "playlist" else None
        folder = Path(job.out_dir)
    else:
        index, folder = None, settings.output_dir

    target = folder / build_filename(track, ext.lstrip("."), index)
    same = _is_same_file(src, target)
    if target.exists() and not same and not force:
        raise FileExistsError(f"{target} already exists (use --force to overwrite)")

    folder.mkdir(parents=True, exist_ok=True)
    if not same:
        shutil.copy2(src, target)
    try:
        tag_file(target, track, cover_fetcher(track.cover_url))
    except Exception:
        if not same:
            target.unlink(missing_ok=True)
        raise
    if not copy and not same:
        src.unlink()

    if job is not None and record is not None:
        record.status = "manual"
        record.file_name = target.name
        record.source = f"manual ({ext.lstrip('.')})"
        record.output = ext.lstrip(".")
        record.upscaled = False
        record.error = None
        record.updated_at = now()
        session.add(record)
        session.commit()
        finish_job(session, job)  # refresh status (+ reports if it is the folder's newest job)
    return target, record
