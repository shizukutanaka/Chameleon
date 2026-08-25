"""Clipping detection and repair.

`DeclippingProcessor` shipped unwired for its whole life, and it did not
work. `detect_clipping` normalized by the file's own peak and called anything
above 95% of it "clipped" -- but a 440 Hz sine spends about a tenth of every
cycle above 95% of its peak, so one second of a clean tone reported 880
clipped regions, and the repair stage then damaged every one of them: 8,920
of 44,100 samples altered, peak error 0.248 on a signal of amplitude 0.5.

The repair had a second bug on top. Its crossfade read

    result[start:end] = restored * window + result[start:end] * (1 - window) * 0.5

whose weights sum to less than one, so every region edge came out at exactly
half amplitude -- punching a hole precisely where it was repairing.

What separates a clipped peak from a merely loud one is that clipping is
flat. These tests pin that: clean material must come back untouched, and
clipped material must come back closer to the truth.
"""

import numpy as np
import pytest

pytest.importorskip("scipy")

import audio_restoration


SAMPLE_RATE = 44100


def _sine(freq, amplitude=0.5, seconds=1.0):
    count = int(SAMPLE_RATE * seconds)
    return amplitude * np.sin(2 * np.pi * freq * np.arange(count) / SAMPLE_RATE)


def _rms_db(signal):
    return 20.0 * np.log10(np.sqrt(np.mean(signal ** 2)) + 1e-20)


@pytest.fixture
def declipper():
    return audio_restoration.DeclippingProcessor()


# --- no false positives ---------------------------------------------------

@pytest.mark.parametrize("freq", [50, 100, 440, 1000, 5000, 12000])
def test_a_clean_tone_has_no_clipped_regions(declipper, freq):
    starts, _ = declipper.detect_clipping(_sine(freq))
    assert starts == [], f"{freq} Hz sine reported {len(starts)} clipped regions"


@pytest.mark.parametrize("freq", [50, 440, 5000])
def test_clean_audio_passes_through_bit_exact(declipper, freq):
    # The strongest statement available: not "close to", but untouched.
    clean = _sine(freq)
    assert np.array_equal(declipper.restore_clipped(clean.copy(), SAMPLE_RATE), clean)


def test_a_bass_note_with_harmonics_is_not_mistaken_for_clipping(declipper):
    # 40 Hz alone is near the detector's documented resolution limit; real
    # low-frequency material carries harmonics that curve the peak.
    bass = sum(_sine(40 * k, amplitude=0.5 / k) for k in (1, 2, 3))
    assert declipper.detect_clipping(bass)[0] == []


def test_the_low_frequency_limit_is_where_the_docstring_says_it_is(declipper):
    # Honest labelling: the detector cannot tell a sub-33 Hz full-scale pure
    # tone from a plateau, and says so. If this ever starts passing at 30 Hz,
    # the docstring needs updating -- it is not a free win to leave undocumented.
    assert declipper.detect_clipping(_sine(30))[0] != []
    assert declipper.detect_clipping(_sine(35))[0] == []


def test_silence_is_handled(declipper):
    assert declipper.detect_clipping(np.zeros(1000))== ([], [])


# --- true positives -------------------------------------------------------

def test_every_clipped_crest_is_found(declipper):
    # 440 Hz for one second, clipped on both half-cycles: 880 plateaus.
    clipped = np.clip(_sine(440, amplitude=1.0), -0.7, 0.7)
    starts, ends = declipper.detect_clipping(clipped)

    assert len(starts) == 880
    assert len(ends) == len(starts)
    assert all(end - start >= declipper.min_run_length
               for start, end in zip(starts, ends))


def test_clipping_survives_16_bit_quantisation(declipper):
    # Real files are quantised; the plateau is flat to the LSB, not to zero.
    truth = _sine(220, amplitude=1.0)
    clipped = np.round(np.clip(truth, -0.8, 0.8) * 32767) / 32767

    assert len(declipper.detect_clipping(clipped)[0]) == 440


def test_repair_moves_the_signal_towards_the_unclipped_truth(declipper):
    truth = _sine(440, amplitude=1.0)
    clipped = np.clip(truth, -0.7, 0.7)

    repaired = declipper.restore_clipped(clipped.copy(), SAMPLE_RATE)

    before = _rms_db(clipped - truth)
    after = _rms_db(repaired - truth)
    assert after < before - 10.0, f"error only improved {before - after:.1f} dB"


def test_repair_reconstructs_the_peak_above_the_clip_level(declipper):
    truth = _sine(440, amplitude=1.0)
    clipped = np.clip(truth, -0.7, 0.7)

    repaired = declipper.restore_clipped(clipped.copy(), SAMPLE_RATE)

    # It cannot know the true peak was 1.0, but it must recover most of it.
    assert 0.85 < np.abs(repaired).max() < 1.15


def test_region_edges_are_not_halved(declipper):
    # The exact symptom of the `* 0.5` crossfade bug: the first sample of
    # every repaired region came out at half its input value.
    truth = _sine(440, amplitude=1.0)
    clipped = np.clip(truth, -0.7, 0.7)
    starts, _ = declipper.detect_clipping(clipped)

    repaired = declipper.restore_clipped(clipped.copy(), SAMPLE_RATE)

    edge = starts[0]
    assert repaired[edge] == pytest.approx(clipped[edge], rel=0.02)


def test_the_crossfade_weights_sum_to_one(declipper):
    # Structural version of the same check, so a future edit that reintroduces
    # an unbalanced blend fails even if the sine happens to survive it.
    import inspect
    source = inspect.getsource(declipper.restore_clipped)
    assert "(1 - window) * 0.5" not in source
    assert "(1.0 - window)" in source
