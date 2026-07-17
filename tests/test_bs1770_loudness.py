"""Tests for bs1770_loudness.py — a pure stdlib ITU-R BS.1770 K-weighted
integrated loudness meter (CHARTER §9's "C1" follow-up).

The K-weighting biquad coefficients are validated against the published
BS.1770-4 Annex 1 reference values at 48kHz. The gated-loudness algorithm is
validated with signal-agnostic physical invariants (gain scaling, frequency
weighting, gating) rather than hardcoded "correct" LUFS numbers, since those
invariants hold regardless of small implementation differences and are a
stronger correctness signal.
"""

import math

import pytest

import bs1770_loudness as bs1770


def _sine(freq, sample_rate, count, amplitude=1.0):
    return [amplitude * math.sin(2 * math.pi * freq * i / sample_rate)
            for i in range(count)]


# --- K-weighting coefficients (reference values from BS.1770-4 Annex 1) ----

def test_stage1_coefficients_match_published_reference_at_48k():
    coeffs = bs1770._stage1_head_effects(48000)
    assert coeffs.b0 == pytest.approx(1.53512485958697, abs=1e-9)
    assert coeffs.b1 == pytest.approx(-2.69169618940638, abs=1e-9)
    assert coeffs.b2 == pytest.approx(1.19839281085285, abs=1e-9)
    assert coeffs.a1 == pytest.approx(-1.69065929318241, abs=1e-9)
    assert coeffs.a2 == pytest.approx(0.73248077421585, abs=1e-9)


def test_stage2_coefficients_match_published_reference_at_48k():
    # The reference table (and libebur128) leaves the numerator unnormalized
    # ([1.0, -2.0, 1.0]) and only divides the denominator by a0.
    coeffs = bs1770._stage2_high_pass(48000)
    assert coeffs.b0 == pytest.approx(1.0, abs=1e-12)
    assert coeffs.b1 == pytest.approx(-2.0, abs=1e-12)
    assert coeffs.b2 == pytest.approx(1.0, abs=1e-12)
    assert coeffs.a1 == pytest.approx(-1.99004745483398, abs=1e-9)
    assert coeffs.a2 == pytest.approx(0.99007225036621, abs=1e-9)


# --- Integrated loudness: physical invariants -------------------------------

def test_silence_returns_negative_infinity():
    sample_rate = 44100
    assert bs1770.measure_integrated_loudness([0.0] * sample_rate, sample_rate) == float('-inf')


def test_empty_input_returns_negative_infinity():
    assert bs1770.measure_integrated_loudness([], 44100) == float('-inf')


def test_signal_shorter_than_one_block_returns_negative_infinity():
    sample_rate = 44100
    short = _sine(1000.0, sample_rate, int(sample_rate * 0.1))  # 100ms < 400ms block
    assert bs1770.measure_integrated_loudness(short, sample_rate) == float('-inf')


def test_six_db_gain_doubles_measured_loudness_by_6_02_db():
    # Loudness is derived from mean-square energy, so scaling amplitude by 2x
    # must raise the measurement by exactly 20*log10(2) =~ 6.02 dB, regardless
    # of the K-weighting filter's exact frequency response. This holds for any
    # linear system, so it's a strong, implementation-agnostic check.
    sample_rate = 48000
    duration_samples = int(sample_rate * 2.0)
    tone = _sine(1000.0, sample_rate, duration_samples, amplitude=0.5)
    tone_2x = _sine(1000.0, sample_rate, duration_samples, amplitude=1.0)

    loud_1x = bs1770.measure_integrated_loudness(tone, sample_rate)
    loud_2x = bs1770.measure_integrated_loudness(tone_2x, sample_rate)

    assert loud_2x - loud_1x == pytest.approx(20 * math.log10(2), abs=0.05)


def test_low_frequency_is_attenuated_relative_to_midband():
    # K-weighting's high-pass stage should make a 40 Hz tone measure quieter
    # than a 1 kHz tone of identical amplitude — the whole point of the filter.
    sample_rate = 48000
    duration_samples = int(sample_rate * 2.0)
    low = _sine(40.0, sample_rate, duration_samples)
    mid = _sine(1000.0, sample_rate, duration_samples)

    loud_low = bs1770.measure_integrated_loudness(low, sample_rate)
    loud_mid = bs1770.measure_integrated_loudness(mid, sample_rate)

    assert loud_mid - loud_low > 3.0


def test_full_scale_1khz_tone_reads_close_to_minus_3_lufs():
    # Widely cited reference figure for a full-scale 997/1000 Hz sine under
    # BS.1770 K-weighting (RMS of a full-scale sine is -3.01 dBFS; K-weighting
    # is close to unity gain in the low-treble region around 1 kHz).
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 3.0))

    lufs = bs1770.measure_integrated_loudness(tone, sample_rate)

    assert -5.0 < lufs < -2.0, lufs


def test_absolute_gate_ignores_trailing_silence():
    # Appending true digital silence must not meaningfully change the
    # integrated loudness — the absolute (-70 LUFS) gate discards those
    # all-zero blocks before averaging.
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 3.0))
    padded = tone + [0.0] * int(sample_rate * 3.0)

    loud_tone_only = bs1770.measure_integrated_loudness(tone, sample_rate)
    loud_padded = bs1770.measure_integrated_loudness(padded, sample_rate)

    assert abs(loud_padded - loud_tone_only) < 0.5


def test_apply_k_weighting_rejects_non_positive_sample_rate():
    with pytest.raises(ValueError):
        bs1770.apply_k_weighting([0.0, 1.0, 0.0], 0)


def test_apply_k_weighting_rejects_unstable_low_sample_rate():
    # Below ~3.36 kHz the stage-1 shelving filter's pole leaves the unit
    # circle (numerically unstable), so this must raise rather than emit a
    # bogus finite-looking-but-wrong (or +inf/NaN) result. 3000 Hz is
    # comfortably inside the unstable region.
    with pytest.raises(ValueError):
        bs1770.apply_k_weighting([0.0] * 100, 3000)


def test_measure_integrated_loudness_propagates_low_sample_rate_error():
    with pytest.raises(ValueError):
        bs1770.measure_integrated_loudness([0.1] * 5000, 3000)


def test_apply_k_weighting_accepts_the_stability_floor():
    # 8000 Hz is the documented floor and must filter without error/instability.
    sample_rate = 8000
    samples = _sine(1000.0, sample_rate, sample_rate * 2)
    weighted = bs1770.apply_k_weighting(samples, sample_rate)
    assert all(math.isfinite(v) for v in weighted)


# --- Multichannel: BS.1770-correct energy summing vs. mono-downmix ---------

def test_multichannel_matches_mono_for_a_single_channel():
    # A single-channel list must reduce to exactly the mono function's result
    # (same K-weighting, same gating), since summing one channel's energy is
    # the same as not summing at all.
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 3.0))

    mono = bs1770.measure_integrated_loudness(tone, sample_rate)
    multi = bs1770.measure_integrated_loudness_multichannel([tone], sample_rate)

    assert multi == pytest.approx(mono, abs=1e-9)


def test_multichannel_identical_stereo_reads_3_01_lu_louder_than_mono_downmix():
    # This is the headline fix: averaging L/R to mono *before* filtering
    # under-reads identical-content stereo by exactly 10*log10(2) =~ 3.01 dB
    # (mean-square of the average of two identical signals is 1/2 the sum of
    # their individual mean-squares), since BS.1770 requires *summing*
    # per-channel energy, not averaging samples.
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 3.0))
    downmixed = tone  # averaging two identical channels reproduces the same signal

    loud_downmix = bs1770.measure_integrated_loudness(downmixed, sample_rate)
    loud_multichannel = bs1770.measure_integrated_loudness_multichannel([tone, tone], sample_rate)

    assert loud_multichannel - loud_downmix == pytest.approx(10 * math.log10(2), abs=0.05)


def test_multichannel_empty_channel_list_returns_negative_infinity():
    assert bs1770.measure_integrated_loudness_multichannel([], 48000) == float('-inf')


def test_multichannel_uses_the_shorter_channel_length():
    # Channels of mismatched length (shouldn't normally happen, but guard it)
    # must not crash -- use the shorter one rather than index out of range.
    sample_rate = 48000
    long_tone = _sine(1000.0, sample_rate, int(sample_rate * 3.0))
    short_tone = long_tone[: int(sample_rate * 2.0)]

    result = bs1770.measure_integrated_loudness_multichannel([long_tone, short_tone], sample_rate)
    assert math.isfinite(result)
