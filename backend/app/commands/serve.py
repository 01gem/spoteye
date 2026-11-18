"""`serve`: run the API and the built web UI on http://127.0.0.1:PORT."""

from __future__ import annotations

import threading
import webbrowser

import typer
import uvicorn

from app.commands import app, console
from app.config import FRONTEND_DIST

BROWSER_DELAY_S: float = 1.5


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Port on 127.0.0.1."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a browser tab."),
) -> None:
    """Start the web UI and API (localhost only). Ctrl+C to quit."""
    if not (FRONTEND_DIST / "index.html").is_file():
        console.print("[yellow]UI not built: cd ..\\frontend; npm run build "
                      "(the API still works at /docs)[/yellow]")  # fmt: skip
    url = f"http://127.0.0.1:{port}"
    if not no_browser:
        threading.Timer(BROWSER_DELAY_S, webbrowser.open, args=(url,)).start()
    console.print(f"Spoteye on [bold]{url}[/bold]  (API docs: {url}/docs)")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
