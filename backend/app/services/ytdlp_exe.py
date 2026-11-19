"""Download through the yt-dlp program (packaged app): live progress from the lines its
--progress-template prints, file info from the JSON it prints after the move."""

from __future__ import annotations

import json
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

from app.services import progress, ytdlp_bin
from app.services.errors import DownloadError

DOWNLOAD_TIMEOUT_S: float = 600
TAIL_LINES: int = 40
PROGRESS_PREFIX: str = "SPOTEYE_PROGRESS "
PROGRESS_TEMPLATE: str = (
    "download:SPOTEYE_PROGRESS %(progress.downloaded_bytes)s %(progress.total_bytes)s "
    "%(progress.total_bytes_estimate)s %(progress.speed)s %(progress.eta)s"
)
AFTER_MOVE_PRINT: str = "after_move:%(.{filepath,format_id,acodec,abr,ext})j"


def _number(text: str) -> float | None:
    """yt-dlp prints NA for unknown values."""
    try:
        return None if text == "NA" else float(text)
    except ValueError:
        return None


def report_line(line: str) -> None:
    """SPOTEYE_PROGRESS <downloaded> <total> <total estimate> <speed> <eta> -> progress.report."""
    values = [_number(v) for v in line.removeprefix(PROGRESS_PREFIX).split()]
    if len(values) == 5:
        downloaded, total, estimate, speed, eta = values
        progress.report_download(downloaded, total or estimate, speed, eta)


def _json_object(line: str) -> dict[str, Any] | None:
    if not line.startswith("{"):
        return None
    try:
        value = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def download(exe: Path, url: str, temp_dir: Path, format_selector: str,
             cookies_file: str | None) -> dict[str, Any]:  # fmt: skip
    """Run the program; the last output line that is a JSON object is the file info."""
    args = [str(exe), "-f", format_selector, "-o", str(temp_dir / "%(id)s.%(ext)s"),
            "--no-playlist", "--retries", "5", "--fragment-retries", "5", "--no-simulate",
            "--progress", "--newline", "--progress-template", PROGRESS_TEMPLATE,
            "--print", AFTER_MOVE_PRINT]  # fmt: skip
    if cookies_file and Path(cookies_file).is_file():
        args += ["--cookies", cookies_file]
    tail: deque[str] = deque(maxlen=TAIL_LINES)
    entry: dict[str, Any] | None = None

    def on_line(line: str) -> None:
        nonlocal entry
        if line.startswith(PROGRESS_PREFIX):
            report_line(line)
        elif line.strip():
            tail.append(line)
            if (parsed := _json_object(line)) is not None:
                entry = parsed

    try:
        returncode = ytdlp_bin.stream([*args, url], DOWNLOAD_TIMEOUT_S, on_line)
    except subprocess.TimeoutExpired as exc:
        raise DownloadError(f"Download failed for {url}: timed out after {DOWNLOAD_TIMEOUT_S:.0f} s") from exc
    except OSError as exc:
        raise DownloadError(f"Download failed for {url}: cannot run {exe}: {exc}") from exc
    if returncode != 0:  # the output tail keeps yt-dlp's own words for friendly_error
        text = "\n".join(tail)
        raise DownloadError(f"Download failed for {url}: {text or f'exit code {returncode}'}")
    if entry is None:
        raise DownloadError(f"Download failed for {url}: yt-dlp printed no file info")
    return entry
