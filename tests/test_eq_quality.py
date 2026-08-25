"""Equalizer correctness: a peaking EQ must be selective.

Both EQ implementations in this project were built on `scipy.iirpeak`, which
is a band-pass resonator rather than a peaking EQ. Filtering with it and then
scaling replaces the signal with its own narrow band, so asking for a boost
destroyed everything outside it:

    main.apply_effects, "+3 dB at 1 kHz"   ->  200 Hz -24.6 dB, 3 kHz -15.3 dB
    ParametricEQ,       "+6 dB at 1 kHz"   ->  1 kHz  -0.0 dB, 200 Hz -26.7 dB

Both now use RBJ "Audio EQ Cookbook" biquads. Rather than asserting against a
transcribed coefficient table, these tests pin the three properties that
*define* a correct peaking EQ, each of which follows from what an equalizer is
meant to do: the requested gain appears at the centre frequency, frequencies
far from it are left alone, and a boost followed by an equal cut is a no-op.
"""

import math

import pytest

# Guarded so the suite is runnable on the project's own default install, which
# has no third-party packages at all. An unguarded `import numpy` here made
# collection fail outright, so the dependency-free core could not be verified
# without first installing the dependency it is defined by not needing.
np = pytest.importorskip("numpy")

import main
import mastering_chain

# These exercise the real biquad path, which needs scipy's lfilter. Without it
# `apply_effects` now refuses rather than returning the input unmodified --
# covered by tests/test_effect_dependencies.py -- so there is nothing to
# measure here.
pytest.importorskip("scipy")


SAMPLE_RATE = 48000


def _tone(freq, amplitude=0.3, seconds=1.0, sample_rate=SAMPLE_RATE):
    t = np.arange(int(sample_rate * seconds)) / sample_rate
    return amplitude * np.sin(2 * np.pi * freq * t)


def _level_db(signal, freq, sample_rate=SAMPLE_RATE):
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freqs = np.fft.rfftfreq(len(signal), 1 / sample_rate)
    return 20.0 * math.log10(spectrum[np.argmin(np.abs(freqs - freq))] / len(signal) + 1e-20)


def _apply_eq(signal, bands):
    processor = main.AudioProcessor(main.ProcessingConfig())
    return processor.apply_effects(signal.copy(), SAMPLE_RATE, {"eq": bands})


# --- the defining property: selectivity -----------------------------------

def test_peaking_eq_leaves_out_of_band_content_alone():
    signal = _tone(200) + _tone(3000)

    processed = _apply_eq(signal, [{"frequency": 1000, "gain": 3.0, "q": 1.0}])

    for freq in (200, 3000):
        change = _level_db(processed, freq) - _level_db(signal, freq)
        assert abs(change) < 1.0, f"{freq} Hz moved {change:+.2f} dB"


def test_peaking_eq_delivers_the_requested_gain_at_the_centre():
    signal = _tone(1000)

    for gain in (3.0, 6.0, -6.0):
        processed = _apply_eq(signal, [{"frequency": 1000, "gain": gain, "q": 1.0}])
        change = _level_db(processed, 1000) - _level_db(signal, 1000)
        assert change == pytest.approx(gain, abs=0.25)


def test_boost_then_equal_cut_restores_the_original():
    signal = _tone(200) + _tone(1000) + _tone(5000)

    boosted = _apply_eq(signal, [{"frequency": 1000, "gain": 6.0, "q": 1.0}])
    restored = _apply_eq(boosted, [{"frequency": 1000, "gain": -6.0, "q": 1.0}])

    # Skip the filter's start-up transient before comparing.
    difference = restored[2000:] - signal[2000:]
    assert 20.0 * math.log10(np.sqrt((difference ** 2).mean()) + 1e-20) < -60.0


# --- RBJ coefficient properties -------------------------------------------

def _response_db(b, a, freq):
    scipy_signal = pytest.importorskip("scipy.signal")
    _, response = scipy_signal.freqz(b, a, worN=[2 * np.pi * freq / SAMPLE_RATE])
    return 20.0 * math.log10(abs(response[0]) + 1e-20)


def test_peaking_design_is_unity_at_dc_and_nyquist():
    b, a = mastering_chain.design_peaking_eq(1000, SAMPLE_RATE, 6.0, 1.0)

    assert _response_db(b, a, 1) == pytest.approx(0.0, abs=0.01)
    assert _response_db(b, a, SAMPLE_RATE // 2 - 1) == pytest.approx(0.0, abs=0.01)
    assert _response_db(b, a, 1000) == pytest.approx(6.0, abs=0.01)


def test_shelf_design_reaches_full_gain_in_its_band_and_unity_outside():
    b, a = mastering_chain.design_shelf_eq(4000, SAMPLE_RATE, 6.0, high=True)

    assert _response_db(b, a, 100) == pytest.approx(0.0, abs=0.1)
    assert _response_db(b, a, 16000) == pytest.approx(6.0, abs=0.1)
    # A shelf sits at half its gain on the corner frequency by definition.
    assert _response_db(b, a, 4000) == pytest.approx(3.0, abs=0.1)


# --- mastering chain ------------------------------------------------------

def test_parametric_eq_bell_boosts_its_band_without_erasing_the_rest():
    signal = _tone(200) + _tone(1000) + _tone(8000)

    equalizer = mastering_chain.ParametricEQ(SAMPLE_RATE)
    equalizer.add_band(mastering_chain.EQBand(
        frequency=1000, gain=6.0, q_factor=1.0, filter_type="bell"))
    processed = equalizer.process(signal.copy())

    assert _level_db(processed, 1000) - _level_db(signal, 1000) == pytest.approx(6.0, abs=0.3)
    for freq in (200, 8000):
        assert abs(_level_db(processed, freq) - _level_db(signal, freq)) < 1.0


def test_streaming_preset_applies_its_requested_boosts():
    # The preset asks for small boosts; the old code delivered attenuation
    # at every one of them (100 Hz -1.26 dB against a requested +0.5 dB).
    signal = sum(_tone(freq, amplitude=0.2) for freq in (100, 3000, 10000))

    preset = mastering_chain.create_mastering_preset("streaming")
    equalizer = mastering_chain.ParametricEQ(SAMPLE_RATE)
    for band in preset.eq_bands:
        equalizer.add_band(band)
    processed = equalizer.process(signal.copy())

    for freq in (100, 3000, 10000):
        change = _level_db(processed, freq) - _level_db(signal, freq)
        assert change > 0.0, f"{freq} Hz was attenuated ({change:+.2f} dB)"


# --- determinism ----------------------------------------------------------

def test_reverb_is_reproducible():
    # The impulse response is synthetic noise; it must be seeded, or the same
    # input produces different output every run (CHARTER §1).
    signal = _tone(1000, seconds=0.3)
    effects = {"reverb": {"room_size": 0.05, "wet": 0.3}}

    processor = main.AudioProcessor(main.ProcessingConfig())
    first = processor.apply_effects(signal.copy(), SAMPLE_RATE, effects)
    second = processor.apply_effects(signal.copy(), SAMPLE_RATE, effects)

    assert np.array_equal(first, second)
