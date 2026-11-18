"""Phase 1 of a job: match tracks to YouTube Music through the MatchCache table."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, timedelta

from sqlmodel import Session

from app.models import MatchCache, now
from app.services.matcher import Matcher
from app.services.spotify_client import TrackMeta


def is_stale(cached: MatchCache, retry_after: timedelta | None) -> bool:
    """A "not_found"/"review" entry older than retry_after. "matched" (incl. hand-picked) never expires."""
    if retry_after is None or cached.status == "matched":
        return False
    matched_at = cached.matched_at
    if matched_at.tzinfo is None:  # SQLite hands back naive UTC
        matched_at = matched_at.replace(tzinfo=UTC)
    return now() - matched_at > retry_after


def match_all(
    tracks: Iterable[TrackMeta], matcher: Matcher, session: Session, rematch: bool = False,
    retry_after: timedelta | None = None,
) -> dict[str, MatchCache]:  # fmt: skip
    """Match each track, using and filling MatchCache (bypassed when rematch).

    Stale "not_found"/"review" entries (see is_stale) are matched again.
    """
    results: dict[str, MatchCache] = {}
    for track in tracks:
        cached = None if rematch else session.get(MatchCache, track.spotify_id)
        if cached is None or is_stale(cached, retry_after):
            result = matcher.match(track)
            fresh = MatchCache(
                spotify_id=track.spotify_id, video_id=result.best.video_id if result.best else None,
                score=result.score, status=result.status, matched_at=now(),
            )  # fmt: skip
            if result.best is not None:  # no candidates at all may be a network error: don't cache
                cached = session.merge(fresh)
                session.commit()
            elif cached is None:  # a stale entry is kept when the retry finds nothing
                cached = fresh
        results[track.spotify_id] = cached
    return results
