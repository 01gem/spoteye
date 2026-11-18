"""Matcher tests: no network, a fake YTMusic returns canned search results."""

from __future__ import annotations

from typing import Any

from app.services.matcher import Candidate, Matcher, score_candidate
from app.services.spotify_client import TrackMeta


def make_track() -> TrackMeta:
    return TrackMeta(
        spotify_id="spotify123",
        title="Bohemian Rhapsody",
        artists=["Queen"],
        album="A Night at the Opera",
        duration_ms=354_000,
        isrc="GBUM71029604",
    )


def song(video_id: str, title: str, duration_s: int | None) -> dict[str, Any]:
    return {
        "videoId": video_id,
        "title": title,
        "artists": [{"name": "Queen", "id": "artist1"}],
        "album": {"name": "A Night at the Opera", "id": "album1"},
        "duration_seconds": duration_s,
        "resultType": "song",
    }


def candidate(title: str, duration_s: int | None) -> Candidate:
    return Candidate("vid", title, ["Queen"], "A Night at the Opera", duration_s, "song")


class FakeYTMusic:
    """Returns the same canned results for every query, or always raises."""

    def __init__(self, results: list[dict[str, Any]], fail: bool = False) -> None:
        self.results = results
        self.fail = fail
        self.calls: list[str] = []

    def search(self, query: str, filter: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        self.calls.append(query)
        if self.fail:
            raise ConnectionError("network down")
        return self.results


def make_matcher(yt: FakeYTMusic, sleeps: list[float] | None = None) -> Matcher:
    record = sleeps if sleeps is not None else []
    return Matcher(yt=yt, sleep=record.append)  # type: ignore[arg-type]


def test_exact_match_scores_matched() -> None:
    yt = FakeYTMusic([song("studio", "Bohemian Rhapsody", 355)])
    result = make_matcher(yt).match(make_track())
    assert result.score >= 0.80
    assert result.status == "matched"
    assert result.best is not None and result.best.video_id == "studio"
    assert len(result.candidates) == 1  # ISRC + text search results de-duplicated
    assert yt.calls == ["GBUM71029604", "Queen bohemian rhapsody"]


def test_live_version_scores_lower_than_studio() -> None:
    track = make_track()
    studio = score_candidate(track, candidate("Bohemian Rhapsody", 355))
    live = score_candidate(track, candidate("Bohemian Rhapsody (Live Aid)", 355))
    assert live < studio

    yt = FakeYTMusic([song("live", "Bohemian Rhapsody (Live Aid)", 355), song("studio", "Bohemian Rhapsody", 355)])
    result = make_matcher(yt).match(track)
    assert result.best is not None and result.best.video_id == "studio"


def test_candidate_15_seconds_longer_scores_zero() -> None:
    assert score_candidate(make_track(), candidate("Bohemian Rhapsody", 354 + 15)) == 0.0


def test_empty_results_give_not_found() -> None:
    result = make_matcher(FakeYTMusic([])).match(make_track())
    assert result.status == "not_found"
    assert result.best is None
    assert result.score == 0.0


def test_search_failing_twice_gives_not_found() -> None:
    sleeps: list[float] = []
    yt = FakeYTMusic([], fail=True)
    result = make_matcher(yt, sleeps).match(make_track())
    assert result.status == "not_found"
    assert result.score == 0.0
    assert sleeps == [2.0]
    assert len(yt.calls) == 2
