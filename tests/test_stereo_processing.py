"""Stereo width and bass-mono processing.

`StereoProcessor` had no tests at all, so its mid/side arithmetic was
unverified. These pin the two things it claims to do -- widen or narrow the
stereo image, and keep the low end centred -- plus the invariant that matters
most in mastering: mono content must survive the round trip untouched.

Also documents, by omission, that `MasteringConfig.stereo_enhancement` is
inert: width is `StereoConfig.width`, and there is deliberately no second knob.
"""

import numpy as np
import pytest

import mastering_chain

pytest.importorskip("scipy")

SAMPLE_RATE = 48000


def _tone(freq, amplitude=0.3, seconds=1.0):
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return amplitude * np.sin(2 * np.pi * freq * t)


def _level_db(signal, freq):
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freqs = np.fft.rfftfreq(len(signal), 1 / SAMPLE_RATE)
    return 20.0 * np.log10(spectrum[np.argmin(np.abs(freqs - freq))] / len(signal) + 1e-20)


def _process(left, right, **config):
    settings = {"width": 1.0, "bass_mono": False, "mono_freq": 120.0}
    settings.update(config)
    processor = mastering_chain.StereoProcessor(
        mastering_chain.StereoConfig(**settings), SAMPLE_RATE)
    return processor.process(np.array([left, right]))


def _mid_side(stereo):
    return (stereo[0] + stereo[1]) / 2, (stereo[0] - stereo[1]) / 2


# --- width ----------------------------------------------------------------

def test_unit_width_is_a_passthrough():
    left, right = _tone(1000.0), _tone(1000.0, amplitude=0.1)

    out = _process(left, right, width=1.0)

    assert np.allclose(out[0], left, atol=1e-9)
    assert np.allclose(out[1], right, atol=1e-9)


def test_zero_width_collapses_to_mono():
    left, right = _tone(1000.0), _tone(1500.0)

    out = _process(left, right, width=0.0)

    # No side component left at all: both channels identical.
    assert np.allclose(out[0], out[1], atol=1e-12)


def test_width_above_one_increases_the_side_component():
    left, right = _tone(1000.0), _tone(1000.0, amplitude=0.1)

    normal = _mid_side(_process(left, right, width=1.0))[1]
    wide = _mid_side(_process(left, right, width=2.0))[1]

    assert np.abs(wide).max() == pytest.approx(2 * np.abs(normal).max(), rel=1e-6)


def test_mono_content_stays_mono_at_any_width():
    # Identical channels have no side component, so width must be a no-op --
    # the property that keeps widening safe on mono-ish material.
    signal = _tone(1000.0)

    for width in (0.0, 1.0, 2.0):
        out = _process(signal, signal, width=width)
        assert np.allclose(out[0], signal, atol=1e-9)
        assert np.allclose(out[1], signal, atol=1e-9)


# --- bass mono ------------------------------------------------------------

def test_bass_mono_removes_low_frequencies_from_the_side_channel():
    # Out-of-phase bass plus out-of-phase treble: all side, no mid.
    bass, treble = _tone(60.0, amplitude=0.4), _tone(2000.0)
    left, right = bass + treble, -(bass + treble)

    out = _process(left, right, bass_mono=True, mono_freq=120.0)
    _, side_out = _mid_side(out)
    _, side_in = _mid_side(np.array([left, right]))

    bass_reduction = _level_db(side_in, 60.0) - _level_db(side_out, 60.0)
    treble_change = _level_db(side_out, 2000.0) - _level_db(side_in, 2000.0)

    assert bass_reduction > 15.0, "bass was not removed from the side channel"
    assert abs(treble_change) < 0.5, "bass-mono should not touch the treble"


def test_bass_mono_leaves_centred_bass_alone():
    # Bass already in the centre lives in mid, which bass-mono must not touch.
    bass = _tone(60.0, amplitude=0.4)

    out = _process(bass, bass, bass_mono=True, mono_freq=120.0)
    mid_out, _ = _mid_side(out)

    assert _level_db(mid_out, 60.0) == pytest.approx(_level_db(bass, 60.0), abs=0.5)


def test_bass_mono_disabled_keeps_side_bass():
    bass = _tone(60.0, amplitude=0.4)
    left, right = bass, -bass

    out = _process(left, right, bass_mono=False)
    _, side_out = _mid_side(out)

    assert _level_db(side_out, 60.0) == pytest.approx(_level_db(bass, 60.0), abs=0.5)


# --- shape handling -------------------------------------------------------

def test_mono_input_is_duplicated_to_stereo():
    processor = mastering_chain.StereoProcessor(
        mastering_chain.StereoConfig(), SAMPLE_RATE)
    signal = _tone(1000.0)

    result = processor.process(signal)

    assert result.shape[0] == 2
    assert np.allclose(result[0], result[1])


def test_the_stereo_enhancement_config_field_is_inert():
    # It is documented as not implemented; StereoConfig.width is the real
    # control. This pins that so nobody wires up a second width knob without
    # noticing the first one.
    config = mastering_chain.MasteringConfig(stereo_enhancement=1.0)
    assert config.stereo_enhancement == 1.0  # stored...
    # ...and never consulted: the stereo stage reads StereoConfig only.
    import inspect
    source = inspect.getsource(mastering_chain.StereoProcessor)
    assert "stereo_enhancement" not in source
