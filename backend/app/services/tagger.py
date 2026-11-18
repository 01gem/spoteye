"""Write Spotify metadata and cover art into mp3, m4a, opus, ogg and flac files with mutagen."""

from __future__ import annotations

import base64
from pathlib import Path

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK, TSRC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from app.services.spotify_client import TrackMeta

COVER_MIME: str = "image/jpeg"
FRONT_COVER: int = 3
MP4_ISRC_KEY: str = "----:com.apple.iTunes:ISRC"


def tag_file(
    path: Path, track: TrackMeta, cover: bytes | None, track_no_override: int | None = None
) -> None:
    """Tag path in place. Raises ValueError for unsupported extensions."""
    track_no = track_no_override if track_no_override is not None else track.track_number
    ext = path.suffix.lower()
    if ext == ".mp3":
        _tag_mp3(path, track, cover, track_no)
    elif ext == ".m4a":
        _tag_m4a(path, track, cover, track_no)
    elif ext in (".opus", ".ogg"):
        _tag_ogg(path, track, cover, track_no)
    elif ext == ".flac":
        _tag_flac(path, track, cover, track_no)
    else:
        raise ValueError(f"Unsupported file type for tagging: {path.suffix or path.name}")


def _artist(track: TrackMeta) -> str:
    return ", ".join(track.artists)


def _tag_mp3(path: Path, track: TrackMeta, cover: bytes | None, track_no: int) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.add(TIT2(encoding=3, text=track.title))
    tags.add(TPE1(encoding=3, text=_artist(track)))
    tags.add(TALB(encoding=3, text=track.album))
    if track.album_artist:
        tags.add(TPE2(encoding=3, text=track.album_artist))
    if track_no:
        tags.add(TRCK(encoding=3, text=str(track_no)))
    if track.disc_number:
        tags.add(TPOS(encoding=3, text=str(track.disc_number)))
    if track.release_date:
        tags.add(TDRC(encoding=3, text=track.release_date))
    if track.isrc:
        tags.add(TSRC(encoding=3, text=track.isrc))
    if cover:
        tags.add(APIC(encoding=3, mime=COVER_MIME, type=FRONT_COVER, desc="Cover", data=cover))
    tags.save(path)


def _tag_m4a(path: Path, track: TrackMeta, cover: bytes | None, track_no: int) -> None:
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    assert tags is not None
    tags["\xa9nam"] = [track.title]
    tags["\xa9ART"] = [_artist(track)]
    tags["\xa9alb"] = [track.album]
    if track.album_artist:
        tags["aART"] = [track.album_artist]
    if track_no:
        tags["trkn"] = [(track_no, 0)]
    if track.disc_number:
        tags["disk"] = [(track.disc_number, 0)]
    if track.release_date:
        tags["\xa9day"] = [track.release_date]
    if cover:
        tags["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
    if track.isrc:
        tags[MP4_ISRC_KEY] = [MP4FreeForm(track.isrc.encode("utf-8"))]
    audio.save()


def _vorbis_fields(track: TrackMeta, track_no: int) -> dict[str, str]:
    """Vorbis comments shared by opus, ogg and flac (empty values are skipped)."""
    fields: dict[str, str] = {
        "TITLE": track.title,
        "ARTIST": _artist(track),
        "ALBUM": track.album,
        "ALBUMARTIST": track.album_artist,
        "TRACKNUMBER": str(track_no) if track_no else "",
        "DISCNUMBER": str(track.disc_number) if track.disc_number else "",
        "DATE": track.release_date,
        "ISRC": track.isrc or "",
    }
    return {key: value for key, value in fields.items() if value}


def _picture(cover: bytes) -> Picture:
    picture = Picture()
    picture.type = FRONT_COVER
    picture.mime = COVER_MIME
    picture.desc = "Cover"
    picture.data = cover
    return picture


def _tag_ogg(path: Path, track: TrackMeta, cover: bytes | None, track_no: int) -> None:
    """Opus or Vorbis in an Ogg container (.opus or .ogg)."""
    audio = mutagen.File(path)
    if not isinstance(audio, (OggOpus, OggVorbis)):
        raise ValueError(f"{path.name} is not an Ogg Opus/Vorbis file")
    for key, value in _vorbis_fields(track, track_no).items():
        audio[key] = [value]
    if cover:
        encoded = base64.b64encode(_picture(cover).write()).decode("ascii")
        audio["METADATA_BLOCK_PICTURE"] = [encoded]
    audio.save()


def _tag_flac(path: Path, track: TrackMeta, cover: bytes | None, track_no: int) -> None:
    audio = FLAC(path)
    for key, value in _vorbis_fields(track, track_no).items():
        audio[key] = [value]
    if cover:
        audio.clear_pictures()
        audio.add_picture(_picture(cover))
    audio.save()
