"""Tests for the standard-library CLI fallback in main.py.

When numpy is unavailable the numpy-based AudioProcessor pipeline cannot run,
so analyze/normalize are delegated to the dependency-free core. These tests
verify that delegation directly (so they run with or without numpy installed).
"""

import time

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
