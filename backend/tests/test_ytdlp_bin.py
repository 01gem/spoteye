"""yt-dlp as a separate program: finding it, downloading through it, version and update."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app import config
from app.services import downloader, ytdlp_bin
from app.services.downloader import DownloadError, download_audio
from app.services.errors import BOT_CHECK, friendly_error

EXE = Path("C:/Spoteye/bin/yt-dlp.exe")


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], dict[str, Any]]]:
    seen: list[tuple[list[str], dict[str, Any]]] = []
    monkeypatch.setenv("YTDLP_PATH", str(EXE))
    monkeypatch.setattr(ytdlp_bin, "_version_cache", None)
    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", lambda *_a: pytest.fail("library mode used"))
    return seen


def fake_run(calls: list[Any], returncode: int, stdout: str = "", stderr: str = "",
             write: Path | None = None) -> Any:  # fmt: skip
    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        if write is not None:
            write.write_bytes(b"audio")
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


def test_binary_download_parses_the_printed_json(tmp_path: Path, calls: list[Any],
                                                 monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    out = tmp_path / "abc.webm"
    line = json.dumps({"filepath": str(out), "format_id": "251", "acodec": "opus", "abr": 130.5,
                       "ext": "webm"})  # fmt: skip
    monkeypatch.setattr(subprocess, "run", fake_run(calls, 0, f"[info] noise\n{line}\n", write=out))
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("", encoding="utf-8")
    audio = download_audio("abc", tmp_path, "251/bestaudio", str(cookies))
    assert (audio.path, audio.format_id, audio.acodec, audio.abr, audio.ext) == (
        out, "251", "opus", 130.5, "webm")  # fmt: skip
    args, kwargs = calls[0]
    assert args[0] == str(EXE) and args[-1] == "https://music.youtube.com/watch?v=abc"
    assert args[args.index("-f") + 1] == "251/bestaudio"
    assert args[args.index("--cookies") + 1] == str(cookies)
    assert args[args.index("--print") + 1] == downloader.AFTER_MOVE_PRINT
    assert kwargs["timeout"] == 600 and kwargs.get("shell") is not True
    assert kwargs["creationflags"] == ytdlp_bin.NO_WINDOW


def test_binary_failure_keeps_stderr_tail_for_friendly_error(tmp_path: Path, calls: list[Any],
                                                             monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    stderr = "\n".join(f"line {i}" for i in range(30)) + "\nERROR: Sign in to confirm you're not a bot"
    monkeypatch.setattr(subprocess, "run", fake_run(calls, 1, stderr=stderr))
    with pytest.raises(DownloadError) as caught:
        download_audio("abc", tmp_path, "bestaudio", None)
    message = str(caught.value)
    assert "line 10" not in message and "line 11" in message  # last 20 lines only
    assert friendly_error(message) == BOT_CHECK
    assert "--cookies" not in calls[0][0]


def test_binary_without_json_line_is_a_download_error(tmp_path: Path, calls: list[Any],
                                                      monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(subprocess, "run", fake_run(calls, 0, "[info] nothing useful\n"))
    with pytest.raises(DownloadError, match="no file info"):
        download_audio("abc", tmp_path, "bestaudio", None)


def test_binary_timeout_is_a_network_error(tmp_path: Path, calls: list[Any],
                                           monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    def run(args: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(DownloadError, match="timed out"):
        download_audio("abc", tmp_path, "bestaudio", None)


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
