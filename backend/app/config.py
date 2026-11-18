"""Paths and settings. From source everything stays in backend/; the packaged app (PyInstaller)
keeps its data in %LOCALAPPDATA%\\Spoteye. SPOTEYE_HOME overrides both."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR: Path = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """True inside a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def resolve_app_home() -> Path:
    """Where .env, the Spotify sign-in, the database and logs live."""
    if home := os.environ.get("SPOTEYE_HOME", "").strip():
        return Path(home)
    if is_frozen():
        return Path(os.environ["LOCALAPPDATA"]) / "Spoteye"
    return BACKEND_DIR


def resolve_bundle_dir() -> Path:
    """Read-only files shipped with the app (PyInstaller unpacks them to sys._MEIPASS)."""
    return Path(getattr(sys, "_MEIPASS")) if is_frozen() else BACKEND_DIR.parent


IS_FROZEN: bool = is_frozen()
APP_HOME: Path = resolve_app_home()
APP_HOME.mkdir(parents=True, exist_ok=True)
BUNDLE_DIR: Path = resolve_bundle_dir()
ENV_PATH: Path = APP_HOME / ".env"
CACHE_PATH: Path = APP_HOME / ".cache"
SIGN_IN_META_PATH: Path = APP_HOME / ".cache-meta.json"  # {"signed_in_at": ISO UTC}
LOG_DIR: Path = APP_HOME / "logs"
FRONTEND_DIST: Path = BUNDLE_DIR / "ui" if IS_FROZEN else BACKEND_DIR.parent / "frontend" / "dist"
BIN_DIR: Path | None = Path(sys.executable).parent / "bin" if IS_FROZEN else None

DEFAULT_REDIRECT_URI: str = "http://127.0.0.1:8765/callback"
DEFAULT_OUTPUT_DIR: str = str(Path.home() / "Music" / "Spoteye") if IS_FROZEN else r"D:\Music\Spoteye"
DEFAULT_DB_PATH: Path = APP_HOME / "spoteye.db"
DEFAULT_MAX_WORKERS: int = 3
DEFAULT_MATCH_RETRY_DAYS: int = 14


@dataclass(frozen=True)
class Settings:
    spotify_client_id: str
    spotify_redirect_uri: str
    output_dir: Path
    cookies_file: Path | None
    db_path: Path = DEFAULT_DB_PATH
    max_workers: int = DEFAULT_MAX_WORKERS
    match_retry_days: int = DEFAULT_MATCH_RETRY_DAYS


def bundled_client_id() -> str:
    """Packaged app only: the Client ID shipped in defaults.json, or "" if there is none."""
    if not is_frozen():
        return ""
    try:
        data = json.loads((BUNDLE_DIR / "defaults.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    value = data.get("spotify_client_id") if isinstance(data, dict) else None
    return value.strip() if isinstance(value, str) else ""


def _optional_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value.strip())


def _db_path(value: str | None) -> Path:
    """DB_PATH from the env; relative paths are resolved against APP_HOME."""
    path = _optional_path(value) or DEFAULT_DB_PATH
    return path if path.is_absolute() else APP_HOME / path


def _positive_int(value: str | None, default: int) -> int:
    try:
        number = int((value or "").strip())
    except ValueError:
        return default
    return number if number > 0 else default


def load_settings(env_path: Path | None = None) -> Settings:
    """Load settings from the .env file (if present) and the process environment.

    The file wins over the environment and is re-read on every call, so edits saved from the
    UI apply without a restart.
    """
    load_dotenv(env_path or ENV_PATH, override=True)
    return Settings(
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", "").strip() or bundled_client_id(),
        spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "").strip()
        or DEFAULT_REDIRECT_URI,
        output_dir=Path(os.getenv("OUTPUT_DIR", "").strip() or DEFAULT_OUTPUT_DIR),
        cookies_file=_optional_path(os.getenv("COOKIES_FILE")),
        db_path=_db_path(os.getenv("DB_PATH")),
        max_workers=_positive_int(os.getenv("MAX_WORKERS"), DEFAULT_MAX_WORKERS),
        match_retry_days=_positive_int(os.getenv("MATCH_RETRY_DAYS"), DEFAULT_MATCH_RETRY_DAYS),
    )
