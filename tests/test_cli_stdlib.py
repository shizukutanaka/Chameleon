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


def _failing_level_pass(*_args, **_kwargs):
    raise OSError("simulated mid-read failure")


def test_level_measurement_failure_marks_levels_unmeasured(tmp_path, monkeypatch):
    """A failed level pass must not read as silence: analyze used to stamp
    the 0.0 dataclass defaults, so a loud file whose measurement crashed
    printed "Peak Level: 0.000" and exported "peak_level": 0.0 -- a default
    presented as a measurement."""
    import json

    import core

    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.3)
    monkeypatch.setattr(
        core._processor, "_calculate_levels_safe", _failing_level_pass
    )

    result = _processor()._process_single_file_stdlib(
        str(wav), "analyze", time.time()
    )

    assert "error" not in result, result
    meta = result["metadata"]
    assert meta.peak_level is None
    assert meta.rms_level is None
    assert meta.dynamic_range is None
    payload = json.loads(json.dumps(meta, default=main._json_export_default))
    assert payload["peak_level"] is None
    assert payload["rms_level"] is None


def test_level_helper_propagates_io_errors(tmp_path):
    """_calculate_levels_safe used to catch every exception and return
    (0.0, 0.0) -- a crashed measurement indistinguishable from measured
    silence. Callers decide what a failure means; the helper reports it."""
    import core

    processor = core.WAVProcessor()
    info = core.AudioInfo(
        duration=0.0, sample_rate=44100, channels=1,
        bit_depth=16, size_bytes=0,
    )

    # open() on a directory raises IsADirectoryError (an OSError).
    with pytest.raises(OSError):
        processor._calculate_levels_safe(str(tmp_path), info)


def test_zero_frame_wav_still_reports_measured_silence(tmp_path):
    """0.0 is the honest answer for a file containing no samples; only a
    *failed* measurement may report None."""
    import core

    wav = write_sine_wave(tmp_path / "empty.wav", duration=0.0)

    result = core.analyze(str(wav))

    assert result.success
    assert result.data.peak_level == 0.0
    assert result.data.rms_level == 0.0


def test_normalize_fails_honestly_when_level_pass_fails(tmp_path, monkeypatch):
    """normalize used to turn a crashed level pass into "No audio signal
    found" -- a claim about the audio's content it never measured. The
    failure now reports as a failure."""
    import core

    src = write_sine_wave(tmp_path / "in.wav", duration=0.3)
    out = tmp_path / "out.wav"
    monkeypatch.setattr(
        core._processor, "_calculate_levels_safe", _failing_level_pass
    )

    result = core.normalize(str(src), str(out))

    assert not result.success
    assert "No audio signal" not in result.message
    assert "Normalization failed" in result.message
