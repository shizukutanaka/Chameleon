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

import math
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


def test_apply_spectral_mask_preserves_tail_in_stdlib_fallback(monkeypatch):
    # The pure-Python DFT transforms at most 4096 samples per call; the
    # equaliser must process longer input in blocks rather than dropping
    # the tail.
    monkeypatch.setattr(spectral_utils, "HAS_NUMPY", False)
    src = [0.0] * 4096 + [1.0] * 904
    out = spectral_utils.apply_spectral_mask(src, 44100)
    assert len(out) == len(src)
    assert out[4500] != 0.0


def test_apply_spectral_mask_does_not_renormalize():
    # A uniform 0.5 gain must halve the signal -- the previous version
    # re-normalised every output to full scale, turning an attenuation
    # request into a boost.
    src = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(4000)]
    out = spectral_utils.apply_spectral_mask(
        src, 44100, low_gain=0.5, mid_gain=0.5, high_gain=0.5
    )
    assert max(abs(x) for x in out) < 0.3


def test_noise_reduce_selection_refuses_an_empty_selection():
    import pytest
    # The noise estimate came from np.median over the selection's bins; an
    # out-of-range selection produces an empty set whose median is NaN.
    # The subtraction runs over the WHOLE spectrogram, so that NaN
    # poisoned every bin -- current_audio came out entirely NaN and the
    # call still returned True. An empty selection must be refused, like
    # paste_selection's empty-target guard.
    np = pytest.importorskip("numpy")
    import spectral_editor

    ed = spectral_editor.SpectralEditor()
    t = np.linspace(0, 1, 44100)
    ed.load_audio(0.3 * np.sin(2 * np.pi * 440 * t), 44100)

    empty = spectral_editor.SpectralSelection(
        time_start=99.0, time_end=100.0, freq_start=0.0, freq_end=100.0)
    assert ed.noise_reduce_selection(empty) is False
    assert np.isfinite(ed.current_audio).all()

    real = spectral_editor.SpectralSelection(
        time_start=0.1, time_end=0.2, freq_start=0.0, freq_end=2000.0)
    assert ed.noise_reduce_selection(real) is True
    assert np.isfinite(ed.current_audio).all()
