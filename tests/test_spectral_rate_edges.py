"""Rate/peak-count edge cases for spectral_utils' exported API.

linear_resample guarded only ``<= 0`` on the sample rates: ``inf`` slipped
through, collapsed the duration to 0, and silently returned a one-sample
"resample". ``analyze_spectrum`` sliced ``peaks[:max_peaks]`` verbatim, so a
negative count silently dropped peaks and a float count leaked TypeError.
"""


import math

import pytest

import spectral_utils


def test_linear_resample_rejects_non_finite_rates():
    tone = [0.0, 0.5, -0.5, 1.0]
    for bad in (math.inf, -math.inf, math.nan):
        with pytest.raises(ValueError):
            spectral_utils.linear_resample(tone, bad, 44100)
        with pytest.raises(ValueError):
            spectral_utils.linear_resample(tone, 44100, bad)


def test_linear_resample_finite_rates_still_work():
    tone = [0.0, 0.5, -0.5, 1.0]
    up = spectral_utils.linear_resample(tone, 2, 4)
    assert len(up) == 8
    same = spectral_utils.linear_resample(tone, 44100, 44100)
    assert same == tone


def test_analyze_spectrum_rejects_negative_or_float_max_peaks():
    samples = [math.sin(2 * math.pi * n / 32) for n in range(256)]
    for bad in (-1, -100, 2.5, "3"):
        with pytest.raises(ValueError):
            spectral_utils.analyze_spectrum(samples, 44100, max_peaks=bad)


def test_analyze_spectrum_max_peaks_boundaries():
    samples = [math.sin(2 * math.pi * n / 32) for n in range(256)]
    assert spectral_utils.analyze_spectrum(samples, 44100, max_peaks=0).dominant_peaks == []
    report = spectral_utils.analyze_spectrum(samples, 44100, max_peaks=1)
    assert len(report.dominant_peaks) == 1
