"""Tests for directory batch processing (core.batch_process_async)."""

import asyncio

from tests._helpers import write_sine_wave

import core


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

    # One per-file ProcessingResult plus the trailing batch-summary row --
    # the same contract the synchronous process_directory documents.
    assert len(results) == 4
    # Each entry is a ProcessingResult (batch_process_async no longer leaks
    # the internal (result, attempts) tuple -- see core.BatchProcessor).
    assert all(item.success for item in results), results
    summary = results[-1].data["summary"]
    assert summary["processed"] == 3 and summary["successful"] == 3
    assert len(list(out.glob("*.wav"))) == 3


def test_batch_analyze_reports_each_file(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    for name in ("x.wav", "y.wav"):
        write_sine_wave(src / name, duration=0.3)

    results = _run_batch(src, "analyze")

    assert len(results) == 3  # 2 files + batch summary
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
    # (1 per-file result + trailing batch summary.)
    assert len(results) == 2
    assert results[0].success is True


def _scoped_trusted_roots(monkeypatch, root):
    """Point the shared validator's lazy default at a roots config."""
    from security_validator import SecurityValidator
    monkeypatch.setenv("CHAMELEON_TRUSTED_ROOTS", str(root))
    monkeypatch.setattr(SecurityValidator, "_default_instance", None)


def test_sync_batch_output_dir_outside_trusted_roots_refused(tmp_path, monkeypatch):
    """validate_directory raises SecurityError, so `if not` on it was a dead
    check: an unsafe output_dir escaped process_directory as a raw exception
    instead of the intended 'Invalid output directory provided' result."""
    _scoped_trusted_roots(monkeypatch, tmp_path)
    src = tmp_path / "in"
    src.mkdir()
    write_sine_wave(src / "a.wav", duration=0.2, amplitude=4000)

    results = core.BatchProcessor().process_directory(
        str(src), "normalize", output_dir="/tmp")

    assert [r.success for r in results] == [False]
    assert results[0].message == "Invalid output directory provided"


def test_async_batch_output_dir_outside_trusted_roots_refused(tmp_path, monkeypatch):
    """The async gather honoured output_dir as a feature but skipped its
    validation entirely: under a roots policy it wrote the outputs anywhere
    while the sync path refused (verified: normalized_a.wav landed in /tmp)."""
    _scoped_trusted_roots(monkeypatch, tmp_path)
    src = tmp_path / "in"
    src.mkdir()
    write_sine_wave(src / "a.wav", duration=0.2, amplitude=4000)

    results = _run_batch(src, "normalize", output_dir="/tmp")

    assert [r.success for r in results] == [False]
    assert results[0].message == "Invalid output directory provided"


def test_sync_batch_input_dir_outside_trusted_roots_refused(tmp_path, monkeypatch):
    """Same dead `if not` on the input directory check."""
    _scoped_trusted_roots(monkeypatch, tmp_path)

    results = core.BatchProcessor().process_directory("/etc", "normalize")

    assert [r.success for r in results] == [False]
    assert results[0].message == "Invalid directory provided"
