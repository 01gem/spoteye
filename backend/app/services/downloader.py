"""Download one YouTube Music audio stream with yt-dlp (no postprocessors): as a library from
source, as the separate bin/yt-dlp.exe in the packaged app (see ytdlp_bin)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yt_dlp

from app.services import ytdlp_bin

YTM_WATCH_URL: str = "https://music.youtube.com/watch?v={video_id}"
COVER_TIMEOUT_S: float = 15.0
DOWNLOAD_TIMEOUT_S: float = 600
STDERR_TAIL_LINES: int = 20
AFTER_MOVE_PRINT: str = "after_move:%(.{filepath,format_id,acodec,abr,ext})j"


def fetch_cover(url: str | None) -> bytes | None:
    """Download cover art; any failure just means no cover."""
    if not url:
        return None
    try:
        response = httpx.get(url, timeout=COVER_TIMEOUT_S, follow_redirects=True)
        response.raise_for_status()
        return response.content
    except httpx.HTTPError:
        return None


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


def _download_with_exe(exe: Path, url: str, temp_dir: Path, format_selector: str,
                       cookies_file: str | None) -> dict[str, Any]:  # fmt: skip
    """Run the yt-dlp program; its last stdout line is the JSON printed after the move."""
    args = [str(exe), "-f", format_selector, "-o", str(temp_dir / "%(id)s.%(ext)s"),
            "--no-playlist", "--retries", "5", "--fragment-retries", "5", "--no-simulate",
            "--no-progress", "--print", AFTER_MOVE_PRINT]  # fmt: skip
    if cookies_file and Path(cookies_file).is_file():
        args += ["--cookies", cookies_file]
    try:
        result = ytdlp_bin.run([*args, url], DOWNLOAD_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise DownloadError(f"Download failed for {url}: timed out after {DOWNLOAD_TIMEOUT_S:.0f} s") from exc
    except OSError as exc:
        raise DownloadError(f"Download failed for {url}: cannot run {exe}: {exc}") from exc
    if result.returncode != 0:  # stderr tail keeps yt-dlp's own words for friendly_error
        tail = "\n".join(result.stderr.strip().splitlines()[-STDERR_TAIL_LINES:])
        raise DownloadError(f"Download failed for {url}: {tail or f'exit code {result.returncode}'}")
    lines = result.stdout.strip().splitlines()
    try:
        entry = json.loads(lines[-1]) if lines else None
    except ValueError:
        entry = None
    if not isinstance(entry, dict):
        raise DownloadError(f"Download failed for {url}: yt-dlp printed no file info")
    return entry


def download_audio(
    video_id: str, temp_dir: Path, format_selector: str, cookies_file: str | None
) -> DownloadedAudio:
    """Download the selected audio stream for video_id into temp_dir."""
    url = YTM_WATCH_URL.format(video_id=video_id)
    if (exe := ytdlp_bin.find()) is not None:
        info: dict[str, Any] | None = _download_with_exe(exe, url, temp_dir, format_selector,
                                                         cookies_file)  # fmt: skip
    else:
        try:
            with yt_dlp.YoutubeDL(_build_options(temp_dir, format_selector, cookies_file)) as ydl:
                info = ydl.extract_info(url, download=True)
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
