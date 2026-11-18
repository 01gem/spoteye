"""Round-trip tagging on real files generated with ffmpeg (skipped if ffmpeg is missing)."""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.flac import Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus

from app.services.spotify_client import TrackMeta
from app.services.tagger import MP4_ISRC_KEY, tag_file

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH")

ENCODERS: dict[str, list[str]] = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "128k"],
    "m4a": ["-c:a", "aac", "-b:a", "128k"],
    "opus": ["-c:a", "libopus", "-b:a", "64k"],
}
TRACK = TrackMeta(
    spotify_id="id",
    title="Café Song",
    artists=["Artist One", "Artist Two"],
    album="Album",
    album_artist="Artist One",
    track_number=4,
    disc_number=1,
    release_date="2020-05-01",
    isrc="USABC2000001",
)


def _ffmpeg(*args: str) -> None:
    assert FFMPEG is not None
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def _make_cover(tmp_path: Path) -> bytes:
    cover = tmp_path / "cover.jpg"
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=16x16", "-frames:v", "1", str(cover))
    return cover.read_bytes()


def _read_back(path: Path) -> tuple[str, str, str, bytes]:
    """Return (title, artist, isrc, cover bytes) as stored in the file."""
    ext = path.suffix
    if ext == ".mp3":
        id3 = ID3(path)
        return (id3["TIT2"].text[0], id3["TPE1"].text[0], id3["TSRC"].text[0],
                id3.getall("APIC")[0].data)  # fmt: skip
    if ext == ".m4a":
        tags = MP4(path).tags
        assert tags is not None
        return (tags["\xa9nam"][0], tags["\xa9ART"][0], bytes(tags[MP4_ISRC_KEY][0]).decode(),
                bytes(tags["covr"][0]))  # fmt: skip
    audio = OggOpus(path)
    picture = Picture(base64.b64decode(audio["metadata_block_picture"][0]))
    return audio["title"][0], audio["artist"][0], audio["isrc"][0], picture.data


@pytest.mark.parametrize("ext", ["mp3", "m4a", "opus"])
def test_tag_round_trip(tmp_path: Path, ext: str) -> None:
    audio_path = tmp_path / f"silence.{ext}"
    _ffmpeg("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "2",
            *ENCODERS[ext], str(audio_path))  # fmt: skip
    cover = _make_cover(tmp_path)

    tag_file(audio_path, TRACK, cover)

    title, artist, isrc, stored_cover = _read_back(audio_path)
    assert title == "Café Song"
    assert artist == "Artist One, Artist Two"
    assert isrc == "USABC2000001"
    assert stored_cover == cover


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        tag_file(tmp_path / "song.flac", TRACK, None)
