"""Covers mastering_chain.py wiring into main.py's `process --master`.

mastering_chain.py (LUFS loudness metering, parametric EQ, compressor, brick-wall
limiter, stereo width processing) was packaged but never imported — CHARTER §9's
orphaned-module punch list flagged it as real, working, and more capable than
main.py's existing apply_effects, so the user approved wiring it in.

It requires numpy unconditionally (mastering_chain.py's own top-level import),
so these tests skip under a stdlib-only install rather than asserting a
degraded path exists for it — matching how the CLI itself raises a plain
"requires numpy" ValueError for --master rather than pretending to degrade.
"""

import wave

import pytest

import main
from tests._helpers import write_sine_wave

requires_numpy = pytest.mark.skipif(not main.HAS_NUMPY, reason="mastering_chain needs numpy")


def test_mastering_chain_module_is_wired():
    if main.HAS_NUMPY:
        assert main.HAS_MASTERING_CHAIN is True


@requires_numpy
def test_master_operation_produces_valid_wav(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5, frequency=440.0, amplitude=20000)
    out_dir = tmp_path / "out"
    processor = main.AudioProcessor()

    results = processor.batch_process(
        [str(wav)], "master", output_dir=str(out_dir), master_preset="streaming"
    )

    assert len(results) == 1
    result = results[0]
    assert "error" not in result, result
    assert "lufs_before" in result and "lufs_after" in result
    assert "peak_change_db" in result

    output_path = out_dir / "tone_mastered.wav"
    assert output_path.exists()
    with wave.open(str(output_path), "rb") as handle:
        assert handle.getnframes() > 0
        assert handle.getframerate() == 44100


@requires_numpy
def test_master_operation_dry_run_writes_nothing(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    out_dir = tmp_path / "out"
    processor = main.AudioProcessor()

    results = processor.batch_process(
        [str(wav)], "master", output_dir=str(out_dir),
        master_preset="default", dry_run=True,
    )

    assert results[0]["dry_run"] is True
    assert not out_dir.exists() or not list(out_dir.glob("*.wav"))


@requires_numpy
def test_master_preset_choices_all_produce_output(tmp_path):
    for preset in ("default", "streaming", "cd", "vinyl"):
        wav = write_sine_wave(tmp_path / f"{preset}.wav", frequency=440.0)
        out_dir = tmp_path / f"out_{preset}"
        processor = main.AudioProcessor()

        results = processor.batch_process(
            [str(wav)], "master", output_dir=str(out_dir), master_preset=preset
        )

        assert "error" not in results[0], f"{preset}: {results[0]}"


@requires_numpy
def test_mastering_a_file_shorter_than_the_filter_padlen_fails_cleanly(tmp_path):
    # filtfilt needs more than padlen (9) samples; a shorter file used to
    # surface scipy's internals ("input vector x must be greater than
    # padlen") instead of a readable reason.
    import wave
    import numpy as np
    wav = tmp_path / "one.wav"
    with wave.open(str(wav), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(np.zeros(1, dtype=np.int16).tobytes())

    processor = main.AudioProcessor()
    results = processor.batch_process(
        [str(wav)], "master", output_dir=str(tmp_path / "out"), master_preset="streaming"
    )

    assert "error" in results[0]
    assert "too short for mastering" in results[0]["error"]


def test_mastering_rejects_multichannel_instead_of_dropping_channels():
    # Every stage is mono/stereo-only: the stereo processors zero or
    # truncate channels beyond the first two, so mastering a quad file
    # must refuse loudly rather than write a file missing channels.
    np = pytest.importorskip("numpy")
    import mastering_chain

    quad = np.stack(
        [0.3 * np.sin(2 * np.pi * f * np.arange(4410) / 44100)
         for f in (440, 550, 660, 770)]
    )
    chain = mastering_chain.MasteringChain(
        mastering_chain.create_mastering_preset("default"), 44100
    )
    with pytest.raises(ValueError, match="mono or stereo"):
        chain.process(quad)


def test_stereo_processor_rejects_multichannel_standalone():
    """audit-103: StereoProcessor used standalone silently truncated >2ch
    to audio[:2] -- channels 3+ vanished with no warning. Limiter and
    Compressor already refuse multichannel; this brings it in line."""
    np = pytest.importorskip("numpy")
    import mastering_chain

    audio = np.stack([np.zeros(4410) for _ in range(3)])
    sp = mastering_chain.StereoProcessor(
        mastering_chain.StereoConfig(bass_mono=False), 44100
    )
    with pytest.raises(ValueError, match="mono or stereo"):
        sp.process(audio)


def test_bass_mono_freq_above_nyquist_named_not_scipy_error():
    """mono_freq >= Nyquist used to leak scipy's 'Digital filter critical
    frequencies' ValueError with no mention of the offending knob."""
    np = pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    import mastering_chain

    with pytest.raises(ValueError, match="mono_freq"):
        mastering_chain.StereoProcessor(
            mastering_chain.StereoConfig(bass_mono=True, mono_freq=99999),
            44100,
        )


def test_harmonic_enhancement_past_one_rejected():
    """harmonic_enhancement blends audio*(1-amount) + saturated*amount;
    amount>1 makes the dry term negative -- a phase-flipped subtraction,
    not 'more enhancement'. The documented range is [0, 1]."""
    np = pytest.importorskip("numpy")
    import mastering_chain

    cfg = mastering_chain.MasteringConfig()
    cfg.harmonic_enhancement = 2.0
    cfg.eq_enabled = False
    cfg.compressor_enabled = False
    cfg.limiter_enabled = False
    cfg.stereo_enabled = False
    cfg.dither_enabled = False
    cfg.auto_gain = False
    chain = mastering_chain.MasteringChain(cfg, 44100)
    audio = 0.3 * np.sin(2 * np.pi * 440 * np.arange(4410) / 44100)
    with pytest.raises(ValueError, match="harmonic_enhancement"):
        chain.process(audio)

    cfg.harmonic_enhancement = 0.5
    out, _ = mastering_chain.MasteringChain(cfg, 44100).process(audio)
    assert np.isfinite(out).all()
