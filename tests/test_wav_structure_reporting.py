"""_validate_wav_structure must report every problem it finds, not just the
last one: repeated assignment to metadata["warning"] / ["error"] overwrote
earlier findings, so a file with three problems reported only the third.

Reproduction basis (pre-fix): a float-format 9-channel 12345 Hz WAV reported
only "Non-standard sample rate"; a WAV missing both fmt and data reported
only "Missing data chunk"."""

import struct

import pytest

from advanced_validation import DeepFileInspector


def _wav(fmt_chunk: bytes = b"", extra_chunks: bytes = b"") -> bytes:
    body = b"WAVE" + fmt_chunk + extra_chunks
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _fmt_chunk(format_tag=1, channels=1, sample_rate=8000, bits=16):
    block_align = channels * bits // 8
    fmt = (struct.pack("<HHIIHH", format_tag, channels, sample_rate,
                     sample_rate * block_align, block_align, bits))
    return b"fmt " + struct.pack("<I", len(fmt)) + fmt


def test_every_format_warning_is_reported(tmp_path):
    # Three simultaneous findings: float format, 9 channels, odd sample rate.
    wav = tmp_path / "weird.wav"
    wav.write_bytes(_wav(_fmt_chunk(format_tag=3, channels=9,
                                    sample_rate=12345, bits=32),
                         b"data" + struct.pack("<I", 0)))
    meta = DeepFileInspector()._validate_wav_structure(wav)
    warnings = meta.get("warnings", [])
    assert "Non-PCM format: 3" in warnings
    assert "Unusual channel count: 9" in warnings
    assert "Non-standard sample rate: 12345" in warnings


def test_missing_fmt_and_data_both_reported(tmp_path):
    wav = tmp_path / "empty.wav"
    wav.write_bytes(_wav(extra_chunks=b"JUNK" + struct.pack("<I", 0)))
    meta = DeepFileInspector()._validate_wav_structure(wav)
    errors = meta.get("errors", [])
    assert "Missing fmt chunk" in errors
    assert "Missing data chunk" in errors


def test_healthy_wav_reports_no_problems(tmp_path):
    wav = tmp_path / "ok.wav"
    wav.write_bytes(_wav(_fmt_chunk(), b"data" + struct.pack("<I", 0)))
    meta = DeepFileInspector()._validate_wav_structure(wav)
    assert "warnings" not in meta
    assert "errors" not in meta
    assert meta["format_tag"] == 1


def test_truncated_header_reports_error(tmp_path):
    wav = tmp_path / "tiny.wav"
    wav.write_bytes(b"RIFF\x00\x00")
    meta = DeepFileInspector()._validate_wav_structure(wav)
    assert meta["error"] == "Truncated RIFF header"
