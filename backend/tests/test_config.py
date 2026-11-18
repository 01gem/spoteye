"""APP_HOME and bundle paths (from source, SPOTEYE_HOME, packaged) and .env reloading."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app import config


@pytest.fixture
def frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pretend to be the PyInstaller build, unpacked to tmp_path/bundle."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(config, "BUNDLE_DIR", bundle)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("SPOTEYE_HOME", raising=False)
    return bundle


def test_dev_home_is_backend_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPOTEYE_HOME", raising=False)
    assert not config.is_frozen()
    assert config.resolve_app_home() == config.BACKEND_DIR
    assert config.resolve_bundle_dir() == config.BACKEND_DIR.parent


def test_dev_paths_are_unchanged() -> None:
    if config.APP_HOME != config.BACKEND_DIR:
        pytest.skip("SPOTEYE_HOME is set for this test run")
    assert config.DEFAULT_DB_PATH == config.BACKEND_DIR / "spoteye.db"
    assert config.CACHE_PATH == config.BACKEND_DIR / ".cache"
    assert config.SIGN_IN_META_PATH == config.BACKEND_DIR / ".cache-meta.json"
    assert config.FRONTEND_DIST == config.BACKEND_DIR.parent / "frontend" / "dist"
    assert config.DEFAULT_OUTPUT_DIR == r"D:\Music\Spoteye"
    assert config.BIN_DIR is None


def test_spoteye_home_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frozen: Path) -> None:
    monkeypatch.setenv("SPOTEYE_HOME", str(tmp_path / "home"))
    assert config.resolve_app_home() == tmp_path / "home"


def test_frozen_home_is_localappdata(tmp_path: Path, frozen: Path) -> None:
    assert config.resolve_app_home() == tmp_path / "local" / "Spoteye"
    assert config.resolve_bundle_dir() == frozen


def test_bundled_client_id_fills_an_empty_setting(frozen: Path, env_file: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    (frozen / "defaults.json").write_text(json.dumps({"spotify_client_id": "a" * 32}), "utf-8")
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    assert config.load_settings().spotify_client_id == "a" * 32
    env_file.write_text(f"SPOTIFY_CLIENT_ID={'b' * 32}\n", encoding="utf-8")
    assert config.load_settings().spotify_client_id == "b" * 32


def test_no_bundled_client_id_from_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "defaults.json").write_text(json.dumps({"spotify_client_id": "a" * 32}), "utf-8")
    monkeypatch.setattr(config, "BUNDLE_DIR", tmp_path)
    assert config.bundled_client_id() == ""


def test_bad_defaults_json_is_ignored(frozen: Path) -> None:
    (frozen / "defaults.json").write_text("not json", encoding="utf-8")
    assert config.bundled_client_id() == ""


def test_edited_env_applies_without_restart(env_file: Path) -> None:
    env_file.write_text("MAX_WORKERS=2\nOUTPUT_DIR=D:\\A\n", encoding="utf-8")
    assert config.load_settings().max_workers == 2
    env_file.write_text("MAX_WORKERS=5\nOUTPUT_DIR=D:\\B\n", encoding="utf-8")
    settings = config.load_settings()
    assert (settings.max_workers, settings.output_dir) == (5, Path("D:\\B"))
