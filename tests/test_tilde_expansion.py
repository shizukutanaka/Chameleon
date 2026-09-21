"""`~` must expand consistently on output paths.

The validators expand `~` (validate_directory did; validate_path did not)
but the writers used the literal string: a quoted ``-o "~/x.wav"`` was
validated as ``$HOME/x.wav`` and then written to ``./~/x.wav`` under the
current directory -- validating one path while writing another, and
polluting cwd with a literal ``~`` directory. Inputs already expanded
(resolve_unique_paths); outputs did not.

Also covered: the "will overwrite each other's output" warning compared
*raw* stems, so ``a:b.wav`` and ``a<b.wav`` -- which both sanitize to
``a_b_normalized.wav`` -- collided silently.
"""

import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import pytest

import core
import main
import midi_analysis
from tests._helpers import write_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def test_resolve_output_path_expands_tilde_explicit(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    dest = main.AudioProcessor()._resolve_output_path(
        "in.wav", suffix="_normalized.wav",
        explicit_path="~/out.wav", output_dir=None)

    assert dest == home / "out.wav"
    assert not (workdir / "~").exists()  # no literal-~ directory was created


def test_output_dir_tilde_expands_instead_of_creating_literal(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    dest = main.AudioProcessor()._resolve_output_path(
        "in.wav", suffix="_normalized.wav",
        explicit_path=None, output_dir="~/processed")

    assert dest == home / "processed" / "in_normalized.wav"
    assert (home / "processed").is_dir()
    assert not (workdir / "~").exists()


def test_state_dir_env_tilde_expands(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CHAMELEON_STATE_DIR", "~/statedir")

    mgr = core.StateRecoveryManager()

    assert mgr.state_dir == home / "statedir"


def test_midi_generate_tilde_lands_in_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    ok = midi_analysis.MIDIAnalyzer().generate_midi_file(
        [midi_analysis.MIDINote(60, 100, 0.0, 0.5)], "~/out.mid")

    assert ok
    assert (home / "out.mid").exists()
    assert not (workdir / "~").exists()


def test_analyze_export_tilde_lands_in_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    src = write_sine_wave(workdir / "in.wav", duration=0.05)

    env = dict(os.environ, HOME=str(home))
    proc = subprocess.run(
        [sys.executable, MAIN_PY, "analyze", str(src), "--export", "~/report.json"],
        capture_output=True, text=True, timeout=60, env=env, cwd=str(workdir))

    assert proc.returncode == 0, proc.stderr
    export = home / "report.json"
    assert export.exists()
    json.loads(export.read_text())  # valid JSON
    assert not (workdir / "~").exists()


def _write_named_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x01\x00" * 400)


def test_collision_warning_uses_sanitized_names(tmp_path):
    """`a:b.wav` and `a\\b.wav` are distinct POSIX files whose stems both
    sanitize to `a_b` -> both write `a_b_normalized.wav` into --output-dir.
    The overwrite warning must fire on the *sanitized* name."""
    d1, d2, out = tmp_path / "d1", tmp_path / "d2", tmp_path / "out"
    _write_named_wav(d1 / "a:b.wav")
    _write_named_wav(d2 / "a\\b.wav")

    proc = subprocess.run(
        [sys.executable, MAIN_PY, "process",
         str(d1 / "a:b.wav"), str(d2 / "a\\b.wav"),
         "--normalize", "--output-dir", str(out)],
        capture_output=True, text=True, timeout=60)

    assert proc.returncode == 0, proc.stderr
    assert "will overwrite each other's output" in proc.stderr
    assert out.joinpath("a_b_normalized.wav").exists()
