"""Settings page, Spotify sign-in from the UI, and updating the bundled yt-dlp.

Writes (PUT/POST) are covered by the Origin/Host guard in main.py like every other /api route.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import col, select

from app import config
from app.config import load_settings
from app.db import get_session
from app.models import Job
from app.services import ytdlp_bin
from app.services.env_file import update_env_file
from app.web.login_task import LoginTask
from app.web.settings_form import SettingsIn, SettingsOut, settings_out

router = APIRouter(prefix="/api")
BUSY_STATUSES: tuple[str, ...] = ("queued", "running")


class LoginStatus(BaseModel):
    running: bool
    last_error: str | None


class UpdateOut(BaseModel):
    output: str


def login_task(request: Request) -> LoginTask:
    task: LoginTask = request.app.state.login_task
    return task


@router.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return settings_out(load_settings())


@router.put("/settings", response_model=SettingsOut)
def put_settings(body: SettingsIn) -> SettingsOut:
    """422 per field if invalid (see SettingsIn); applies at once (load_settings re-reads .env)."""
    update_env_file(config.ENV_PATH, body.env_values())
    return settings_out(load_settings())


@router.post("/auth/login", status_code=202, response_model=LoginStatus)
def start_login(request: Request) -> LoginStatus:
    """Open Spotify's sign-in page in the browser; poll GET /api/auth/status for the result.

    A pending sign-in is cancelled and replaced (409 only if it doesn't stop within 3 s).
    """
    settings = load_settings()
    if not settings.spotify_client_id:
        raise HTTPException(status_code=400, detail="Set a Spotify Client ID in Settings first.")
    if not login_task(request).start(settings):
        raise HTTPException(status_code=409, detail="Previous sign-in is still closing, "
                                                    "try again in a few seconds.")  # fmt: skip
    return LoginStatus(running=True, last_error=None)


@router.post("/auth/cancel", status_code=204, response_class=Response)
def cancel_login(request: Request) -> Response:
    """Stop waiting for Spotify's approval (no-op if no sign-in is running)."""
    login_task(request).cancel()
    return Response(status_code=204)


@router.get("/auth/status", response_model=LoginStatus)
def login_status(request: Request) -> LoginStatus:
    running, last_error = login_task(request).status()
    return LoginStatus(running=running, last_error=last_error)


@router.post("/tools/update-ytdlp", response_model=UpdateOut)
def update_ytdlp() -> UpdateOut:
    """Run yt-dlp -U. Not while a job is queued or running (the program would be in use)."""
    if ytdlp_bin.find() is None:
        raise HTTPException(status_code=400, detail="yt-dlp runs as a library here: "
                                                    "pip install -U yt-dlp")  # fmt: skip
    with get_session() as session:
        busy = session.exec(select(Job.id).where(col(Job.status).in_(BUSY_STATUSES))).first()
    if busy is not None:
        raise HTTPException(status_code=409, detail="Wait until no job is queued or running.")
    try:
        return UpdateOut(output=ytdlp_bin.update())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
