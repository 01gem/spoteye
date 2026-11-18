"""Job run + resume with fake matcher, fake Spotify client and fake download worker."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlmodel import Session

from app.config import Settings
from app.db import init_db
from app.services.filenames import build_filename
from app.services.job_runner import create_job, resume_job, run_job
from app.services.job_state import job_records
from app.services.matcher import Candidate, MatchResult
from app.services.pipeline import TrackResult, WorkItem
from app.services.presets import Preset
from app.services.spotify_client import TrackMeta

TRACKS = [TrackMeta(spotify_id=f"sp{i}", title=f"Song {i}", artists=["Artist"], duration_ms=180_000)
          for i in (1, 2, 3)]  # fmt: skip


class FakeMatcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def match(self, track: TrackMeta) -> MatchResult:
        self.calls.append(track.spotify_id)
        best = Candidate(f"vid-{track.spotify_id}", track.title, track.artists, None, 180, "song")
        return MatchResult("matched", best, 0.95, [(best, 0.95)])


class FakeClient:
    def get_track(self, track_id: str) -> TrackMeta:
        return next(t for t in TRACKS if t.spotify_id == track_id)


class FakeWorker:
    """Writes an empty .opus file instead of downloading; fails for ids in fail_ids."""

    def __init__(self, fail_ids: set[str]) -> None:
        self.fail_ids = fail_ids
        self.calls: list[str] = []

    def __call__(self, item: WorkItem, preset: Preset, out_dir: Path, settings: Settings) -> TrackResult:
        self.calls.append(item.track.spotify_id)
        if item.track.spotify_id in self.fail_ids:
            return TrackResult(item.track, "failed", error="simulated network error")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / build_filename(item.track, "opus", item.index)
        path.write_bytes(b"fake audio")
        return TrackResult(item.track, "done", path=path, source="opus 130k", output="opus copy")


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = init_db(tmp_path / "jobs.db")
    with Session(engine, expire_on_commit=False) as s:
        yield s
    engine.dispose()


def test_resume_reprocesses_only_failed_track_and_uses_match_cache(
    session: Session, tmp_path: Path
) -> None:
    out = tmp_path / "Mix"
    settings = Settings("client", "http://127.0.0.1:8765/callback", tmp_path, None, max_workers=2)
    matcher, worker = FakeMatcher(), FakeWorker(fail_ids={"sp2"})
    job, records = create_job(session, "url", "playlist", "pl", "Mix", Preset.BEST, out, TRACKS)
    options = {"worker": worker, "sleep": lambda _s: None}

    run_job(session, job, list(zip(records, TRACKS)), matcher, settings,  # type: ignore[arg-type]
            accept_review=False, **options)  # fmt: skip

    assert job.id is not None
    assert {r.spotify_id: r.status for r in job_records(session, job.id)} == {
        "sp1": "done", "sp2": "failed", "sp3": "done"}  # fmt: skip
    assert job.status == "partial"
    assert sorted(matcher.calls) == ["sp1", "sp2", "sp3"]
    assert "sp2" in (out / "_missing.txt").read_text(encoding="utf-8")

    worker.fail_ids.clear()
    worker.calls.clear()
    final = resume_job(session, job, FakeClient(), matcher, settings,  # type: ignore[arg-type]
                       accept_review=False, **options)  # fmt: skip

    assert worker.calls == ["sp2"]
    assert sorted(matcher.calls) == ["sp1", "sp2", "sp3"]  # second run used MatchCache
    assert [r.status for r in final] == ["done", "done", "done"]
    assert final[1].file_name == "02 - Artist - Song 2.opus"
    assert final[1].video_id == "vid-sp2"
    assert job.status == "done" and job.finished_at is not None
    assert not (out / "_missing.txt").exists()
    playlist = (out / "Mix.m3u8").read_text(encoding="utf-8").splitlines()
    assert [line for line in playlist if not line.startswith("#")] == [
        "01 - Artist - Song 1.opus", "02 - Artist - Song 2.opus", "03 - Artist - Song 3.opus"]  # fmt: skip


def test_existing_file_is_skipped_without_matching(session: Session, tmp_path: Path) -> None:
    out = tmp_path / "Mix"
    out.mkdir()
    (out / "01 - Artist - Song 1.m4a").write_bytes(b"already here")
    settings = Settings("client", "http://127.0.0.1:8765/callback", tmp_path, None)
    matcher, worker = FakeMatcher(), FakeWorker(fail_ids=set())
    job, records = create_job(session, "url", "playlist", "pl", "Mix", Preset.BEST, out, TRACKS[:1])

    final = run_job(session, job, list(zip(records, TRACKS[:1])), matcher, settings,  # type: ignore[arg-type]
                    accept_review=False, worker=worker, sleep=lambda _s: None)  # fmt: skip

    assert final[0].status == "skipped"
    assert final[0].file_name == "01 - Artist - Song 1.m4a"
    assert matcher.calls == [] and worker.calls == []
    assert job.status == "done"
