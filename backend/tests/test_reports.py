from __future__ import annotations

from pathlib import Path

from app.models import Job, TrackRecord
from app.services.reports import write_m3u8, write_missing_report

JOB = Job(id=1, url="u", kind="playlist", spotify_id="p", name="Road: Trip?", preset="best",
          out_dir="unused")  # fmt: skip


def record(position: int, status: str, file_name: str | None = None) -> TrackRecord:
    return TrackRecord(job_id=1, spotify_id=f"id{position}", position=position,
                       title=f"Song {position}", artists="Artist", isrc=None if position == 2
                       else f"ISRC{position}", duration_ms=200_400, status=status,
                       file_name=file_name)  # fmt: skip


def test_missing_report_lists_only_missing_records(tmp_path: Path) -> None:
    records = [record(3, "failed"), record(1, "done", "a.opus"), record(2, "not_found"),
               record(4, "skipped", "b.opus"), record(5, "manual", "c.flac")]  # fmt: skip
    path = write_missing_report(JOB, records, tmp_path)
    assert path == tmp_path / "_missing.txt"
    assert path.read_text(encoding="utf-8").splitlines() == [
        "02 - Artist - Song 2 | ISRC: - | https://open.spotify.com/track/id2 | not_found",
        "03 - Artist - Song 3 | ISRC: ISRC3 | https://open.spotify.com/track/id3 | failed",
    ]


def test_missing_report_removed_when_nothing_missing(tmp_path: Path) -> None:
    write_missing_report(JOB, [record(1, "failed")], tmp_path)
    assert (tmp_path / "_missing.txt").exists()
    assert write_missing_report(JOB, [record(1, "done", "a.opus")], tmp_path) is None
    assert not (tmp_path / "_missing.txt").exists()


def test_m3u8_is_in_position_order_and_skips_missing_files(tmp_path: Path) -> None:
    for name in ("01 - a.opus", "03 - c.opus"):
        (tmp_path / name).write_bytes(b"x")
    records = [record(3, "done", "03 - c.opus"), record(2, "done", "02 - gone.opus"),
               record(1, "skipped", "01 - a.opus"), record(4, "failed")]  # fmt: skip
    path = write_m3u8(JOB, records, tmp_path)
    assert path.name == "Road Trip.m3u8"
    assert path.read_text(encoding="utf-8").splitlines() == [
        "#EXTM3U",
        "#EXTINF:200,Artist - Song 1",
        "01 - a.opus",
        "#EXTINF:200,Artist - Song 3",
        "03 - c.opus",
    ]
