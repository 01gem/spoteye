"""attach_file on a real silent .flac (skipped if ffmpeg is missing)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from mutagen.flac import FLAC
from sqlmodel import Session

from app.config import Settings
from app.db import init_db
from app.models import Job, TrackRecord
from app.services.attach import attach_file
from app.services.spotify_client import TrackMeta

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH")

TRACK = TrackMeta(spotify_id="sp4", title="Title", artists=["Artist"], album="Album",
                  duration_ms=2000, isrc="USABC2600004")  # fmt: skip


class FakeClient:
    def get_track(self, track_id: str) -> TrackMeta:
        assert track_id == TRACK.spotify_id
        return TRACK


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = init_db(tmp_path / "attach.db")
    with Session(engine, expire_on_commit=False) as s:
        yield s
    engine.dispose()


def _silent_flac(path: Path) -> Path:
    assert FFMPEG is not None
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=stereo", "-t", "2", "-c:a", "flac", str(path)],
                   check=True)  # fmt: skip
    return path


def test_attach_moves_renames_tags_and_updates_job(session: Session, tmp_path: Path) -> None:
    out = tmp_path / "Mix"
    job = Job(url="u", kind="playlist", spotify_id="pl", name="Mix", preset="best", out_dir=str(out))
    session.add(job)
    session.commit()
    assert job.id is not None
    record = TrackRecord(job_id=job.id, spotify_id="sp4", position=4, title="Title",
                         artists="Artist", duration_ms=2000, status="not_found")  # fmt: skip
    session.add(record)
    session.commit()
    src = _silent_flac(tmp_path / "my own rip.flac")
    settings = Settings("client", "http://127.0.0.1:8765/callback", tmp_path / "unused", None)

    target, updated = attach_file(src, "sp4", job, session, copy=False, client=FakeClient(),
                                  settings=settings, cover_fetcher=lambda _url: None)  # fmt: skip

    assert target == out / "04 - Artist - Title.flac"
    assert target.is_file() and not src.exists()
    tags = FLAC(target)
    assert tags["title"] == ["Title"]
    assert tags["isrc"] == ["USABC2600004"]
    assert updated is not None and updated.status == "manual"
    assert updated.file_name == "04 - Artist - Title.flac"
    assert updated.source == "manual (flac)" and updated.output == "flac"
    assert job.status == "done"
    assert "04 - Artist - Title.flac" in (out / "Mix.m3u8").read_text(encoding="utf-8")


def test_attach_refuses_existing_target_and_keeps_source(session: Session, tmp_path: Path) -> None:
    settings = Settings("client", "http://127.0.0.1:8765/callback", tmp_path / "lib", None)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "Artist - Title.flac").write_bytes(b"existing")
    src = _silent_flac(tmp_path / "rip.flac")

    with pytest.raises(FileExistsError):
        attach_file(src, "sp4", None, session, copy=False, client=FakeClient(), settings=settings,
                    cover_fetcher=lambda _url: None)  # fmt: skip
    assert src.exists()


def test_attach_rejects_unsupported_extension(session: Session, tmp_path: Path) -> None:
    src = tmp_path / "song.wav"
    src.write_bytes(b"RIFF")
    with pytest.raises(ValueError):
        attach_file(src, "sp4", None, session, copy=True, client=FakeClient())
