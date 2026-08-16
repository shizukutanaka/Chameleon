"""Compressor static transfer curve (soft knee).

The gain computer mixed two knee conventions: a quadratic knee placed above the
threshold, [0, W], combined with the above-knee formula for a knee *centred* on
the threshold. The pieces did not meet, so the input/output curve jumped
downward at the knee boundary and was non-monotonic there -- a 1 dB rise in
input could drop the output by 2 dB (measured -16.25 -> -18.25 dB at the knee).

It now uses the standard centred soft knee (Giannoulis, Massberg & Reiss, JAES
2012). These tests assert the properties that define a correct compressor
curve, so they hold without transcribing a reference table: monotonic,
continuous, full ratio above the knee, no reduction below it, and the knee
centred on the threshold.
"""

import math

import numpy as np
import pytest

import mastering_chain


def _reduction_db(compressor, level_db):
    return compressor._gain_reduction_db(10.0 ** (level_db / 20.0))


def _compressor(threshold=-20.0, ratio=4.0, knee=6.0):
    config = mastering_chain.CompressorConfig(
        threshold=threshold, ratio=ratio, knee=knee, makeup_gain=0.0)
    return mastering_chain.Compressor(config, 48000)


def test_transfer_curve_is_monotonic():
    compressor = _compressor()
    levels = np.arange(-40.0, 0.01, 0.25)
    outputs = [level + _reduction_db(compressor, level) for level in levels]

    diffs = np.diff(outputs)
    assert np.all(diffs >= -1e-9), "output level decreases as input rises"


def test_transfer_curve_is_continuous_across_the_knee():
    compressor = _compressor(knee=6.0)
    levels = np.arange(-40.0, 0.01, 0.1)
    outputs = np.array([level + _reduction_db(compressor, level) for level in levels])

    # No step bigger than the sampling interval; the old kink was ~2 dB.
    assert np.max(np.abs(np.diff(outputs))) < 0.15


def test_no_gain_reduction_below_the_knee():
    compressor = _compressor(threshold=-20.0, knee=6.0)
    # Knee starts at threshold - knee/2 = -23 dB.
    assert _reduction_db(compressor, -24.0) == pytest.approx(0.0, abs=1e-9)
    assert _reduction_db(compressor, -30.0) == pytest.approx(0.0, abs=1e-9)


def test_knee_is_centred_on_the_threshold():
    compressor = _compressor(threshold=-20.0, ratio=4.0, knee=6.0)
    # Compression must already be under way at the threshold (the knee
    # straddles it) -- the old curve was still flat here. At the exact centre
    # the analytic reduction is slope * knee/8.
    slope = 1.0 / 4.0 - 1.0
    expected = slope * 6.0 / 8.0
    assert _reduction_db(compressor, -20.0) == pytest.approx(expected, abs=1e-6)
    assert _reduction_db(compressor, -20.0) < -1e-6


def test_above_the_knee_the_slope_is_one_over_ratio():
    compressor = _compressor(threshold=-20.0, ratio=4.0, knee=6.0)
    # Well above the knee (> threshold + knee/2 = -17 dB).
    out_a = -10.0 + _reduction_db(compressor, -10.0)
    out_b = -5.0 + _reduction_db(compressor, -5.0)
    slope = (out_b - out_a) / 5.0
    assert slope == pytest.approx(1.0 / 4.0, abs=1e-3)


def test_asymptotic_output_matches_the_ratio_line():
    compressor = _compressor(threshold=-20.0, ratio=4.0, knee=6.0)
    # out = T + (in - T)/R at 0 dBFS input -> -20 + 20/4 = -15.
    assert 0.0 + _reduction_db(compressor, 0.0) == pytest.approx(-15.0, abs=1e-3)


def test_hard_knee_is_a_clean_corner():
    compressor = _compressor(threshold=-20.0, ratio=4.0, knee=0.0)
    assert _reduction_db(compressor, -20.5) == pytest.approx(0.0, abs=1e-9)
    # Just above threshold, full ratio immediately.
    assert 0.0 + _reduction_db(compressor, 0.0) == pytest.approx(-15.0, abs=1e-3)


def test_silence_does_not_produce_nan():
    compressor = _compressor()
    assert compressor._gain_reduction_db(0.0) == 0.0
    assert math.isfinite(compressor._gain_reduction_db(1e-20))


def test_full_mono_process_curve_is_monotonic():
    # End-to-end through the sample loop, not just the helper.
    compressor = _compressor(threshold=-20.0, ratio=4.0, knee=6.0)
    outputs = []
    for level in range(-30, 1):
        fresh = _compressor(threshold=-20.0, ratio=4.0, knee=6.0)
        block = np.full(20000, 10.0 ** (level / 20.0))
        _, reduction = fresh._process_mono(block)
        outputs.append(level + reduction[-1])
    assert np.all(np.diff(outputs) >= -1e-6)
