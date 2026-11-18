"""Two phases: sequential cached matching (main thread), then concurrent download/transcode/tag.

Workers never touch the database: they receive plain values and return a TrackResult.
"""

from __future__ import annotations

import logging
import os
import random
import shutil
import tempfile
import time
from collections.abc import Callable, Generator, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlmodel import Session

from app.config import Settings
from app.models import MatchCache, now
from app.services.downloader import download_audio, fetch_cover
from app.services.errors import friendly_error
from app.services.filenames import build_filename, existing_output
from app.services.matcher import Matcher
from app.services.presets import PRESET_SPECS, Preset, describe_output, describe_source
from app.services.presets import plan_output
from app.services.spotify_client import TrackMeta
from app.services.tagger import tag_file
from app.services.transcoder import transcode

__all__ = ["TrackResult", "WorkItem", "Worker", "existing_output", "fetch_cover", "match_all",
           "download_track", "download_all", "cleanup_tmp"]  # fmt: skip

Status = Literal["done", "skipped", "not_found", "review_skipped", "failed"]
TMP_DIR_NAME: str = ".spoteye_tmp"
log = logging.getLogger(__name__)


@dataclass
class TrackResult:
    track: TrackMeta
    status: Status
    path: Path | None = None
    source: str = ""
    output: str = ""
    upscaled: bool = False
    error: str | None = None


@dataclass(frozen=True)
class WorkItem:
    key: int  # caller's id for this track (TrackRecord.id)
    track: TrackMeta
    video_id: str
    index: int | None  # number in the file name (playlists only)


Worker = Callable[[WorkItem, Preset, Path, Settings], TrackResult]


def match_all(
    tracks: Iterable[TrackMeta], matcher: Matcher, session: Session, rematch: bool = False
) -> dict[str, MatchCache]:
    """Phase 1: match each track, using and filling MatchCache (bypassed when rematch)."""
    results: dict[str, MatchCache] = {}
    for track in tracks:
        cached = None if rematch else session.get(MatchCache, track.spotify_id)
        if cached is None:
            result = matcher.match(track)
            cached = MatchCache(
                spotify_id=track.spotify_id, video_id=result.best.video_id if result.best else None,
                score=result.score, status=result.status, matched_at=now(),
            )  # fmt: skip
            if result.best is not None:  # no candidates at all may be a network error: don't cache
                cached = session.merge(cached)
                session.commit()
        results[track.spotify_id] = cached
    return results


def download_track(item: WorkItem, preset: Preset, out_dir: Path, settings: Settings) -> TrackResult:
    """Download -> transcode -> cover -> tag one matched track (same steps as M3)."""
    track = item.track
    tmp_dir: Path | None = None
    try:
        tmp_root = out_dir / TMP_DIR_NAME
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(dir=tmp_root))
        cookies = str(settings.cookies_file) if settings.cookies_file else None
        selector = PRESET_SPECS[preset].format_selector
        audio = download_audio(item.video_id, tmp_dir, selector, cookies)
        plan = plan_output(preset, audio.acodec, audio.abr)
        name = build_filename(track, plan.ext, item.index)
        staged = tmp_dir / "out" / name  # convert + tag here; the final name appears only complete
        staged.parent.mkdir()
        transcode(audio.path, staged, plan.ffmpeg_args)
        tag_file(staged, track, fetch_cover(track.cover_url))
        final = out_dir / name
        os.replace(staged, final)  # same drive (tmp is inside out_dir) -> atomic
        return TrackResult(
            track, "done", path=final, source=describe_source(audio.acodec, audio.abr),
            output=describe_output(plan), upscaled=plan.upscaled,
        )  # fmt: skip
    except Exception as exc:
        log.exception("Download failed: %s - %s", track.spotify_id, track.title)
        return TrackResult(track, "failed", error=friendly_error(str(exc) or type(exc).__name__))
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def download_all(
    items: list[WorkItem],
    preset: Preset,
    out_dir: Path,
    settings: Settings,
    max_workers: int,
    worker: Worker = download_track,
    sleep: Callable[[float], None] = time.sleep,
) -> Generator[tuple[WorkItem, TrackResult]]:
    """Phase 2: run worker concurrently and yield (item, result) as each finishes."""

    def run(item: WorkItem) -> TrackResult:
        sleep(random.uniform(1, 3))
        return worker(item, preset, out_dir, settings)

    pool = ThreadPoolExecutor(max_workers=max(1, max_workers))
    try:
        futures: dict[Future[TrackResult], WorkItem] = {pool.submit(run, i): i for i in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = TrackResult(item.track, "failed", error=str(exc) or type(exc).__name__)
            yield item, result
    finally:
        pool.shutdown(wait=True, cancel_futures=True)  # Ctrl+C: drop queued tracks


def cleanup_tmp(out_dir: Path) -> None:
    """Remove the temp folder once all workers are finished (only if empty)."""
    try:
        (out_dir / TMP_DIR_NAME).rmdir()
    except OSError:
        pass
