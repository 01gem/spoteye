"""Keep tests away from the real backend/.env.

load_settings uses load_dotenv(override=True), so the real file would beat the variables the
tests set (e.g. OUTPUT_DIR) and would leak into os.environ for later tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from app import config


@pytest.fixture(autouse=True)
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", path)
    saved = dict(os.environ)
    yield path
    os.environ.clear()
    os.environ.update(saved)
