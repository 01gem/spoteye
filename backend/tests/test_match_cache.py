"""Stale "not_found"/"review" cache entries are matched again; "matched" ones never expire."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from sqlmodel import Session

from app.db import init_db
from app.models import MatchCache, now
from app.services.match_cache import match_all
from app.services.matcher import Candidate, MatchResult
from app.services.spotify_client import TrackMeta

RETRY = timedelta(days=14)


class FakeMatcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def match(self, track: TrackMeta) -> MatchResult:
        self.calls.append(track.spotify_id)
        best = Candidate(f"vid-{track.spotify_id}", track.title, track.artists, None, 180, "song")
        return MatchResult("matched", best, 0.95, [(best, 0.95)])


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = init_db(tmp_path / "cache.db")
    with Session(engine, expire_on_commit=False) as s:
        old, fresh = now() - timedelta(days=30), now()
        s.add_all([
            MatchCache(spotify_id="old_nf", status="not_found", matched_at=old),
            MatchCache(spotify_id="old_review", video_id="v1", score=0.7, status="review", matched_at=old),
            MatchCache(spotify_id="new_nf", status="not_found", matched_at=fresh),
            MatchCache(spotify_id="old_ok", video_id="v2", score=1.0, status="matched", matched_at=old),
        ])  # fmt: skip
        s.commit()
        s.expunge_all()  # reload from SQLite: naive datetimes, as in real runs
        yield s
    engine.dispose()


def tracks(*ids: str) -> list[TrackMeta]:
    return [TrackMeta(spotify_id=i, title=i, artists=["Artist"]) for i in ids]


def test_only_stale_not_found_and_review_are_matched_again(session: Session) -> None:
    matcher = FakeMatcher()
    results = match_all(tracks("old_nf", "old_review", "new_nf", "old_ok"), matcher, session,  # type: ignore[arg-type]
                        retry_after=RETRY)  # fmt: skip
    assert matcher.calls == ["old_nf", "old_review"]
    assert results["old_nf"].status == "matched" and results["old_nf"].video_id == "vid-old_nf"
    assert results["new_nf"].status == "not_found"
    assert results["old_ok"].video_id == "v2"


def test_without_retry_after_cache_is_kept(session: Session) -> None:
    matcher = FakeMatcher()
    match_all(tracks("old_nf", "old_review", "old_ok"), matcher, session)  # type: ignore[arg-type]
    assert matcher.calls == []
