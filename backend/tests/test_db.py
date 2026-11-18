from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.db import get_session, init_db
from app.models import Job, MatchCache, TrackRecord


def test_job_with_three_track_records(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    engine = init_db(db_file)
    assert db_file.is_file()

    with Session(engine) as session:
        job = Job(url="https://open.spotify.com/playlist/x", kind="playlist", spotify_id="x",
                  name="Mix", preset="best", out_dir=str(tmp_path))  # fmt: skip
        session.add(job)
        session.commit()
        session.refresh(job)
        assert job.id is not None
        job_id = job.id
        session.add_all(
            TrackRecord(job_id=job_id, spotify_id=f"t{p}", position=p, title=f"Song {p}",
                        artists="A, B", duration_ms=1000 * p)
            for p in (3, 1, 2)
        )  # fmt: skip
        session.add(MatchCache(spotify_id="t1", video_id="v1", score=0.9, status="matched"))
        session.commit()

    with get_session() as session:
        stored = session.get(Job, job_id)
        assert stored is not None and stored.status == "running" and stored.finished_at is None
        query = select(TrackRecord).where(TrackRecord.job_id == job_id).order_by(TrackRecord.position)
        records = session.exec(query).all()
        assert [r.position for r in records] == [1, 2, 3]
        assert {r.status for r in records} == {"pending"}
        assert all(r.upscaled is False and r.file_name is None for r in records)
        cached = session.get(MatchCache, "t1")
        assert cached is not None and cached.video_id == "v1"
    engine.dispose()
