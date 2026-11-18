"""Wait for Spotify's sign-in redirect on 127.0.0.1, with a timeout and a cancel switch.

spotipy's own local-server sign-in waits forever and never closes the server, so a sign-in page
left unfinished would hold the redirect port and block every later sign-in.
"""

from __future__ import annotations

import logging
import threading
import time
import webbrowser
from urllib.parse import urlparse

from spotipy.oauth2 import SpotifyOauthError, SpotifyPKCE, start_local_http_server

LOGIN_TIMEOUT_S: float = 300  # an unfinished sign-in page gives up after 5 minutes
POLL_S: float = 0.5  # how often the wait checks the cancel Event
TIMEOUT_MSG: str = ("Spotify sign-in timed out: the sign-in page wasn't finished within "
                    "5 minutes. Try again.")  # fmt: skip
LOCAL_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost"})
log = logging.getLogger(__name__)


class LoginCancelled(Exception):
    """The sign-in was cancelled (not a SpotifyOauthError: a cancel is not a failure)."""


def local_port(redirect_uri: str) -> int | None:
    """Port to listen on for http://127.0.0.1:PORT/... (or localhost), else None."""
    url = urlparse(redirect_uri)
    try:
        port = url.port
    except ValueError:
        return None
    return port if url.scheme == "http" and url.hostname in LOCAL_HOSTS else None


def wait_for_code(auth: SpotifyPKCE, port: int, timeout_s: float,
                  cancel: threading.Event | None = None) -> str:  # fmt: skip
    """Like spotipy's local-server sign-in, but with a timeout, a cancel Event (checked every
    0.5 s; raises LoginCancelled) and the port always freed. Stray requests are ignored."""
    try:
        server = start_local_http_server(port)
    except OSError as exc:
        raise SpotifyOauthError(f"Port {port} is in use, so Spotify can't send the sign-in "
                                "back. Close the other program and try again.") from exc  # fmt: skip
    try:
        server.timeout = POLL_S
        url = auth.get_authorize_url()
        if not webbrowser.open(url):
            log.warning("Open this page to sign in to Spotify: %s", url)
        deadline = time.monotonic() + timeout_s
        while server.auth_code is None and server.error is None and time.monotonic() < deadline:
            if cancel is not None and cancel.is_set():
                raise LoginCancelled("Sign-in cancelled.")
            server.handle_request()  # one request, or returns after POLL_S
    finally:
        server.server_close()
    if server.auth_code:
        return str(server.auth_code)
    if server.error is not None:
        raise SpotifyOauthError(f"Spotify refused the sign-in: {server.error}")
    raise SpotifyOauthError(TIMEOUT_MSG)
