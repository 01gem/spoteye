"""Sign-in from the browser with a timeout and cancel (no network: the token exchange is faked)."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from spotipy.oauth2 import SpotifyOauthError, SpotifyPKCE
from typer.testing import CliRunner

from app.commands import app
from app.config import Settings
from app.services import spotify_auth, spotify_login
from app.services.spotify_login import LoginCancelled


@pytest.fixture
def port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def exchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Any]]:
    """Codes passed to the token exchange; cache files go to tmp_path."""
    codes: list[Any] = []
    monkeypatch.setattr(spotify_auth, "CACHE_PATH", tmp_path / ".cache")
    monkeypatch.setattr(spotify_auth, "SIGN_IN_META", tmp_path / ".cache-meta.json")
    monkeypatch.setattr(SpotifyPKCE, "get_access_token",
                        lambda self, code=None, check_cache=True: codes.append(code))  # fmt: skip
    yield codes


def settings(port: int) -> Settings:
    return Settings("client", f"http://127.0.0.1:{port}/callback", Path("out"), None)


def browser_visits(monkeypatch: pytest.MonkeyPatch, port: int, query: str) -> None:
    """The fake browser follows Spotify's redirect back to the waiting server."""
    def visit(_url: str) -> bool:
        get = lambda: httpx.get(f"http://127.0.0.1:{port}/callback?{query}", timeout=5)  # noqa: E731
        threading.Thread(target=get, daemon=True).start()
        return True

    monkeypatch.setattr(spotify_login.webbrowser, "open", visit)


def test_unfinished_sign_in_times_out_and_frees_the_port(port: int, exchanged: list[Any],
                                                         monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(spotify_login.webbrowser, "open", lambda _url: True)
    with pytest.raises(SpotifyOauthError, match="timed out"):
        spotify_auth.login(settings(port), timeout_s=0.2)
    assert exchanged == []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))  # would raise if the server still held the port


def test_redirect_code_is_exchanged(port: int, exchanged: list[Any],
                                    monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    browser_visits(monkeypatch, port, "code=abc")
    spotify_auth.login(settings(port), timeout_s=5)
    assert exchanged == ["abc"]
    assert spotify_auth.signed_in_at() is not None


def test_refused_sign_in_reports_spotify_error(port: int, exchanged: list[Any],
                                               monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    browser_visits(monkeypatch, port, "error=access_denied")
    with pytest.raises(SpotifyOauthError, match="Spotify refused the sign-in"):
        spotify_auth.login(settings(port), timeout_s=5)
    assert exchanged == []


def test_busy_port_is_reported_without_opening_a_browser(port: int, exchanged: list[Any],
                                                         monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(spotify_login.webbrowser, "open", lambda _url: pytest.fail("opened"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
        sock.listen()
        with pytest.raises(SpotifyOauthError, match="in use"):
            spotify_auth.login(settings(port), timeout_s=5)


@pytest.mark.parametrize(("uri", "expected"), [
    ("http://127.0.0.1:8765/callback", 8765),
    ("http://localhost:9000/cb", 9000),
    ("http://127.0.0.1/callback", None),
    ("https://127.0.0.1:8765/callback", None),
    ("http://example.com:8765/callback", None),
])  # fmt: skip
def test_local_port(uri: str, expected: int | None) -> None:
    assert spotify_login.local_port(uri) == expected


def test_cancel_frees_the_port_within_a_second(port: int, exchanged: list[Any],
                                               monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(spotify_login.webbrowser, "open", lambda _url: True)
    cancel, raised = threading.Event(), []

    def run() -> None:
        try:
            spotify_auth.login(settings(port), cancel=cancel, timeout_s=30)
        except LoginCancelled as exc:
            raised.append(str(exc))

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.3)  # let it start listening
    started = time.monotonic()
    cancel.set()
    worker.join(1)
    assert not worker.is_alive() and time.monotonic() - started < 1
    assert raised == ["Sign-in cancelled."] and exchanged == []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def test_cli_login_ctrl_c_exits_130(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted(settings: Settings, cancel: threading.Event | None = None) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(spotify_auth, "login", interrupted)
    result = CliRunner().invoke(app, ["login"])
    assert result.exit_code == 130
    assert "Sign-in cancelled." in result.output
