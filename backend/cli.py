"""Spoteye command-line entry point. Commands live in app/commands/."""

from __future__ import annotations

from app.commands import app
from app.db import init_db

if __name__ == "__main__":
    init_db()
    app()
