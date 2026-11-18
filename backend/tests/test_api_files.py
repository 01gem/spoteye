"""Open-folder / reveal endpoints with recorders instead of the real Explorer."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import PLAYLIST_URL, add_job, client, env  # noqa: F401  (pytest fixtures)

from app.db import get_session
from app.models import TrackRecord
from app.services.job_state import job_records
from app.web import api_files


class Recorder:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def __call__(self, arg: object) -> None:
        self.calls.append(arg)


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> tuple[Recorder, Recorder]:
    startfile, popen = Recorder(), Recorder()
    monkeypatch.setattr(api_files, "is_windows", lambda: True)
    monkeypatch.setattr(api_files.os, "startfile", startfile, raising=False)
    monkeypatch.setattr(api_files.subprocess, "Popen", popen)
    return startfile, popen


def first_record(job_id: int, file_name: str) -> int:
    with get_session() as session:
        record: TrackRecord = job_records(session, job_id)[0]
        record.status, record.file_name = "done", file_name
        session.add(record)
        session.commit()
        assert record.id is not None
        return record.id


def test_open_folder_opens_existing_folder(client: TestClient, env: Path,
                                           windows: tuple[Recorder, Recorder]) -> None:  # fmt: skip
    folder = env / "music" / "Mix"
    folder.mkdir(parents=True)
    job_id = add_job("done", folder)
    assert client.post(f"/api/jobs/{job_id}/open-folder").status_code == 204
    assert windows[0].calls == [str(folder)]


def test_open_folder_missing_folder_is_404(client: TestClient, env: Path,
                                           windows: tuple[Recorder, Recorder]) -> None:  # fmt: skip
    job_id = add_job("done", env / "music" / "Nope")
    res = client.post(f"/api/jobs/{job_id}/open-folder")
    assert res.status_code == 404
    assert res.json()["detail"].startswith("The folder doesn't exist yet:")
    assert windows[0].calls == []


def test_reveal_selects_file_in_explorer(client: TestClient, env: Path,
                                         windows: tuple[Recorder, Recorder]) -> None:  # fmt: skip
    folder = env / "music" / "Mix"
    folder.mkdir(parents=True)
    (folder / "01 - Song.opus").write_bytes(b"x")
    job_id = add_job("done", folder)
    record_id = first_record(job_id, "01 - Song.opus")
    assert client.post(f"/api/jobs/{job_id}/tracks/{record_id}/reveal").status_code == 204
    expected = (folder / "01 - Song.opus").resolve()
    assert windows[1].calls == [["explorer", f"/select,{expected}"]]


def test_reveal_outside_job_folder_is_400(client: TestClient, env: Path,
                                          windows: tuple[Recorder, Recorder]) -> None:  # fmt: skip
    folder = env / "music" / "Mix"
    folder.mkdir(parents=True)
    (env / "evil.txt").write_bytes(b"x")
    job_id = add_job("done", folder)
    record_id = first_record(job_id, "..\\..\\evil.txt")
    assert client.post(f"/api/jobs/{job_id}/tracks/{record_id}/reveal").status_code == 400
    assert windows[1].calls == []


def test_not_windows_is_501(client: TestClient, env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_files, "is_windows", lambda: False)
    folder = env / "music" / "Mix"
    folder.mkdir(parents=True)
    job_id = add_job("done", folder)
    res = client.post(f"/api/jobs/{job_id}/open-folder")
    assert res.status_code == 501
    assert res.json()["detail"] == api_files.NOT_WINDOWS_MSG
    assert client.post(f"/api/jobs/{job_id}/tracks/1/reveal").status_code == 501


def test_resolve_includes_target_dir(client: TestClient, env: Path) -> None:
    body = client.post("/api/resolve", json={"url": PLAYLIST_URL}).json()
    assert body["target_dir"] == str(env / "music" / "Mix")
