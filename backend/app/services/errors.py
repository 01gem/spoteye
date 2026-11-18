"""Turn raw download errors (yt-dlp, ffmpeg, network) into a short message a user can act on."""

from __future__ import annotations

from collections.abc import Callable

from app.services.hints import hint

MAX_RAW_CHARS: int = 300

BOT_CHECK = hint("bot_check")
HTTP_403 = hint("http_403")
UNAVAILABLE = "That YouTube Music upload is unavailable. Use Pick match to choose another."
NEED_DENO = hint("need_deno")
NO_FFMPEG = hint("no_ffmpeg")
NETWORK = "Network problem while downloading. Resume the job to retry."

Rule = tuple[Callable[[str], bool], str]


def _any(*needles: str) -> Callable[[str], bool]:
    return lambda text: any(n in text for n in needles)


def _ffmpeg_missing(text: str) -> bool:
    return "ffmpeg" in text and _any("not found", "not installed", "no such file")(text)


# Checked in order against the lower-cased message; the first match wins.
RULES: list[Rule] = [
    (_any("sign in to confirm", "not a bot"), BOT_CHECK),
    (_any("http error 403"), HTTP_403),
    (_any("video unavailable", "private video"), UNAVAILABLE),
    (_any("javascript runtime", "deno"), NEED_DENO),
    (_ffmpeg_missing, NO_FFMPEG),
    (_any("timed out", "connection"), NETWORK),
]


def friendly_error(raw: str) -> str:
    """The first matching rule's message, else the raw text trimmed to 300 characters."""
    text = raw.lower()
    for matches, message in RULES:
        if matches(text):
            return message
    return raw.strip()[:MAX_RAW_CHARS]
