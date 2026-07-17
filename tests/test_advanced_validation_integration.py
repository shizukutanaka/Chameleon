"""Integration tests for wiring DeepFileInspector into the default batch path.

CHARTER §5/§9: the deep file inspector must actually run on the default
batch/load path, not just exist. These tests pin three behaviours:

1. A real WAV passes inspection and survives `_filter_safe_files`.
2. A file with a .wav extension whose bytes are an executable/script is
   rejected (magic-number mismatch).
3. A *real* WAV whose PCM payload coincidentally contains a "suspicious" byte
   sequence still passes — the scan only warns, it never rejects. This is the
   false-positive guard that keeps the gate safe for legitimate audio.
"""

import struct
import wave
from pathlib import Path

from tests._helpers import write_sine_wave

from advanced_validation import DeepFileInspector


def _write_wav_with_payload(path: Path, payload: bytes) -> Path:
    """Write a valid mono 16-bit WAV whose sample data embeds ``payload``."""
    path = Path(path)
    # Pad the payload to an even length so it forms whole 16-bit samples.
    if len(payload) % 2:
        payload += b"\x00"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        # A little silence, the payload bytes, then a little more silence.
        handle.writeframes(b"\x00\x00" * 100 + payload + b"\x00\x00" * 100)
    return path


# --- 1. real WAV passes -----------------------------------------------------

def test_real_wav_is_valid(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = DeepFileInspector().validate_for_processing(wav)
    assert result.is_valid, result.errors
    assert result.file_type == "WAV"


def test_real_wav_survives_filter(tmp_path):
    from main import AudioProcessor

    wav = write_sine_wave(tmp_path / "tone.wav")
    processor = AudioProcessor()
    assert processor._filter_safe_files([str(wav)]) == [str(wav)]


# --- 2. disguised non-WAV is rejected ---------------------------------------

def test_disguised_executable_is_rejected(tmp_path):
    for name, magic in (
        ("dos.wav", b"MZ\x90\x00" + b"\x00" * 64),
        ("elf.wav", b"\x7fELF" + b"\x00" * 64),
        ("script.wav", b"#!/bin/sh\nrm -rf /\n"),
    ):
        fake = tmp_path / name
        fake.write_bytes(magic)
        result = DeepFileInspector().validate_for_processing(fake)
        assert not result.is_valid, f"{name} should be rejected"
        assert result.errors


def test_disguised_executable_is_filtered_out(tmp_path):
    from main import AudioProcessor

    good = write_sine_wave(tmp_path / "good.wav")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"MZ\x90\x00" + b"\x00" * 128)

    processor = AudioProcessor()
    safe = processor._filter_safe_files([str(good), str(bad)])
    assert str(good) in safe
    assert str(bad) not in safe


# --- 3. false-positive guard ------------------------------------------------

def test_real_wav_with_suspicious_payload_still_passes(tmp_path):
    """A genuine WAV whose audio data happens to contain bytes like ``MZ`` or
    ``import `` must NOT be rejected — those patterns are warnings, not errors."""
    wav = _write_wav_with_payload(
        tmp_path / "noisy.wav", b"MZ here is import os; eval( something )"
    )
    result = DeepFileInspector().validate_for_processing(wav)
    assert result.is_valid, result.errors
    # The scan should have noticed the pattern (proving it ran) but only warned.
    assert any("Suspicious pattern" in w for w in result.warnings)


def test_suspicious_payload_wav_survives_filter(tmp_path):
    from main import AudioProcessor

    wav = _write_wav_with_payload(tmp_path / "noisy.wav", b"MZ import os eval(")
    processor = AudioProcessor()
    assert processor._filter_safe_files([str(wav)]) == [str(wav)]


# --- method contract --------------------------------------------------------

def test_validate_for_processing_skips_checksum(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = DeepFileInspector().validate_for_processing(wav)
    assert result.checksum_sha256 == ""
