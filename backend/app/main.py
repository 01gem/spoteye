"""Spoteye local API. Run on 127.0.0.1 only:

    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
"""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import col, select
from yt_dlp.version import __version__ as YT_DLP_VERSION

from app.config import FRONTEND_DIST, load_settings
from app.db import get_session, init_db
from app.models import Job, now
from app.services.presets import PRESET_SPECS
from app.web import api_files, api_jobs, api_stream, api_tracks, auth
from app.web.events import EventBus
from app.web.job_queue import JobQueue
from app.web.schemas import Health, PresetOut

# Extra keyword arguments for run_job (tests inject a fake worker and a no-op sleep here).
RUN_OPTIONS: dict[str, Any] = {}
ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


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
app.include_router(api_jobs.router)
app.include_router(api_stream.router)
app.include_router(api_files.router)
app.include_router(api_tracks.router)


@app.get("/api/health", response_model=Health)
def health() -> Health:
    settings = load_settings()
    return Health(
        ffmpeg=shutil.which("ffmpeg") is not None,
        deno=shutil.which("deno") is not None,
        spotify_auth=auth.has_spotify_token(),
        output_dir=str(settings.output_dir),
        yt_dlp_version=YT_DLP_VERSION,
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
