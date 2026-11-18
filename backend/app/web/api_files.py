"""Open a job's folder, or reveal one track's file, in Windows File Explorer.

The client only ever sends job and record ids; paths come from the database.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.concurrency import run_in_threadpool

from app.db import get_session
from app.models import TrackRecord
from app.web.api_jobs import get_job_or_404

router = APIRouter(prefix="/api")
NOT_WINDOWS_MSG = "Opening folders is only supported on Windows."


def is_windows() -> bool:
    """Module-level so tests can force either answer."""
    return os.name == "nt"


def _require_windows() -> None:
    if not is_windows():
        raise HTTPException(status_code=501, detail=NOT_WINDOWS_MSG)


def _job_folder(job_id: int) -> Path:
    with get_session() as session:
        return Path(get_job_or_404(session, job_id).out_dir)


def _track_file(job_id: int, record_id: int) -> Path:
    """The record's file, resolved and guaranteed to sit inside the resolved job folder."""
    with get_session() as session:
        folder = Path(get_job_or_404(session, job_id).out_dir).resolve()
        record = session.get(TrackRecord, record_id)
        if record is None or record.job_id != job_id:
            raise HTTPException(status_code=404, detail=f"Track {record_id} not found in job {job_id}.")
        if not record.file_name:
            raise HTTPException(status_code=404, detail="This track has no file yet.")
        file = (folder / record.file_name).resolve()
    if not file.is_relative_to(folder):
        raise HTTPException(status_code=400, detail="The file is outside the job folder.")
    if not file.is_file():
        raise HTTPException(status_code=404, detail=f"The file doesn't exist: {file}")
    return file


@router.post("/jobs/{job_id}/open-folder", status_code=204, response_class=Response)
async def open_folder(job_id: int) -> Response:
    folder = await run_in_threadpool(_job_folder, job_id)
    _require_windows()
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail=f"The folder doesn't exist yet: {folder}")
    os.startfile(str(folder))  # type: ignore[attr-defined,unused-ignore]  # Windows-only
    return Response(status_code=204)


@router.post("/jobs/{job_id}/tracks/{record_id}/reveal", status_code=204, response_class=Response)
async def reveal(job_id: int, record_id: int) -> Response:
    _require_windows()
    file = await run_in_threadpool(_track_file, job_id, record_id)
    # No check=True / no wait: explorer.exe exits with code 1 even when it worked.
    subprocess.Popen(["explorer", f"/select,{file}"])
    return Response(status_code=204)
