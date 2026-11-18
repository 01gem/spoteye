"""Thin FFmpeg wrapper for remuxing/transcoding downloaded audio."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.services.hints import hint

FFMPEG_MISSING_MSG: str = hint("ffmpeg_path")


def ensure_ffmpeg() -> None:
    """Raise RuntimeError if ffmpeg is not on PATH."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(FFMPEG_MISSING_MSG)


def transcode(src: Path, dst: Path, ffmpeg_args: list[str]) -> Path:
    """Run ffmpeg on src -> dst with the given codec args, dropping video and source metadata."""
    cmd: list[str] = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-vn", "-map_metadata", "-1",
        *ffmpeg_args, str(dst),
    ]  # fmt: skip
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(FFMPEG_MISSING_MSG) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed ({exc.returncode}) for {dst.name}: {stderr}") from exc
    return dst
