"""CLI `batch` gather must only admit real files inside the scanned tree.

The gather mirrored into main.py from glob results used to hand every
name-matching entry to `_filter_safe_files`, so a `.wav` symlink pointing
outside the scanned directory survived every check (the *target* is a
real WAV) and was processed — while core.py's own gather refuses file
symlinks. A `foo.wav`-named directory (or a symlink to one) likewise
reached the deep-inspection gate and was counted among the rejections.
"""

import os
import subprocess
import sys
from pathlib import Path

from tests._helpers import write_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _run_batch(directory, *extra):
    return subprocess.run(
        [sys.executable, MAIN_PY, "batch", str(directory), "analyze",
         "--dry-run", *extra],
        capture_output=True, text=True, timeout=120)


def test_escaping_file_symlink_is_not_gathered(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    write_sine_wave(inside / "real.wav")
    write_sine_wave(outside / "secret.wav")
    (inside / "link.wav").symlink_to(outside / "secret.wav")

    proc = _run_batch(inside)

    assert proc.returncode == 0, proc.stderr
    # Pre-fix the escaping link reached the file list: "Found 2".
    assert "Found 1 audio files" in proc.stdout
    assert "link.wav" not in proc.stdout


def test_dot_wav_named_directory_is_not_gathered(tmp_path):
    write_sine_wave(tmp_path / "real.wav")
    fake = tmp_path / "fake.wav"
    fake.mkdir()
    write_sine_wave(fake / "nested.wav")

    proc = _run_batch(tmp_path, "--recursive")

    assert proc.returncode == 0, proc.stderr
    # real.wav + nested.wav are the only files to process.
    assert "Found 2 audio files" in proc.stdout
    # Pre-fix `fake.wav` (the directory) was handed to the inspection
    # gate and logged as a rejection.
    assert "fake.wav" not in proc.stderr


def test_directory_of_only_symlinks_reports_no_inputs(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    write_sine_wave(outside / "secret.wav")
    scanned = tmp_path / "scanned"
    scanned.mkdir()
    (scanned / "link.wav").symlink_to(outside / "secret.wav")

    proc = _run_batch(scanned)

    assert proc.returncode != 0
    assert "no supported audio files" in proc.stderr
