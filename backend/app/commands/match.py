"""`match` command: match Spotify tracks to YouTube Music (moved unchanged from cli.py)."""

from __future__ import annotations

from collections import Counter

import typer
from rich.progress import track as progress
from rich.table import Table

from app.commands import app, console, fail
from app.services.link_parser import parse_spotify_link
from app.services.matcher import Matcher, MatchResult
from app.services.spotify_client import (
    PlaylistNotAccessible,
    SpotifyClient,
    SpotifyConfigError,
    TrackMeta,
)
from app.services.spotify_errors import SPOTIFY_ERRORS, spotify_error_message

STATUS_STYLE: dict[str, str] = {"matched": "green", "review": "yellow", "not_found": "red"}
YTM_URL: str = "https://music.youtube.com/watch?v={video_id}"


def _fetch_tracks(url: str) -> list[TrackMeta]:
    """Parse a Spotify link and fetch its tracks, exiting with a message on failure."""
    try:
        kind, spotify_id = parse_spotify_link(url)
        if kind == "album":
            raise ValueError("Album links are not supported yet.")
        client = SpotifyClient()
        if kind == "track":
            return [client.get_track(spotify_id)]
        return client.get_playlist_tracks(spotify_id)
    except SPOTIFY_ERRORS as exc:  # first: some requests errors are also ValueErrors
        raise fail(spotify_error_message(exc)) from exc
    except (ValueError, SpotifyConfigError, PlaylistNotAccessible) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _delta(track: TrackMeta, result: MatchResult) -> str:
    if result.best is None or result.best.duration_s is None:
        return "-"
    return f"{round(result.best.duration_s - track.duration_ms / 1000):+d}"


def build_match_table(rows: list[tuple[TrackMeta, MatchResult]]) -> Table:
    table = Table(title="YouTube Music matches")
    for name in ("No", "Spotify title", "Spotify artist", "Match title", "Match artist"):
        table.add_column(name, justify="right" if name == "No" else "left")
    table.add_column("Δ seconds", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Status")
    table.add_column("URL", overflow="fold")
    for index, (track, result) in enumerate(rows, start=1):
        best = result.best
        style = STATUS_STYLE[result.status]
        table.add_row(
            str(index),
            track.title,
            ", ".join(track.artists),
            best.title if best else "-",
            ", ".join(best.artists) if best else "-",
            _delta(track, result),
            f"{result.score:.2f}",
            f"[{style}]{result.status}[/{style}]",
            YTM_URL.format(video_id=best.video_id) if best else "-",
        )
    return table


@app.command()
def match(url: str = typer.Argument(..., help="Spotify track or playlist URL/URI.")) -> None:
    """Match Spotify tracks to YouTube Music songs (no downloading)."""
    tracks = _fetch_tracks(url)
    matcher = Matcher()
    rows = [(t, matcher.match(t)) for t in progress(tracks, description="Matching...", console=console)]
    console.print(build_match_table(rows))
    counts = Counter(result.status for _, result in rows)
    rate = counts["matched"] / len(rows) * 100 if rows else 0.0
    console.print(
        f"{counts['matched']} matched, {counts['review']} review, "
        f"{counts['not_found']} not found, match rate {rate:.1f}%"
    )
