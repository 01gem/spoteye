"""Spotify sign-in started from the UI: one background thread at a time.

spotify_auth.login opens the browser and waits for Spotify's redirect on the redirect URI port,
so it can't run inside a request.
"""

from __future__ import annotations

import logging
import threading

from app.config import Settings
from app.services import spotify_auth

log = logging.getLogger(__name__)


class LoginTask:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running = False
        self.last_error: str | None = None

    def start(self, settings: Settings) -> bool:
        """Start a sign-in thread; False if one is already running."""
        with self._lock:
            if self.running:
                return False
            self.running, self.last_error = True, None
        threading.Thread(target=self._run, args=(settings,), name="spoteye-login", daemon=True).start()
        return True

    def _run(self, settings: Settings) -> None:
        error: str | None = None
        try:
            spotify_auth.login(settings)
            spotify_auth.clear_status_cache()
        except Exception as exc:
            log.warning("Spotify sign-in failed (%s): %s", type(exc).__name__, exc)
            error = str(exc) or type(exc).__name__
        with self._lock:
            self.running, self.last_error = False, error

    def status(self) -> tuple[bool, str | None]:
        with self._lock:
            return self.running, self.last_error
