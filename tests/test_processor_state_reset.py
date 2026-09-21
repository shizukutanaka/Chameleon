"""DSP processor state must not leak across process() calls, and the
Limiter must not drop audio within a call.

At HEAD the Limiter emitted a delay-line-shifted signal: every output
began with lookahead_samples of zeros (or the previous buffer's tail)
and silently dropped that many samples off the end. The Compressor's
envelope and gain_reduction carried into the next buffer. Invalid
config values (ratio=0, release rounding to 0 samples, NaN anywhere)
either crashed inside the loop or were silently accepted.
"""
import pytest

np = pytest.importorskip("numpy")

from mastering_chain import (Compressor, CompressorConfig, Limiter,
                             LimiterConfig)


def _limiter(**kw):
    base = dict(threshold=-1.0, lookahead=5.0, release=50.0)
    base.update(kw)
    return Limiter(LimiterConfig(**base), 44100)


def _compressor(**kw):
    base = dict(threshold=-20.0, ratio=4.0, attack=1.0, release=10.0)
    base.update(kw)
    return Compressor(CompressorConfig(**base), 44100)


def test_limiter_output_is_unshifted_and_complete():
    # Quiet input stays under threshold: output must equal input
    # sample-for-sample -- no zero prefix, no dropped tail.
    lim = _limiter()
    audio = np.ones(4410) * 0.001
    out = lim.process(audio)
    assert np.allclose(out, audio)


def test_limiter_stereo_unshifted():
    lim = _limiter()
    audio = np.vstack([np.ones(2000) * 0.001, np.ones(2000) * 0.002])
    out = lim.process(audio)
    assert np.allclose(out, audio)


def test_limiter_second_buffer_has_no_bleed():
    lim = _limiter()
    lim.process(np.ones(4410) * 0.9)
    out = lim.process(np.ones(4410) * 0.001)
    assert np.allclose(out, 0.001)


def test_compressor_envelope_resets():
    comp = _compressor()
    comp.process(np.ones(4410) * 0.9)
    assert comp.envelope > 0.5
    comp.process(np.zeros(4410))
    assert comp.envelope < 0.5


def test_limiter_sub_ms_release_does_not_divide_by_zero():
    lim = _limiter(release=0.01)  # rounds to 0 samples without the clamp
    out = lim.process(np.r_[np.ones(100) * 0.9, np.ones(100) * 0.01])
    assert np.all(np.isfinite(out))


@pytest.mark.parametrize("kw", [
    {"ratio": 0.0}, {"ratio": -2.0}, {"ratio": float("nan")},
    {"threshold": float("nan")}, {"attack": float("inf")},
    {"release": -1.0}, {"knee": float("nan")}, {"makeup_gain": float("inf")},
])
def test_compressor_rejects_invalid_config(kw):
    with pytest.raises(ValueError):
        _compressor(**kw)


@pytest.mark.parametrize("kw", [
    {"threshold": float("nan")}, {"lookahead": -1.0},
    {"lookahead": float("nan")}, {"release": float("inf")},
    {"release": -1.0},
])
def test_limiter_rejects_invalid_config(kw):
    with pytest.raises(ValueError):
        _limiter(**kw)
