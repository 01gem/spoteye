"""Live progress: no-op when unbound, throttling, binding per worker, the yt-dlp library hook."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.services import downloader, progress
from app.services.pipeline import TrackResult, WorkItem, download_all
from app.services.presets import Preset
from app.services.spotify_client import TrackMeta

Events = list[dict[str, Any]]
TRACK = TrackMeta(spotify_id="sp1", title="Song", artists=["Artist"], duration_ms=180_000)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [0.0]
    monkeypatch.setattr(progress, "_now", lambda: now[0])
    return now


def bound(record_id: int, events: Events, body: Callable[[], None]) -> None:
    token = progress.bind(record_id, events.append)
    try:
        body()
    finally:
        progress.reset(token)


def test_report_is_a_noop_when_nothing_is_bound() -> None:
    progress.report("downloading", 50.0)  # CLI: nothing bound, nothing happens
    progress.announce(None, 1, "matching")
    events: Events = []
    progress.announce(events.append, 3, "waiting")
    assert events == [{"type": "progress", "record_id": 3, "phase": "waiting", "percent": None,
                       "downloaded_bytes": None, "total_bytes": None, "speed": None, "eta": None}]


def test_throttle_keeps_phase_changes_big_steps_and_the_final_100(clock: list[float]) -> None:
    events: Events = []
    steps: list[tuple[float, progress.Phase, float | None]] = [
        (0.0, "downloading", 10), (0.1, "downloading", 11), (0.2, "downloading", 11.5),  # small: dropped
        (0.3, "downloading", 11.8),  # 0.25 s passed
        (0.35, "downloading", 99.5), (0.36, "downloading", 100), (0.37, "downloading", 100),
        (0.38, "converting", None), (0.39, "tagging", None),
    ]  # fmt: skip

    def run() -> None:
        for at, phase, percent in steps:
            clock[0] = at
            progress.report(phase, percent)

    bound(7, events, run)
    assert [(e["phase"], e["percent"]) for e in events] == [
        ("downloading", 10), ("downloading", 11.8), ("downloading", 99.5), ("downloading", 100),
        ("converting", None), ("tagging", None)]  # fmt: skip
    assert {e["record_id"] for e in events} == {7}
    bound(7, events, lambda: progress.report("tagging"))  # reset() forgot the record: first again
    assert len(events) == 7


def test_report_download_computes_the_percent(clock: list[float]) -> None:
    events: Events = []
    bound(1, events, lambda: progress.report_download(1024, 4096.0, 512.5, 6))
    assert events == [{
        "type": "progress", "record_id": 1, "phase": "downloading", "percent": 25.0,
        "downloaded_bytes": 1024, "total_bytes": 4096, "speed": 512.5, "eta": 6}]  # fmt: skip


def test_download_all_binds_each_items_key(tmp_path: Path) -> None:
    def worker(item: WorkItem, preset: Preset, out_dir: Path, settings: Settings) -> TrackResult:
        progress.report("converting")
        return TrackResult(item.track, "done")

    items = [WorkItem(key, TRACK, f"vid{key}", None) for key in (11, 12, 13)]
    settings = Settings("client", "http://127.0.0.1:8765/callback", tmp_path, None)
    events: Events = []
    results = list(download_all(items, Preset.BEST, tmp_path, settings, 2, worker=worker,
                                sleep=lambda _s: None, on_progress=events.append))  # fmt: skip
    assert len(results) == 3
    assert sorted((e["record_id"], e["phase"]) for e in events) == [
        (11, "converting"), (12, "converting"), (13, "converting")]  # fmt: skip
    list(download_all(items, Preset.BEST, tmp_path, settings, 2, worker=worker,
                      sleep=lambda _s: None))  # fmt: skip
    assert len(events) == 3  # no on_progress: workers report into nothing


def test_library_progress_hook_maps_downloading_and_finished(clock: list[float]) -> None:
    events: Events = []
    opts = downloader._build_options(Path("tmp"), "bestaudio", None)
    assert opts["progress_hooks"] == [downloader._progress_hook]

    def run() -> None:
        downloader._progress_hook({"status": "downloading", "downloaded_bytes": 500, "total_bytes": None,
                                   "total_bytes_estimate": 2000.0, "speed": 100.0, "eta": 15})
        downloader._progress_hook({"status": "finished", "downloaded_bytes": 2000, "total_bytes": 2000})

    bound(4, events, run)
    assert [(e["percent"], e["downloaded_bytes"], e["total_bytes"], e["speed"], e["eta"])
            for e in events] == [(25.0, 500, 2000, 100.0, 15), (100.0, 2000, 2000, None, 0)]  # fmt: skip
