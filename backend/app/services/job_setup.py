"""Shared job setup for the CLI and the API: load a link's tracks, pick the folder and the job name."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlmodel import Session, col, select

from app.models import Job
from app.services.filenames import MAX_FOLDER_LEN, safe_filename
from app.services.link_parser import parse_spotify_link
from app.services.spotify_client import SpotifyClient, TrackMeta


class TrackSource(Protocol):
    def get_track(self, track_id: str) -> TrackMeta: ...
    def get_playlist_name(self, playlist_id: str) -> str: ...
    def get_playlist_tracks(self, playlist_id: str) -> list[TrackMeta]: ...


@dataclass
class LoadedTracks:
    kind: str  # "track" | "playlist"
    spotify_id: str
    tracks: list[TrackMeta]
    playlist_name: str | None


def load_tracks(url: str, limit: int | None, client: TrackSource | None = None) -> LoadedTracks:
    """Parse the link and fetch its tracks. Raises ValueError for invalid or album links.

    Without a client, SpotifyClient() is created only after the link checks (CLI behaviour).
    """
    kind, spotify_id = parse_spotify_link(url)
    if kind == "album":
        raise ValueError("Album links are not supported yet.")
    source: TrackSource = client if client is not None else SpotifyClient()
    if kind == "track":
        return LoadedTracks(kind, spotify_id, [source.get_track(spotify_id)], None)
    name = source.get_playlist_name(spotify_id)
    tracks = source.get_playlist_tracks(spotify_id)
    return LoadedTracks(kind, spotify_id, tracks[:limit] if limit else tracks, name)


def job_target(base: Path, playlist_name: str | None) -> Path:
    """Playlists get their own sub-folder of base; single tracks go straight into base."""
    return base / safe_filename(playlist_name, max_len=MAX_FOLDER_LEN) if playlist_name else base


def job_name(playlist_name: str | None, tracks: Sequence[TrackMeta], spotify_id: str) -> str:
    first = tracks[0] if tracks else None
    return playlist_name or (f"{', '.join(first.artists)} - {first.title}" if first else spotify_id)


def previous_folder(session: Session, kind: str, spotify_id: str) -> Path | None:
    """out_dir of the newest job for this playlist if that folder still exists (names can change)."""
    if kind != "playlist":
        return None
    query = select(Job).where(Job.kind == "playlist", Job.spotify_id == spotify_id)
    job = session.exec(query.order_by(col(Job.created_at).desc(), col(Job.id).desc())).first()
    folder = Path(job.out_dir) if job is not None else None
    return folder if folder is not None and folder.is_dir() else None
