"""Limiter lookahead correctness (mastering_chain.Limiter).

The previous implementation delayed the signal through a zero-filled buffer
instead of looking ahead on the input itself. Verified empirically before the
rewrite: the output opened with `lookahead` zeros, the last `lookahead`
samples of every call were dropped entirely (the second call re-emitted the
first call's tail as its leading chunk), `lookahead=0` crashed on an empty
window max, and `release=0` divided by zero.

These tests pin the direct form: `out[i] = audio[i] · g[i]` with `g[i]`
driven by `max|audio[i:i+L)|` — proven the same gain alignment the delayed
form intended, minus the artifacts. numpy-gated like every mastering test.
"""

import pytest

import main

requires_numpy = pytest.mark.skipif(not main.HAS_NUMPY, reason="mastering_chain needs numpy")


def _limiter(**kw):
    from mastering_chain import Limiter, LimiterConfig
    return Limiter(LimiterConfig(**kw), sample_rate=44100)


@requires_numpy
def test_limiter_output_covers_every_input_sample():
    """No leading zero pad, no dropped tail: out[i] must be audio[i] scaled,
    for every i — the old delayed form emitted L zeros then audio[:N-L]."""
    import numpy as np
    n = 1000
    audio = np.linspace(0.0, 0.4, n)
    audio[500] = 0.9  # a single over-threshold peak mid-buffer
    lim = _limiter(threshold=-1.0, lookahead=5.0, release=50.0)

    out = lim.process(audio)

    assert len(out) == n
    # Leading samples pass through (sub-threshold → gain 1.0), not zeros.
    assert out[0] == pytest.approx(audio[0])
    assert out[100] == pytest.approx(audio[100])
    # Tail samples are processed, not dropped: out[-1] ≠ 0.
    assert out[-1] == pytest.approx(audio[-1] * lim.gain_reduction)


@requires_numpy
def test_limiter_lookahead_engages_gain_before_the_peak():
    """With lookahead, reduction is already in place when the peak arrives —
    the sample at the peak reads ≤ threshold, not the un-limited original."""
    import numpy as np
    n = 800
    audio = np.full(n, 0.2)
    peak_at = 600
    audio[peak_at] = 1.0
    lim = _limiter(threshold=-1.0, lookahead=5.0, release=50.0)
    threshold_lin = 10 ** (-1.0 / 20)

    out = lim.process(audio)

    assert abs(out[peak_at]) <= threshold_lin + 1e-6


@requires_numpy
def test_limiter_zero_lookahead_and_release_do_not_crash():
    """0 ms lookahead rounds to 0 samples (empty window → .max() crashed);
    0 ms release divided by zero. max(1, …) makes both the degenerate-but-
    safe floor: instant lookahead, instant release."""
    import numpy as np
    audio = np.linspace(-0.5, 0.5, 400)
    lim = _limiter(threshold=-1.0, lookahead=0.0, release=0.0)

    out = lim.process(audio)

    assert len(out) == len(audio)
    assert np.isfinite(out).all()


@requires_numpy
def test_limiter_stereo_covers_every_input_sample_and_stays_linked():
    """Stereo shares the same fix: every input frame emitted (no pad/tail
    loss), one gain for both channels so the image doesn't wobble."""
    import numpy as np
    from mastering_chain import Limiter, LimiterConfig
    lim = Limiter(LimiterConfig(threshold=-1.0, lookahead=5.0, release=50.0), 44100)

    n = 600
    audio = np.vstack([
        np.linspace(0.0, 0.3, n),
        np.linspace(0.0, 0.3, n) * 0.5,
    ])
    audio[0, 400] = 1.0  # peak on left only — linked gain must clip it

    out = lim.process(audio)

    assert out.shape == audio.shape
    threshold_lin = 10 ** (-1.0 / 20)
    assert abs(out[0, 400]) <= threshold_lin + 1e-6
    # Both channels scaled by the same gain at every sample — the right
    # channel's shape is preserved, just attenuated.
    assert (out[1, 400] / audio[1, 400]) == pytest.approx(out[0, 400] / audio[0, 400])
    assert out[0, -1] != 0.0  # tail emitted, not dropped
