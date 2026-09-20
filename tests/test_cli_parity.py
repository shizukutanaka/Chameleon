"""Covers the Phase 7 excess/deficiency fixes in main.py's CLI:

- Ghost parameters removed (process --parallel, ml enhance --model,
  stream --monitor) now correctly rejected by argparse.
- Previously-unreachable options wired for real: batch --quality,
  process/batch --target-peak, batch effects.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def _peak(wav_path) -> float:
    import wave
    with wave.open(str(wav_path), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
    import array
    samples = array.array("h", frames)
    return max(abs(s) for s in samples) / 32768.0


# -- removed ghost parameters: argparse must now reject them (exit 2) --------

def test_process_parallel_flag_removed(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--normalize", "--parallel", cwd=str(tmp_path))
    assert result.returncode == 2


def test_ml_command_removed(tmp_path):
    # The `--model` flag went first; the command followed it in 2026-08. Its
    # one operation was remove_noise() + normalize_audio() -- no model, no
    # learning -- and `process --denoise --normalize` does the same work under
    # a name that is true. See CHARTER.md §9.
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("ml", "enhance", "--input", str(wav), cwd=str(tmp_path))
    assert result.returncode == 2


def test_stream_monitor_flag_removed(tmp_path):
    result = _run("stream", "--monitor", cwd=str(tmp_path))
    assert result.returncode == 2


def test_stream_device_flags_require_int(tmp_path):
    result = _run("stream", "--input-device", "not-a-number", cwd=str(tmp_path))
    assert result.returncode == 2


# -- --target-peak wired end-to-end ------------------------------------------

def test_process_target_peak_is_honored(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", amplitude=8000)
    out_dir = tmp_path / "out"
    result = _run(
        "process", str(wav), "--normalize", "--target-peak", "0.5",
        "--output-dir", str(out_dir), cwd=str(tmp_path),
    )
    assert result.returncode == 0
    produced = list(out_dir.glob("*.wav"))
    assert produced, result.stdout + result.stderr
    assert abs(_peak(produced[0]) - 0.5) < 0.02


def test_batch_target_peak_is_honored(tmp_path):
    write_sine_wave(tmp_path / "tone.wav", amplitude=8000)
    out_dir = tmp_path / "out"
    result = _run(
        "batch", str(tmp_path), "normalize", "--target-peak", "0.4",
        "--output-dir", str(out_dir), cwd=str(tmp_path),
    )
    assert result.returncode == 0
    produced = list(out_dir.glob("*.wav"))
    assert produced, result.stdout + result.stderr
    assert abs(_peak(produced[0]) - 0.4) < 0.02


# -- batch effects operation --------------------------------------------------

def test_batch_effects_requires_effects_flag(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    result = _run("batch", str(tmp_path), "effects", cwd=str(tmp_path))
    assert result.returncode == 2


@pytest.mark.skipif(not main.HAS_NUMPY,
                    reason="the effects operation needs numpy; the stdlib core has no effects")
def test_batch_effects_runs_with_effects_file(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    effects_file = tmp_path / "effects.json"
    effects_file.write_text(json.dumps({}))
    out_dir = tmp_path / "out"
    result = _run(
        "batch", str(tmp_path), "effects", "--effects", str(effects_file),
        "--output-dir", str(out_dir), cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr


# -- batch --quality now sets the shared AudioProcessor config --------------

def test_batch_quality_flag_sets_processor_config(tmp_path, monkeypatch):
    write_sine_wave(tmp_path / "tone.wav")
    captured = {}
    original_init = main.AudioProcessor.__init__

    def spy_init(self, *a, **kw):
        original_init(self, *a, **kw)
        captured["processor"] = self

    monkeypatch.setattr(main.AudioProcessor, "__init__", spy_init)
    monkeypatch.setattr(
        sys, "argv",
        ["main.py", "batch", str(tmp_path), "analyze", "--quality", "low"],
    )
    monkeypatch.chdir(tmp_path)

    asyncio.run(main.main())

    # Legacy tier names never had distinct behavior; they map to 'standard'
    # (the flag is still wired end to end).
    assert captured["processor"].config.quality == "standard"


# -- midi --key/--mode: wired for real (previously accepted and ignored) -----

def _midi_pitch_classes(mid_path):
    """Pitch classes of note-on/note-off events in a SMF file."""
    data = Path(mid_path).read_bytes()
    pitches = [
        data[i - 1] for i in range(2, len(data))
        if data[i - 2] in (0x90, 0x80) and 0 < data[i - 1] < 128
    ]
    return {p % 12 for p in pitches}


def test_midi_generate_honors_key_and_mode(tmp_path):
    out = tmp_path / "ebm.mid"
    result = _run(
        "midi", "generate", "--key", "Eb", "--mode", "minor", "--output", str(out),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Eb natural minor pitch classes: Eb F Gb Ab Bb Cb Db -> {1,3,5,6,8,10,11}
    pcs = _midi_pitch_classes(out)
    assert pcs <= {1, 3, 5, 6, 8, 10, 11}, pcs
    assert 3 in pcs  # the tonic actually moves


def test_midi_compose_honors_key_and_mode(tmp_path):
    out = tmp_path / "gm.mid"
    result = _run(
        "midi", "compose", "--key", "G", "--mode", "minor", "--output", str(out),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Melody AND chords must stay inside G natural minor; a transposed
    # major-mode progression would inject F# (pc 6).
    assert _midi_pitch_classes(out) <= {0, 2, 3, 5, 7, 9, 10}


def test_midi_generate_rejects_an_unknown_key(tmp_path):
    result = _run(
        "midi", "generate", "--key", "ZZ", "--output", str(tmp_path / "x.mid"),
        cwd=str(tmp_path),
    )
    assert result.returncode == 3  # INPUT -- a bad key is a bad argument
    assert not (tmp_path / "x.mid").exists()


# -- --target-peak range: the documented (0, 1.0] contract is enforced ------

def test_process_rejects_target_peak_above_one(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--normalize", "--target-peak", "2.0",
                  cwd=str(tmp_path))
    assert result.returncode == 3  # INPUT
    # Above-unity targets used to "succeed" while the soft clipper silently
    # crushed the overshoot; nothing may be written on rejection.
    assert not (tmp_path / "tone_normalized.wav").exists()


def test_batch_rejects_target_peak_zero(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    result = _run("batch", str(tmp_path), "normalize", "--target-peak", "0",
                  cwd=str(tmp_path))
    assert result.returncode == 3  # INPUT


# -- plugins flags work in the documented post-subcommand position ----------

def test_plugins_list_accepts_json_after_subcommand(tmp_path):
    result = _run("plugins", "list", "--json", cwd=str(tmp_path))
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "directories" in payload and "plugins" in payload


def test_plugins_directory_positions_merge(tmp_path):
    a = tmp_path / "dir_a"
    b = tmp_path / "dir_b"
    a.mkdir()
    b.mkdir()
    result = _run("plugins", "--directory", str(a), "list",
                  "--directory", str(b), "--json", cwd=str(tmp_path))
    assert result.returncode == 0
    dirs = json.loads(result.stdout)["directories"]
    assert str(a) in dirs and str(b) in dirs, dirs


def test_batch_dry_run_writes_nothing(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    out = tmp_path / "out"
    result = _run("batch", str(tmp_path), "normalize", "--dry-run",
                  "--output-dir", str(out), cwd=str(tmp_path))
    assert result.returncode == 0
    # README promises a preview; nothing may be written, and the summary
    # must not claim files were processed.
    assert not out.exists()
    assert list(tmp_path.glob("*_normalized.wav")) == []
    assert "Would process" in result.stdout
