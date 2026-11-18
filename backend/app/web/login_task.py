"""Spotify sign-in started from the UI: one background attempt at a time.

spotify_auth.login opens the browser and waits for Spotify's redirect on the redirect URI port,
so it can't run inside a request. Starting again cancels a pending attempt first; a cancel is
never reported as an error.
"""

from __future__ import annotations

import logging
import threading

from app.config import Settings
from app.services import spotify_auth
from app.services.spotify_login import LoginCancelled

log = logging.getLogger(__name__)
JOIN_S: float = 3.0  # how long to wait for a cancelled attempt to release the port


class LoginTask:
    def __init__(self) -> None:
        self._lock = threading.Lock()  # guards the fields below; never held while joining
        self._start_lock = threading.Lock()  # one start at a time
        self._current: threading.Event | None = None  # cancel Event of the running attempt
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    def start(self, settings: Settings) -> bool:
        """Cancel a pending attempt, then start a new one. False if the old one is still
        running after JOIN_S."""
        with self._start_lock:
            if not self.cancel():
                return False
            cancel = threading.Event()
            thread = threading.Thread(target=self._run, args=(settings, cancel),
                                      name="spoteye-login", daemon=True)  # fmt: skip
            with self._lock:
                self._current, self._thread, self.last_error = cancel, thread, None
            thread.start()
            return True

    def cancel(self, wait_s: float | None = None) -> bool:
        """Stop the running attempt (no-op if none). True once it has ended."""
        with self._lock:
            current, thread = self._current, self._thread
        if current is None or thread is None:
            return True
        current.set()
        thread.join(JOIN_S if wait_s is None else wait_s)
        if thread.is_alive():
            return False
        with self._lock:
            if self._current is current:
                self._current, self.last_error = None, None
        return True

    def _run(self, settings: Settings, cancel: threading.Event) -> None:
        error: str | None = None
        try:
            spotify_auth.login(settings, cancel=cancel)
            spotify_auth.clear_status_cache()
        except LoginCancelled:
            pass
        except Exception as exc:
            log.warning("Spotify sign-in failed (%s): %s", type(exc).__name__, exc)
            error = str(exc) or type(exc).__name__
        with self._lock:
            if self._current is cancel:  # a replaced attempt must not overwrite the new one
                self._current, self.last_error = None, error

    def status(self) -> tuple[bool, str | None]:
        with self._lock:
            return self._current is not None, self.last_error
