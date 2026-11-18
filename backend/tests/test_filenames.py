from __future__ import annotations

from pathlib import Path

import pytest

from app.services.filenames import MAX_FOLDER_LEN, MAX_PATH_LEN, MIN_STEM_LEN, build_filename
from app.services.filenames import existing_output, safe_filename
from app.services.job_setup import job_target
from app.services.presets import Preset
from app.services.spotify_client import TrackMeta


@pytest.mark.parametrize("name", ["CON", "nul", "COM1", "LPT9", "Aux.mp3"])
def test_reserved_names_are_prefixed(name: str) -> None:
    assert safe_filename(name) == f"_{name}"


def test_non_reserved_lookalike_is_untouched() -> None:
    assert safe_filename("CONTROL") == "CONTROL"


def test_illegal_characters_are_removed() -> None:
    assert safe_filename('a<b>c:d"e/f\\g|h?i*j\x01k') == "abcdefghijk"


@pytest.mark.parametrize(("raw", "expected"), [("Hello...", "Hello"), ("Hello. . ", "Hello")])
def test_trailing_dots_and_spaces_are_stripped(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected


def test_whitespace_is_collapsed() -> None:
    assert safe_filename("  a \t  b\n c  ") == "a b c"


def test_length_is_truncated() -> None:
    assert len(safe_filename("x" * 300)) == 150
    assert safe_filename("abcdefghijkl", max_len=5) == "abcde"


def make_track(title: str = "Song") -> TrackMeta:
    return TrackMeta(spotify_id="id", title=title, artists=["Artist", "Guest"])


def test_numbered_filename() -> None:
    assert build_filename(make_track(), "mp3", 3) == "03 - Artist - Song.mp3"


def test_unnumbered_filename() -> None:
    assert build_filename(make_track(), "opus", None) == "Artist - Song.opus"


def test_long_filename_keeps_extension() -> None:
    name = build_filename(make_track("T" * 400), "m4a", 12)
    assert name.endswith(".m4a")
    assert len(name) <= 150


LONG_FOLDER = Path("D:/" + "F" * 80) / ("G" * 80)


def test_long_title_in_long_folder_fits_path_limit() -> None:
    name = build_filename(make_track("T" * 200), "opus", 7, LONG_FOLDER)
    assert len(str(LONG_FOLDER / name)) <= MAX_PATH_LEN
    assert name.startswith("07 - Artist - TTT") and name.endswith(".opus")


def test_short_names_are_unchanged_with_a_folder() -> None:
    assert build_filename(make_track(), "mp3", 3, LONG_FOLDER) == "03 - Artist - Song.mp3"


def test_stem_is_never_shorter_than_minimum() -> None:
    name = build_filename(make_track("T" * 200), "mp3", 1, Path("D:/" + "F" * 250))
    assert len(name) == MIN_STEM_LEN + len(".mp3")


def test_existing_output_finds_capped_and_legacy_names(tmp_path: Path) -> None:
    # A 100-char folder: the legacy 150-char name still fits Windows' 260, the capped one is shorter.
    room = 100 - len(str(tmp_path)) - 1
    if room < 1:
        pytest.skip("temp folder path too long for this test")
    folder = tmp_path / ("F" * room)
    folder.mkdir()
    track = make_track("T" * 200)
    capped, legacy = build_filename(track, "opus", 1, folder), build_filename(track, "opus", 1)
    assert capped != legacy
    for name in (capped, legacy):
        path = folder / name
        path.write_bytes(b"audio")
        assert existing_output(track, Preset.BEST, folder, 1) == path
        path.unlink()


def test_playlist_folder_name_is_capped() -> None:
    assert len(job_target(Path("D:/Music"), "P" * 200).name) == MAX_FOLDER_LEN
