"""`download` command: match, download, transcode and tag Spotify tracks.

Lives outside cli.py to keep each module under 150 lines; cli.py registers it.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track as progress
from rich.table import Table

from app.config import load_settings
from app.services.filenames import safe_filename
from app.services.link_parser import parse_spotify_link
from app.services.matcher import Matcher
from app.services.pipeline import TrackResult, process_track
from app.services.presets import Preset
from app.services.spotify_client import (
    PlaylistNotAccessible,
    SpotifyClient,
    SpotifyConfigError,
    TrackMeta,
)
from app.services.transcoder import ensure_ffmpeg

console = Console()

STATUS_STYLE: dict[str, str] = {
    "done": "green",
    "skipped": "cyan",
    "not_found": "red",
    "review_skipped": "yellow",
    "failed": "bold red",
}


def _load_tracks(url: str, limit: int | None) -> tuple[list[TrackMeta], str | None]:
    """Return the tracks to process and, for playlists, the playlist name."""
    kind, spotify_id = parse_spotify_link(url)
    if kind == "album":
        raise ValueError("Album links are not supported yet.")
    client = SpotifyClient()
    if kind == "track":
        return [client.get_track(spotify_id)], None
    name = client.get_playlist_name(spotify_id)
    tracks = client.get_playlist_tracks(spotify_id)
    return (tracks[:limit] if limit else tracks), name


def build_download_table(results: list[TrackResult]) -> Table:
    table = Table(title="Downloads")
    table.add_column("No", justify="right")
    for name in ("Title", "Status", "Source", "Output", "Upscaled"):
        table.add_column(name)
    table.add_column("File name", overflow="fold")
    for index, r in enumerate(results, start=1):
        style = STATUS_STYLE[r.status]
        table.add_row(
            str(index),
            r.track.title,
            f"[{style}]{r.status}[/{style}]",
            r.source or "-",
            r.output or "-",
            "[yellow]yes[/yellow]" if r.upscaled else "no",
            r.path.name if r.path else "-",
        )
    return table


def download(
    url: str = typer.Argument(..., help="Spotify track or playlist URL/URI."),
    preset: Preset = typer.Option(Preset.BEST, "--preset", help="Output format preset."),
    out: Path | None = typer.Option(None, "--out", help="Output folder (default: OUTPUT_DIR)."),
    accept_review: bool = typer.Option(
        False, "--accept-review", help="Also download matches that need review."
    ),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Only the first N playlist tracks."),
) -> None:
    """Download, transcode and tag Spotify tracks via YouTube Music."""
    try:
        ensure_ffmpeg()
        settings = load_settings()
        tracks, playlist_name = _load_tracks(url, limit)
    except (RuntimeError, ValueError, SpotifyConfigError, PlaylistNotAccessible) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    base = out or settings.output_dir
    target = base / safe_filename(playlist_name) if playlist_name else base
    matcher = Matcher()
    results: list[TrackResult] = []
    for i, track in enumerate(progress(tracks, description="Downloading...", console=console), 1):
        number = i if playlist_name else None
        results.append(process_track(track, preset, target, matcher, settings, number, accept_review))

    console.print(build_download_table(results))
    for i, r in enumerate(results, start=1):
        if r.error:
            console.print(f"[red]#{i} {r.track.title}: {r.error}[/red]")
    counts = Counter(r.status for r in results)
    console.print(
        f"{counts['done']} done / {counts['skipped']} skipped / {counts['not_found']} not found / "
        f"{counts['review_skipped']} review skipped / {counts['failed']} failed"
    )
    console.print(f"Output folder: {target}")
