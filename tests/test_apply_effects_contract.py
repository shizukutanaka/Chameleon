"""apply_effects is a public entry point, not just the CLI's DSP step.

The command line reaches it through _load_effects, which validates the
effects spec before it is applied. A direct call skipped that layer:
malformed specs leaked KeyError/TypeError/AttributeError internals, a
band at/below DC was silently skipped, and an unknown effect name was
silently ignored. apply_effects now runs the same validation -- the
spec names its own mistake instead of failing deeper or not at all.
"""

import sys

import pytest

np = pytest.importorskip("numpy")

import main


@pytest.fixture
def processor():
    return main.AudioProcessor(main.ProcessingConfig())


@pytest.fixture
def tone():
    count = 44100
    return (0.5 * np.sin(2 * np.pi * 440 * np.arange(count) / 44100)
            .astype(np.float64)[np.newaxis, :])


def test_missing_band_key_raises_value_error(processor, tone):
    # Used to crash with KeyError('gain') inside the DSP loop.
    with pytest.raises(ValueError, match="gain"):
        processor.apply_effects(tone, 44100, {"eq": [{"frequency": 1000}]})


def test_eq_as_dict_raises_value_error(processor, tone):
    # Used to iterate the dict's keys as "bands" and die with
    # TypeError: string indices must be integers.
    with pytest.raises(ValueError, match="list of band objects"):
        processor.apply_effects(
            tone, 44100, {"eq": {"frequency": 1000, "gain": 3}})


def test_band_at_or_below_dc_is_rejected(processor, tone):
    # Used to fall through both branches of `0 < freq < sr/2` and return
    # the input byte-identical -- a silent no-op under "Processed".
    with pytest.raises(ValueError, match="frequency must be positive"):
        processor.apply_effects(
            tone, 44100, {"eq": [{"frequency": -100, "gain": 99}]})


def test_effect_params_as_list_raises_value_error(processor, tone):
    # Used to crash with AttributeError: 'list' object has no attribute 'get'.
    with pytest.raises(ValueError, match="parameter object"):
        processor.apply_effects(tone, 44100, {"reverb": [{"room_size": 0.5}]})


def test_non_dict_effects_spec_raises_value_error(processor, tone):
    # A list spec used to pass the `"eq" in effects` checks silently and
    # return the input unchanged.
    with pytest.raises(ValueError, match="map effect names"):
        processor.apply_effects(tone, 44100, [{"eq": []}])


def test_unknown_effect_name_warns_but_returns_input(
        processor, tone, capsys):
    # Same contract as the CLI's effects file: unknown names are warned
    # about and ignored, not applied and not silently dropped.
    out = processor.apply_effects(
        tone, 44100, {"equalizer": {"frequency": 1000, "gain": 3}})
    assert np.array_equal(out, tone)
    assert "unknown effect" in capsys.readouterr().err.lower()


def test_valid_eq_spec_still_applies(processor, tone):
    # Contract pin: validation must not reject the shape the CLI produces.
    pytest.importorskip("scipy")
    out = processor.apply_effects(
        tone, 44100, {"eq": [{"frequency": 1000, "gain": 3}]})
    assert not np.array_equal(out, tone)
