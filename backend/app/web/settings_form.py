"""Settings page models: what GET /api/settings shows and what PUT may change (checked per field)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

from app import config
from app.config import Settings

CLIENT_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_WORKERS_RANGE: tuple[int, int] = (1, 8)
RETRY_DAYS_RANGE: tuple[int, int] = (1, 365)


def invalid(message: str) -> PydanticCustomError:
    """A 422 field error whose msg is exactly `message` (no "Value error, " prefix)."""
    return PydanticCustomError("invalid_setting", message)


class SettingsOut(BaseModel):
    spotify_client_id: str
    output_dir: str
    cookies_file: str | None
    max_workers: int
    match_retry_days: int
    app_home: str
    frozen: bool


def _in_range(name: str, value: int, bounds: tuple[int, int]) -> int:
    low, high = bounds
    if not low <= value <= high:
        raise invalid(f"{name} must be between {low} and {high}.")
    return value


def _writable_dir(value: str) -> str:
    """Create the folder if needed and prove a file can be written there."""
    path = Path(value)
    if not path.is_absolute():
        raise invalid(r"Use a full folder path, like D:\Music\Spoteye.")
    probe = path / f".spoteye-write-test-{uuid.uuid4().hex}"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as exc:
        raise invalid(f"Can't write to this folder: {exc.strerror or exc}") from exc
    return value


class SettingsIn(BaseModel):
    """PUT body: every editable field (the client sends the whole form)."""

    spotify_client_id: str
    output_dir: str
    cookies_file: str | None = None
    max_workers: int
    match_retry_days: int

    @field_validator("spotify_client_id", "output_dir", "cookies_file", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("spotify_client_id")
    @classmethod
    def _client_id(cls, value: str) -> str:
        if value and not CLIENT_ID.match(value):
            raise invalid("A Client ID is 32 characters, 0-9 and a-f (copy it from the "
                             "Spotify developer dashboard).")  # fmt: skip
        return value

    @field_validator("output_dir")
    @classmethod
    def _output_dir(cls, value: str) -> str:
        if not value:
            raise invalid("Choose a folder for the music.")
        return _writable_dir(value)

    @field_validator("cookies_file")
    @classmethod
    def _cookies_file(cls, value: str | None) -> str | None:
        if value and not Path(value).is_file():
            raise invalid("No file at this path.")
        return value or None

    @field_validator("max_workers")
    @classmethod
    def _max_workers(cls, value: int) -> int:
        return _in_range("Parallel downloads", value, MAX_WORKERS_RANGE)

    @field_validator("match_retry_days")
    @classmethod
    def _retry_days(cls, value: int) -> int:
        return _in_range("Retry days", value, RETRY_DAYS_RANGE)

    def env_values(self) -> dict[str, str]:
        """The .env lines to write. A Client ID equal to the bundled default stays unset."""
        client_id = "" if self.spotify_client_id == config.bundled_client_id() else self.spotify_client_id
        return {
            "SPOTIFY_CLIENT_ID": client_id,
            "OUTPUT_DIR": self.output_dir,
            "COOKIES_FILE": self.cookies_file or "",
            "MAX_WORKERS": str(self.max_workers),
            "MATCH_RETRY_DAYS": str(self.match_retry_days),
        }


def settings_out(settings: Settings) -> SettingsOut:
    return SettingsOut(
        spotify_client_id=settings.spotify_client_id,
        output_dir=str(settings.output_dir),
        cookies_file=str(settings.cookies_file) if settings.cookies_file else None,
        max_workers=settings.max_workers,
        match_retry_days=settings.match_retry_days,
        app_home=str(config.APP_HOME),
        frozen=config.IS_FROZEN,
    )
