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


def test_ml_model_flag_removed(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("ml", "enhance", "--input", str(wav), "--model", "x", cwd=str(tmp_path))
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

    assert captured["processor"].config.quality == "low"
