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
