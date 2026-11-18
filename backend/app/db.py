"""SQLite engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  (importing registers the tables)
from app.config import load_settings

_engine: Engine | None = None


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
    SQLModel.metadata.create_all(_engine)
    return _engine


def get_engine() -> Engine:
    return _engine if _engine is not None else init_db()


@contextmanager
def get_session() -> Iterator[Session]:
    """Session whose objects stay readable after commit (expire_on_commit=False)."""
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
