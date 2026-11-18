"""Ctrl+C -> "stopped", the `stop` helper, report ownership per folder, and staged (atomic) writes."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session

from app.config import Settings
from app.models import TrackRecord
from app.services import pipeline
from app.services.downloader import DownloadedAudio
from app.services.job_runner import create_job, resume_job, run_job
from app.services.job_state import JobStopped, finish_job, job_records, save_result, stop_job
from app.services.pipeline import TrackResult, WorkItem
from app.services.presets import Preset
from app.services.spotify_client import TrackMeta
from tests.test_pipeline_resume import TRACKS, FakeClient, FakeMatcher, FakeWorker, session

__all__ = ["session"]  # pytest fixture re-used from test_pipeline_resume


def _settings(tmp_path: Path) -> Settings:
    return Settings("client", "http://127.0.0.1:8765/callback", tmp_path, None, max_workers=1)


class InterruptingWorker(FakeWorker):
    """Simulates Ctrl+C arriving while track sp2 is being processed."""

    def __call__(self, item: WorkItem, *args: object) -> TrackResult:  # type: ignore[override]
        if item.track.spotify_id == "sp2" and "sp2" in self.fail_ids:
            raise KeyboardInterrupt
        return super().__call__(item, *args)  # type: ignore[arg-type]


def test_ctrl_c_marks_job_stopped_and_resume_finishes_it(session: Session, tmp_path: Path) -> None:
    out, settings = tmp_path / "Mix", _settings(tmp_path)
    matcher, worker = FakeMatcher(), InterruptingWorker(fail_ids={"sp2"})
    job, records = create_job(session, "url", "playlist", "pl", "Mix", Preset.BEST, out, TRACKS)
    options = {"worker": worker, "sleep": lambda _s: None}

    with pytest.raises(JobStopped) as stopped:
        run_job(session, job, list(zip(records, TRACKS)), matcher, settings,  # type: ignore[arg-type]
                accept_review=False, **options)  # fmt: skip

    assert job.id is not None and stopped.value.job_id == job.id
    assert job.status == "stopped" and job.finished_at is not None
    statuses = {r.spotify_id: r.status for r in job_records(session, job.id)}
    assert statuses["sp1"] == "done" and statuses["sp2"] == "pending"
    assert not (out / "_missing.txt").exists()  # stopping never writes reports

    worker.fail_ids.clear()
    final = resume_job(session, job, FakeClient(), matcher, settings,  # type: ignore[arg-type]
                       accept_review=False, **options)  # fmt: skip
    assert [r.status for r in final][0:2] == ["done", "done"]
    assert final[2].status in {"done", "skipped"}  # sp3 may have finished during shutdown
    assert job.status == "done"


def test_stop_job_only_changes_running_jobs(session: Session, tmp_path: Path) -> None:
    job, _ = create_job(session, "url", "track", "t", "One", Preset.BEST, tmp_path, TRACKS[:1])
    assert stop_job(session, job) is True
    assert job.status == "stopped" and job.finished_at is not None
    job.status = "partial"
    assert stop_job(session, job) is False
    assert job.status == "partial"


def _not_found(session: Session, record: TrackRecord, track: TrackMeta) -> None:
    save_result(session, record, TrackResult(track, "not_found"))


def test_older_job_does_not_overwrite_newer_jobs_reports(session: Session, tmp_path: Path) -> None:
    out = tmp_path / "Mix"
    out.mkdir()
    old, old_records = create_job(session, "url", "playlist", "pl", "Mix", Preset.BEST, out, TRACKS[:1])
    new, new_records = create_job(session, "url", "playlist", "pl", "Mix", Preset.BEST, out, TRACKS[:1])
    _not_found(session, old_records[0], TRACKS[0])
    _not_found(session, new_records[0], TRACKS[0])
    (out / "Mix.m3u8").write_text("SENTINEL", encoding="utf-8")

    finish_job(session, old)
    assert old.status == "failed"
    assert not (out / "_missing.txt").exists()
    assert (out / "Mix.m3u8").read_text(encoding="utf-8") == "SENTINEL"

    finish_job(session, new)
    assert "sp1" in (out / "_missing.txt").read_text(encoding="utf-8")
    assert (out / "Mix.m3u8").read_text(encoding="utf-8").startswith("#EXTM3U")


def _fake_download(video_id: str, temp_dir: Path, *_args: object) -> DownloadedAudio:
    src = temp_dir / f"{video_id}.webm"
    src.write_bytes(b"source")
    return DownloadedAudio(src, video_id, "251", "opus", 130.0, "webm")


@pytest.mark.parametrize("fail", [False, True])
def test_download_track_never_leaves_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    def fake_transcode(src: Path, dst: Path, args: list[str]) -> None:
        dst.write_bytes(b"half written")
        if fail:
            raise RuntimeError("ffmpeg died")

    monkeypatch.setattr(pipeline, "download_audio", _fake_download)
    monkeypatch.setattr(pipeline, "transcode", fake_transcode)
    monkeypatch.setattr(pipeline, "tag_file", lambda *_a: None)
    monkeypatch.setattr(pipeline, "fetch_cover", lambda _u: None)
    out = tmp_path / "Mix"
    out.mkdir()

    result = pipeline.download_track(WorkItem(1, TRACKS[0], "vid", 1), Preset.BEST, out,
                                     _settings(tmp_path))  # fmt: skip

    files = [p.name for p in out.iterdir() if p.is_file()]
    if fail:
        assert result.status == "failed" and files == []
    else:
        assert result.status == "done" and files == ["01 - Artist - Song 1.opus"]
    assert not any((out / pipeline.TMP_DIR_NAME).iterdir())  # staging folder cleaned up
