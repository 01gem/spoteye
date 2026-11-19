"""yt-dlp as a separate program: finding it, version and update (downloading: test_ytdlp_exe)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from app import config
from app.services import downloader, ytdlp_bin

EXE = Path("C:/Spoteye/bin/yt-dlp.exe")


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], dict[str, Any]]]:
    seen: list[tuple[list[str], dict[str, Any]]] = []
    monkeypatch.setenv("YTDLP_PATH", str(EXE))
    monkeypatch.setattr(ytdlp_bin, "_version_cache", None)
    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", lambda *_a: pytest.fail("library mode used"))
    return seen


def fake_run(calls: list[Any], returncode: int, stdout: str = "", stderr: str = "") -> Any:
    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)

    return run


def test_find_prefers_ytdlp_path_then_bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    assert ytdlp_bin.find() is None and ytdlp_bin.mode() == "library"
    (tmp_path / "yt-dlp.exe").write_bytes(b"")
    monkeypatch.setattr(config, "BIN_DIR", tmp_path)
    assert ytdlp_bin.find() == tmp_path / "yt-dlp.exe" and ytdlp_bin.mode() == "binary"
    monkeypatch.setenv("YTDLP_PATH", "D:/tools/yt-dlp.exe")
    assert ytdlp_bin.find() == Path("D:/tools/yt-dlp.exe")


def test_version_is_cached(calls: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", fake_run(calls, 0, "2026.11.01\n"))
    assert ytdlp_bin.version() == ytdlp_bin.version() == "2026.11.01"
    assert len(calls) == 1 and calls[0][0] == [str(EXE), "--version"]


def test_library_version_and_update_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    assert ytdlp_bin.version() == ytdlp_bin.LIBRARY_VERSION
    with pytest.raises(RuntimeError):
        ytdlp_bin.update()


def test_update_returns_combined_output(calls: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", fake_run(calls, 0, "Updating to 2026.11.10\n", "warn\n"))
    assert ytdlp_bin.update() == "Updating to 2026.11.10\nwarn"
    assert calls[0][0] == [str(EXE), "-U"] and calls[0][1]["timeout"] == 120
