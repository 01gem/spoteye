"""Match Spotify tracks to YouTube Music songs: ISRC-first search plus fuzzy scoring."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from rapidfuzz import fuzz
from ytmusicapi import YTMusic

from app.services.normalize import normalize_artist, normalize_title, penalty_words_in
from app.services.spotify_client import TrackMeta

Status = Literal["matched", "review", "not_found"]

MATCHED_THRESHOLD: float = 0.80
REVIEW_THRESHOLD: float = 0.65
RETRY_DELAY_S: float = 2.0
TOP_N: int = 3
ISRC_LIMIT: int = 5
TEXT_LIMIT: int = 10

W_TITLE, W_ARTIST, W_DURATION, W_ALBUM = 0.45, 0.30, 0.20, 0.05
PENALTY_PER_WORD: float = 0.25
FULL_DURATION_DELTA_S: float = 2.0
MAX_DURATION_DELTA_S: float = 7.0


@dataclass
class Candidate:
    video_id: str
    title: str
    artists: list[str]
    album: str | None
    duration_s: int | None
    result_type: str


@dataclass
class MatchResult:
    status: Status
    best: Candidate | None
    score: float
    candidates: list[tuple[Candidate, float]] = field(default_factory=list)


def _ratio(a: str, b: str) -> float:
    return fuzz.token_set_ratio(a, b) / 100


def score_candidate(track: TrackMeta, c: Candidate) -> float:
    """Score how well a YouTube Music candidate matches a Spotify track, in [0, 1]."""
    if c.duration_s is None:
        duration = 0.5
    else:
        delta = abs(track.duration_ms / 1000 - c.duration_s)
        if delta > MAX_DURATION_DELTA_S:
            return 0.0
        span = MAX_DURATION_DELTA_S - FULL_DURATION_DELTA_S
        duration = 1.0 if delta <= FULL_DURATION_DELTA_S else (MAX_DURATION_DELTA_S - delta) / span

    title = _ratio(normalize_title(track.title), normalize_title(c.title))
    artist = max(
        (_ratio(normalize_artist(a), normalize_artist(b)) for a in track.artists for b in c.artists),
        default=0.0,
    )
    album = 0.0
    if track.album and c.album:
        album = 1.0 if _ratio(normalize_title(track.album), normalize_title(c.album)) >= 0.90 else 0.0

    score = W_TITLE * title + W_ARTIST * artist + W_DURATION * duration + W_ALBUM * album
    score -= PENALTY_PER_WORD * len(penalty_words_in(c.title, track.title))
    return max(0.0, min(1.0, score))


def to_candidate(r: dict[str, Any]) -> Candidate | None:
    """Convert a ytmusicapi search result into a Candidate (None if it has no videoId)."""
    video_id = r.get("videoId")
    if not video_id:
        return None
    album = r.get("album")
    return Candidate(
        video_id=video_id,
        title=r.get("title") or "",
        artists=[a["name"] for a in r.get("artists") or [] if a.get("name")],
        album=album.get("name") if isinstance(album, dict) else None,
        duration_s=r.get("duration_seconds"),
        result_type=r.get("resultType") or "",
    )


def _status_for(score: float) -> Status:
    if score >= MATCHED_THRESHOLD:
        return "matched"
    if score >= REVIEW_THRESHOLD:
        return "review"
    return "not_found"


class Matcher:
    """Find the best YouTube Music song for a Spotify track."""

    def __init__(
        self, yt: YTMusic | None = None, sleep: Callable[[float], None] = time.sleep,
        top_n: int = TOP_N,
    ) -> None:  # fmt: skip
        self.top_n = top_n
        self.yt: YTMusic = yt if yt is not None else YTMusic()
        self._sleep = sleep

    def _search(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Search songs, retrying once after a short delay. Raises on the second failure."""
        try:
            return self.yt.search(query, filter="songs", limit=limit)
        except Exception:
            self._sleep(RETRY_DELAY_S)
            return self.yt.search(query, filter="songs", limit=limit)

    def match(self, track: TrackMeta) -> MatchResult:
        results: list[dict[str, Any]] = []
        try:
            if track.isrc:
                results += self._search(track.isrc, ISRC_LIMIT)
            lead_artist = track.artists[0] if track.artists else ""
            query = f"{lead_artist} {normalize_title(track.title)}".strip()
            results += self._search(query, TEXT_LIMIT)
        except Exception:
            return MatchResult(status="not_found", best=None, score=0.0)

        seen: set[str] = set()
        candidates: list[Candidate] = []
        for r in results:
            c = to_candidate(r)
            if c is None or c.video_id in seen:
                continue
            seen.add(c.video_id)
            candidates.append(c)

        scored = sorted(
            ((c, score_candidate(track, c)) for c in candidates), key=lambda p: p[1], reverse=True
        )
        if not scored:
            return MatchResult(status="not_found", best=None, score=0.0)
        best, score = scored[0]
        return MatchResult(
            status=_status_for(score), best=best, score=score, candidates=scored[: self.top_n]
        )
