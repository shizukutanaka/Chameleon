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
