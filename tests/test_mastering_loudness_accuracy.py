"""Covers the accuracy fixes to mastering_chain.LoudnessMeter and the
auto_adjust/dither correctness fixes made alongside them (CHARTER §9).

LoudnessMeter now reuses bs1770_loudness's exact BS.1770-4 K-weighting
coefficients via a single-pass scipy.signal.lfilter, instead of its own
approximate band-pass via scipy.signal.filtfilt. These tests require both
NumPy (mastering_chain's hard dependency) and SciPy (needed for the exact
K-weighting path -- without it, LoudnessMeter falls back to a rough RMS
estimate that these tests aren't checking); they skip under a minimal
install rather than assert a degraded path, matching test_mastering_wiring.py.
"""

import math

import numpy as np
import pytest

import mastering_chain
import bs1770_loudness

requires_scipy_bs1770 = pytest.mark.skipif(
    not (mastering_chain.HAS_SCIPY and mastering_chain.HAS_BS1770),
    reason="exact K-weighting needs scipy + bs1770_loudness",
)


def _sine(freq, sample_rate, count, amplitude=1.0):
    t = np.arange(count) / sample_rate
    return amplitude * np.sin(2 * np.pi * freq * t)


# --- measure_lufs matches the pure-Python reference implementation --------

@requires_scipy_bs1770
def test_mono_lufs_matches_pure_python_bs1770_loudness():
    # The scipy.signal.lfilter path and the pure-Python bs1770_loudness path
    # apply the same coefficients via different mechanisms; they must agree
    # to floating-point precision, not just "roughly".
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 5.0))

    meter = mastering_chain.LoudnessMeter(sample_rate)
    lufs_mastering = meter.measure_lufs(tone)
    lufs_reference = bs1770_loudness.measure_integrated_loudness(tone.tolist(), sample_rate)

    assert lufs_mastering == pytest.approx(lufs_reference, abs=1e-6)


@requires_scipy_bs1770
def test_identical_stereo_reads_3_01_lu_louder_than_mono():
    # BS.1770 sums per-channel energy; averaging (the pre-fix behavior)
    # under-reads identical-content stereo by 10*log10(2) ~= 3.01 dB.
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 3.0))
    stereo = np.array([tone, tone])

    meter = mastering_chain.LoudnessMeter(sample_rate)
    mono_lufs = meter.measure_lufs(tone)
    stereo_lufs = meter.measure_lufs(stereo)

    assert stereo_lufs - mono_lufs == pytest.approx(10 * math.log10(2), abs=0.05)


@requires_scipy_bs1770
def test_measure_lufs_gates_out_short_clips():
    sample_rate = 48000
    short = _sine(1000.0, sample_rate, int(sample_rate * 0.1))  # 100ms < 400ms block

    meter = mastering_chain.LoudnessMeter(sample_rate)
    assert meter.measure_lufs(short) == float('-inf')


# --- setup_filters: low/zero sample-rate handling (found by adversarial review) ---

def test_zero_sample_rate_does_not_crash():
    # bs1770_loudness's private coefficient functions divide by sample_rate
    # with no validation (only the public apply_k_weighting wrapper checks);
    # setup_filters must validate explicitly rather than rely on an
    # exception those functions never raise.
    meter = mastering_chain.LoudnessMeter(0)
    assert meter._bs1770_ready is False


@requires_scipy_bs1770
def test_unstable_low_sample_rate_falls_back_instead_of_diverging():
    # Below ~3.36kHz the stage-1 shelving filter's pole leaves the unit
    # circle and lfilter diverges to inf/NaN. 3000 Hz is comfortably inside
    # the unstable region; the meter must fall back to the RMS
    # approximation (a finite number) rather than measure inf/NaN.
    sample_rate = 3000
    meter = mastering_chain.LoudnessMeter(sample_rate)
    assert meter._bs1770_ready is False

    tone = _sine(440.0, sample_rate, sample_rate * 2, amplitude=0.5)
    lufs = meter.measure_lufs(tone)
    assert math.isfinite(lufs)


@requires_scipy_bs1770
def test_stability_floor_itself_still_uses_exact_k_weighting():
    sample_rate = 8000  # the documented floor
    meter = mastering_chain.LoudnessMeter(sample_rate)
    assert meter._bs1770_ready is True


# --- NaN-in-input safety net (found by adversarial review) ----------------

@requires_scipy_bs1770
def test_measure_lufs_returns_nan_for_nan_input_instead_of_silently_dropping_it():
    # A single NaN sample contaminates the causal IIR filter's state for
    # every later sample, and the contaminated blocks simply fail the
    # gate's ">=" comparison -- silently discarding data rather than
    # surfacing an error. Must return NaN explicitly instead.
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 3.0), amplitude=0.5)
    tone[100] = float('nan')

    meter = mastering_chain.LoudnessMeter(sample_rate)
    assert math.isnan(meter.measure_lufs(tone))


@requires_scipy_bs1770
def test_measure_range_returns_nan_for_nan_input():
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 10.0), amplitude=0.5)
    tone[100] = float('nan')

    meter = mastering_chain.LoudnessMeter(sample_rate)
    assert math.isnan(meter.measure_range(tone))


# --- measure_range (LRA) ----------------------------------------------------

@requires_scipy_bs1770
def test_constant_level_signal_has_near_zero_lra():
    sample_rate = 48000
    tone = _sine(1000.0, sample_rate, int(sample_rate * 10.0))

    meter = mastering_chain.LoudnessMeter(sample_rate)
    lra = meter.measure_range(tone)

    assert lra < 0.5, lra


@requires_scipy_bs1770
def test_varying_level_signal_has_positive_lra():
    sample_rate = 48000
    loud = _sine(1000.0, sample_rate, int(sample_rate * 10.0), amplitude=1.0)
    quiet = _sine(1000.0, sample_rate, int(sample_rate * 10.0), amplitude=0.05)
    varying = np.concatenate([loud, quiet, loud, quiet])

    meter = mastering_chain.LoudnessMeter(sample_rate)
    lra = meter.measure_range(varying)

    assert lra > 1.0, lra


def test_measure_range_without_scipy_or_bs1770_returns_placeholder_zero():
    # Simulate the degraded path directly rather than uninstalling scipy.
    meter = mastering_chain.LoudnessMeter(48000)
    meter._bs1770_ready = False
    assert meter.measure_range(_sine(1000.0, 48000, 48000)) == 0.0


# --- auto_adjust: no aliasing / no infinite-gain propagation --------------

def test_auto_adjust_does_not_mutate_shared_config():
    config = mastering_chain.MasteringConfig(auto_gain=True)
    chain = mastering_chain.MasteringChain(config, sample_rate=48000)
    tone = _sine(1000.0, 48000, int(48000 * 3.0), amplitude=0.3)
    original_gain = chain.config.compressor.makeup_gain

    chain.auto_adjust(tone)

    assert chain.config.compressor.makeup_gain == original_gain


def test_auto_adjust_is_idempotent_across_repeated_calls():
    config = mastering_chain.MasteringConfig(auto_gain=True)
    chain = mastering_chain.MasteringChain(config, sample_rate=48000)
    tone = _sine(1000.0, 48000, int(48000 * 3.0), amplitude=0.3)

    first = chain.auto_adjust(tone)
    second = chain.auto_adjust(tone)

    assert first.compressor.makeup_gain == second.compressor.makeup_gain


@requires_scipy_bs1770
def test_process_does_not_produce_nan_for_a_clip_shorter_than_one_block():
    # A clip shorter than 400ms gates out entirely (-inf LUFS). Before the
    # fix, auto_adjust computed target_lufs - (-inf) = +inf and added it to
    # makeup_gain, propagating NaN through the compressor/limiter.
    sample_rate = 44100
    short = _sine(440.0, sample_rate, int(sample_rate * 0.3), amplitude=0.6)

    chain = mastering_chain.MasteringChain(
        mastering_chain.MasteringConfig(auto_gain=True), sample_rate=sample_rate
    )
    processed, info = chain.process(short)

    assert not np.any(np.isnan(processed))
    assert not np.any(np.isinf(processed))
    assert info['input_analysis']['lufs'] == float('-inf')


# --- dither: unknown types fall back instead of silently no-opping --------

def test_unknown_dither_type_falls_back_to_tpdf_not_silence(caplog):
    config = mastering_chain.MasteringConfig()
    chain = mastering_chain.MasteringChain(config, sample_rate=48000)
    audio = np.zeros((2, 1000))

    dithered = chain._apply_dither(audio, "shaped")

    assert not np.array_equal(dithered, audio)  # dither noise was actually added


# --- analyze(): dynamic_range is no longer a P95/P10 blow-up --------------

def test_dynamic_range_matches_crest_factor_not_a_percentile_ratio():
    config = mastering_chain.MasteringConfig(auto_gain=False)
    chain = mastering_chain.MasteringChain(config, sample_rate=48000)
    # Audio with a long near-silent stretch used to blow up the old P95/P10
    # ratio toward ~180dB; dynamic_range must track crest_factor instead.
    loud = _sine(1000.0, 48000, 48000, amplitude=0.8)
    silence = np.zeros(48000 * 5)
    audio = np.concatenate([loud, silence])

    analysis = chain.analyze(audio)

    assert analysis['dynamic_range'] == analysis['crest_factor']
    assert abs(analysis['dynamic_range']) < 100  # sane dB range, not ~180dB
