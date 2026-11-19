"""yt-dlp as a separate program (packaged app) or as the imported library (from source).

The packaged app ships bin/yt-dlp.exe so it can update itself (yt-dlp -U) without a new build.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from yt_dlp.version import __version__ as LIBRARY_VERSION

from app import config
from app.services.hints import hint

Mode = Literal["binary", "library"]
NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows only
VERSION_TTL_S: float = 600
VERSION_TIMEOUT_S: float = 15
UPDATE_TIMEOUT_S: float = 120
_version_cache: tuple[Path, float, str] | None = None  # (exe, expires at, version)


def find() -> Path | None:
    """YTDLP_PATH if set, else bin/yt-dlp.exe next to the packaged app, else None (library)."""
    if override := os.environ.get("YTDLP_PATH", "").strip():
        return Path(override)
    if config.BIN_DIR is not None and (exe := config.BIN_DIR / "yt-dlp.exe").is_file():
        return exe
    return None


def mode() -> Mode:
    return "library" if find() is None else "binary"


def run(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """Run yt-dlp without a shell or a console window; output decoded as UTF-8."""
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=NO_WINDOW, check=False)  # fmt: skip


def stream(args: list[str], timeout: float, on_line: Callable[[str], None]) -> int:
    """Run yt-dlp like run(), passing each output line (stderr merged into stdout) to on_line.

    Returns the exit code; kills the process and raises TimeoutExpired after timeout seconds.
    """
    expired = threading.Event()
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW) as proc:  # fmt: skip

        def expire() -> None:
            expired.set()
            proc.kill()

        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                on_line(line.rstrip("\r\n"))
        except BaseException:
            proc.kill()
            raise
        finally:
            timer.cancel()
        returncode = proc.wait()
    if expired.is_set():
        raise subprocess.TimeoutExpired(args, timeout)
    return returncode


def version() -> str:
    """The program's --version (cached 10 minutes), or the library version."""
    global _version_cache
    exe = find()
    if exe is None:
        return LIBRARY_VERSION
    if _version_cache and _version_cache[0] == exe and time.monotonic() < _version_cache[1]:
        return _version_cache[2]
    try:
        value = run([str(exe), "--version"], VERSION_TIMEOUT_S).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"  # not cached: try again next time
    _version_cache = (exe, time.monotonic() + VERSION_TTL_S, value)
    return value


def update() -> str:
    """Run yt-dlp -U and return what it printed. RuntimeError in library mode or if it can't run."""
    global _version_cache
    exe = find()
    if exe is None:
        raise RuntimeError(hint("ytdlp_library"))
    try:
        result = run([str(exe), "-U"], UPDATE_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"yt-dlp -U did not finish within {UPDATE_TIMEOUT_S:.0f} s") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not run {exe}: {exc}") from exc
    finally:
        _version_cache = None
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
