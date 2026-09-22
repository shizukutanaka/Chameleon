"""Tests for the standard-library CLI fallback in main.py.

When numpy is unavailable the numpy-based AudioProcessor pipeline cannot run,
so analyze/normalize are delegated to the dependency-free core. These tests
verify that delegation directly (so they run with or without numpy installed).
"""

import time
from pathlib import Path

import pytest

from tests._helpers import write_sine_wave

import main


def _processor():
    return main.AudioProcessor()


def test_stdlib_analyze_returns_metadata(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5)

    result = _processor()._process_single_file_stdlib(
        str(wav), "analyze", time.time()
    )

    assert "error" not in result, result
    meta = result["metadata"]
    assert meta.sample_rate == 44100
    assert meta.channels == 1
    assert meta.duration > 0
    assert meta.peak_level > 0


def test_stdlib_normalize_writes_output(tmp_path):
    src = write_sine_wave(tmp_path / "in.wav", duration=0.5, amplitude=4000)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = _processor()._process_single_file_stdlib(
        str(src), "normalize", time.time(), output_dir=str(out_dir)
    )

    assert "error" not in result, result
    assert result["output"].endswith("_normalized.wav")
    assert (out_dir / "in_normalized.wav").exists()


def test_stdlib_normalize_dry_run_does_not_write(tmp_path):
    src = write_sine_wave(tmp_path / "in.wav", duration=0.5)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = _processor()._process_single_file_stdlib(
        str(src), "normalize", time.time(), output_dir=str(out_dir), dry_run=True
    )

    assert result["dry_run"] is True
    assert "planned_output" in result
    assert list(out_dir.iterdir()) == []


@pytest.mark.skipif(main.HAS_NUMPY, reason="numpy present; numpy-only op does not raise")
def test_numpy_only_operation_raises_clear_error(tmp_path):
    src = write_sine_wave(tmp_path / "in.wav", duration=0.3)

    with pytest.raises(ValueError, match="requires numpy"):
        _processor()._process_single_file(str(src), "denoise")


def test_missing_dependency_op_is_internal_not_input(tmp_path):
    """An operation that needs a missing extra used to surface as
    ValueError -> kind "input" -> INPUT(3). Per the ExitCode table INPUT
    means a supplied path failed validation; nothing is wrong with the
    file -- the install lacks the capability. ERROR(1) is the honest
    answer."""
    src = write_sine_wave(tmp_path / "in.wav", duration=0.3)
    try:
        _processor()._process_single_file(str(src), "denoise")
        pytest.skip("numpy present; the unsupported path does not trigger")
    except main.UnsupportedOperationError as exc:
        assert main._error_kind(exc) == "internal"


def test_batch_same_stem_inputs_do_not_share_one_output(tmp_path):
    # dirA/mix.wav and dirB/mix.wav under --output-dir both wanted
    # out/mix_normalized.wav: sequential runs silently overwrote the first
    # file with the second's audio, parallel runs interleaved two writers
    # into one corrupt file. Names are now claimed atomically per batch.
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    wav_a = write_sine_wave(dir_a / "mix.wav", amplitude=9000)
    wav_b = write_sine_wave(dir_b / "mix.wav", amplitude=3000)
    out_dir = tmp_path / "out"

    processor = _processor()
    results = processor.batch_process(
        [str(wav_a), str(wav_b)], "normalize", output_dir=str(out_dir)
    )

    outputs = {r["output"] for r in results if "error" not in r}
    assert len(outputs) == 2, results
    for path in outputs:
        assert Path(path).is_file()


def test_batch_output_claims_reset_between_batches(tmp_path):
    src = write_sine_wave(tmp_path / "mix.wav")
    out_dir = tmp_path / "out"
    processor = _processor()

    first = processor.batch_process([str(src)], "normalize", output_dir=str(out_dir))
    second = processor.batch_process([str(src)], "normalize", output_dir=str(out_dir))

    # Re-running a batch reuses the canonical name (and overwrites) rather
    # than inventing _2 -- claims are per-batch, not cumulative.
    assert first[0]["output"] == second[0]["output"]
