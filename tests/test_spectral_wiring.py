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

import pytest

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


def test_normalize_peak_rejects_nonfinite_target_peak():
    # `target_peak <= 0` alone passes NaN (NaN comparisons are False) and inf,
    # which scaled the output to NaN/inf.
    for bad in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="target_peak"):
            spectral_utils.normalize_peak([0.5, -0.3], bad)


def test_analyze_spectrum_rejects_nonfinite_sample_rate_and_bad_max_peaks():
    samples = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(4000)]
    for bad_rate in (float("nan"), float("inf"), "44100"):
        with pytest.raises(ValueError, match="sample_rate"):
            spectral_utils.analyze_spectrum(samples, bad_rate)
    for bad_peaks in (-1, 2.5, float("nan"), "5"):
        with pytest.raises(ValueError, match="max_peaks"):
            spectral_utils.analyze_spectrum(samples, 44100, max_peaks=bad_peaks)


def test_apply_spectral_mask_rejects_nonfinite_scalars():
    samples = [0.5] * 64
    with pytest.raises(ValueError, match="sample_rate"):
        spectral_utils.apply_spectral_mask(samples, float("nan"))
    for name in ("low_gain", "mid_gain", "high_gain"):
        for bad in (float("nan"), float("inf"), -0.5):
            with pytest.raises(ValueError, match=name):
                spectral_utils.apply_spectral_mask(samples, 44100, **{name: bad})


def test_linear_resample_rejects_nonfinite_rates():
    for name, kwargs in (
        ("source_rate", {"source_rate": float("nan"), "target_rate": 22050}),
        ("target_rate", {"source_rate": 44100, "target_rate": float("inf")}),
    ):
        with pytest.raises(ValueError, match=name):
            spectral_utils.linear_resample([0.5] * 100, **kwargs)


def test_sliding_window_rms_rejects_noninteger_window():
    for bad in (2.5, float("nan"), "3"):
        with pytest.raises(ValueError, match="window_size"):
            spectral_utils.sliding_window_rms([1.0] * 10, bad)
