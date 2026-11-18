"""Output presets: which YouTube stream to fetch and how to encode it.

Lossy sources are never turned into FLAC/WAV: every plan ends in opus, m4a or mp3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Preset(StrEnum):
    BEST = "best"
    AAC256 = "aac256"
    MP3_320 = "mp3-320"
    MP3_V0 = "mp3-v0"


@dataclass(frozen=True)
class PresetSpec:
    format_selector: str
    label: str


@dataclass(frozen=True)
class OutputPlan:
    ext: str
    ffmpeg_args: list[str]
    upscaled: bool


PRESET_SPECS: dict[Preset, PresetSpec] = {
    Preset.BEST: PresetSpec("bestaudio", "Original stream (no re-encode)"),
    Preset.AAC256: PresetSpec("141/bestaudio[ext=m4a]/bestaudio", "AAC 256k"),
    Preset.MP3_320: PresetSpec("bestaudio", "MP3 320k (compatibility; quality <= source)"),
    Preset.MP3_V0: PresetSpec("bestaudio", "MP3 V0"),
}

COPY: list[str] = ["-c:a", "copy"]
_CODEC_BY_EXT: dict[str, str] = {"opus": "opus", "m4a": "aac", "mp3": "mp3"}


def is_opus(acodec: str) -> bool:
    return acodec.lower().startswith("opus")


def is_aac(acodec: str) -> bool:
    return acodec.lower().startswith(("mp4a", "aac"))


def possible_exts(preset: Preset) -> tuple[str, ...]:
    """Every extension plan_output can produce for this preset (used for skip checks)."""
    if preset is Preset.BEST:
        return ("opus", "m4a")
    if preset is Preset.AAC256:
        return ("m4a",)
    return ("mp3",)


def plan_output(preset: Preset, src_acodec: str, src_abr: float | None) -> OutputPlan:
    """Decide the output container and ffmpeg codec arguments for a downloaded stream."""
    abr = src_abr or 0.0
    if preset is Preset.BEST:
        if is_opus(src_acodec):
            return OutputPlan("opus", list(COPY), False)
        if is_aac(src_acodec):
            return OutputPlan("m4a", list(COPY), False)
        return OutputPlan("opus", ["-c:a", "libopus", "-b:a", "160k"], False)
    if preset is Preset.AAC256:
        if is_aac(src_acodec) and abr >= 250:
            return OutputPlan("m4a", list(COPY), False)
        return OutputPlan("m4a", ["-c:a", "aac", "-b:a", "256k"], abr < 250)
    if preset is Preset.MP3_320:
        return OutputPlan("mp3", ["-c:a", "libmp3lame", "-b:a", "320k"], abr < 320)
    return OutputPlan("mp3", ["-c:a", "libmp3lame", "-q:a", "0"], False)


def describe_source(acodec: str, abr: float | None) -> str:
    """Short label for a downloaded stream, e.g. "opus 135k"."""
    name = "aac" if is_aac(acodec) else (acodec.split(".")[0] or "unknown")
    return f"{name} {round(abr)}k" if abr else name


def describe_output(plan: OutputPlan) -> str:
    """Short label for an output plan, e.g. "mp3 320k", "opus copy", "mp3 V0"."""
    codec = _CODEC_BY_EXT.get(plan.ext, plan.ext)
    args = plan.ffmpeg_args
    if args == COPY:
        return f"{codec} copy"
    if "-b:a" in args:
        return f"{codec} {args[args.index('-b:a') + 1]}"
    if "-q:a" in args:
        return f"{codec} V{args[args.index('-q:a') + 1]}"
    return codec
