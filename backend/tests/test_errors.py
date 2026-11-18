"""friendly_error: one case per rule, the fallback and the 300-character trim."""

from __future__ import annotations

import pytest

from app.services import errors
from app.services.errors import friendly_error


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", errors.BOT_CHECK),
        ("Please prove you are NOT A BOT", errors.BOT_CHECK),
        ("ERROR: unable to download video data: HTTP Error 403: Forbidden", errors.HTTP_403),
        ("ERROR: [youtube] abc: Video unavailable", errors.UNAVAILABLE),
        ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access",
         errors.UNAVAILABLE),
        ("No supported JavaScript runtime could be found", errors.NEED_DENO),
        ("deno: command failed", errors.NEED_DENO),
        ("FFmpeg not found. Install it and add it to PATH", errors.NO_FFMPEG),
        ("Read timed out. (read timeout=20)", errors.NETWORK),
        ("Connection reset by peer", errors.NETWORK),
    ],
)  # fmt: skip
def test_rules(raw: str, expected: str) -> None:
    assert friendly_error(raw) == expected


def test_ffmpeg_failure_that_is_not_missing_falls_back() -> None:
    raw = "ffmpeg failed (1) for x.opus: Invalid data found"
    assert friendly_error(raw) == raw


def test_unknown_message_is_returned_trimmed() -> None:
    assert friendly_error("  Something odd happened \n") == "Something odd happened"


def test_long_message_is_cut_to_300_characters() -> None:
    assert friendly_error("x" * 1000) == "x" * 300
