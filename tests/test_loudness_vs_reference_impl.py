"""Cross-check the loudness meter against an independent implementation.

Everything else validating `bs1770_loudness` is either self-referential (our
own tests) or derived from first principles. This file adds the one kind of
evidence those cannot give: agreement with a separate, widely-used
implementation of the same standard, written by other people from the same
document.

`pyloudnorm` is an optional *test-only* dependency. It is deliberately not in
any install extra -- the product's whole point is that the loudness meter
needs no third-party packages -- so these tests skip when it is absent.

Recorded result at the time of writing: integrated loudness agrees to within
0.043 LU across sines from 100 Hz to 5 kHz, noise, and dynamic programme
material. That gap is a flat ~0.043 dB offset in the K-weighting passband,
and it is *pyloudnorm's*: our stage-1 coefficients match the BS.1770-4
published table to ~1e-12, pyloudnorm's to ~1e-4. EBU Tech 3341 allows
+/-0.1 LU, so both are conformant; we are simply nearer the printed numbers.
"""

import numpy as np
import pytest

import bs1770_loudness

pyloudnorm = pytest.importorskip(
    "pyloudnorm", reason="optional test-only reference implementation")


SAMPLE_RATE = 48000
# EBU Tech 3341 tolerance for an "EBU Mode" meter.
TOLERANCE_LU = 0.1


def _sine(freq, seconds=5.0, amplitude=0.5):
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return amplitude * np.sin(2 * np.pi * freq * t)


def _ours(signal):
    return bs1770_loudness.measure_integrated_loudness_multichannel(
        [np.asarray(signal, dtype=float).tolist()], SAMPLE_RATE)


def _reference(signal):
    return pyloudnorm.Meter(SAMPLE_RATE).integrated_loudness(
        np.asarray(signal, dtype=float))


@pytest.mark.parametrize("freq", [100.0, 1000.0, 5000.0])
def test_integrated_loudness_matches_the_reference_for_sines(freq):
    signal = _sine(freq)
    assert _ours(signal) == pytest.approx(_reference(signal), abs=TOLERANCE_LU)


def test_integrated_loudness_matches_the_reference_for_noise():
    rng = np.random.default_rng(0)
    signal = 0.1 * rng.standard_normal(SAMPLE_RATE * 5)
    assert _ours(signal) == pytest.approx(_reference(signal), abs=TOLERANCE_LU)


def test_integrated_loudness_matches_the_reference_across_a_gate_boundary():
    # Quiet passage then loud, so the relative gate actually does something.
    quiet = _sine(1000.0, seconds=2.0, amplitude=0.02)
    loud = _sine(1000.0, seconds=3.0, amplitude=0.5)
    signal = np.concatenate([quiet, loud])

    assert _ours(signal) == pytest.approx(_reference(signal), abs=TOLERANCE_LU)


def test_level_changes_track_the_reference_exactly():
    # Absolute agreement is bounded by the coefficient difference; the
    # *response* to a level change should have no such offset at all.
    quiet, loud = _sine(1000.0, amplitude=0.1), _sine(1000.0, amplitude=0.2)

    ours_delta = _ours(loud) - _ours(quiet)
    reference_delta = _reference(loud) - _reference(quiet)

    assert ours_delta == pytest.approx(reference_delta, abs=0.01)
    assert ours_delta == pytest.approx(6.02, abs=0.05)  # doubling amplitude


def test_our_coefficients_are_closer_to_the_published_table():
    # BS.1770-4 Table 1, stage 1 (high shelf) at 48 kHz.
    published_b = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    published_a2 = 0.73248077421585

    ours = bs1770_loudness._stage1_head_effects(SAMPLE_RATE)
    reference_filter = pyloudnorm.Meter(SAMPLE_RATE)._filters["high_shelf"]

    our_error = max(abs(mine - pub) for mine, pub
                    in zip([ours.b0, ours.b1, ours.b2], published_b))
    reference_error = max(abs(theirs - pub) for theirs, pub
                          in zip(reference_filter.b, published_b))

    assert our_error < 1e-9
    assert abs(ours.a2 - published_a2) < 1e-9
    # Not a competition -- this pins *why* the two meters differ slightly, so
    # a future reader does not "fix" ours toward the reference.
    assert our_error < reference_error
