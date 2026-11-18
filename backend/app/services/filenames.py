"""Windows-safe file names for downloaded tracks."""

from __future__ import annotations

import re
from pathlib import Path

from app.services.presets import Preset, possible_exts
from app.services.spotify_client import TrackMeta

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_SPACES = re.compile(r"\s+")
_RESERVED: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
MAX_FILENAME_LEN: int = 150


def safe_filename(name: str, max_len: int = MAX_FILENAME_LEN) -> str:
    """Strip characters Windows rejects, avoid reserved names, and cap the length."""
    s = _SPACES.sub(" ", _ILLEGAL.sub("", name)).strip().rstrip(". ")
    if s.split(".")[0].strip().upper() in _RESERVED:
        s = f"_{s}"
    s = s[:max_len].rstrip(". ")
    return s or "_"


def build_filename(track: TrackMeta, ext: str, index: int | None) -> str:
    """"{index:02d} - {Artist} - {Title}.{ext}", or without the number when index is None."""
    artist = track.artists[0] if track.artists else "Unknown Artist"
    stem = f"{artist} - {track.title}"
    if index is not None:
        stem = f"{index:02d} - {stem}"
    return f"{safe_filename(stem, max_len=MAX_FILENAME_LEN - len(ext) - 1)}.{ext}"


def existing_output(track: TrackMeta, preset: Preset, out_dir: Path, index: int | None) -> Path | None:
    """The already-downloaded file for this track under any extension the preset can produce."""
    for ext in possible_exts(preset):
        candidate = out_dir / build_filename(track, ext, index)
        if candidate.exists():
            return candidate
    return None
