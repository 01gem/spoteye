"""Settings page API and the yt-dlp update button (no network)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_api import add_job, client, env  # noqa: F401  (pytest fixtures)

from app.services import ytdlp_bin

CLIENT_ID = "0123456789abcdef0123456789abcdef"


def form(env: Path, **changes: Any) -> dict[str, Any]:
    body = {"spotify_client_id": CLIENT_ID, "output_dir": str(env / "out"), "cookies_file": None,
            "max_workers": 4, "match_retry_days": 30}  # fmt: skip
    return body | changes


def test_put_round_trip_keeps_unknown_keys(client: TestClient, env: Path, env_file: Path) -> None:
    env_file.write_text("# my notes\nSPOTIFY_REDIRECT_URI=http://127.0.0.1:9999/cb\n"
                        "MAX_WORKERS=2\nCUSTOM=keep me\n", encoding="utf-8")  # fmt: skip
    cookies = env / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    music = env / "My Music #1"
    res = client.put("/api/settings", json=form(env, output_dir=str(music), cookies_file=str(cookies)))
    assert res.status_code == 200, res.text
    expected = {"spotify_client_id": CLIENT_ID, "output_dir": str(music), "cookies_file": str(cookies),
                "max_workers": 4, "match_retry_days": 30, "frozen": False}  # fmt: skip
    assert res.json().items() >= expected.items()
    assert client.get("/api/settings").json() == res.json()
    text = env_file.read_text(encoding="utf-8")
    assert text.startswith("# my notes\nSPOTIFY_REDIRECT_URI=http://127.0.0.1:9999/cb\nMAX_WORKERS=4\n")
    assert "CUSTOM=keep me\n" in text
    assert music.is_dir() and list(music.iterdir()) == []  # write test file removed


@pytest.mark.parametrize(("field", "value"), [
    ("spotify_client_id", "not-a-client-id"),
    ("spotify_client_id", "0123456789ABCDEF0123456789ABCDEF"),
    ("output_dir", ""),
    ("output_dir", "relative/folder"),
    ("cookies_file", "Z:/no/such/cookies.txt"),
    ("max_workers", 0),
    ("max_workers", 9),
    ("match_retry_days", 0),
    ("match_retry_days", 366),
])  # fmt: skip
def test_put_rejects_bad_value_per_field(client: TestClient, env: Path, env_file: Path,
                                         field: str, value: Any) -> None:  # fmt: skip
    res = client.put("/api/settings", json=form(env, **{field: value}))
    assert res.status_code == 422
    errors = res.json()["detail"]
    assert [e["loc"] for e in errors] == [["body", field]]
    assert errors[0]["msg"] and not errors[0]["msg"].startswith("Value error")
    assert not env_file.exists()


def test_put_rejects_unwritable_output_dir(client: TestClient, env: Path) -> None:
    blocker = env / "a file"
    blocker.write_text("x", encoding="utf-8")
    res = client.put("/api/settings", json=form(env, output_dir=str(blocker / "sub")))
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "output_dir"]


def test_put_accepts_empty_client_id(client: TestClient, env: Path) -> None:
    res = client.put("/api/settings", json=form(env, spotify_client_id=""))
    assert res.status_code == 200 and res.json()["spotify_client_id"] == ""


def test_update_ytdlp_in_library_mode_is_400(client: TestClient) -> None:
    assert client.post("/api/tools/update-ytdlp").status_code == 400


def test_update_ytdlp_is_409_during_a_running_job(client: TestClient, env: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setattr(ytdlp_bin, "find", lambda: Path("yt-dlp.exe"))
    monkeypatch.setattr(ytdlp_bin, "update", lambda: pytest.fail("must not update"))
    add_job("running", env / "music" / "Mix")
    assert client.post("/api/tools/update-ytdlp").status_code == 409


def test_update_ytdlp_returns_output(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ytdlp_bin, "find", lambda: Path("yt-dlp.exe"))
    monkeypatch.setattr(ytdlp_bin, "update", lambda: "yt-dlp is up to date")
    res = client.post("/api/tools/update-ytdlp")
    assert res.status_code == 200 and res.json() == {"output": "yt-dlp is up to date"}
