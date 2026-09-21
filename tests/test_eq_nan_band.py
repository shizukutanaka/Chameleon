"""ParametricEQ.add_band must not register a filter whose parameters
would poison the signal: a NaN frequency slips every comparison guard
(NaN >= x is False), producing an all-NaN biquad that turns the whole
audio buffer NaN."""
import math

import pytest

np = pytest.importorskip("numpy")
mastering_chain = pytest.importorskip("mastering_chain")
pytestmark = pytest.mark.skipif(
    not mastering_chain.HAS_SCIPY, reason="EQ bands require scipy")


def _tone(sr=44100, seconds=0.05):
    t = np.arange(int(sr * seconds)) / sr
    return 0.5 * np.sin(2 * np.pi * 440 * t)


def test_nan_frequency_band_skipped():
    eq = mastering_chain.ParametricEQ(sample_rate=44100)
    eq.add_band(mastering_chain.EQBand(
        frequency=float('nan'), gain=6.0, q_factor=1.0,
        filter_type='bell'))
    assert eq.filters == []
    out = eq.process(_tone())
    assert np.isfinite(out).all()


@pytest.mark.parametrize("freq", [float('-inf'), -100.0, 0.0])
def test_nonpositive_frequency_band_skipped(freq):
    eq = mastering_chain.ParametricEQ(sample_rate=44100)
    eq.add_band(mastering_chain.EQBand(
        frequency=freq, gain=6.0, q_factor=1.0,
        filter_type='bell'))
    assert eq.filters == []


def test_infinite_gain_band_skipped():
    """gain=inf designs non-finite coefficients; never register it."""
    eq = mastering_chain.ParametricEQ(sample_rate=44100)
    eq.add_band(mastering_chain.EQBand(
        frequency=1000.0, gain=float('inf'), q_factor=1.0,
        filter_type='bell'))
    assert eq.filters == []


def test_nan_frequency_highpass_skipped():
    eq = mastering_chain.ParametricEQ(sample_rate=44100)
    eq.add_band(mastering_chain.EQBand(
        frequency=float('nan'), gain=0.0, q_factor=1.0,
        filter_type='highpass'))
    assert eq.filters == []


def test_valid_band_still_registers():
    eq = mastering_chain.ParametricEQ(sample_rate=44100)
    eq.add_band(mastering_chain.EQBand(
        frequency=1000.0, gain=6.0, q_factor=1.0,
        filter_type='bell'))
    assert len(eq.filters) == 1
