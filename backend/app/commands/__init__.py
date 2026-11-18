"""Shared Typer app and console; each command module registers itself on import."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import track

from app.services.hints import CLI

app = typer.Typer(help="Spoteye: Spotify metadata tools.", no_args_is_help=True)
console = Console()

RECORD_STYLE: dict[str, str] = {
    "pending": "dim",
    "done": "green",
    "skipped": "cyan",
    "manual": "magenta",
    "not_found": "red",
    "review_skipped": "yellow",
    "failed": "bold red",
    "running": "blue",
    "stopped": "yellow",
}


def styled(status: str) -> str:
    style = RECORD_STYLE.get(status, "white")
    return f"[{style}]{escape(status)}[/{style}]"


def rich_progress(items: Iterable[Any], description: str, total: int) -> Iterable[Any]:
    """Progress bar for job_runner (it passes total because results arrive as a generator)."""
    return track(items, description=description, total=total, console=console)


def fail(message: str) -> typer.Exit:
    """Print an error and return an Exit to raise."""
    console.print(f"[red]{escape(message)}[/red]")
    return typer.Exit(code=1)


def stopped_exit(job_id: int) -> typer.Exit:
    """Ctrl+C during a job: say how to continue and return an Exit (130 = interrupted)."""
    console.print(f"[yellow]Stopped.[/yellow] Job {job_id} saved; continue with: "
                  f"{CLI} resume {job_id}")  # fmt: skip
    return typer.Exit(code=130)


@app.callback()
def main() -> None:
    """Spoteye CLI."""


# Import order = order in --help. Must come after `app` exists.
from app.commands import info, login, match, download, jobs, attach, serve  # noqa: E402,F401,I001
