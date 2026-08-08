"""EBU Mode momentary (M) and short-term (S) loudness.

EBU Tech 3341's "EBU Mode" is Momentary + Short-term + Integrated. The
integrated (gated) meter was already covered by test_bs1770_loudness.py;
these tests cover the two ungated sliding-window meters:

    Momentary  (M): 400 ms window, ungated
    Short-term (S): 3 s   window, ungated

The primary Tech 3341 PDF could not be fetched in the environment where this
was written, so rather than asserting against transcribed reference numbers,
these tests assert *first-principles invariants* that any correct
implementation must satisfy -- most importantly that a stationary signal
yields M == S == I, since all three then average the same energy.
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
