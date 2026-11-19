"""Live per-track progress: a worker thread reports phases and download bytes for the record
bound to it. Nothing is bound in the CLI and in most tests, so report() is then a no-op.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from contextvars import ContextVar, Token
from typing import Any, Literal

Phase = Literal["matching", "waiting", "downloading", "converting", "tagging"]
ProgressFn = Callable[[dict[str, Any]], None]
Binding = tuple[int, ProgressFn]

MIN_STEP: float = 2.0  # percent points
MIN_INTERVAL_S: float = 0.25
log = logging.getLogger(__name__)

_binding: ContextVar[Binding | None] = ContextVar("spoteye_progress", default=None)
_lock = threading.Lock()
_last: dict[int, tuple[Phase, float | None, float]] = {}  # record_id -> (phase, percent, sent at)
_now: Callable[[], float] = time.monotonic


def event(record_id: int, phase: Phase, percent: float | None = None, downloaded: int | None = None,
          total: int | None = None, speed: float | None = None,
          eta: float | None = None) -> dict[str, Any]:  # fmt: skip
    return {"type": "progress", "record_id": record_id, "phase": phase, "percent": percent,
            "downloaded_bytes": downloaded, "total_bytes": total, "speed": speed, "eta": eta}  # fmt: skip


def announce(emit: ProgressFn | None, record_id: int | None, phase: Phase) -> None:
    """Emit a phase without numbers directly (main thread: matching, waiting); never throttled."""
    if emit is not None and record_id is not None:
        emit(event(record_id, phase))


def bind(record_id: int, emit: ProgressFn) -> Token[Binding | None]:
    return _binding.set((record_id, emit))


def reset(token: Token[Binding | None]) -> None:
    binding = _binding.get()
    _binding.reset(token)
    if binding is not None:
        with _lock:
            _last.pop(binding[0], None)


def _due(record_id: int, phase: Phase, percent: float | None) -> bool:
    """First event, phase change, final 100 %, a step of MIN_STEP points or MIN_INTERVAL_S passed."""
    now = _now()
    with _lock:
        last = _last.get(record_id)
        due = (
            last is None or last[0] != phase
            or (percent is not None and (last[1] is None or abs(percent - last[1]) >= MIN_STEP))
            or (percent is not None and percent >= 100 > (last[1] or 0))
            or now - last[2] >= MIN_INTERVAL_S
        )  # fmt: skip
        if due:
            _last[record_id] = (phase, percent, now)
    return due


def report(phase: Phase, percent: float | None = None, downloaded: int | None = None,
           total: int | None = None, speed: float | None = None,
           eta: float | None = None) -> None:  # fmt: skip
    """Emit (throttled) for the bound record; a failing emit must never break a download."""
    binding = _binding.get()
    if binding is None:
        return
    record_id, emit = binding
    if not _due(record_id, phase, percent):
        return
    try:
        emit(event(record_id, phase, percent, downloaded, total, speed, eta))
    except Exception:
        log.exception("Progress callback failed for record %s", record_id)


def _int(value: float | None) -> int | None:
    return int(value) if value is not None else None


def report_download(downloaded: float | None, total: float | None, speed: float | None,
                    eta: float | None) -> None:  # fmt: skip
    """report("downloading") with the percent computed from bytes (total may be an estimate)."""
    percent = min(100.0, downloaded * 100 / total) if downloaded is not None and total else None
    report("downloading", percent, _int(downloaded), _int(total), speed, eta)
