"""Live job progress (Server-Sent Events) and attaching an uploaded audio file to a track."""

from __future__ import annotations

import asyncio
import json
import queue
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.config import load_settings
from app.db import get_session
from app.models import Job, TrackRecord
from app.services.attach import ALLOWED_EXTS, attach_file
from app.services.job_runner import TrackFetcher
from app.services.job_state import job_records
from app.services.pipeline import TMP_DIR_NAME, cleanup_tmp
from app.services.spotify_client import SpotifyConfigError
from app.web import auth
from app.web.api_jobs import get_job_or_404, is_busy, load_detail
from app.web.events import EventBus, job_event, record_event
from app.web.schemas import JobDetail, RecordOut, record_out

router = APIRouter(prefix="/api")
CHUNK: int = 1024 * 1024
MAX_UPLOAD: int = 500 * 1024 * 1024
KEEPALIVE_S: float = 15


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def snapshot_data(detail: JobDetail, bus: EventBus) -> str:
    """The JobDetail plus "progress": {record_id: latest progress event} of running tracks."""
    return json.dumps({**detail.model_dump(mode="json"), "progress": bus.progress(detail.id)})


@router.get("/jobs/{job_id}/events")
async def events(job_id: int, request: Request) -> StreamingResponse:
    bus: EventBus = request.app.state.bus
    q = bus.subscribe(job_id)  # subscribe before the snapshot so no event falls in between
    try:
        detail = await run_in_threadpool(load_detail, job_id)
    except Exception:
        bus.unsubscribe(job_id, q)
        raise

    async def stream() -> AsyncIterator[str]:
        try:
            yield _sse("snapshot", snapshot_data(detail, bus))
            while not await request.is_disconnected():
                try:
                    event = await asyncio.to_thread(q.get, True, KEEPALIVE_S)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                yield _sse(str(event["type"]), json.dumps(event))
        finally:
            bus.unsubscribe(job_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})  # fmt: skip


def _check_target(request: Request, job_id: int, record_id: int) -> Job:
    with get_session() as session:
        job = get_job_or_404(session, job_id)
        if is_busy(request, job):
            raise HTTPException(status_code=409, detail=f"Job {job_id} is {job.status}.")
        record = session.get(TrackRecord, record_id)
        if record is None or record.job_id != job_id:
            raise HTTPException(status_code=404, detail=f"Track {record_id} is not in job {job_id}.")
        return job


async def _save_upload(file: UploadFile, dest: Path) -> None:
    """Stream the upload to dest in 1 MB chunks; 400 once it passes MAX_UPLOAD."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(status_code=400, detail="File is larger than 500 MB.")
            await run_in_threadpool(out.write, chunk)


def _attach(bus: EventBus, job_id: int, record_id: int, src: Path, client: TrackFetcher) -> RecordOut:
    with get_session() as session:
        job = get_job_or_404(session, job_id)
        record = session.get(TrackRecord, record_id)
        assert record is not None
        try:
            _, updated = attach_file(src, record.spotify_id, job, session, copy=False, client=client)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result = updated or record
        bus.publish(job_id, record_event(result))
        bus.publish(job_id, job_event(job, job_records(session, job_id)))
        return record_out(result)


@router.post("/jobs/{job_id}/tracks/{record_id}/attach", response_model=RecordOut)
async def attach(job_id: int, record_id: int, request: Request, file: UploadFile) -> RecordOut:
    job = await run_in_threadpool(_check_target, request, job_id, record_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type {ext or '(none)'}; "
                                                    f"use one of {sorted(ALLOWED_EXTS)}")  # fmt: skip
    try:
        client = await run_in_threadpool(auth.require_spotify_client, load_settings())
    except SpotifyConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    out_dir = Path(job.out_dir)
    upload_dir = out_dir / TMP_DIR_NAME / "uploads"
    tmp_path = upload_dir / f"{uuid4().hex}{ext}"
    try:
        await _save_upload(file, tmp_path)
        return await run_in_threadpool(_attach, request.app.state.bus, job_id, record_id,
                                       tmp_path, client)  # fmt: skip
    finally:
        tmp_path.unlink(missing_ok=True)
        try:
            upload_dir.rmdir()
        except OSError:
            pass
        cleanup_tmp(out_dir)
