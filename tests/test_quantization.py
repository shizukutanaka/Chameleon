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


def _save_and_read_via_save_audio(signal, *, apply_dither=False, bit_depth=16):
    """Drive the primary write path (soundfile when present) and read the
    PCM back with the stdlib wave module."""
    config = main.ProcessingConfig()
    config.apply_dither = apply_dither
    processor = main.AudioProcessor(config)

    directory = Path(tempfile.mkdtemp())
    path = directory / "out.wav"
    written = processor.save_audio(
        np.asarray(signal, dtype=np.float32), str(path), 48000,
        bit_depth=bit_depth)
    assert written == bit_depth

    with wave.open(str(path)) as handle:
        raw = handle.readframes(handle.getnframes())
        width = handle.getsampwidth()
    if width == 2:
        return np.frombuffer(raw, dtype=np.int16).astype(float)
    # 24-bit PCM: unpack manually (little-endian, sign-extended)
    a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
    ints = (a[:, 0].astype(np.int32)
            | (a[:, 1].astype(np.int32) << 8)
            | (a[:, 2].astype(np.int32) << 16))
    ints = np.where(ints & 0x800000, ints - 0x1000000, ints)
    return ints.astype(float)


def test_apply_dither_also_dithers_on_the_soundfile_path():
    # Before this fix, apply_dither only existed in the soundfile-free
    # fallback: on a full install the same config silently wrote undithered
    # output. A constant between two codes must decorrelate on BOTH paths.
    if not main.HAS_SOUNDFILE:
        pytest.skip("soundfile not installed")

    signal = np.full(20000, 9830.43 / 32767.0, dtype=np.float32)
    undithered = _save_and_read_via_save_audio(signal)
    dithered = _save_and_read_via_save_audio(signal, apply_dither=True)

    # Without dither every sample quantises to one code; with TPDF dither
    # the codes spread and the mean sits within an LSB of the true
    # 9830.43 (libsndfile's own float->int quantizer is not plain
    # round-to-nearest, so we don't pin a tighter convergence).
    assert set(undithered.tolist()) == {9830.0}
    assert len(set(dithered.tolist())) >= 2
    assert abs(dithered.mean() - 9830.43) < 1.0
    assert not np.array_equal(undithered, dithered)


def test_apply_dither_scales_to_24_bit_depth():
    # At 24-bit the LSB is ~2e-7 in float; 16-bit-scaled dither would sit
    # hundreds of codes above the quantisation floor.
    if not main.HAS_SOUNDFILE:
        pytest.skip("soundfile not installed")

    signal = np.full(20000, 0.3, dtype=np.float32)
    codes = _save_and_read_via_save_audio(
        signal, apply_dither=True, bit_depth=24)
    ideal = 0.3 * 8388607.0

    # The spread that proves dithering happened, but bounded at +-3 LSB of
    # THIS depth -- 16-bit-scaled dither would sit ~512 codes wide.
    assert len(set(codes.tolist())) >= 2
    assert np.abs(codes - ideal).max() <= 3.0
