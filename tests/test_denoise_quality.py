"""Noise reduction: the noise estimate must not be the signal.

`remove_noise` estimated its noise profile from the first half second of the
file. That assumes every recording opens with silence. When one starts
straight into music, the "noise" it measured was the music's own spectrum and
the subtraction attacked the signal: a 440 Hz tone beginning at t=0 came out
20.0 dB down, with the overall level 19.4 dB lower.

The estimate is now the 10th percentile of each frequency bin over time,
scaled by the Rayleigh quantile-to-median ratio. These tests assert the two
properties that matter and are in tension with each other -- material with no
quiet lead-in must survive, and genuine noise must still be reduced -- so
neither can be traded away silently.
"""

import math

import pytest

# Guarded so the suite is runnable on the project's own default install, which
# has no third-party packages at all. An unguarded `import numpy` here made
# collection fail outright, so the dependency-free core could not be verified
# without first installing the dependency it is defined by not needing.
np = pytest.importorskip("numpy")

import main

pytest.importorskip("scipy")

SAMPLE_RATE = 48000


def _rms_db(signal):
    signal = np.asarray(signal, dtype=float)
    return 20.0 * math.log10(math.sqrt(np.mean(signal ** 2)) + 1e-20)


def _tone_db(signal, freq):
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freqs = np.fft.rfftfreq(len(signal), 1 / SAMPLE_RATE)
    return 20.0 * math.log10(spectrum[np.argmin(np.abs(freqs - freq))] / len(signal) + 1e-20)


def _melody(seconds_per_note=1.0, amplitude=0.3):
    """Notes that change over time, starting immediately -- no silent lead-in."""
    count = int(SAMPLE_RATE * seconds_per_note)
    t = np.arange(count) / SAMPLE_RATE
    return np.concatenate([amplitude * np.sin(2 * np.pi * f * t)
                           for f in (440.0, 554.0, 659.0, 523.0)])


def _processor():
    return main.AudioProcessor(main.ProcessingConfig())


def test_material_starting_without_silence_is_not_destroyed():
    rng = np.random.default_rng(0)
    clean = _melody()
    noisy = clean + 0.02 * rng.standard_normal(len(clean))

    processed = _processor().remove_noise(noisy.copy(), SAMPLE_RATE)
    length = min(len(processed), len(noisy))

    # The old estimator took this down 19.4 dB.
    change = _rms_db(processed[:length]) - _rms_db(noisy[:length])
    assert change > -2.0, f"signal lost {change:.1f} dB"


def test_notes_survive_when_there_is_no_quiet_lead_in():
    rng = np.random.default_rng(0)
    clean = _melody()
    noisy = clean + 0.02 * rng.standard_normal(len(clean))

    processed = _processor().remove_noise(noisy.copy(), SAMPLE_RATE)
    # Second note, away from the segment boundaries.
    region = slice(SAMPLE_RATE + 5000, 2 * SAMPLE_RATE - 5000)

    change = _tone_db(processed[region], 554.0) - _tone_db(noisy[region], 554.0)
    assert change == pytest.approx(0.0, abs=1.5)


def test_noise_is_still_reduced_when_the_file_opens_with_silence():
    rng = np.random.default_rng(0)
    tone_t = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
    signal = np.concatenate([np.zeros(SAMPLE_RATE // 2),
                             0.3 * np.sin(2 * np.pi * 440.0 * tone_t)])
    noisy = signal + 0.02 * rng.standard_normal(len(signal))

    processed = _processor().remove_noise(noisy.copy(), SAMPLE_RATE)
    lead_in = slice(1000, SAMPLE_RATE // 2 - 1000)

    reduction = _rms_db(noisy[lead_in]) - _rms_db(processed[lead_in])
    assert reduction > 5.0, f"only {reduction:.1f} dB of noise reduction"


def test_the_tone_survives_alongside_that_noise_reduction():
    rng = np.random.default_rng(0)
    tone_t = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
    signal = np.concatenate([np.zeros(SAMPLE_RATE // 2),
                             0.3 * np.sin(2 * np.pi * 440.0 * tone_t)])
    noisy = signal + 0.02 * rng.standard_normal(len(signal))

    processed = _processor().remove_noise(noisy.copy(), SAMPLE_RATE)
    region = slice(SAMPLE_RATE // 2 + 5000, SAMPLE_RATE // 2 + SAMPLE_RATE)

    change = _tone_db(processed[region], 440.0) - _tone_db(noisy[region], 440.0)
    assert change == pytest.approx(0.0, abs=1.5)


def test_a_sustained_note_is_not_gutted():
    # Every fixture above uses *changing* content, so each bin has quiet
    # frames to estimate noise from. A note held for the whole file never
    # empties its bin: the p10 is the note itself, and subtracting the
    # scaled estimate used to take a steady tone down ~21 dB.
    rng = np.random.default_rng(0)
    t = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
    sustained = 0.3 * np.sin(2 * np.pi * 440.0 * t)
    noisy = sustained + 0.02 * rng.standard_normal(len(t))

    processed = _processor().remove_noise(noisy.copy(), SAMPLE_RATE)
    region = slice(5000, 2 * SAMPLE_RATE - 5000)

    change = _tone_db(processed[region], 440.0) - _tone_db(noisy[region], 440.0)
    assert change == pytest.approx(0.0, abs=1.5), f"sustained tone lost {change:.1f} dB"


def test_pure_noise_is_reduced():
    rng = np.random.default_rng(1)
    noise = 0.02 * rng.standard_normal(2 * SAMPLE_RATE)

    processed = _processor().remove_noise(noise.copy(), SAMPLE_RATE)

    reduction = _rms_db(noise) - _rms_db(processed[:len(noise)])
    assert reduction > 5.0


def test_an_explicit_noise_profile_is_still_honoured():
    # Passing a zero profile must leave the signal essentially untouched,
    # which also pins the STFT/ISTFT round-trip.
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    clean = 0.3 * np.sin(2 * np.pi * 440.0 * t)
    zero_profile = np.zeros((1025, 1))

    processed = _processor().remove_noise(clean.copy(), SAMPLE_RATE,
                                          noise_profile=zero_profile)
    length = min(len(processed), len(clean))

    assert _rms_db(processed[:length] - clean[:length]) < -100.0


def test_silence_does_not_raise():
    processed = _processor().remove_noise(np.zeros(SAMPLE_RATE), SAMPLE_RATE)
    assert np.all(np.isfinite(processed))


def test_input_shorter_than_the_stft_window_does_not_crash():
    # stft shrinks nperseg to fit a short input; istft used to keep a
    # literal 2048 and crashed broadcasting (500,) against (2048,).
    t = np.arange(500) / SAMPLE_RATE
    short = 0.3 * np.sin(2 * np.pi * 440.0 * t)

    processed = _processor().remove_noise(short.copy(), SAMPLE_RATE)
    assert np.all(np.isfinite(processed))


def test_output_preserves_input_length():
    # scipy istft emits frame-aligned output: its boundary padding left
    # denoised files ~+1% longer (88200 -> 89088 samples). A processor that
    # changes duration misaligns sync and lies about what it did.
    t = np.arange(88200) / SAMPLE_RATE
    signal = 0.2 * np.sin(2 * np.pi * 440.0 * t) + 0.02 * np.random.randn(len(t))

    processed = _processor().remove_noise(signal.copy(), SAMPLE_RATE)

    assert processed.shape[-1] == signal.shape[-1]


def _chameleon_messages():
    # The 'chameleon' logger sets propagate=False, so caplog never sees its
    # records; capture by attaching a collector directly.
    import logging

    records = []

    class _Collector(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("chameleon")
    handler = _Collector()
    logger.addHandler(handler)
    return records, logger, handler


def test_save_audio_warns_when_samples_will_clip(tmp_path):
    # save_audio hard-clips out-of-range floats on int PCM write. The clip
    # is unavoidable, but silence about it let an overdriven effects chain
    # (+12 dB EQ on a hot signal) distort invisibly. The count must surface.
    proc = _processor()
    hot = np.full(4096, 1.5, dtype=np.float32)
    records, logger, handler = _chameleon_messages()
    try:
        proc.save_audio(hot, str(tmp_path / "hot.wav"), SAMPLE_RATE)
    finally:
        logger.removeHandler(handler)

    assert any("hard-clip" in m for m in records)


def test_save_audio_silent_when_in_range(tmp_path):
    proc = _processor()
    quiet = np.full(4096, 0.5, dtype=np.float32)
    records, logger, handler = _chameleon_messages()
    try:
        proc.save_audio(quiet, str(tmp_path / "quiet.wav"), SAMPLE_RATE)
    finally:
        logger.removeHandler(handler)

    assert not any("hard-clip" in m for m in records)


def test_save_audio_warns_on_nan_and_writes_deterministic(tmp_path):
    # NaN bypassed the old |x|>1.0 count and passed np.clip unchanged,
    # writing as 0 with no warning.
    proc = _processor()
    dirty = np.array([0.0, np.nan, 0.5, np.inf, -np.inf], dtype=np.float32)
    records, logger, handler = _chameleon_messages()
    try:
        proc.save_audio(dirty, str(tmp_path / "dirty.wav"), SAMPLE_RATE)
    finally:
        logger.removeHandler(handler)

    warnings = [m for m in records if "hard-clip" in m]
    assert warnings, f"no sanitization warning surfaced: {records}"
    assert warnings[0].startswith("3 ")  # nan + two infs counted

    import wave
    with wave.open(str(tmp_path / "dirty.wav")) as w:
        vals = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    assert vals.tolist() == [0, 0, 16384, 32767, -32768]
