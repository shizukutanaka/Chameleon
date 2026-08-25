"""What audio_restoration claims versus what it does.

Restoration is the one place where a tool is most tempted to overclaim: the
input is already damaged, so any output looks like progress. This module had
four ways of saying more than it did.

* `AdaptiveDenoiser.denoise` and `SpectralRepairer.repair_gaps` returned their
  input unchanged when librosa was absent -- and `AudioRestorer.restore` then
  listed "denoising" among the processes it had applied. On a numpy-only
  install, which is this project's own default, the pipeline reported five
  steps and performed four.
* `estimate_noise_profile`'s fallback returned a noise floor of 1.0 in every
  bin, which the subtraction turns into a blanket -20 dB across the file.
* `HumRemover._detect_hum` compared a bin against a neighbourhood that
  included the bin itself, so it answered True for a clean 440 Hz sine with no
  hum in it, and the notch filters ran unconditionally.
* `_calculate_metrics` exported `mean(restored**2) / mean((original -
  restored)**2)` under the name `snr_db`. That ratio measures how little the
  restorer changed the signal -- it is highest for a restorer that does
  nothing -- and says nothing about noise.

The property that ties these together, and the one worth defending hardest:
**a restorer handed clean audio must return it unchanged.**
"""

import numpy as np
import pytest

pytest.importorskip("scipy")

import audio_restoration


SAMPLE_RATE = 44100


def _sine(freq, amplitude=0.5, seconds=1.0):
    count = int(SAMPLE_RATE * seconds)
    return amplitude * np.sin(2 * np.pi * freq * np.arange(count) / SAMPLE_RATE)


def _level_db(signal, freq):
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freqs = np.fft.rfftfreq(len(signal), 1 / SAMPLE_RATE)
    return 20.0 * np.log10(spectrum[np.argmin(np.abs(freqs - freq))] / len(signal) + 1e-20)


# --- the central property -------------------------------------------------

def test_restoring_clean_audio_changes_nothing():
    restored, _ = audio_restoration.AudioRestorer().restore(_sine(440).copy(), SAMPLE_RATE)

    assert np.abs(restored - _sine(440)).max() == 0.0, (
        "restoration altered audio that had nothing wrong with it")


# --- reporting what actually ran ------------------------------------------

def test_a_step_that_could_not_run_is_reported_as_skipped():
    _, info = audio_restoration.AudioRestorer().restore(_sine(440), SAMPLE_RATE)

    listed = set(info["applied_processes"]) | {
        entry["process"] for entry in info["skipped_processes"]}
    assert "denoising" in listed

    if not audio_restoration.HAS_LIBROSA:
        assert "denoising" not in info["applied_processes"]
        skipped = {entry["process"]: entry["reason"] for entry in info["skipped_processes"]}
        assert "librosa" in skipped["denoising"]


def test_the_librosa_stages_refuse_rather_than_no_op():
    if audio_restoration.HAS_LIBROSA:
        pytest.skip("librosa present; the silent-fallback path cannot be reached")

    with pytest.raises(RuntimeError, match="librosa"):
        audio_restoration.AdaptiveDenoiser().denoise(_sine(440), SAMPLE_RATE)
    with pytest.raises(RuntimeError, match="librosa"):
        audio_restoration.SpectralRepairer().repair_gaps(_sine(440), [(100, 200)], SAMPLE_RATE)


def test_no_metric_is_called_snr_unless_it_is_one():
    _, info = audio_restoration.AudioRestorer().restore(_sine(440), SAMPLE_RATE)

    assert "snr_db" not in info["quality_metrics"], (
        "signal-to-change ratio must not ship under an SNR label")


# --- hum detection --------------------------------------------------------

def test_hum_is_not_detected_in_audio_that_has_none():
    remover = audio_restoration.HumRemover()

    assert remover._detect_hum(_sine(440), SAMPLE_RATE, 60.0) is False
    assert remover._detect_hum(_sine(440), SAMPLE_RATE, 50.0) is False


def test_hum_is_detected_when_present():
    remover = audio_restoration.HumRemover()
    hummy = _sine(440) + 0.1 * _sine(60, amplitude=1.0)

    assert remover._detect_hum(hummy, SAMPLE_RATE, 60.0) is True


def test_clean_audio_passes_through_the_hum_remover_untouched():
    # The point of a detector: with nothing to remove, five notch filters per
    # power-line frequency must not be applied anyway.
    clean = _sine(440)

    assert np.array_equal(
        audio_restoration.HumRemover().remove_hum(clean.copy(), SAMPLE_RATE), clean)


def test_hum_removal_cuts_the_hum_and_spares_the_music():
    hummy = _sine(440) + 0.1 * _sine(60, amplitude=1.0)

    cleaned = audio_restoration.HumRemover().remove_hum(hummy.copy(), SAMPLE_RATE)

    assert _level_db(hummy, 60.0) - _level_db(cleaned, 60.0) > 20.0
    assert abs(_level_db(cleaned, 440.0) - _level_db(hummy, 440.0)) < 0.5


# --- metrics that cannot blow up -----------------------------------------

def test_quiet_residual_metric_survives_input_with_no_quiet_part():
    # np.std of an empty or single-element slice is NaN and raises under the
    # project's -W error::RuntimeWarning DSP gate.
    loud = np.full(100, 0.5)

    assert audio_restoration.VinylRestorer()._calculate_snr_improvement(loud, loud) == 0.0


def test_quiet_residual_metric_reports_a_quieter_floor_as_positive():
    rng = np.random.default_rng(0)
    noisy = rng.standard_normal(10000) * 0.01   # well inside the |x| < 0.1 window
    quieter = noisy * 0.5

    value = audio_restoration.VinylRestorer()._calculate_snr_improvement(noisy, quieter)
    assert value == pytest.approx(6.02, abs=0.2)


def test_the_quiet_window_is_absolute_and_that_biases_loud_noise_floors():
    # Worth pinning because it is a real limitation of the measure, not a bug:
    # the "quiet part" is defined as |x| < 0.1 regardless of the material, so a
    # noise floor comparable to that window gets its own tail cut off and its
    # spread under-measured. At sigma = 0.05 the window sits at +/-2 sigma, the
    # truncated std is 0.044 rather than 0.05, and halving the noise therefore
    # reads as 4.9 dB instead of 6.0.
    rng = np.random.default_rng(0)
    noisy = rng.standard_normal(10000) * 0.05
    quieter = noisy * 0.5

    value = audio_restoration.VinylRestorer()._calculate_snr_improvement(noisy, quieter)
    assert value == pytest.approx(4.91, abs=0.2)


# --- claims in comments ---------------------------------------------------

def test_click_repair_does_not_claim_an_ar_model_it_never_fits():
    import inspect
    source = inspect.getsource(audio_restoration.ClickRemover.remove_clicks)

    assert "Use autoregressive prediction" not in source
    assert "surrounding = np.concatenate" not in source, (
        "the AR-model scaffolding was computed and discarded")
