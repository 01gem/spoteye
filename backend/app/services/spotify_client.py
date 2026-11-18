"""Thin Spotify Web API wrapper using spotipy with PKCE (no client secret)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyPKCE

from app.config import CACHE_PATH, Settings, load_settings

SCOPE: str = "playlist-read-private playlist-read-collaborative"
PAGE_LIMIT: int = 50
NOT_ACCESSIBLE_MSG: str = (
    "Spotify only returns tracks for playlists you own or collaborate on. "
    "Copy it to your library first."
)


class PlaylistNotAccessible(Exception):
    """Raised when Spotify returns no items for a playlist."""


class SpotifyConfigError(Exception):
    """Raised when required Spotify settings are missing."""


@dataclass
class TrackMeta:
    spotify_id: str
    title: str
    artists: list[str] = field(default_factory=list)
    album: str = ""
    album_artist: str = ""
    track_number: int = 0
    disc_number: int = 0
    release_date: str = ""
    duration_ms: int = 0
    isrc: str | None = None
    cover_url: str | None = None


def _largest_image_url(images: list[dict[str, Any]] | None) -> str | None:
    if not images:
        return None
    best = max(images, key=lambda img: (img.get("width") or 0) * (img.get("height") or 0))
    return best.get("url")


def track_from_json(data: dict[str, Any]) -> TrackMeta:
    """Convert a Spotify track object into TrackMeta."""
    album: dict[str, Any] = data.get("album") or {}
    album_artists: list[dict[str, Any]] = album.get("artists") or []
    external_ids: dict[str, Any] = data.get("external_ids") or {}
    return TrackMeta(
        spotify_id=data["id"],
        title=data.get("name", ""),
        artists=[a.get("name", "") for a in data.get("artists") or []],
        album=album.get("name", ""),
        album_artist=album_artists[0].get("name", "") if album_artists else "",
        track_number=data.get("track_number") or 0,
        disc_number=data.get("disc_number") or 0,
        release_date=album.get("release_date", ""),
        duration_ms=data.get("duration_ms") or 0,
        isrc=external_ids.get("isrc"),
        cover_url=_largest_image_url(album.get("images")),
    )


class SpotifyClient:
    """Fetch track metadata for single tracks and playlists."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings: Settings = settings or load_settings()
        if not self.settings.spotify_client_id:
            raise SpotifyConfigError(
                "SPOTIFY_CLIENT_ID is not set. Copy backend/.env.example to "
                "backend/.env and fill it in."
            )
        auth = SpotifyPKCE(
            client_id=self.settings.spotify_client_id,
            redirect_uri=self.settings.spotify_redirect_uri,
            scope=SCOPE,
            cache_handler=CacheFileHandler(cache_path=str(CACHE_PATH)),
        )
        self.sp: spotipy.Spotify = spotipy.Spotify(auth_manager=auth)

    def get_track(self, track_id: str) -> TrackMeta:
        """Fetch one track via GET /tracks/{id}."""
        data: dict[str, Any] = self.sp._get(f"tracks/{track_id}")
        return track_from_json(data)

    def get_playlist_tracks(self, playlist_id: str) -> list[TrackMeta]:
        """Fetch all tracks in a playlist via paginated GET /playlists/{id}/items."""
        tracks: list[TrackMeta] = []
        offset = 0
        saw_items = False
        while True:
            page: dict[str, Any] = self.sp._get(
                f"playlists/{playlist_id}/items", limit=PAGE_LIMIT, offset=offset
            )
            items: list[dict[str, Any]] = page.get("items") or []
            if not items:
                break
            saw_items = True
            for entry in items:
                obj = entry.get("item") or entry.get("track")
                if not obj or obj.get("type", "track") != "track":
                    continue
                if entry.get("is_local") or obj.get("is_local") or not obj.get("id"):
                    continue
                tracks.append(track_from_json(obj))
            if not page.get("next"):
                break
            offset += PAGE_LIMIT
        if not saw_items:
            raise PlaylistNotAccessible(NOT_ACCESSIBLE_MSG)
        return tracks
