"""Covers spectral_utils.py wiring into core.py / main.py.

spectral_utils.py was previously packaged but never imported (CHARTER §9's
orphaned-module punch list). It is real, deterministic (numpy-optional, with a
pure-Python DFT fallback), and non-duplicative — main.py's existing
--detailed frequency_range/spectral_centroid fields only populate when
librosa is installed, so the default stdlib-only install had no spectral
analysis at all. It was wired in via a new core.get_samples_for_analysis
helper (bounded, mono-mixed, *signed* waveform extraction — the existing
_normalize_amplitude discards sign, which is fine for peak/RMS but wrong for
spectral analysis) and a new `analyze --spectrum` CLI flag.
"""

import subprocess
import sys
from pathlib import Path

import core
import spectral_utils
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


def test_get_samples_for_analysis_extracts_signed_waveform(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.3, frequency=440.0)

    result = core.get_samples_for_analysis(str(wav))

    assert result.success, result.message
    samples = result.data["samples"]
    assert result.data["sample_rate"] == 44100
    assert len(samples) > 0
    assert min(samples) < 0 < max(samples)  # signed, not abs()-only magnitude


def test_get_samples_for_analysis_respects_max_samples(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=1.0, frequency=440.0)

    result = core.get_samples_for_analysis(str(wav), max_samples=500)

    assert result.success
    assert len(result.data["samples"]) <= 500


def test_get_samples_for_analysis_rejects_missing_file(tmp_path):
    result = core.get_samples_for_analysis(str(tmp_path / "missing.wav"))
    assert not result.success


def test_spectral_analysis_pipeline_detects_known_frequency(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5, frequency=880.0)

    result = core.get_samples_for_analysis(str(wav))
    report = spectral_utils.analyze_spectrum(
        result.data["samples"], result.data["sample_rate"]
    )

    assert report.dominant_peaks
    assert abs(report.dominant_peaks[0].frequency_hz - 880.0) < 5.0


def test_cli_analyze_spectrum_flag(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5, frequency=880.0)

    result = _run("analyze", str(wav), "--spectrum", cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Dominant Frequencies:" in result.stdout
    assert "880." in result.stdout


def test_cli_analyze_without_spectrum_flag_omits_spectrum_output(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")

    result = _run("analyze", str(wav), cwd=str(tmp_path))

    assert result.returncode == 0
    assert "Dominant Frequencies" not in result.stdout
