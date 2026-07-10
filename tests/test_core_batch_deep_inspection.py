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
# NOTE: process_directory's per-file execution path independently calls
# self._execute_operation(...), a method that does not exist on BatchProcessor
# (only the async _execute_operation_async exists) — a pre-existing bug
# unrelated to the DeepFileInspector wiring, found while writing these tests.
# It has zero callers anywhere in the codebase (confirmed via grep), so these
# tests check counts only — proving the *gathering/filtering* stage works —
# rather than per-file success, which the unrelated bug always breaks.
# Recorded in CHARTER §9; not fixed here (out of scope for this parity pass).

def test_real_wav_survives_process_directory_gathering(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    processor = core.BatchProcessor()

    # One per-file result plus a trailing batch-summary result.
    results = processor.process_directory(str(tmp_path), "analyze")

    assert len(results) == 2


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

    # Per tests/test_batch.py's established convention: each entry is a
    # (ProcessingResult, attempt_count) tuple on the success path.
    assert len(results) == 1
    assert results[0][0].success
