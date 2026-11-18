"""`serve`: run the API and the built web UI on http://127.0.0.1:PORT."""

from __future__ import annotations

import socket
import threading
import webbrowser

import httpx
import typer
import uvicorn

from app.commands import app, console, fail
from app.config import FRONTEND_DIST

HOST: str = "127.0.0.1"
BROWSER_DELAY_S: float = 1.5
PROBE_TIMEOUT_S: float = 1.0
PORT_TRIES: int = 10  # port, then port+1 .. port+10


def is_spoteye(port: int) -> bool:
    """True if a Spoteye server already answers /api/health on this port."""
    try:
        res = httpx.get(f"http://{HOST}:{port}/api/health", timeout=PROBE_TIMEOUT_S)
        return res.status_code == 200 and res.json().get("app") == "spoteye"
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def free_port(start: int) -> int | None:
    """The first free port of start .. start+PORT_TRIES (at most 65535), or None."""
    return next((p for p in range(start, min(start + PORT_TRIES, 65535) + 1) if port_is_free(p)), None)


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Port on 127.0.0.1."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a browser tab."),
) -> None:
    """Start the web UI and API (localhost only). Ctrl+C to quit."""
    if is_spoteye(port):
        url = f"http://{HOST}:{port}"
        console.print(f"Spoteye is already running: {url}")
        if not no_browser:
            webbrowser.open(url)
        raise typer.Exit(code=0)
    chosen = free_port(port)
    if chosen is None:
        raise fail(f"Ports {port}-{port + PORT_TRIES} are all in use. Try --port <another number>.")
    if chosen != port:
        console.print(f"[yellow]Port {port} is used by another program; using {chosen}.[/yellow]")
    if not (FRONTEND_DIST / "index.html").is_file():
        console.print("[yellow]UI not built: cd ..\\frontend; npm run build "
                      "(the API still works at /docs)[/yellow]")  # fmt: skip
    url = f"http://{HOST}:{chosen}"
    if not no_browser:
        threading.Timer(BROWSER_DELAY_S, webbrowser.open, args=(url,)).start()
    console.print(f"Spoteye on [bold]{url}[/bold]  (API docs: {url}/docs)")
    from app.main import app as api  # here, not at the top: other commands don't load the API

    uvicorn.run(api, host=HOST, port=chosen)
