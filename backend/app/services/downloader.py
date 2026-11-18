"""Download one YouTube Music audio stream with yt-dlp (library mode, no postprocessors)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp

YTM_WATCH_URL: str = "https://music.youtube.com/watch?v={video_id}"


class DownloadError(Exception):
    """Raised when yt-dlp cannot download the requested stream."""


@dataclass
class DownloadedAudio:
    path: Path
    video_id: str
    format_id: str
    acodec: str
    abr: float | None
    ext: str


class _SilentLogger:
    """Keep yt-dlp from printing over the progress bar; failures surface as exceptions."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


def _build_options(temp_dir: Path, format_selector: str, cookies_file: str | None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "format": format_selector,
        "outtmpl": str(temp_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 5,
        "fragment_retries": 5,
        "noplaylist": True,
        "logger": _SilentLogger(),
    }
    if cookies_file and Path(cookies_file).is_file():
        opts["cookiefile"] = cookies_file
    return opts


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def download_audio(
    video_id: str, temp_dir: Path, format_selector: str, cookies_file: str | None
) -> DownloadedAudio:
    """Download the selected audio stream for video_id into temp_dir."""
    url = YTM_WATCH_URL.format(video_id=video_id)
    try:
        with yt_dlp.YoutubeDL(_build_options(temp_dir, format_selector, cookies_file)) as ydl:
            info: dict[str, Any] | None = ydl.extract_info(url, download=True)
    except Exception as exc:
        raise DownloadError(f"Download failed for {url}: {exc}") from exc
    if not info:
        raise DownloadError(f"Download failed for {url}: yt-dlp returned no info")

    entry: dict[str, Any] = (info.get("requested_downloads") or [info])[0]
    file_path = entry.get("filepath") or entry.get("_filename")
    if not file_path or not Path(file_path).is_file():
        raise DownloadError(f"Download failed for {url}: no output file was written")
    return DownloadedAudio(
        path=Path(file_path),
        video_id=video_id,
        format_id=str(entry.get("format_id") or info.get("format_id") or ""),
        acodec=str(entry.get("acodec") or info.get("acodec") or ""),
        abr=_float_or_none(entry.get("abr") or info.get("abr")),
        ext=str(entry.get("ext") or info.get("ext") or Path(file_path).suffix.lstrip(".")),
    )
