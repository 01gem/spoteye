"""Packaged-mode hints never name a dev command; source-mode wording is unchanged."""

from __future__ import annotations

import re

import pytest

from app.services import errors, hints, spotify_client, spotify_errors, transcoder
from app.web import auth

DEV_COMMANDS = re.compile(r"cli\.py|winget|pip install|backend[/\\]|\.env|npm", re.IGNORECASE)


@pytest.mark.parametrize("key", sorted(hints.HINTS))
def test_packaged_hints_have_no_dev_commands(key: str) -> None:
    text = hints.hint(key, frozen=True)
    assert text and not DEV_COMMANDS.search(text), text


def test_source_mode_keeps_todays_wording() -> None:
    assert hints.CLI == "python cli.py"
    assert auth.NEED_TOKEN_MSG == hints.hint("need_token", frozen=False)
    assert "python cli.py info" in auth.NEED_TOKEN_MSG
    assert spotify_errors.EXPIRED_MSG.endswith("Run: python cli.py login")
    assert "backend/.env" in spotify_client.MISSING_CLIENT_ID_MSG
    assert "winget install Gyan.FFmpeg" in transcoder.FFMPEG_MISSING_MSG
    assert errors.HTTP_403.endswith("pip install -U yt-dlp")


def test_packaged_texts_still_match_the_frontend_rewrites() -> None:
    """frontend/src/messages.ts matches on these phrases."""
    assert "bot check" in hints.hint("bot_check", frozen=True).lower()
    assert "refused the download (403)" in hints.hint("http_403", frozen=True)
