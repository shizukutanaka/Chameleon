"""Range guards on the exported RBJ biquad designers.

ParametricEQ pre-filters out-of-range bands (audit 32), but the module-level
design_peaking_eq / design_shelf_eq accepted anything: a frequency above
Nyquist or below zero produced finite, real-looking coefficients for a
filter centred on an aliased or mirrored position, and a non-positive
Q or slope was clamped to 1e-6 -- silently designing a resonator instead
of the band the caller typo'd.
"""

import math

import pytest

# mastering_chain imports numpy at module scope; on the project's default
# (zero-dependency) install this module cannot be collected at all.
np = pytest.importorskip("numpy")

import mastering_chain

SR = 44100


@pytest.mark.parametrize("frequency", [0, -100, SR / 2, 48000, math.nan, math.inf])
def test_peaking_eq_rejects_unrealizable_frequencies(frequency):
    with pytest.raises(ValueError):
        mastering_chain.design_peaking_eq(frequency, SR, 6.0)


@pytest.mark.parametrize("frequency", [0, -100, SR / 2, 48000, math.nan])
def test_shelf_eq_rejects_unrealizable_frequencies(frequency):
    with pytest.raises(ValueError):
        mastering_chain.design_shelf_eq(frequency, SR, 6.0, high=True)


@pytest.mark.parametrize("q", [0.0, -1.0, -0.7, math.nan])
def test_peaking_eq_rejects_non_positive_q(q):
    # q <= 0 used to be clamped to 1e-6: the caller's typo became an
    # extreme resonator and the coefficients still looked plausible.
    with pytest.raises(ValueError):
        mastering_chain.design_peaking_eq(1000, SR, 6.0, q)


@pytest.mark.parametrize("slope", [0.0, -1.0, math.nan])
def test_shelf_eq_rejects_non_positive_slope(slope):
    with pytest.raises(ValueError):
        mastering_chain.design_shelf_eq(1000, SR, 6.0, high=False, slope=slope)


def test_both_designers_reject_nonfinite_gain():
    with pytest.raises(ValueError):
        mastering_chain.design_peaking_eq(1000, SR, math.nan)
    with pytest.raises(ValueError):
        mastering_chain.design_shelf_eq(1000, SR, math.inf, high=True)


def test_both_designers_reject_bad_sample_rate():
    for sr in (0, -44100, math.nan):
        with pytest.raises(ValueError):
            mastering_chain.design_peaking_eq(1000, sr, 6.0)
        with pytest.raises(ValueError):
            mastering_chain.design_shelf_eq(1000, sr, 6.0, high=False)


def test_zero_gain_designs_the_identity_filter():
    # 0 dB must be a true pass-through: b == a exactly.
    b, a = mastering_chain.design_peaking_eq(1000, SR, 0.0, 1.0)
    assert b == a
    b, a = mastering_chain.design_shelf_eq(1000, SR, 0.0, high=False)
    assert b == a


def test_valid_params_still_design_finite_coefficients():
    b, a = mastering_chain.design_peaking_eq(1000, SR, 6.0, 0.7)
    assert all(math.isfinite(c) for c in b + a)
    b, a = mastering_chain.design_shelf_eq(200, SR, -3.0, high=False, slope=0.7)
    assert all(math.isfinite(c) for c in b + a)
