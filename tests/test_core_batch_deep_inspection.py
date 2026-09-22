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
    # The async path now appends the same batch-summary row as the sync
    # process_directory, so a filtered-out executable yields 1 per-file + 1
    # summary = 2 results.
    assert len(results) == 2
    assert results[0].success


# ------------------------------------------------- sync/async contract drift --
#
# process_directory_async documents the same contract as process_directory,
# but the two had drifted (audit 41): the async scan dispatched on the raw
# operation string (so 'NORMALIZE' validated then failed every file),
# followed symlinks the sync scan refuses, and never validated output_dir
# or the numeric bounds. validate_directory also *raises* SecurityError
# rather than returning a bool, so unsafe directories escaped as raw
# exceptions on both paths instead of the documented error result.

def test_async_batch_dispatches_normalized_operation(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    out = tmp_path / "out"
    processor = core.BatchProcessor()
    results = asyncio.run(
        processor.process_directory_async(str(tmp_path), "  NoRmAlIzE  ",
                                          output_dir=str(out)))
    per_file = results[:-1]
    assert per_file and all(r.success for r in per_file)


def test_async_scan_does_not_follow_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    write_sine_wave(outside / "target.wav")
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "linked.wav").symlink_to(outside / "target.wav")
    processor = core.BatchProcessor()
    results = asyncio.run(
        processor.process_directory_async(str(inside), "analyze"))
    # The dir contains only a symlink: the async scan must not follow it.
    assert len(results) == 1
    assert results[0].message == "No WAV files found"


def test_unsafe_directory_returns_error_result_not_exception(tmp_path):
    processor = core.BatchProcessor()
    sync_result = processor.process_directory("/tmp/../bad\x00dir", "analyze")
    async_result = asyncio.run(
        processor.process_directory_async("/tmp/../bad\x00dir", "analyze"))
    assert sync_result[0].success is False
    assert async_result[0].success is False
    assert "Invalid directory" in sync_result[0].message
    assert "Invalid directory" in async_result[0].message


def test_batch_bounds_match_per_op_bounds(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    processor = core.BatchProcessor()
    # normalize rejects target_peak <= 0 per file; the batch-level guard
    # must reject the same value up front, not fail every file downstream.
    result = processor.process_directory(
        str(tmp_path), "normalize", target_peak=0.0)
    assert result[0].success is False and "target_peak" in result[0].message
    result = processor.process_directory(
        str(tmp_path), "trim", threshold=1.0)
    assert result[0].success is False and "threshold" in result[0].message
    result = asyncio.run(processor.process_directory_async(
        str(tmp_path), "trim", threshold=0.0))
    assert result[0].success is False and "threshold" in result[0].message
