"""Per-track pipeline: match -> download -> transcode -> tag (sequential in M3)."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from app.config import Settings
from app.services.downloader import download_audio
from app.services.filenames import build_filename
from app.services.matcher import Matcher
from app.services.presets import (
    PRESET_SPECS,
    Preset,
    describe_output,
    describe_source,
    plan_output,
    possible_exts,
)
from app.services.spotify_client import TrackMeta
from app.services.tagger import tag_file
from app.services.transcoder import transcode

Status = Literal["done", "skipped", "not_found", "review_skipped", "failed"]

TMP_DIR_NAME: str = ".spoteye_tmp"
COVER_TIMEOUT_S: float = 15.0


@dataclass
class TrackResult:
    track: TrackMeta
    status: Status
    path: Path | None = None
    source: str = ""
    output: str = ""
    upscaled: bool = False
    error: str | None = None


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


def _existing_output(track: TrackMeta, preset: Preset, out_dir: Path, index: int | None) -> Path | None:
    for ext in possible_exts(preset):
        candidate = out_dir / build_filename(track, ext, index)
        if candidate.exists():
            return candidate
    return None


def process_track(
    track: TrackMeta,
    preset: Preset,
    out_dir: Path,
    matcher: Matcher,
    settings: Settings,
    index: int | None,
    accept_review: bool,
) -> TrackResult:
    """Produce one tagged audio file for track in out_dir. Never raises for per-track errors."""
    existing = _existing_output(track, preset, out_dir, index)
    if existing is not None:
        return TrackResult(track, "skipped", path=existing)

    match = matcher.match(track)
    if match.status == "not_found" or match.best is None:
        return TrackResult(track, "not_found")
    if match.status == "review" and not accept_review:
        return TrackResult(track, "review_skipped")

    tmp_root = out_dir / TMP_DIR_NAME
    tmp_dir: Path | None = None
    final: Path | None = None
    try:
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(dir=tmp_root))
        cookies = str(settings.cookies_file) if settings.cookies_file else None
        audio = download_audio(
            match.best.video_id, tmp_dir, PRESET_SPECS[preset].format_selector, cookies
        )
        plan = plan_output(preset, audio.acodec, audio.abr)
        final = out_dir / build_filename(track, plan.ext, index)
        transcode(audio.path, final, plan.ffmpeg_args)
        tag_file(final, track, fetch_cover(track.cover_url))
        return TrackResult(
            track,
            "done",
            path=final,
            source=describe_source(audio.acodec, audio.abr),
            output=describe_output(plan),
            upscaled=plan.upscaled,
        )
    except BaseException as exc:
        # Never leave a half-written file behind: the next run would "skip" it.
        if final is not None:
            final.unlink(missing_ok=True)
        if not isinstance(exc, Exception):
            raise
        return TrackResult(track, "failed", error=str(exc) or type(exc).__name__)
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            tmp_root.rmdir()  # only succeeds once empty
        except OSError:
            pass
