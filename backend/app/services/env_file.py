"""Rewrite keys in a .env file atomically, keeping other keys, comments and blank lines."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

KEY_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
PLAIN_VALUE = re.compile(r"^[^\s#'\"]*(?:[^\S\r\n]+[^\s#'\"]+)*$")  # no quotes, '#' or edge spaces


def quote(value: str) -> str:
    """A value python-dotenv reads back unchanged (Windows backslashes stay literal)."""
    if "\n" in value or "\r" in value:
        raise ValueError("Settings can't contain line breaks.")
    if PLAIN_VALUE.match(value):
        return value
    if "'" not in value:
        return f"'{value}'"  # single quotes: no escape sequences
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def update_env_file(path: Path, values: Mapping[str, str]) -> None:
    """Set each key in `values` (replacing its line, or appending it) and keep everything else."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        lines = []
    pending = dict(values)
    out: list[str] = []
    for line in lines:
        match = KEY_LINE.match(line)
        key = match.group(1) if match else None
        if key in values:
            if key in pending:  # first occurrence wins; later duplicates are dropped
                out.append(f"{key}={quote(pending.pop(key))}")
            continue
        out.append(line)
    out.extend(f"{key}={quote(value)}" for key, value in pending.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".env.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(out) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
