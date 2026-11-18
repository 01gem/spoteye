"""Entry point of the packaged app (PyInstaller). From source, cli.py stays the entry point.

Double-clicking Spoteye.exe passes no arguments, which runs `serve`.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from app import config

LOG_BYTES: int = 1_000_000
LOG_BACKUPS: int = 3
CONSOLE_TITLE: str = "Spoteye - close this window to quit"


def setup_frozen() -> None:
    """Find the bundled programs first, log to APP_HOME/logs and name the console window."""
    if config.BIN_DIR is not None:
        os.environ["PATH"] = f"{config.BIN_DIR}{os.pathsep}{os.environ.get('PATH', '')}"
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(config.LOG_DIR / "spoteye.log", maxBytes=LOG_BYTES,
                                       backupCount=LOG_BACKUPS, encoding="utf-8")  # fmt: skip
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, logging.StreamHandler()],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")  # fmt: skip
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(CONSOLE_TITLE)


def default_args(argv: list[str]) -> list[str]:
    """No arguments (double-click) means `serve`."""
    return argv if len(argv) > 1 else [*argv, "serve"]


def main() -> None:
    if config.IS_FROZEN:
        setup_frozen()
    sys.argv = default_args(sys.argv)
    from app.commands import app  # after logging is set up
    from app.db import init_db

    init_db()
    app()


if __name__ == "__main__":
    main()
