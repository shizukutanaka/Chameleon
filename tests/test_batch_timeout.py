"""CHAMELEON_TIMEOUT wiring and state-directory laziness.

Two defects found by re-deriving expected behavior from first principles:

* ``DEFAULT_OPERATION_TIMEOUT`` was an unconditional 30s cap on a batch's
  *total* wall-clock time (not per file), silently truncating legitimate
  batches. Worse, the CLI batch path never consumed it at all — the
  documented knob had no wire. Now: default 0 (no cap), explicit
  ``CHAMELEON_TIMEOUT`` honored in both sequential and parallel
  ``AudioProcessor.batch_process`` paths, unprocessed files marked
  ``kind="timeout"`` instead of silently dropped, and the CLI prints a
  stderr warning when the cap fires.

* ``StateRecoveryManager.__init__`` ran ``mkdir`` eagerly. Because
  ``BatchProcessor`` is a module-level singleton, every ``import core``
  (i.e. every CLI invocation, including ``--help``) created
  ``~/.chameleon_state`` — a filesystem write the user never asked for.
  The directory is now created lazily on the first ``record_state()``.
"""

import asyncio
import sys

import pytest

import core
import main
from tests._helpers import write_sine_wave


def _processor(parallel=False):
    proc = main.AudioProcessor()
    proc.config.parallel = parallel
    return proc


# -- CHAMELEON_TIMEOUT parsing ------------------------------------------------

def test_determine_timeout_zero_disables_cap(monkeypatch, recwarn):
    monkeypatch.setenv("CHAMELEON_TIMEOUT", "0")
    assert core._determine_timeout() == 0
    assert not recwarn.list  # 0 is a valid setting, not a parse failure


def test_determine_timeout_honors_positive_int(monkeypatch):
    monkeypatch.setenv("CHAMELEON_TIMEOUT", "120")
    assert core._determine_timeout() == 120


def test_determine_timeout_invalid_warns_and_uses_default(monkeypatch):
    monkeypatch.setenv("CHAMELEON_TIMEOUT", "banana")
    with pytest.warns(UserWarning):
        assert core._determine_timeout() == core.DEFAULT_OPERATION_TIMEOUT


def test_default_operation_timeout_is_uncapped():
    # An unconditional cap silently truncated batches; the default is no cap.
    assert core.DEFAULT_OPERATION_TIMEOUT == 0


# -- batch_process timeout enforcement ----------------------------------------

def test_batch_timeout_marks_unprocessed_files_sequential(tmp_path):
    files = [write_sine_wave(tmp_path / f"{i}.wav", duration=0.05)
             for i in range(5)]

    results = _processor().batch_process(
        [str(f) for f in files], "analyze", timeout_seconds=1e-9)

    assert len(results) == 5
    timed_out = [r for r in results if r.get("kind") == "timeout"]
    assert timed_out, results
    assert all("batch timeout" in r["error"] for r in timed_out)


def test_batch_timeout_marks_unprocessed_files_parallel(tmp_path):
    files = [write_sine_wave(tmp_path / f"{i}.wav", duration=0.05)
             for i in range(6)]

    results = _processor(parallel=True).batch_process(
        [str(f) for f in files], "analyze", timeout_seconds=1e-9)

    assert len(results) == 6
    assert any(r.get("kind") == "timeout" for r in results)


def test_batch_timeout_zero_processes_everything(tmp_path):
    files = [write_sine_wave(tmp_path / f"{i}.wav", duration=0.05)
             for i in range(3)]

    results = _processor().batch_process(
        [str(f) for f in files], "analyze", timeout_seconds=0)

    assert len(results) == 3
    assert all("error" not in r for r in results), results


def test_batch_timeout_default_uses_env_resolution(tmp_path, monkeypatch):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.05)
    monkeypatch.setattr(core, "OPERATION_TIMEOUT", 0)

    results = _processor().batch_process([str(wav)], "analyze")

    assert len(results) == 1
    assert "error" not in results[0]


def test_cli_batch_timeout_warns_on_stderr(tmp_path, monkeypatch, capsys):
    for i in range(4):
        write_sine_wave(tmp_path / f"{i}.wav", duration=0.05)
    monkeypatch.setattr(core, "OPERATION_TIMEOUT", 1e-9)
    monkeypatch.setattr(
        sys, "argv", ["main.py", "batch", str(tmp_path), "analyze"])
    monkeypatch.chdir(tmp_path)

    exit_code = asyncio.run(main.main())

    captured = capsys.readouterr()
    assert "CHAMELEON_TIMEOUT" in captured.err
    assert exit_code != 0
