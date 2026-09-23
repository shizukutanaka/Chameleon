"""Measured bounds that used to be lies the user could not see.

Three defects found by probing, each with a concrete reproduction:

* `WAVProcessor._calculate_levels_safe` stopped decoding after 1M
  channel-samples (~10-21 s at 44.1/48 kHz) and still returned its partial
  result as the file's peak/RMS. A 40 s file that is silent for ~29 s and
  then peaks at 0.9 reported ``peak_level=0.0, rms_level=0.0`` -- and a
  different answer than the numpy analysis path gives for the same input.

* `WAVProcessor._apply_gain_safe` (behind ``normalize``) refused any payload
  past 10M channel-samples with "Too many samples processed - possible
  corruption". A 110 s stereo 48 kHz file -- ordinary audio -- failed while
  the size validator happily accepts it (the 500 MB cap is ~268 s of 16-bit
  stereo). The loop's real bound was already ``to_consume``.

* ``SecurityValidator.sanitize_filename("..")`` returned ``".."``, which
  resolves to the parent of whatever directory a caller joins it under.
  Existing call sites re-check containment; the primitive itself must not
  hand back a parent-reference for the next caller that does not.
"""

import math
import struct
import wave
from pathlib import Path

import pytest

import core
import security_validator


def _write_late_peak(path, *, silent_samples, loud_samples, peak, rate=48000):
    """Mono 16-bit WAV: silence, then a constant-level burst."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframesraw(b"\x00\x00" * silent_samples)
        handle.writeframesraw(struct.pack("<h", int(peak * 32767)) * loud_samples)


def test_analyze_measures_levels_past_the_former_one_million_sample_cap(tmp_path):
    # Measured defect: peak_level=0.0, rms_level=0.0 for a file that is silent
    # for the first ~29 s and then holds 0.9 FS. The cap bit at 1M samples;
    # the loud region starts at sample 1,400,000.
    source = tmp_path / "late_peak.wav"
    _write_late_peak(source, silent_samples=1_400_000, loud_samples=2_000, peak=0.9)

    result = core.WAVProcessor().analyze(str(source))

    assert result.success, result.message
    assert result.data.peak_level == pytest.approx(0.9, abs=0.01)
    assert result.data.rms_level > 0


def test_analyze_reports_zero_levels_only_for_real_silence(tmp_path):
    # The flip side: a genuinely silent file must still report zeros -- the
    # whole-file rewrite must not start "finding" levels in digital silence.
    source = tmp_path / "silence.wav"
    _write_late_peak(source, silent_samples=48_000, loud_samples=0, peak=0.0)

    result = core.WAVProcessor().analyze(str(source))

    assert result.success, result.message
    assert result.data.peak_level == 0.0
    assert result.data.rms_level == 0.0


def _write_constant_wav(path, *, channels, sample_rate, seconds, byte_value):
    """Bulk-write a constant-amplitude WAV: every payload byte is byte_value."""
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(1)
        handle.setframerate(sample_rate)
        handle.writeframesraw(bytes([byte_value]) * frames * channels)


def test_normalize_completes_for_a_file_over_the_former_sample_cap(tmp_path):
    # Measured defect: "Too many samples processed - possible corruption" on
    # anything past 10M channel-samples -- an arbitrary counter, not the
    # 500 MB validator limit (~39% of it at 16-bit stereo). 8 ch x 8-bit x
    # 8 kHz x 160 s = 10.24M samples: minimal file that tripped it.
    source = tmp_path / "long.wav"
    _write_constant_wav(source, channels=8, sample_rate=8000, seconds=160,
                        byte_value=129)  # decoded value +1: nonzero signal

    output = tmp_path / "long_out.wav"
    result = core.WAVProcessor().normalize(str(source), str(output))

    assert result.success, result.message
    info = core.WAVProcessor()._read_wav_header(str(output))
    assert info is not None
    # Every input sample was +1; gain to 0.95 peak maps it to round(1*gain),
    # encoded back as unsigned byte.
    expected_sample = int(round(0.95 / (1 / 128))) + 128
    payload = Path(output).read_bytes()[info.data_offset:info.data_offset + 8]
    assert payload == bytes([expected_sample]) * 8


def test_mono_downmix_rounds_instead_of_truncating(tmp_path):
    # (0, +3) averages to +1.5: int() truncation gave +1, round() gives +2 --
    # the same quantization rule the gain path already applies.
    source = tmp_path / "stereo.wav"
    with wave.open(str(source), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(struct.pack("<hh", 0, 3) * 4410)

    output = tmp_path / "mono.wav"
    result = core.WAVProcessor().convert_to_mono(str(source), str(output))

    assert result.success, result.message
    with wave.open(str(output), "rb") as handle:
        payload = handle.readframes(4410)
    samples = struct.unpack(f"<{len(payload) // 2}h", payload)
    assert set(samples) == {2}


def test_sanitize_filename_collapses_dot_only_names():
    # Measured defect: sanitize_filename("..") -> "..", which resolves to the
    # parent of any directory a caller joins it under. "." and "..." are the
    # same shape; a name made only of dots is not a usable filename.
    for name in (".", "..", "...", "...."):
        assert security_validator.SecurityValidator.sanitize_filename(name) == "untitled"


def test_sanitize_filename_keeps_normal_names():
    assert security_validator.SecurityValidator.sanitize_filename("mix..final.wav") == "mix..final.wav"
    assert security_validator.SecurityValidator.sanitize_filename("a..b") == "a..b"


def test_sanitized_name_cannot_escape_a_join(tmp_path):
    # Join-level proof: whatever sanitize_filename returns, joining it under
    # an output dir must stay inside that dir.
    base = tmp_path / "out"
    base.mkdir()
    for name in (".", "..", "...", "....", "foo/../../bar", "???.wav"):
        sanitized = security_validator.SecurityValidator.sanitize_filename(name)
        resolved = (base / sanitized).resolve()
        assert resolved.parent == base.resolve() or resolved == base.resolve()
