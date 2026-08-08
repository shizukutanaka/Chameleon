"""EBU Mode: momentary (M), short-term (S) and loudness range (LRA).

EBU Tech 3341's "EBU Mode" is Momentary + Short-term + Integrated + LRA. The
integrated (gated) meter is covered by test_bs1770_loudness.py; this file
covers the rest:

    Momentary  (M): 400 ms window, ungated          (Tech 3341)
    Short-term (S): 3 s   window, ungated           (Tech 3341)
    LRA:            P95 - P10 of gated S, in LU     (Tech 3342)

Neither primary document could be fetched in the environment where this was
written, so rather than asserting against transcribed reference numbers,
these tests assert *first-principles invariants* that any correct
implementation must satisfy: a stationary signal yields M == S == I (all
three then average the same energy), and a signal alternating between two
amplitudes yields an LRA equal to the dB difference between them (that is
what a loudness *range* means). The LRA is additionally cross-checked against
the independent numpy/scipy implementation in mastering_chain.
"""

import math

import pytest

import bs1770_loudness as bs1770


def _sine(freq, sample_rate, count, amplitude=1.0):
    return [amplitude * math.sin(2 * math.pi * freq * i / sample_rate)
            for i in range(count)]


# --- the core invariant: stationary signal => M == S == I ------------------

def test_stationary_signal_gives_identical_momentary_short_term_integrated():
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, sample_rate * 10, amplitude=0.5)

    integrated = bs1770.measure_integrated_loudness_multichannel([tone], sample_rate)
    max_m = bs1770.measure_max_momentary_loudness([tone], sample_rate)
    max_s = bs1770.measure_max_short_term_loudness([tone], sample_rate)

    assert math.isfinite(integrated)
    # A steady tone has the same energy in every window, so all three meters
    # must agree -- they differ only in window length and gating.
    assert max_m == pytest.approx(integrated, abs=0.1)
    assert max_s == pytest.approx(integrated, abs=0.1)


# --- window length semantics: M must react faster than S ------------------

def test_momentary_reacts_faster_than_short_term_after_a_level_step():
    sample_rate = 48000
    quiet = _sine(1000.0, sample_rate, sample_rate * 5, amplitude=0.02)
    loud = _sine(1000.0, sample_rate, sample_rate * 5, amplitude=0.5)
    channel = quiet + loud

    momentary = bs1770.measure_momentary_loudness([channel], sample_rate)
    short_term = bs1770.measure_short_term_loudness([channel], sample_rate)

    # Index of the window ENDING at t=5.5s, i.e. 0.5s after the step.
    # A 400ms window is entirely inside the loud region by then; a 3s window
    # is still mostly averaging the quiet region.
    m_index = int(round((5.5 - 0.4) / 0.1))
    s_index = int(round((5.5 - 3.0) / 0.1))

    assert momentary[m_index] > short_term[s_index]


# --- ungated: quiet passages must survive in the series -------------------

def test_momentary_and_short_term_are_not_gated():
    sample_rate = 48000
    quiet = _sine(1000.0, sample_rate, sample_rate * 4, amplitude=0.02)
    loud = _sine(1000.0, sample_rate, sample_rate * 6, amplitude=0.5)
    channel = quiet + loud

    momentary = bs1770.measure_momentary_loudness([channel], sample_rate)

    # The quiet section sits far below the -10 LU relative gate that the
    # integrated meter applies. EBU Mode M/S are ungated, so those windows
    # must still be present in the series.
    assert any(value < -30.0 for value in momentary)


# --- series geometry: 100 ms hop (10 Hz refresh) --------------------------

def test_series_length_matches_a_100ms_hop():
    sample_rate = 48000
    seconds = 10
    tone = _sine(1000.0, sample_rate, sample_rate * seconds, amplitude=0.5)

    momentary = bs1770.measure_momentary_loudness([tone], sample_rate)
    short_term = bs1770.measure_short_term_loudness([tone], sample_rate)

    total = sample_rate * seconds
    hop = int(round(0.1 * sample_rate))
    expected_m = (total - int(round(0.4 * sample_rate))) // hop + 1
    expected_s = (total - int(round(3.0 * sample_rate))) // hop + 1

    assert len(momentary) == expected_m
    assert len(short_term) == expected_s


# --- boundaries -----------------------------------------------------------

def test_signal_shorter_than_the_window_returns_empty_series():
    sample_rate = 48000
    short = _sine(1000.0, sample_rate, int(sample_rate * 0.2))  # 200 ms

    assert bs1770.measure_momentary_loudness([short], sample_rate) == []
    # 1 s is long enough for a 400ms window but not a 3s one.
    one_second = _sine(1000.0, sample_rate, sample_rate)
    assert bs1770.measure_momentary_loudness([one_second], sample_rate) != []
    assert bs1770.measure_short_term_loudness([one_second], sample_rate) == []


def test_no_channels_returns_empty_and_negative_infinity():
    assert bs1770.measure_momentary_loudness([], 48000) == []
    assert bs1770.measure_short_term_loudness([], 48000) == []
    assert bs1770.measure_max_momentary_loudness([], 48000) == float('-inf')
    assert bs1770.measure_max_short_term_loudness([], 48000) == float('-inf')


def test_digital_silence_reports_negative_infinity_max():
    sample_rate = 48000
    silence = [0.0] * (sample_rate * 5)

    assert bs1770.measure_max_momentary_loudness([silence], sample_rate) == float('-inf')
    assert bs1770.measure_max_short_term_loudness([silence], sample_rate) == float('-inf')


def test_stereo_sums_channel_energy_like_the_integrated_meter():
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, sample_rate * 5, amplitude=0.5)

    mono_max_m = bs1770.measure_max_momentary_loudness([tone], sample_rate)
    stereo_max_m = bs1770.measure_max_momentary_loudness([tone, tone], sample_rate)

    # Two identical channels sum to double the energy: +10*log10(2) = +3.01 LU.
    assert stereo_max_m == pytest.approx(mono_max_m + 3.01, abs=0.05)


# --- Loudness Range (LRA), EBU Tech 3342 ----------------------------------
#
# Same approach as above: the primary Tech 3342 document could not be fetched
# here, so these assert first-principles invariants rather than transcribed
# reference numbers. The sharpest one is that a signal alternating between two
# amplitudes must yield an LRA equal to the dB difference between them --
# that is what "loudness range" means, so it follows from the definition and
# needs no reference table.

def _alternating(sample_rate, amp_a, amp_b, block_seconds=5, repeats=2):
    channel = []
    for _ in range(repeats):
        channel += _sine(1000.0, sample_rate, sample_rate * block_seconds, amplitude=amp_a)
        channel += _sine(1000.0, sample_rate, sample_rate * block_seconds, amplitude=amp_b)
    return channel


def test_steady_signal_has_zero_loudness_range():
    sample_rate = 48000
    steady = _sine(1000.0, sample_rate, sample_rate * 20, amplitude=0.5)

    assert bs1770.measure_loudness_range([steady], sample_rate) == pytest.approx(0.0, abs=0.5)


@pytest.mark.parametrize("amp_a,amp_b", [(0.5, 0.25), (0.6, 0.15), (0.5, 0.05)])
def test_two_level_signal_range_equals_the_level_difference(amp_a, amp_b):
    sample_rate = 48000
    channel = _alternating(sample_rate, amp_a, amp_b)

    expected = 20.0 * math.log10(amp_a / amp_b)
    measured = bs1770.measure_loudness_range([channel], sample_rate)

    assert measured == pytest.approx(expected, abs=0.2)


def test_loudness_range_grows_with_the_level_spread():
    sample_rate = 48000
    narrow = bs1770.measure_loudness_range([_alternating(sample_rate, 0.5, 0.25)], sample_rate)
    wide = bs1770.measure_loudness_range([_alternating(sample_rate, 0.5, 0.05)], sample_rate)

    assert wide > narrow > 0.0


def test_unmeasurable_inputs_return_nan_not_zero():
    # NaN distinguishes "could not measure" from a real 0 LU (no variation).
    sample_rate = 48000

    assert math.isnan(bs1770.measure_loudness_range([], sample_rate))
    # Shorter than one 3 s short-term window.
    short = _sine(1000.0, sample_rate, sample_rate)
    assert math.isnan(bs1770.measure_loudness_range([short], sample_rate))
    assert math.isnan(bs1770.measure_loudness_range([[0.0] * (sample_rate * 10)], sample_rate))


def test_relative_gate_keeps_a_brief_quiet_tail_from_inflating_the_range():
    # A passage 40 LU below the body of the programme sits under the -20 LU
    # relative gate and must not widen the reported range to ~40 LU.
    sample_rate = 48000
    loud = _sine(1000.0, sample_rate, sample_rate * 15, amplitude=0.5)
    very_quiet = _sine(1000.0, sample_rate, sample_rate * 5, amplitude=0.005)

    measured = bs1770.measure_loudness_range([loud + very_quiet], sample_rate)

    assert measured < 25.0


def test_stdlib_lra_agrees_with_the_numpy_scipy_implementation():
    # Independent cross-check: mastering_chain computes LRA with scipy
    # filtering and np.percentile. Two separate implementations agreeing is
    # the substitute for the reference document we could not fetch.
    mastering_chain = pytest.importorskip("mastering_chain")
    numpy = pytest.importorskip("numpy")
    if not (mastering_chain.HAS_SCIPY and mastering_chain.HAS_BS1770):
        pytest.skip("exact K-weighting needs scipy + bs1770_loudness")

    sample_rate = 48000
    channel = _alternating(sample_rate, 0.6, 0.15)

    meter = mastering_chain.LoudnessMeter(sample_rate)
    theirs = meter.measure_range(numpy.array(channel, dtype=float))
    mine = bs1770.measure_loudness_range([channel], sample_rate)

    assert mine == pytest.approx(theirs, abs=0.1)
