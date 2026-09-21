"""Requesting an effect that cannot be applied must fail, not pass quietly.

`apply_effects` guarded each effect with its dependency -- `if "eq" in effects
and HAS_SCIPY and ...` -- and did nothing when the guard was false. On an
install without scipy, `chameleon process --effects eq.json` therefore wrote an
output file, printed a success line, and applied no EQ. Nothing in the output
distinguished that from an EQ that had been applied and happened to be subtle.

This is the same failure mode as the restoration pipeline reporting a denoising
step it had skipped: the tool was not wrong about the audio, it was wrong about
itself. Three tests in tests/test_eq_quality.py were failing for exactly this
reason under a numpy-only install, which is how it was found.
"""

import pytest

# Guarded so the suite is runnable on the project's own default install, which
# has no third-party packages at all. An unguarded `import numpy` here made
# collection fail outright, so the dependency-free core could not be verified
# without first installing the dependency it is defined by not needing.
np = pytest.importorskip("numpy")

import main


@pytest.fixture
def processor():
    return main.AudioProcessor(main.ProcessingConfig())


def _tone(freq=1000.0, sample_rate=44100, seconds=0.5):
    count = int(sample_rate * seconds)
    return (0.5 * np.sin(2 * np.pi * freq * np.arange(count) / sample_rate)).astype(np.float32)


def test_every_dependency_backed_effect_is_declared():
    # The table and the code must not drift: anything apply_effects gates on an
    # optional package needs an entry, or the silent-skip bug comes back for it.
    import inspect
    source = inspect.getsource(main.AudioProcessor.apply_effects)

    for name in main.AudioProcessor._EFFECT_REQUIREMENTS:
        assert f'"{name}" in effects' in source, f"{name} is declared but not applied"


def test_requesting_eq_without_scipy_raises(processor, monkeypatch):
    monkeypatch.setattr(main, "HAS_SCIPY", False)

    with pytest.raises(ValueError, match="scipy"):
        processor.apply_effects(_tone(), 44100, {"eq": [{"frequency": 1000, "gain": 3.0}]})


def test_requesting_reverb_without_scipy_raises(processor, monkeypatch):
    monkeypatch.setattr(main, "HAS_SCIPY", False)

    with pytest.raises(ValueError, match="reverb"):
        processor.apply_effects(_tone(), 44100, {"reverb": {"room_size": 0.5}})


def test_the_error_names_the_extra_that_fixes_it(processor, monkeypatch):
    monkeypatch.setattr(main, "HAS_SCIPY", False)

    with pytest.raises(ValueError, match=r"\[audio\]"):
        processor.apply_effects(_tone(), 44100, {"eq": [{"frequency": 1000, "gain": 3.0}]})


def test_effects_needing_nothing_optional_still_work(processor, monkeypatch):
    # Compression is implemented in plain numpy and must not be caught by the
    # dependency check.
    monkeypatch.setattr(main, "HAS_SCIPY", False)

    result = processor.apply_effects(_tone(), 44100, {"compression": {"threshold": 0.3}})

    assert result.shape == _tone().shape


def test_an_empty_effects_dict_is_a_passthrough(processor):
    tone = _tone()
    assert np.array_equal(processor.apply_effects(tone, 44100, {}), tone)


def test_compression_is_dynamics_processing_not_waveshaping(processor):
    # The old "compression" remapped |x| sample-by-sample -- soft-clipping,
    # which adds harmonics: a 0.8 sine at threshold -20 dB / ratio 4 came out
    # with the 3rd harmonic only ~13 dB below the fundamental. A real
    # compressor applies a slowly-varying gain from an attack/release
    # envelope, so a compressed sine stays a sine; the implementation is now
    # mastering_chain.Compressor. This pins both halves of the claim: the
    # level actually came down, AND the waveform kept its shape.
    tone = _tone(440, seconds=1.0) * 1.6  # 0.8 peak -> over the threshold
    out = processor.apply_effects(
        tone.copy(), 44100, {"compression": {"threshold": -20.0, "ratio": 4.0}})

    steady = out[22050:]  # skip the attack transient
    spec = np.abs(np.fft.rfft(steady * np.hanning(len(steady))))
    freqs = np.fft.rfftfreq(len(steady), 1 / 44100)

    def level(freq):
        return 20 * np.log10(spec[np.argmin(np.abs(freqs - freq))] + 1e-20)

    assert 20 * np.log10(np.abs(steady).max()) < -10.0, "crest did not come down"
    assert level(1320) - level(440) < -60.0  # 3rd harmonic
    assert level(2200) - level(440) < -60.0  # 5th harmonic


def _skip_unless(scipy_needed=False, mastering_needed=False):
    import pytest as _p
    if scipy_needed and not getattr(main, "HAS_SCIPY", False):
        _p.skip("effect path needs scipy")
    if mastering_needed and not getattr(main, "HAS_MASTERING_CHAIN", False):
        _p.skip("effect path needs mastering_chain")


def test_apply_effects_eq_band_with_nonpositive_frequency_named(processor):
    # freq<=0 used to fall between `0 < freq < sr/2` and `freq >= sr/2`,
    # being silently skipped -- a no-op reported as "Processed".
    _skip_unless(scipy_needed=True, mastering_needed=True)
    with pytest.raises(ValueError, match="positive"):
        processor.apply_effects(
            _tone(), 44100, {"eq": [{"frequency": -100.0, "gain": 3.0}]})
    with pytest.raises(ValueError, match="positive"):
        processor.apply_effects(
            _tone(), 44100, {"eq": [{"frequency": 0.0, "gain": 3.0}]})


def test_apply_effects_eq_band_with_nan_gain_rejected(processor):
    # A NaN gain produced NaN biquad coefficients, which lfilter spread
    # across the entire output -- the whole file became NaN.
    _skip_unless(scipy_needed=True, mastering_needed=True)
    with pytest.raises(ValueError, match="finite"):
        processor.apply_effects(
            _tone(), 44100, {"eq": [{"frequency": 1000.0, "gain": float("nan")}]})


def test_apply_effects_eq_band_with_nonpositive_q_rejected(processor):
    # q<=0 was silently clamped to 1e-6 inside design_peaking_eq, producing
    # a degenerate biquad unrelated to the requested band.
    _skip_unless(scipy_needed=True, mastering_needed=True)
    with pytest.raises(ValueError, match="'q'"):
        processor.apply_effects(
            _tone(), 44100, {"eq": [{"frequency": 1000.0, "gain": 3.0, "q": 0.0}]})


def test_apply_effects_reverb_wet_outside_unit_interval_rejected(processor):
    # wet is a blend ratio; 1.5 extrapolated to dry*(-0.5)+wet*1.5 and
    # clipped a 0.5-amplitude sine to a 2.2 peak.
    _skip_unless(scipy_needed=True)
    with pytest.raises(ValueError, match="wet"):
        processor.apply_effects(
            _tone(), 44100, {"reverb": {"wet": 1.5}})
    with pytest.raises(ValueError, match="wet"):
        processor.apply_effects(
            _tone(), 44100, {"reverb": {"wet": -0.5}})


def test_apply_effects_reverb_nonpositive_room_size_rejected(processor):
    _skip_unless(scipy_needed=True)
    with pytest.raises(ValueError, match="room_size"):
        processor.apply_effects(
            _tone(), 44100, {"reverb": {"room_size": 0.0}})


def test_apply_effects_compression_ratio_below_one_rejected(processor):
    # ratio<1 makes slope positive -- an expander, not a compressor; ratio=0
    # reached a raw ZeroDivisionError inside _gain_reduction_db.
    _skip_unless(mastering_needed=True)
    with pytest.raises(ValueError, match="ratio"):
        processor.apply_effects(
            _tone(), 44100, {"compression": {"ratio": 0.0}})
    with pytest.raises(ValueError, match="ratio"):
        processor.apply_effects(
            _tone(), 44100, {"compression": {"ratio": 0.5}})
