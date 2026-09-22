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


def test_limiter_preserves_head_and_tail():
    # The delay-line was emitted as output: lookahead_samples of leading
    # zeros were written and the same count of input samples dropped off
    # the tail -- ~5 ms lost at both ends of every mastered file.
    np = pytest.importorskip("numpy")
    import mastering_chain

    sr = 44100
    limiter = mastering_chain.Limiter(
        mastering_chain.LimiterConfig(threshold=-1.0, lookahead=5.0,
                                      release=50.0), sr)
    audio = np.full(sr, 0.5)
    audio[-100:] = 0.3
    out = limiter.process(audio)

    la = limiter.lookahead_samples
    assert len(out) == len(audio)
    assert not (out[:la] == 0).all()
    assert np.allclose(out[-100:], 0.3, atol=1e-3)


def test_limiter_still_brickwalls():
    np = pytest.importorskip("numpy")
    import mastering_chain

    sr = 44100
    limiter = mastering_chain.Limiter(
        mastering_chain.LimiterConfig(threshold=-1.0, lookahead=5.0), sr)
    out = limiter.process(np.full(sr, 0.95))
    assert out.max() <= 10 ** (-1.0 / 20) + 1e-6


def test_limiter_zero_lookahead_does_not_crash():
    # lookahead=0 left an empty slice for .max() -- a legal config value
    # that crashed with ValueError.
    np = pytest.importorskip("numpy")
    import mastering_chain

    limiter = mastering_chain.Limiter(
        mastering_chain.LimiterConfig(threshold=-1.0, lookahead=0.0), 44100)
    out = limiter.process(np.full(1000, 0.5))
    assert out.shape == (1000,)


def test_two_dimensional_mono_does_not_take_the_stereo_path():
    # (1, N) arrays are mono; the stereo path reads audio[1] and used to
    # IndexError on them.
    np = pytest.importorskip("numpy")
    import mastering_chain

    mono2d = np.zeros((1, 44100))
    out, _curve = mastering_chain.Compressor(
        mastering_chain.CompressorConfig(), 44100).process(mono2d)
    assert out.shape == (1, 44100)
    assert mastering_chain.Limiter(
        mastering_chain.LimiterConfig(), 44100).process(mono2d).shape == (1, 44100)


def test_bass_mono_freq_above_nyquist_fails_clearly():
    # scipy.butter's raw ValueError was the only message a bad mono_freq
    # produced -- now a configuration error names the parameter.
    np = pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    import mastering_chain

    with pytest.raises(ValueError, match="mono_freq"):
        mastering_chain.StereoProcessor(
            mastering_chain.StereoConfig(mono_freq=30000), 44100)
