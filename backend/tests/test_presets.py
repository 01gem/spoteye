from __future__ import annotations

import itertools

from app.services.presets import (
    COPY,
    Preset,
    describe_output,
    describe_source,
    plan_output,
    possible_exts,
)

CODECS = ["opus", "mp4a.40.2", "aac", "vorbis", "flac", "pcm_s16le", ""]
BITRATES: list[float | None] = [None, 48.0, 128.0, 160.0, 256.0, 320.0]


def test_best_opus_source_is_copied_to_opus() -> None:
    plan = plan_output(Preset.BEST, "opus", 135.0)
    assert plan.ext == "opus"
    assert plan.ffmpeg_args == COPY
    assert plan.upscaled is False


def test_best_unknown_codec_reencodes_to_opus() -> None:
    plan = plan_output(Preset.BEST, "vorbis", 128.0)
    assert plan.ext == "opus"
    assert plan.ffmpeg_args == ["-c:a", "libopus", "-b:a", "160k"]


def test_aac256_from_aac_256_is_copied_not_upscaled() -> None:
    plan = plan_output(Preset.AAC256, "mp4a.40.2", 256.0)
    assert plan.ext == "m4a"
    assert plan.ffmpeg_args == COPY
    assert plan.upscaled is False


def test_aac256_from_aac_128_is_upscaled() -> None:
    plan = plan_output(Preset.AAC256, "mp4a.40.2", 129.5)
    assert plan.ffmpeg_args == ["-c:a", "aac", "-b:a", "256k"]
    assert plan.upscaled is True


def test_mp3_320_from_opus_160_is_upscaled() -> None:
    plan = plan_output(Preset.MP3_320, "opus", 160.0)
    assert plan.ext == "mp3"
    assert plan.upscaled is True


def test_no_plan_is_lossless_and_ext_is_predicted() -> None:
    for preset, codec, abr in itertools.product(Preset, CODECS, BITRATES):
        plan = plan_output(preset, codec, abr)
        assert plan.ext not in {"flac", "wav"}, (preset, codec, abr)
        assert plan.ext in possible_exts(preset), (preset, codec, abr)


def test_labels() -> None:
    assert describe_source("mp4a.40.2", 129.4) == "aac 129k"
    assert describe_source("opus", None) == "opus"
    assert describe_output(plan_output(Preset.MP3_320, "opus", 160.0)) == "mp3 320k"
    assert describe_output(plan_output(Preset.MP3_V0, "opus", 160.0)) == "mp3 V0"
    assert describe_output(plan_output(Preset.BEST, "opus", 160.0)) == "opus copy"
