"""Downloading through the yt-dlp program: streamed output, live progress, errors (fake Popen)."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from app.services import downloader, progress, ytdlp_bin, ytdlp_exe
from app.services.downloader import DownloadError, download_audio
from app.services.errors import BOT_CHECK, friendly_error

EXE = Path("C:/Spoteye/bin/yt-dlp.exe")
Calls = list[tuple[list[str], dict[str, Any]]]


@pytest.fixture(autouse=True)
def binary_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YTDLP_PATH", str(EXE))
    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", lambda *_a: pytest.fail("library mode used"))


def fake_popen(monkeypatch: pytest.MonkeyPatch, output: str, returncode: int = 0,
               write: Path | None = None) -> Calls:  # fmt: skip
    """subprocess.Popen that prints output (stdout + stderr merged) and exits with returncode."""
    calls: Calls = []

    class Proc:
        def __init__(self, args: list[str], **kwargs: Any) -> None:
            calls.append((args, kwargs))
            if write is not None:
                write.write_bytes(b"audio")
            self.stdout = io.StringIO(output)

        def __enter__(self) -> Proc:
            return self

        def __exit__(self, *exc: object) -> None:
            pass

        def wait(self) -> int:
            return returncode

        def kill(self) -> None:
            pass

    monkeypatch.setattr(subprocess, "Popen", Proc)
    return calls


def test_progress_lines_are_reported_and_the_json_line_is_the_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "abc.webm"
    info = json.dumps({"filepath": str(out), "format_id": "251", "acodec": "opus", "abr": 130.5,
                       "ext": "webm"})  # fmt: skip
    output = ("SPOTEYE_PROGRESS 1024 NA 4096 NA NA\n[download] a normal line\n"
              f"SPOTEYE_PROGRESS 4096 4096 NA 2048.5 0\n{info}\n")  # fmt: skip
    calls = fake_popen(monkeypatch, output, write=out)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("", encoding="utf-8")
    events: list[dict[str, Any]] = []
    token = progress.bind(9, events.append)
    try:
        audio = download_audio("abc", tmp_path, "251/bestaudio", str(cookies))
    finally:
        progress.reset(token)

    assert (audio.path, audio.format_id, audio.acodec, audio.abr, audio.ext) == (
        out, "251", "opus", 130.5, "webm")  # fmt: skip
    assert [(e["record_id"], e["phase"], e["percent"], e["downloaded_bytes"], e["total_bytes"],
             e["speed"], e["eta"]) for e in events] == [
        (9, "downloading", 25.0, 1024, 4096, None, None),  # NA total -> the estimate
        (9, "downloading", 100.0, 4096, 4096, 2048.5, 0)]  # fmt: skip
    args, kwargs = calls[0]
    assert args[0] == str(EXE) and args[-1] == "https://music.youtube.com/watch?v=abc"
    assert args[args.index("-f") + 1] == "251/bestaudio"
    assert args[args.index("--cookies") + 1] == str(cookies)
    assert args[args.index("--print") + 1] == ytdlp_exe.AFTER_MOVE_PRINT
    assert args[args.index("--progress-template") + 1] == ytdlp_exe.PROGRESS_TEMPLATE
    assert "--newline" in args and "--no-progress" not in args and "--no-simulate" in args
    assert kwargs["stdout"] == subprocess.PIPE and kwargs["stderr"] == subprocess.STDOUT
    assert kwargs["encoding"] == "utf-8" and kwargs.get("shell") is not True
    assert kwargs["creationflags"] == ytdlp_bin.NO_WINDOW


def test_failure_keeps_the_output_tail_for_friendly_error(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    lines = [f"line {i}" for i in range(50)] + ["SPOTEYE_PROGRESS 1 2 NA NA NA",
                                                "ERROR: Sign in to confirm you're not a bot"]  # fmt: skip
    calls = fake_popen(monkeypatch, "\n".join(lines) + "\n", returncode=1)
    with pytest.raises(DownloadError) as caught:
        download_audio("abc", tmp_path, "bestaudio", None)
    message = str(caught.value)
    assert "line 10" not in message and "line 11" in message  # last 40 lines only
    assert "SPOTEYE_PROGRESS" not in message
    assert friendly_error(message) == BOT_CHECK
    assert "--cookies" not in calls[0][0]


def test_output_without_json_line_is_a_download_error(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    fake_popen(monkeypatch, "[info] nothing useful\n")
    with pytest.raises(DownloadError, match="no file info"):
        download_audio("abc", tmp_path, "bestaudio", None)


def test_timeout_is_a_network_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def stream(args: list[str], timeout: float, on_line: Any) -> int:
        assert timeout == 600
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(ytdlp_bin, "stream", stream)
    with pytest.raises(DownloadError, match="timed out"):
        download_audio("abc", tmp_path, "bestaudio", None)


def test_stream_merges_stderr_and_returns_the_exit_code() -> None:
    script = "import sys; print('out'); print('err', file=sys.stderr, flush=True); sys.exit(3)"
    lines: list[str] = []
    assert ytdlp_bin.stream([sys.executable, "-c", script], 30, lines.append) == 3
    assert sorted(lines) == ["err", "out"]


def test_stream_kills_the_process_after_the_timeout() -> None:
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        ytdlp_bin.stream([sys.executable, "-c", "import time; time.sleep(30)"], 0.5, lambda _l: None)
    assert time.monotonic() - started < 10
