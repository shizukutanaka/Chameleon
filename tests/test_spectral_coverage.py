"""The pure-Python spectral path must not lie about coverage or parity.

Found on the spectral_utils audit:

* ``analyze --spectrum`` is the flagship dependency-free analysis flag, but
  without NumPy ``analyze_spectrum`` transformed only the first 4096
  samples -- a tone anywhere past ~93 ms of the buffer reported "Dominant
  Frequencies: none detected" on a file that is mostly tone. The fallback
  now tiles up to ``_DFT_MAX_WINDOWS`` 4096-sample windows across the buffer
  and averages magnitudes, and the report discloses the covered span.
* ``_inverse_real_transform`` mirrored ``spectrum[1:-1]`` unconditionally,
  which is only right for even-length transforms -- odd N has no Nyquist
  bin, so the top bin was dropped and the result mis-normalised (a 0.5
  amplitude sine round-tripped with 0.156 max error vs 0.0 for even N).
* ``_compute_bandwidth``/``_detect_peaks``/``_apply_band_gains`` derived the
  bin width as ``sr / (2*(bins-1))``, exact only for even N -- on odd
  input every reported frequency stretched by ~1/(N-1), moving EQ band
  edges.
* ``sliding_window_rms([])`` divided by a window clamped to zero --
  ZeroDivisionError where every sibling returns ``[]``.
"""

import math

import pytest

import spectral_utils
from spectral_utils import (
    analyze_spectrum,
    apply_spectral_mask,
    sliding_window_rms,
)


def _sine(freq, sample_rate, count, amplitude=0.8):
    return [amplitude * math.sin(2 * math.pi * freq * i / sample_rate)
            for i in range(count)]


@pytest.fixture
def force_pure_python(monkeypatch):
    """Exercise the dependency-free DFT path regardless of installed extras."""
    monkeypatch.setattr(spectral_utils, "HAS_NUMPY", False)
    return spectral_utils


def test_sliding_window_rms_empty_input_returns_empty():
    # Siblings (normalize_peak, apply_spectral_mask) all return [] on empty;
    # this one divided by a window clamped to zero instead.
    assert sliding_window_rms([], 100) == []


def test_fallback_spectrum_covers_the_whole_buffer(force_pure_python):
    # A 3 kHz tone living entirely past the old 4096-sample cut must not be
    # invisible: before the fix this reported zero dominant peaks.
    sample_rate = 44100
    silence = [0.0] * 44100
    tone = _sine(3000.0, sample_rate, 44100)
    report = analyze_spectrum(silence + tone, sample_rate)

    assert report.analyzed_samples == len(silence + tone) or \
        report.analyzed_samples == spectral_utils._DFT_MAX_WINDOWS * spectral_utils._DFT_BLOCK
    assert report.dominant_peaks, "tone past the first block was invisible"
    assert abs(report.dominant_peaks[0].frequency_hz - 3000.0) < 15.0


def test_fallback_report_discloses_capped_coverage(force_pure_python, monkeypatch):
    # Direct API calls over the window cap must not read as full coverage.
    monkeypatch.setattr(spectral_utils, "_DFT_MAX_WINDOWS", 2)
    report = analyze_spectrum(_sine(440.0, 44100, 9000), 44100)
    assert report.analyzed_samples == 2 * spectral_utils._DFT_BLOCK


def test_odd_length_inverse_transform_keeps_the_top_bin(force_pure_python):
    # Identity gains on an odd-length buffer must reproduce the input:
    # [1:-1] mirroring is right for even N only and cost ~31% distortion.
    sample_rate, count = 990, 99
    source = _sine(50.0, sample_rate, count, amplitude=0.5)

    restored = apply_spectral_mask(
        source, sample_rate, low_gain=1.0, mid_gain=1.0, high_gain=1.0)

    assert len(restored) == count
    assert max(abs(a - b) for a, b in zip(source, restored)) < 1e-6


def test_odd_length_transform_labels_bins_with_true_n(force_pure_python):
    # 101 samples at sr=1010 -> true bin width 10 Hz; the 2*(bins-1)
    # shortcut gave 10.1 and reported 50.5 for a 50 Hz tone.
    report = analyze_spectrum(_sine(50.0, 1010, 101), 1010, max_peaks=1)
    assert report.dominant_peaks
    assert abs(report.dominant_peaks[0].frequency_hz - 50.0) < 0.4


def test_odd_length_band_edges_use_true_n(force_pure_python):
    # sr=8000, N=801 -> bin 200 sits at 1997.5 Hz, inside the mid band. The
    # old bin width (sr/(2*(bins-1)) = 10.0) labeled it exactly 2000.0 and
    # pushed it into the high band; mid=2/high=3 exposes the mislabel.
    sample_rate, count = 8000, 801
    source = _sine(1997.5, sample_rate, count, amplitude=0.4)

    restored = apply_spectral_mask(
        source, sample_rate, low_gain=1.0, mid_gain=2.0, high_gain=3.0)
    output_peak = max(abs(s) for s in restored)

    # mid band (2x): ~0.8; the mislabeled high band (3x) would give ~1.2.
    assert output_peak < 1.0
