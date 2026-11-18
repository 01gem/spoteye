"""`info` command: show Spotify track metadata (moved unchanged from cli.py)."""

from __future__ import annotations

import typer
from rich.table import Table

from app.commands import app, console, fail
from app.services import spotify_auth
from app.services.spotify_errors import SPOTIFY_ERRORS, spotify_error_message
from app.services.link_parser import parse_spotify_link
from app.services.spotify_client import (
    PlaylistNotAccessible,
    SpotifyClient,
    SpotifyConfigError,
    TrackMeta,
)


def format_duration(duration_ms: int) -> str:
    total_seconds = duration_ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def build_table(tracks: list[TrackMeta], title: str) -> Table:
    table = Table(title=title)
    table.add_column("No", justify="right")
    table.add_column("Title")
    table.add_column("Artists")
    table.add_column("Duration", justify="right")
    table.add_column("ISRC")
    for index, track in enumerate(tracks, start=1):
        table.add_row(
            str(index),
            track.title,
            ", ".join(track.artists),
            format_duration(track.duration_ms),
            track.isrc or "-",
        )
    return table


@app.command()
def info(url: str = typer.Argument(..., help="Spotify track or playlist URL/URI.")) -> None:
    """Show track metadata for a Spotify link."""
    try:
        kind, spotify_id = parse_spotify_link(url)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if kind == "album":
        console.print("[yellow]Album links are not supported yet.[/yellow]")
        raise typer.Exit(code=1)

    try:
        client = SpotifyClient()
        if kind == "track":
            tracks = [client.get_track(spotify_id)]
        else:
            tracks = client.get_playlist_tracks(spotify_id)
    except SPOTIFY_ERRORS as exc:
        raise fail(spotify_error_message(exc)) from exc
    except (SpotifyConfigError, PlaylistNotAccessible) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(build_table(tracks, title=f"{kind}: {spotify_id}"))
    if spotify_auth.signed_in_at() is None:  # the first sign-in happened through info
        spotify_auth.mark_signed_in()
