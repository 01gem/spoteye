"""SQLite engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  (importing registers the tables)
from app.config import load_settings

_engine: Engine | None = None


def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
    """WAL + busy timeout: the API's worker thread and request threads share the database."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def init_db(db_path: Path | None = None) -> Engine:
    """Create (or open) the SQLite database and make sure all tables exist."""
    global _engine
    path = db_path or load_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(
        f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False}
    )
    event.listen(_engine, "connect", _sqlite_pragmas)
    SQLModel.metadata.create_all(_engine)
    return _engine


def get_engine() -> Engine:
    return _engine if _engine is not None else init_db()


@contextmanager
def get_session() -> Iterator[Session]:
    """Session whose objects stay readable after commit (expire_on_commit=False)."""
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
