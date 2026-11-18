"""Application settings loaded from backend/.env via python-dotenv."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
ENV_PATH: Path = BACKEND_DIR / ".env"
CACHE_PATH: Path = BACKEND_DIR / ".cache"
FRONTEND_DIST: Path = BACKEND_DIR.parent / "frontend" / "dist"

DEFAULT_REDIRECT_URI: str = "http://127.0.0.1:8765/callback"
DEFAULT_OUTPUT_DIR: str = r"D:\Music\Spoteye"
DEFAULT_DB_PATH: Path = BACKEND_DIR / "spoteye.db"
DEFAULT_MAX_WORKERS: int = 3


@dataclass(frozen=True)
class Settings:
    spotify_client_id: str
    spotify_redirect_uri: str
    output_dir: Path
    cookies_file: Path | None
    db_path: Path = DEFAULT_DB_PATH
    max_workers: int = DEFAULT_MAX_WORKERS


def _optional_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value.strip())


def _db_path(value: str | None) -> Path:
    """DB_PATH from the env; relative paths are resolved against backend/."""
    path = _optional_path(value) or DEFAULT_DB_PATH
    return path if path.is_absolute() else BACKEND_DIR / path


def _positive_int(value: str | None, default: int) -> int:
    try:
        number = int((value or "").strip())
    except ValueError:
        return default
    return number if number > 0 else default


def load_settings(env_path: Path = ENV_PATH) -> Settings:
    """Load settings from the .env file (if present) and the process environment."""
    load_dotenv(env_path)
    return Settings(
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", "").strip(),
        spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "").strip()
        or DEFAULT_REDIRECT_URI,
        output_dir=Path(os.getenv("OUTPUT_DIR", "").strip() or DEFAULT_OUTPUT_DIR),
        cookies_file=_optional_path(os.getenv("COOKIES_FILE")),
        db_path=_db_path(os.getenv("DB_PATH")),
        max_workers=_positive_int(os.getenv("MAX_WORKERS"), DEFAULT_MAX_WORKERS),
    )
