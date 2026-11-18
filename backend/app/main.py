"""Spoteye local API. Run on 127.0.0.1 only:

    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOauthError
from sqlmodel import col, select

from app.config import FRONTEND_DIST, IS_FROZEN, load_settings
from app.db import get_session, init_db
from app.models import Job, now
from app.services import ytdlp_bin
from app.services.presets import PRESET_SPECS
from app.services.spotify_auth import sign_in_expires_at
from app.services.spotify_errors import spotify_error_message, spotify_error_status
from app.web import api_files, api_jobs, api_settings, api_stream, api_tracks, auth
from app.web.events import EventBus
from app.web.job_queue import JobQueue
from app.web.login_task import LoginTask
from app.web.schemas import Health, PresetOut
from app.web.security import OriginCheckMiddleware

# Extra keyword arguments for run_job (tests inject a fake worker and a no-op sleep here).
RUN_OPTIONS: dict[str, Any] = {}
ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
ALLOWED_HOSTS: list[str] = ["127.0.0.1", "localhost"]
log = logging.getLogger(__name__)


def mark_interrupted_jobs() -> int:
    """Jobs left "running"/"queued" by a crash or --reload can't still be running: stop them."""
    with get_session() as session:
        stale = session.exec(select(Job).where(col(Job.status).in_(("running", "queued")))).all()
        for job in stale:
            job.status, job.finished_at = "stopped", now()
            session.add(job)
        session.commit()
        return len(stale)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    mark_interrupted_jobs()
    app.state.bus = EventBus()
    app.state.job_queue = JobQueue(app.state.bus, **RUN_OPTIONS)
    app.state.login_task = LoginTask()
    try:
        yield
    finally:
        app.state.job_queue.shutdown()


app = FastAPI(title="Spoteye", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(OriginCheckMiddleware, allowed_origins=ALLOWED_ORIGINS)
# Added last = runs first: other Host names (DNS rebinding) get 400 before anything else.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


async def spotify_error(request: Request, exc: Exception) -> JSONResponse:
    """401 expired sign-in, 502 Spotify's own errors, 503 unreachable/rate-limited (no traceback).

    Also catches errors re-raised from run_in_threadpool, so every endpoint is covered.
    """
    log.warning("%s %s: Spotify request failed (%s): %s", request.method, request.url.path,
                type(exc).__name__, exc)  # fmt: skip
    return JSONResponse({"detail": spotify_error_message(exc)}, status_code=spotify_error_status(exc))


app.add_exception_handler(requests.RequestException, spotify_error)
app.add_exception_handler(SpotifyException, spotify_error)
app.add_exception_handler(SpotifyOauthError, spotify_error)  # refresh refused within the "ok" cache
app.include_router(api_jobs.router)
app.include_router(api_stream.router)
app.include_router(api_files.router)
app.include_router(api_tracks.router)
app.include_router(api_settings.router)


@app.get("/api/ping")
def ping() -> dict[str, str]:
    """Instant answer for `serve`'s single-instance check (no Spotify, yt-dlp or DB calls)."""
    return {"app": "spoteye"}


@app.get("/api/health", response_model=Health)
def health() -> Health:
    settings = load_settings()
    return Health(
        app="spoteye",
        frozen=IS_FROZEN,
        ffmpeg=shutil.which("ffmpeg") is not None,
        deno=shutil.which("deno") is not None,
        spotify_auth=auth.token_status(settings),
        spotify_auth_expires=sign_in_expires_at(),
        output_dir=str(settings.output_dir),
        yt_dlp_version=ytdlp_bin.version(),
        yt_dlp_mode=ytdlp_bin.mode(),
        cookies=settings.cookies_file is not None and settings.cookies_file.is_file(),
    )


@app.get("/api/presets", response_model=list[PresetOut])
def presets() -> list[PresetOut]:
    return [PresetOut(value=preset.value, label=spec.label) for preset, spec in PRESET_SPECS.items()]


def mount_ui(target: FastAPI, dist: Path) -> bool:
    """Serve the built frontend at "/" (mounted after every /api route). False if not built."""
    if not (dist / "index.html").is_file():
        return False
    target.mount("/", StaticFiles(directory=dist, html=True), name="ui")
    return True


mount_ui(app, FRONTEND_DIST)  # must stay last: "/" would shadow routes added after it
