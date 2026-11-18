"""`download` command: create a job, then match, download, transcode and tag its tracks."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import typer
from rich.markup import escape
from rich.table import Table

from app.commands import app, console, fail, rich_progress, stopped_exit, styled
from app.config import load_settings
from app.db import get_session
from app.models import Job, TrackRecord
from app.services.filenames import safe_filename
from app.services.job_runner import create_job, run_job
from app.services.job_state import JobStopped
from app.services.link_parser import parse_spotify_link
from app.services.matcher import Matcher
from app.services.presets import Preset
from app.services.spotify_client import (
    PlaylistNotAccessible,
    SpotifyClient,
    SpotifyConfigError,
    TrackMeta,
)
from app.services.transcoder import ensure_ffmpeg


def _load_tracks(url: str, limit: int | None) -> tuple[str, str, list[TrackMeta], str | None]:
    """Return (kind, spotify_id, tracks, playlist name or None)."""
    kind, spotify_id = parse_spotify_link(url)
    if kind == "album":
        raise ValueError("Album links are not supported yet.")
    client = SpotifyClient()
    if kind == "track":
        return kind, spotify_id, [client.get_track(spotify_id)], None
    name = client.get_playlist_name(spotify_id)
    tracks = client.get_playlist_tracks(spotify_id)
    return kind, spotify_id, (tracks[:limit] if limit else tracks), name


def build_download_table(records: Sequence[TrackRecord]) -> Table:
    table = Table(title="Downloads")
    table.add_column("No", justify="right")
    for name in ("Title", "Status", "Source", "Output", "Upscaled"):
        table.add_column(name)
    table.add_column("File name", overflow="fold")
    for r in records:
        table.add_row(
            str(r.position),
            escape(r.title),
            styled(r.status),
            r.source or "-",
            r.output or "-",
            "[yellow]yes[/yellow]" if r.upscaled else "no",
            escape(r.file_name or "-"),
        )
    return table


def print_job_summary(job: Job, records: Sequence[TrackRecord]) -> None:
    """Download table, per-track errors, status counts and where the files are."""
    console.print(build_download_table(records))
    for r in records:
        if r.error:
            console.print(f"[red]#{r.position} {escape(r.title)}: {escape(r.error)}[/red]")
    counts = Counter(r.status for r in records)
    manual = f" / {counts['manual']} manual" if counts["manual"] else ""
    console.print(
        f"{counts['done']} done / {counts['skipped']} skipped / {counts['not_found']} not found / "
        f"{counts['review_skipped']} review skipped / {counts['failed']} failed{manual}"
    )
    console.print(f"Output folder: {escape(job.out_dir)}")
    console.print(f"Job {job.id}: {styled(job.status)}")


@app.command()
def download(
    url: str = typer.Argument(..., help="Spotify track or playlist URL/URI."),
    preset: Preset = typer.Option(Preset.BEST, "--preset", help="Output format preset."),
    out: Path | None = typer.Option(None, "--out", help="Output folder (default: OUTPUT_DIR)."),
    accept_review: bool = typer.Option(
        False, "--accept-review", help="Also download matches that need review."
    ),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Only the first N playlist tracks."),
    workers: int | None = typer.Option(
        None, "--workers", min=1, help="Parallel downloads (default: MAX_WORKERS)."
    ),
    rematch: bool = typer.Option(False, "--rematch", help="Ignore the match cache."),
) -> None:
    """Download, transcode and tag Spotify tracks via YouTube Music."""
    try:
        ensure_ffmpeg()
        settings = load_settings()
        kind, spotify_id, tracks, playlist_name = _load_tracks(url, limit)
    except (RuntimeError, ValueError, SpotifyConfigError, PlaylistNotAccessible) as exc:
        raise fail(str(exc)) from exc

    base = out or settings.output_dir
    target = base / safe_filename(playlist_name) if playlist_name else base
    first = tracks[0] if tracks else None
    name = playlist_name or (f"{', '.join(first.artists)} - {first.title}" if first else spotify_id)
    with get_session() as session:
        job, records = create_job(session, url, kind, spotify_id, name, preset, target, tracks)
        console.print(f"Job {job.id}: {escape(name)} ({len(records)} tracks, preset {preset.value})")
        try:
            all_records = run_job(
                session, job, list(zip(records, tracks, strict=True)), Matcher(), settings,
                accept_review=accept_review, rematch=rematch, max_workers=workers,
                progress=rich_progress,
            )  # fmt: skip
        except JobStopped as exc:
            raise stopped_exit(exc.job_id) from None
        print_job_summary(job, all_records)
