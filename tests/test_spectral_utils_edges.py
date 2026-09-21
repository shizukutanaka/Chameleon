"""Edge inputs for spectral_utils.

At HEAD:
- ``sliding_window_rms([], n)`` clamped window_size to 0 and the loop
  divided 0/0 -- a crash on an input every sibling returns [] for.
- ``normalize_peak(..., nan)`` and ``apply_spectral_mask(..., *_gain=nan)``
  slipped past bare-comparison guards and returned all-NaN audio
  (the same class fixed in round 13 for normalize/trim).
- ``analyze_spectrum(..., max_peaks=-1)`` evaluated ``peaks[:-1]`` --
  silently dropping the strongest peak instead of failing.
"""
import math

import pytest

from spectral_utils import (
    analyze_spectrum,
    apply_spectral_mask,
    linear_resample,
    normalize_peak,
    sliding_window_rms,
)

SAMPLES = [0.1, 0.5, -0.3, 0.8, -0.2, 0.4]


def test_sliding_window_rms_empty_returns_empty():
    assert sliding_window_rms([], 4) == []
    assert sliding_window_rms([], 1) == []


def test_sliding_window_rms_clamps_window():
    assert len(sliding_window_rms(SAMPLES, 100)) == 1
    assert len(sliding_window_rms(SAMPLES, 2)) == len(SAMPLES) - 1


def test_sliding_window_rms_rejects_non_integer_window():
    with pytest.raises(ValueError):
        sliding_window_rms(SAMPLES, 2.5)
    with pytest.raises(ValueError):
        sliding_window_rms(SAMPLES, float("nan"))


def test_normalize_peak_rejects_nan_target():
    with pytest.raises(ValueError):
        normalize_peak(SAMPLES, float("nan"))
    with pytest.raises(ValueError):
        normalize_peak(SAMPLES, float("inf"))


def test_apply_spectral_mask_rejects_nan_gain():
    for kw in ("low_gain", "mid_gain", "high_gain"):
        with pytest.raises(ValueError):
            apply_spectral_mask(SAMPLES, 44100, **{kw: float("nan")})


def test_linear_resample_rejects_nan_rate():
    with pytest.raises(ValueError):
        linear_resample(SAMPLES, float("nan"), 44100)
    with pytest.raises(ValueError):
        linear_resample(SAMPLES, 44100, float("inf"))


def test_analyze_spectrum_rejects_negative_max_peaks():
    with pytest.raises(ValueError):
        analyze_spectrum(SAMPLES, 44100, max_peaks=-1)


def test_analyze_spectrum_zero_max_peaks_ok():
    report = analyze_spectrum(SAMPLES, 44100, max_peaks=0)
    assert report.dominant_peaks == []
