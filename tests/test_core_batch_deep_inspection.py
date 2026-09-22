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


# ----------------------------------------------------- sync gather: suffix --
#
# The gather used a literal "*.wav"/"**/*.wav" glob; glob's match is
# case-sensitive, so a lone "A.WAV" produced "No WAV files found" even though
# the suffix test right below accepts it. The gather now globs "*" and lets
# the lowered-suffix filter decide (same fix the CLI batch needed).

def test_process_directory_gathers_uppercase_suffix(tmp_path):
    write_sine_wave(tmp_path / "A.WAV", duration=0.01, amplitude=0.5)
    processor = core.BatchProcessor()
    results = processor.process_directory(str(tmp_path), "analyze")
    assert results[0].success, results[0].message


def test_process_directory_async_gathers_uppercase_suffix(tmp_path):
    write_sine_wave(tmp_path / "A.WAV", duration=0.01, amplitude=0.5)
    processor = core.BatchProcessor()
    results = asyncio.run(processor.process_directory_async(str(tmp_path), "analyze"))
    assert results[0].success, results[0].message


# --------------------------------------------- summary["errors"] once only --
#
# An exception inside _execute_operation appended its analysis to
# summary["errors"] in the except block, then the failed-result branch
# appended the same analysis again via result.data -- one failure, two
# entries.

def test_exception_failure_records_one_error_entry(tmp_path):
    write_sine_wave(tmp_path / "a.wav", duration=0.01, amplitude=0.5)
    processor = core.BatchProcessor()

    def boom(operation, file_path, options):
        raise OSError("disk exploded")

    processor._execute_operation = boom
    results = processor.process_directory(str(tmp_path), "analyze")
    summary = results[-1].data["summary"]
    assert summary["failed"] == 1
    assert len(summary["errors"]) == 1


# ------------------------------------------------- degradation: failed-only --
#
# processed == 0 with failed > 0 computed failure_rate 0.0, so a run that
# only ever failed was indistinguishable from an idle one -- the level stayed
# "full" with no reason recorded.

def test_degradation_treats_failed_only_run_as_high_failure_rate():
    manager = core.ServiceDegradationManager()
    outcome = manager.evaluate({"processed": 0, "failed": 3, "errors": [], "timed_out": False})
    assert outcome["current_level"] == "minimal"
    assert "high_failure_rate" in outcome["reasons"]


def test_degradation_idle_run_still_stabilises():
    manager = core.ServiceDegradationManager()
    outcome = manager.evaluate({"processed": 0, "failed": 0, "errors": [], "timed_out": False})
    assert outcome["current_level"] == "full"
    assert "stabilised" in outcome["reasons"]


# ------------------------------------------- temp cleanup: files, not dirs --
#
# _cleanup_temp_files globbed "chameleon_*" and recursed into matching
# directories -- which includes StateRecoveryManager's chameleon_state
# fallback. A disk-full retry wiped the batch-state snapshots recovery is
# meant to preserve.

def test_cleanup_temp_files_preserves_chameleon_state_dir(tmp_path, monkeypatch):
    state_dir = tmp_path / "chameleon_state"
    state_dir.mkdir()
    state_file = state_dir / "batch_state_keep.json"
    state_file.write_text("{}")
    junk_file = tmp_path / "chameleon_junk.bin"
    junk_file.write_bytes(b"x")
    junk_dir_file = tmp_path / "chameleon_other" / "nested.bin"
    junk_dir_file.parent.mkdir()
    junk_dir_file.write_bytes(b"y")

    monkeypatch.setattr(core.tempfile, "gettempdir", lambda: str(tmp_path))
    core.RecoveryManager()._cleanup_temp_files()

    assert state_file.exists()
    assert junk_dir_file.exists()  # directories are no longer recursed into
    assert not junk_file.exists()
