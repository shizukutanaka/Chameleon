"""Exercise the CLI's process exit codes (main.ExitCode) end-to-end.

These invoke ``main.py`` as a real subprocess so the assertions cover the
actual ``sys.exit(cli())`` wiring, not just the in-process return value of
``main()``.
"""

import subprocess
import sys
from pathlib import Path

from tests._helpers import write_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, MAIN_PY, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


def test_no_command_is_usage_error(tmp_path):
    result = _run(cwd=str(tmp_path))
    assert result.returncode == 2  # ExitCode.USAGE


def test_analyze_success_is_ok(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("analyze", str(wav), cwd=str(tmp_path))
    assert result.returncode == 0  # ExitCode.OK
    assert "tone.wav" in result.stdout


def test_analyze_missing_file_is_error(tmp_path):
    missing = tmp_path / "does_not_exist.wav"
    result = _run("analyze", str(missing), cwd=str(tmp_path))
    assert result.returncode == 1  # ExitCode.ERROR


def test_wildcard_input_is_input_validation_error(tmp_path):
    result = _run("analyze", "a*.wav", cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT


def test_process_without_operation_is_usage_error(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), cwd=str(tmp_path))
    assert result.returncode == 2  # ExitCode.USAGE


def test_batch_missing_directory_is_input_error(tmp_path):
    missing_dir = tmp_path / "nope"
    result = _run("batch", str(missing_dir), "analyze", cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
