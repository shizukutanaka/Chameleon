"""Commercial-grade CLI contract: stderr separation, --version, quiet default.

Phase 8 polish (CHARTER §9): a scriptable CLI must keep diagnostics out of
stdout, answer --version, and not spam warnings on the supported stdlib-only
default install.
"""

import subprocess
import sys
from pathlib import Path

import main
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


def test_version_flag_reports_single_source_version(tmp_path):
    result = _run("--version", cwd=str(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == f"chameleon {main.VERSION}"


def test_help_shows_current_version_not_stale_v3(tmp_path):
    result = _run("--help", cwd=str(tmp_path))
    assert result.returncode == 0
    assert "v3.0" not in result.stdout
    assert main.VERSION in result.stdout


def test_errors_go_to_stderr_not_stdout(tmp_path):
    missing = tmp_path / "missing.wav"
    result = _run("analyze", str(missing), cwd=str(tmp_path))
    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "Error" not in result.stdout


def test_input_validation_error_goes_to_stderr(tmp_path):
    result = _run("analyze", "a*.wav", cwd=str(tmp_path))
    assert result.returncode == 3
    assert "Input validation error" in result.stderr
    assert "Input validation error" not in result.stdout


def test_default_run_emits_no_optional_dep_warnings(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("analyze", str(wav), cwd=str(tmp_path))
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "UserWarning" not in combined
    assert "not installed" not in combined


def test_successful_analyze_output_stays_on_stdout(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("analyze", str(wav), cwd=str(tmp_path))
    assert result.returncode == 0
    assert "tone.wav" in result.stdout
    assert result.stderr.strip() == ""
