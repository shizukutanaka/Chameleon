"""Covers DeepFileInspector wiring into core.py's BatchProcessor — the parity
gap CHARTER §9 tracked ("main.py's _filter_safe_files has it; core.py's
BatchProcessor did not").

Same contract as tests/test_advanced_validation_integration.py (which covers
main.py's side): a real WAV passes, a disguised executable is rejected, and a
real WAV whose PCM payload coincidentally contains a suspicious byte pattern
still passes (the scan warns, never rejects — the false-positive guard).
"""

import asyncio
import wave
from pathlib import Path

import core
from tests._helpers import write_sine_wave


def _write_wav_with_payload(path: Path, payload: bytes) -> Path:
    path = Path(path)
    if len(payload) % 2:
        payload += b"\x00"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(b"\x00\x00" * 100 + payload + b"\x00\x00" * 100)
    return path


def test_deep_inspector_is_wired_into_core():
    assert core.HAS_DEEP_INSPECTOR is True


# --------------------------------------------------- sync process_directory --
#
# process_directory's per-file execution path previously called a
# nonexistent self._execute_operation(...), so every file was silently
# reported as failed (the AttributeError was swallowed by the per-file
# except). The sync _execute_operation now exists (mirrors the async twin),
# so these tests assert per-file *success*, not just gathering counts.

def test_real_wav_survives_process_directory_gathering(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    processor = core.BatchProcessor()

    # One per-file result plus a trailing batch-summary result.
    results = processor.process_directory(str(tmp_path), "analyze")

    assert len(results) == 2
    per_file = [r for r in results if isinstance(r.data, dict)
                and r.data.get("operation") == "analyze"]
    assert len(per_file) == 1 and per_file[0].success


def test_disguised_executable_is_filtered_from_process_directory(tmp_path):
    write_sine_wave(tmp_path / "good.wav")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"MZ\x90\x00" + b"\x00" * 128)
    processor = core.BatchProcessor()

    results = processor.process_directory(str(tmp_path), "analyze")

    # If the disguised executable had NOT been filtered, there would be 2
    # per-file results + 1 summary = 3. It's dropped at the gathering stage,
    # so the count matches the good-file-only case: 1 per-file + 1 summary.
    assert len(results) == 2


def test_suspicious_payload_wav_survives_process_directory_gathering(tmp_path):
    _write_wav_with_payload(tmp_path / "noisy.wav", b"MZ import os eval(")
    processor = core.BatchProcessor()

    results = processor.process_directory(str(tmp_path), "analyze")

    assert len(results) == 2


# ------------------------------------------- async batch_process_async API --

def test_disguised_executable_is_filtered_from_batch_process_async(tmp_path):
    write_sine_wave(tmp_path / "good.wav")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"\x7fELF" + b"\x00" * 128)

    results = asyncio.run(core.batch_process_async(str(tmp_path), "analyze"))

    # Each entry is a ProcessingResult (the internal (result, attempts) tuple
    # is no longer leaked -- see core.BatchProcessor._execute_operation_async).
    assert len(results) == 1
    assert results[0].success
