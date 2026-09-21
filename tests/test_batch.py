"""Tests for directory batch processing (core.batch_process_async)."""

import asyncio

import pytest

from tests._helpers import write_sine_wave

import core


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path, monkeypatch):
    """Batch runs used to write ~2.8MB snapshots into the real
    ~/.chameleon_state on every suite run. Point them at tmp_path instead;
    the singleton is reset so each test's env dir actually takes effect."""
    monkeypatch.setenv("CHAMELEON_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(core, "_batch_processor", None)


def _run_batch(directory, operation, **kwargs):
    return asyncio.run(core.batch_process_async(str(directory), operation, **kwargs))


def test_batch_normalize_processes_all_files(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    for name in ("a.wav", "b.wav", "c.wav"):
        write_sine_wave(src / name, duration=0.3, amplitude=4000)

    results = _run_batch(src, "normalize", output_dir=str(out))

    assert len(results) == 3
    # Each entry is a ProcessingResult (batch_process_async no longer leaks
    # the internal (result, attempts) tuple -- see core.BatchProcessor).
    assert all(item.success for item in results), results
    assert len(list(out.glob("*.wav"))) == 3


def test_batch_analyze_reports_each_file(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    for name in ("x.wav", "y.wav"):
        write_sine_wave(src / name, duration=0.3)

    results = _run_batch(src, "analyze")

    assert len(results) == 2
    assert all(item.success for item in results), results


def test_batch_rejects_unknown_operation(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    write_sine_wave(src / "a.wav", duration=0.3)

    results = _run_batch(src, "definitely-not-an-operation")

    # Validation failures short-circuit with a bare ProcessingResult (no index).
    assert len(results) == 1
    assert results[0].success is False
    assert "Unsupported operation" in results[0].message


def test_batch_empty_directory_reports_no_files(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    results = _run_batch(empty, "analyze")

    # An empty directory is a graceful failure: one result with success=False
    # and a human-readable message, not an exception.
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].message  # non-empty message tells the user why


def test_batch_skips_unsupported_file_types(tmp_path):
    src = tmp_path / "mixed"
    src.mkdir()
    (src / "note.txt").write_text("not audio")
    (src / "image.png").write_bytes(b"\x89PNG")
    write_sine_wave(src / "real.wav", duration=0.2)

    results = _run_batch(src, "analyze")

    # Only the WAV should be processed; non-audio files are silently skipped.
    assert len(results) == 1
    assert results[0].success is True


def test_state_dir_created_on_record_not_on_construction(tmp_path, monkeypatch):
    """import core / BatchProcessor() must not create ~/.chameleon_state --
    the dir is made when a batch actually records state. Covers the
    module-level `_batch_processor = BatchProcessor()` side effect."""
    state_dir = tmp_path / "state"
    monkeypatch.setenv("CHAMELEON_STATE_DIR", str(state_dir))

    proc = core.BatchProcessor()
    assert not state_dir.exists()

    src = tmp_path / "in"
    src.mkdir()
    write_sine_wave(src / "a.wav", duration=0.3)
    results = proc.process_directory(str(src), "analyze")

    assert all(r.success for r in results)
    assert list(state_dir.glob("batch_state_*.json"))
