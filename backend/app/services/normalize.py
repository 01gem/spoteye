"""Text normalization helpers for matching Spotify tracks to YouTube Music results."""

from __future__ import annotations

import re
import unicodedata

PENALTY_WORDS: list[str] = [
    "live",
    "cover",
    "karaoke",
    "instrumental",
    "sped up",
    "slowed",
    "nightcore",
    "remix",
    "8d",
    "reverb",
    "acoustic",
]

# Suffix content that never changes which recording it is (unlike "live" or "remix").
_NOISE: str = (
    r"(?:\d{4}\s+)?remaster(?:ed)?(?:\s+(?:version|edition))?(?:\s+\d{4})?"
    r"|(?:featuring|feat|ft)\.?\s+[^)\]]*"
    r"|official\s+(?:music\s+)?(?:audio|video|lyric\s+video|visuali[sz]er)"
    r"|lyrics?(?:\s+video)?"
    r"|visuali[sz]er"
)
_BRACKETED_NOISE = re.compile(rf"[(\[]\s*(?:{_NOISE})\s*[)\]]")
_DASHED_NOISE = re.compile(rf"\s+-\s+(?:{_NOISE})\s*$")
_INLINE_FEAT = re.compile(r"\s+(?:featuring|feat|ft)\.?\s+.*$")
_APOSTROPHES = re.compile(r"['’`]")
_NON_WORD = re.compile(r"[^\w\s]|_")
_SPACES = re.compile(r"\s+")


def _strip_accents(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _collapse(s: str) -> str:
    return _SPACES.sub(" ", s).strip()


def _clean(s: str) -> str:
    """Lowercase, strip accents, turn punctuation into spaces, collapse whitespace."""
    s = _APOSTROPHES.sub("", _strip_accents(s.lower()))
    return _collapse(_NON_WORD.sub(" ", s))


def normalize_title(s: str) -> str:
    """Normalize a song title, dropping remaster/feat/official-audio style suffixes."""
    s = _strip_accents(s.lower())
    s = _BRACKETED_NOISE.sub(" ", s)
    previous = None
    while previous != s:
        previous = s
        s = _DASHED_NOISE.sub("", s)
    s = _INLINE_FEAT.sub("", s)
    return _clean(s)


def normalize_artist(s: str) -> str:
    """Normalize an artist name: lowercase, strip accents, drop a leading "the "."""
    s = _collapse(_strip_accents(s.lower()))
    if s.startswith("the "):
        s = s[4:]
    return s.strip()


def penalty_words_in(candidate_title: str, spotify_title: str) -> list[str]:
    """Return penalty words found in the candidate title but not in the Spotify title."""
    candidate = f" {_clean(candidate_title)} "
    spotify = f" {_clean(spotify_title)} "
    return [w for w in PENALTY_WORDS if f" {w} " in candidate and f" {w} " not in spotify]
