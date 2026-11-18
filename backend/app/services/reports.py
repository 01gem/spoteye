"""Per-job reports in the playlist folder: _missing.txt and a .m3u8 playlist."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.models import Job, TrackRecord
from app.services.filenames import safe_filename

MISSING_FILE_NAME: str = "_missing.txt"
MISSING_STATUSES: frozenset[str] = frozenset({"not_found", "review_skipped", "failed"})
SPOTIFY_TRACK_URL: str = "https://open.spotify.com/track/{spotify_id}"


def _ordered(records: Sequence[TrackRecord]) -> list[TrackRecord]:
    return sorted(records, key=lambda r: r.position)


def missing_lines(records: Sequence[TrackRecord]) -> list[str]:
    """One line per record that still needs attention, in playlist order."""
    return [
        f"{r.position:02d} - {r.artists} - {r.title} | ISRC: {r.isrc or '-'} | "
        f"{SPOTIFY_TRACK_URL.format(spotify_id=r.spotify_id)} | {r.status}"
        for r in _ordered(records)
        if r.status in MISSING_STATUSES
    ]


def write_missing_report(job: Job, records: Sequence[TrackRecord], folder: Path) -> Path | None:
    """Write folder/_missing.txt, or delete it when nothing is missing."""
    path = folder / MISSING_FILE_NAME
    lines = missing_lines(records)
    if not lines:
        path.unlink(missing_ok=True)
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_m3u8(job: Job, records: Sequence[TrackRecord], folder: Path) -> Path:
    """Write folder/<job name>.m3u8 with every record whose file exists, in playlist order."""
    lines = ["#EXTM3U"]
    for r in _ordered(records):
        if r.file_name and (folder / r.file_name).is_file():
            lines.append(f"#EXTINF:{round(r.duration_ms / 1000)},{r.artists} - {r.title}")
            lines.append(r.file_name)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{safe_filename(job.name)}.m3u8"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_reports(job: Job, records: Sequence[TrackRecord], folder: Path) -> None:
    write_missing_report(job, records, folder)
    write_m3u8(job, records, folder)
