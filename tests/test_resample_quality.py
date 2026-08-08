"""Resampling quality: the built-in fallback must band-limit, not alias.

`AudioProcessor._resample_audio` picks librosa, then scipy, then a built-in
resampler. That last branch used to be `np.interp` -- plain linear
interpolation with no anti-aliasing -- so downsampling folded everything above
the new Nyquist frequency back into the audible band.

These tests pin the property that matters: a tone above the *target* Nyquist
must be attenuated, not reflected. They exercise the built-in path directly so
they are meaningful even in an environment that has scipy installed.
"""

import math

import numpy as np
import pytest

import main


SOURCE_RATE = 48000
TARGET_RATE = 16000  # new Nyquist = 8 kHz


def _tone(freq, sample_rate, seconds=2.0, amplitude=1.0):
    count = int(sample_rate * seconds)
    t = np.arange(count) / sample_rate
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _rms_db(signal):
    signal = np.asarray(signal, dtype=float)
    return 20.0 * math.log10(math.sqrt((signal ** 2).mean()) + 1e-20)


def _linear_resample(channel, source_sr, target_sr):
    """The old np.interp behaviour, kept here as the thing we improved on."""
    count = max(1, int(round(len(channel) * target_sr / source_sr)))
    return np.interp(
        np.linspace(0.0, len(channel) - 1, count),
        np.linspace(0.0, len(channel) - 1, len(channel)),
        channel,
    )


def test_downsampling_attenuates_content_above_the_new_nyquist():
    # 15 kHz cannot exist at 16 kHz output; it must be filtered out, not
    # folded down to 16000 - 15000 = 1 kHz.
    tone = _tone(15000.0, SOURCE_RATE)

    resampled = main.AudioProcessor._bandlimited_resample(tone, SOURCE_RATE, TARGET_RATE)

    assert _rms_db(resampled) < -40.0


def test_builtin_resampler_beats_plain_linear_interpolation_on_aliasing():
    tone = _tone(15000.0, SOURCE_RATE)

    aliased = _linear_resample(tone, SOURCE_RATE, TARGET_RATE)
    band_limited = main.AudioProcessor._bandlimited_resample(tone, SOURCE_RATE, TARGET_RATE)

    # Linear interpolation passes the alias through at near full level.
    assert _rms_db(aliased) > -10.0
    # The improvement is the whole point of the change.
    assert _rms_db(aliased) - _rms_db(band_limited) > 40.0


def test_passband_content_survives_downsampling():
    # 1 kHz is comfortably below the 8 kHz target Nyquist and must be kept.
    tone = _tone(1000.0, SOURCE_RATE, amplitude=0.5)

    resampled = main.AudioProcessor._bandlimited_resample(tone, SOURCE_RATE, TARGET_RATE)

    assert np.abs(resampled).max() == pytest.approx(0.5, abs=0.02)


def test_constant_signal_is_preserved_exactly_unit_dc_gain():
    constant = np.ones(SOURCE_RATE, dtype=np.float32)

    resampled = main.AudioProcessor._bandlimited_resample(constant, SOURCE_RATE, 44100)

    # Ignore the filter's edge transients.
    assert resampled[200:-200].mean() == pytest.approx(1.0, abs=1e-4)


def test_upsampling_preserves_amplitude_and_length_ratio():
    tone = _tone(1000.0, SOURCE_RATE, seconds=1.0, amplitude=0.5)

    resampled = main.AudioProcessor._bandlimited_resample(tone, SOURCE_RATE, 96000)

    assert len(resampled) == pytest.approx(len(tone) * 2, abs=2)
    assert np.abs(resampled).max() == pytest.approx(0.5, abs=0.02)


def test_empty_and_identical_rate_are_handled():
    assert len(main.AudioProcessor._bandlimited_resample(
        np.array([], dtype=np.float32), SOURCE_RATE, TARGET_RATE)) == 0

    processor = main.AudioProcessor(main.ProcessingConfig())
    tone = _tone(1000.0, SOURCE_RATE, seconds=0.1)
    # Same rate in and out short-circuits and must return the input untouched.
    assert np.array_equal(processor._resample_audio(tone, SOURCE_RATE, SOURCE_RATE), tone)


def test_matches_scipy_resample_poly_within_a_small_tolerance():
    # Independent implementation check, mirroring how true-peak was validated.
    scipy_signal = pytest.importorskip("scipy.signal")

    tone = _tone(15000.0, SOURCE_RATE)
    divisor = math.gcd(SOURCE_RATE, TARGET_RATE)
    reference = scipy_signal.resample_poly(
        tone, TARGET_RATE // divisor, SOURCE_RATE // divisor
    )
    mine = main.AudioProcessor._bandlimited_resample(tone, SOURCE_RATE, TARGET_RATE)

    # Both should suppress the out-of-band tone to a similar degree.
    assert _rms_db(mine) == pytest.approx(_rms_db(reference), abs=3.0)
