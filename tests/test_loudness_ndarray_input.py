"""Public loudness API must accept ndarrays, not only lists.

The exported meters type-annotate `Sequence[float]`/`Sequence[Sequence]`
and callers feed them exactly what `load_wav` returns: numpy arrays. Each
guard was written `if not <seq>:` -- on an ndarray that raises
`ValueError: truth value of an array ... is ambiguous`, so every exported
meter crashed on its most natural input dtype. The check is now
`len(...) == 0`.
"""

import pytest

np = pytest.importorskip("numpy")

import bs1770_loudness

SAMPLE_RATE = 44100


@pytest.fixture
def tone():
    return 0.5 * np.sin(2 * np.pi * 440 * np.arange(SAMPLE_RATE) / SAMPLE_RATE)


def test_integrated_loudness_accepts_ndarray(tone):
    assert np.isfinite(bs1770_loudness.measure_integrated_loudness(tone, SAMPLE_RATE))


def test_integrated_loudness_multichannel_accepts_ndarray(tone):
    assert np.isfinite(
        bs1770_loudness.measure_integrated_loudness_multichannel(
            np.stack([tone, tone]), SAMPLE_RATE))


def test_momentary_and_short_term_accept_ndarray(tone):
    assert bs1770_loudness.measure_momentary_loudness(np.stack([tone]), SAMPLE_RATE)
    assert bs1770_loudness.measure_max_momentary_loudness(np.stack([tone]), SAMPLE_RATE)
    # 1 s is shorter than the 3 s short-term window: an empty series, not a crash.
    assert bs1770_loudness.measure_short_term_loudness(np.stack([tone]), SAMPLE_RATE) == []


def test_true_peak_accepts_ndarray(tone):
    assert np.isfinite(bs1770_loudness.measure_true_peak(tone))
    assert np.isfinite(bs1770_loudness.measure_true_peak_multichannel(np.stack([tone, tone])))


def test_empty_ndarray_still_means_silence():
    assert bs1770_loudness.measure_integrated_loudness(np.array([]), SAMPLE_RATE) == float("-inf")
    assert bs1770_loudness.measure_true_peak_multichannel(
        np.zeros((2, 0))) == float("-inf")
