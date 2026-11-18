"""`attach` command: file a song you downloaded yourself under its Spotify track."""

from __future__ import annotations

from pathlib import Path

import typer
from mutagen import MutagenError
from rich.markup import escape

from app.commands import app, console, fail
from app.db import get_session
from app.models import Job
from app.services.attach import attach_file
from app.services.link_parser import parse_spotify_link
from app.services.spotify_client import SpotifyConfigError


@app.command()
def attach(
    url: str = typer.Argument(..., help="Spotify track URL/URI the file belongs to."),
    file: Path = typer.Argument(..., help="Audio file (.mp3 .m4a .opus .flac .ogg)."),
    job_id: int | None = typer.Option(None, "--job", help="Job id whose track this fills in."),
    copy: bool = typer.Option(False, "--copy", help="Copy instead of move."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing target file."),
) -> None:
    """Rename, tag and file your own audio file (never re-encoded)."""
    try:
        kind, track_id = parse_spotify_link(url)
        if kind != "track":
            raise ValueError("attach needs a Spotify track link, not a playlist or album.")
        with get_session() as session:
            job: Job | None = None
            if job_id is not None:
                job = session.get(Job, job_id)
                if job is None:
                    raise ValueError(f"Job {job_id} not found.")
            target, record = attach_file(file, track_id, job, session, copy, force=force)
    except (ValueError, OSError, SpotifyConfigError, MutagenError) as exc:
        raise fail(str(exc)) from exc

    console.print(f"{'Copied' if copy else 'Moved'} to [green]{escape(str(target))}[/green]")
    if job is not None and record is not None:
        console.print(f"Job {job.id} #{record.position:02d} marked manual (job is now {job.status})")
