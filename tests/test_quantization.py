"""16-bit quantisation: rounding, bias, and opt-in dither.

`_save_wav_basic` used `(audio * 32767).astype(np.int16)`, which truncates
toward zero. That is a biased quantiser: on single-signed material every
sample is pulled toward zero by up to a full LSB, and the worst-case error is
twice what rounding gives. These tests pin the corrected behaviour.

Dither is deliberately off by default -- CHARTER §1 sells the tool on
deterministic, reproducible output, and dither is noise from a random source.
The tests assert both halves of that trade: identical bytes by default,
different bytes when the user opts in.
"""

import tempfile
import warnings
import wave
from pathlib import Path

import pytest

# Guarded so the suite is runnable on the project's own default install, which
# has no third-party packages at all. An unguarded `import numpy` here made
# collection fail outright, so the dependency-free core could not be verified
# without first installing the dependency it is defined by not needing.
np = pytest.importorskip("numpy")

import main


def _write_and_read(signal, *, apply_dither=False):
    config = main.ProcessingConfig()
    config.apply_dither = apply_dither
    processor = main.AudioProcessor(config)

    directory = Path(tempfile.mkdtemp())
    path = directory / "out.wav"
    processor._save_wav_basic(np.asarray(signal, dtype=np.float32), str(path), 48000)

    with wave.open(str(path)) as handle:
        raw = handle.readframes(handle.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(float)


def test_quantisation_rounds_to_nearest_rather_than_truncating():
    # 0.30001 * 32767 = 9830.43 -> nearest is 9830; truncation also gives 9830
    # here, so use a value whose fraction is above .5 to separate them.
    # 0.30003 * 32767 = 9831.08... choose one clearly above .5:
    value = 9830.7 / 32767.0
    written = _write_and_read(np.full(1000, value, dtype=np.float32))

    assert written[0] == 9831  # rounded up; truncation would have given 9830


def test_rounding_removes_the_toward_zero_bias_on_single_signed_audio():
    rng = np.random.default_rng(0)
    signal = (rng.random(20000) * 0.5).astype(np.float32)  # all positive

    written = _write_and_read(signal)
    ideal = signal.astype(np.float64) * 32767.0

    mean_error = (written - ideal).mean()
    # Truncation toward zero would sit near -0.5 LSB on this material.
    assert abs(mean_error) < 0.1


def test_worst_case_quantisation_error_is_half_an_lsb():
    rng = np.random.default_rng(1)
    signal = ((rng.random(20000) * 2.0 - 1.0) * 0.5).astype(np.float32)

    written = _write_and_read(signal)
    # Compute the target in float32, matching the precision the writer works
    # in -- widening to float64 first shifts values by ~1e-3 LSB and makes an
    # exact 0.5 boundary look like a 0.5005 violation.
    ideal = np.clip(signal, -1.0, 1.0) * np.float32(32767.0)

    # Rounding bounds the error at 0.5 LSB; truncation allows a full LSB.
    assert np.abs(written - ideal.astype(np.float64)).max() <= 0.5 + 1e-6


def test_output_is_deterministic_by_default():
    signal = np.full(5000, 0.30001, dtype=np.float32)

    first = _write_and_read(signal)
    second = _write_and_read(signal)

    assert np.array_equal(first, second)


def test_opting_into_dither_changes_the_output_and_is_not_deterministic():
    signal = np.full(5000, 0.30001, dtype=np.float32)

    undithered = _write_and_read(signal)
    dithered = _write_and_read(signal, apply_dither=True)
    dithered_again = _write_and_read(signal, apply_dither=True)

    assert not np.array_equal(undithered, dithered)
    # Dither is genuine noise, so two dithered runs must differ too.
    assert not np.array_equal(dithered, dithered_again)


def test_dither_makes_the_average_converge_on_the_true_value():
    # This is the reason to dither at all. A constant that falls between two
    # codes quantises to the same wrong code every time, so the error is a
    # fixed DC offset. TPDF dither decorrelates the error from the signal, so
    # the *average* of the dithered codes lands on the true value even though
    # each individual sample is still one of two integers.
    value = 0.30001
    ideal = value * 32767.0  # 9830.43 -- between codes 9830 and 9831
    signal = np.full(20000, value, dtype=np.float32)

    undithered = _write_and_read(signal)
    dithered = _write_and_read(signal, apply_dither=True)

    undithered_error = abs(undithered.mean() - ideal)
    dithered_error = abs(dithered.mean() - ideal)

    assert undithered_error > 0.4  # stuck on one code, ~0.43 LSB off
    assert dithered_error < 0.05  # averages onto the true value
    assert dithered_error < undithered_error

    # Individual samples still stay in the immediate neighbourhood -- dither
    # must not be a gross level shift.
    assert np.abs(dithered - ideal).max() <= 2.0


def test_full_scale_input_does_not_wrap_around():
    # Dither pushes samples past +32767; clipping must catch it rather than
    # wrapping to a large negative int16.
    signal = np.ones(5000, dtype=np.float32)

    written = _write_and_read(signal, apply_dither=True)

    assert written.max() <= 32767
    assert written.min() >= 0  # no wrap to negative


def test_non_finite_samples_write_defined_pcm_not_garbage():
    # The int16 cast cannot represent NaN/inf -- without substitution they
    # become platform-dependent garbage under a RuntimeWarning. The writer
    # substitutes defined values: NaN -> 0 (silence), +/-inf -> the rails.
    # (On this platform the garbage cast happens to yield the same PCM, so
    # the written values alone cannot pin the fix -- the RuntimeWarning is
    # the observable difference. Catch it explicitly.)
    signal = np.array([0.5, np.nan, -np.inf, np.inf, 0.25], dtype=np.float32)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        written = _write_and_read(signal)

    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert written[0] == round(0.5 * 32767)
    assert written[1] == 0          # NaN -> silence
    assert written[2] == -32767     # -inf -> lower rail
    assert written[3] == 32767      # +inf -> upper rail
    assert written[4] == round(0.25 * 32767)
    assert np.isfinite(written).all()


class _CollectingLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append(message % args if args else message)


def test_save_audio_warns_on_non_finite_samples():
    # Silent substitution would hide a corrupt pipeline stage; the write must
    # report how many samples were NaN/inf.
    config = main.ProcessingConfig()
    processor = main.AudioProcessor(config)
    collector = _CollectingLogger()
    processor.logger = collector
    path = Path(tempfile.mkdtemp()) / "out.wav"

    processor.save_audio(
        np.array([0.5, np.nan, 0.25], dtype=np.float32), str(path), 48000
    )

    assert any("non-finite" in message for message in collector.warnings)


def test_save_audio_does_not_warn_on_finite_audio():
    # The non-finite warning must not fire on clean input.
    config = main.ProcessingConfig()
    processor = main.AudioProcessor(config)
    collector = _CollectingLogger()
    processor.logger = collector
    path = Path(tempfile.mkdtemp()) / "out.wav"

    processor.save_audio(
        np.array([0.5, -0.5, 0.25], dtype=np.float32), str(path), 48000
    )

    assert not any("non-finite" in message for message in collector.warnings)
