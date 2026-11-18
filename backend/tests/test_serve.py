"""`serve`: reuse a running Spoteye, otherwise the first free port; and the packaged entry point."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from app.commands import app, serve
from spoteye_main import default_args


@pytest.fixture
def busy_port() -> Iterator[int]:
    """A port on 127.0.0.1 held by another program (bound, not answering HTTP)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        yield sock.getsockname()[1]


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    urls: list[str] = []
    monkeypatch.setattr(serve.webbrowser, "open", urls.append)
    return urls


def test_free_port_skips_a_busy_port(busy_port: int) -> None:
    assert not serve.port_is_free(busy_port)
    chosen = serve.free_port(busy_port)
    assert chosen is not None and busy_port < chosen <= busy_port + serve.PORT_TRIES


def test_serve_falls_back_to_the_next_free_port(busy_port: int, opened: list[str],
                                                monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    started: dict[str, Any] = {}
    monkeypatch.setattr(serve.uvicorn, "run", lambda api, **kw: started.update(kw, api=api))
    result = CliRunner().invoke(app, ["serve", "--port", str(busy_port), "--no-browser"])
    assert result.exit_code == 0, result.output
    assert busy_port < started["port"] <= busy_port + serve.PORT_TRIES
    assert started["host"] == "127.0.0.1" and not isinstance(started["api"], str)


def test_serve_exits_when_spoteye_already_runs(opened: list[str],
                                               monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    def fake_get(url: str, timeout: float) -> httpx.Response:
        assert url == "http://127.0.0.1:8000/api/ping" and timeout == 1.0
        return httpx.Response(200, json={"app": "spoteye"})

    monkeypatch.setattr(serve.httpx, "get", fake_get)
    monkeypatch.setattr(serve.uvicorn, "run", lambda *_a, **_k: pytest.fail("second server started"))
    result = CliRunner().invoke(app, ["serve"])
    assert result.exit_code == 0
    assert "Spoteye is already running" in result.output
    assert opened == ["http://127.0.0.1:8000"]


def test_other_app_on_the_port_is_not_spoteye(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(serve.httpx, "get", lambda *_a, **_k: httpx.Response(200, json={"ok": 1}))
    assert not serve.is_spoteye(8000)


def test_no_arguments_means_serve() -> None:
    assert default_args(["Spoteye.exe"]) == ["Spoteye.exe", "serve"]
    assert default_args(["Spoteye.exe", "login"]) == ["Spoteye.exe", "login"]
