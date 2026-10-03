#!/usr/bin/env python3
"""Test suite for the Chameleon audio core and security primitives.

These tests exercise the real, dependency-light public API:

* ``core``: ``analyze``, ``normalize``, ``to_mono``, ``trim_silence``,
  ``open_secure``
* ``security_validator``: ``SecurityValidator``, ``SecurityConfig``,
  ``SecurityError``, ``SecureFileOperations``
"""

from __future__ import annotations

import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from core import (
    analyze,
    normalize,
    to_mono,
    trim_silence,
    open_secure,
    EnhancedSecurityValidator,
)
from security_validator import (
    SecurityValidator,
    SecurityConfig,
    SecurityError,
    SecureFileOperations,
)


SAMPLE_RATE = 44100


def _write_sine_wave(path: Path, *, duration: float = 0.5,
                     frequency: float = 440.0, channels: int = 1) -> Path:
    """Generate a simple PCM sine wave for testing (no numpy required)."""
    sample_count = int(SAMPLE_RATE * duration)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        frames = []
        for index in range(sample_count):
            value = int(12000 * math.sin(2 * math.pi * frequency * index / SAMPLE_RATE))
            frames.extend((value,) if channels == 1 else (value, value))
        handle.writeframes(struct.pack("<" + "h" * len(frames), *frames))
    return path


class CoreAudioTests(unittest.TestCase):
    """Behaviour checks for the synchronous core audio API."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_analyze_basic_properties(self) -> None:
        wav_path = _write_sine_wave(self.tmp_path / "tone.wav")
        result = analyze(str(wav_path))
        self.assertTrue(result.success, msg=result.message)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data.sample_rate, SAMPLE_RATE)
        self.assertGreater(result.data.duration, 0)

    def test_normalize_creates_output(self) -> None:
        input_path = _write_sine_wave(self.tmp_path / "input.wav")
        output_path = self.tmp_path / "output.wav"
        result = normalize(str(input_path), str(output_path), 0.8)
        self.assertTrue(result.success, msg=result.message)
        self.assertTrue(output_path.exists())

    def test_to_mono_from_stereo(self) -> None:
        stereo_path = _write_sine_wave(self.tmp_path / "stereo.wav", channels=2)
        mono_path = self.tmp_path / "mono.wav"
        result = to_mono(str(stereo_path), str(mono_path))
        self.assertTrue(result.success, msg=result.message)
        with wave.open(str(mono_path), "rb") as handle:
            self.assertEqual(handle.getnchannels(), 1)

    def test_trim_silence_produces_file(self) -> None:
        input_path = _write_sine_wave(self.tmp_path / "input.wav")
        output_path = self.tmp_path / "trimmed.wav"
        result = trim_silence(str(input_path), str(output_path), 0.01)
        self.assertTrue(result.success, msg=result.message)
        self.assertTrue(output_path.exists())

    def test_open_secure_writes_restricted_file(self) -> None:
        target = self.tmp_path / "secret.bin"
        with open_secure(target, "wb") as handle:
            handle.write(b"data")
        self.assertTrue(target.exists())
        self.assertEqual(target.read_bytes(), b"data")

    def test_trim_silence_reports_mid_scan_failure(self) -> None:
        """A decode/read error mid-scan must surface as a failure, not a
        "Trimmed 0.00s" success: the scan used to swallow every exception and
        return the untouched (0, duration) initial bounds, so the whole file
        was written out and trimming reported success."""
        import core
        wav_path = _write_sine_wave(self.tmp_path / "corrupt_midway.wav")
        output_path = self.tmp_path / "out.wav"

        calls = {"n": 0}
        original = core.WAVProcessor._decode_sample_bytes

        def flaky(sample_bytes, bit_depth):
            calls["n"] += 1
            if calls["n"] > 100:
                raise OSError("simulated mid-scan decode failure")
            return original(sample_bytes, bit_depth)

        core.WAVProcessor._decode_sample_bytes = staticmethod(flaky)
        try:
            result = trim_silence(str(wav_path), str(output_path), 0.01)
        finally:
            core.WAVProcessor._decode_sample_bytes = staticmethod(original)

        self.assertFalse(result.success)
        self.assertIn("failed", result.message.lower())

    def test_find_audio_boundaries_raises_on_scan_failure(self) -> None:
        """Unit level: the helper must propagate the error, not return the
        untouched (0, total) bounds that read as 'the whole file is audio'."""
        import core
        wav_path = _write_sine_wave(self.tmp_path / "corrupt.wav")
        processor = core.WAVProcessor()
        info = processor._read_wav_header(str(wav_path))
        total = int(info.duration * info.sample_rate)

        calls = {"n": 0}
        original = core.WAVProcessor._decode_sample_bytes

        def flaky(sample_bytes, bit_depth):
            calls["n"] += 1
            if calls["n"] > 10:
                raise OSError("simulated mid-scan decode failure")
            return original(sample_bytes, bit_depth)

        core.WAVProcessor._decode_sample_bytes = staticmethod(flaky)
        try:
            with self.assertRaises(OSError):
                processor._find_audio_boundaries(str(wav_path), info, 0.01)
        finally:
            core.WAVProcessor._decode_sample_bytes = staticmethod(original)

        self.assertGreater(total, 0)


class SecurityValidatorTests(unittest.TestCase):
    """Checks for the canonical security primitives."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_validate_path_accepts_normal_path(self) -> None:
        wav = _write_sine_wave(self.tmp_path / "ok.wav")
        self.assertTrue(SecurityValidator.validate_path(str(wav)))

    def test_validate_path_enforces_trusted_roots(self) -> None:
        # With a trusted root configured, paths outside it are rejected.
        inside = _write_sine_wave(self.tmp_path / "inside.wav")
        validator = SecurityValidator(SecurityConfig(trusted_roots={str(self.tmp_path)}))
        self.assertTrue(validator.validate_path(str(inside)))
        self.assertFalse(validator.validate_path("/etc/passwd"))

    def test_validate_path_rejects_suspicious_chars(self) -> None:
        self.assertFalse(SecurityValidator.validate_path("/tmp/bad\x00name.wav"))

    def test_sanitize_filename_strips_dangerous_chars(self) -> None:
        cleaned = SecurityValidator.sanitize_filename('a/b:c*?.wav')
        self.assertNotIn("/", cleaned)
        self.assertNotIn("*", cleaned)

    def test_enhanced_copy_agrees_on_reserved_names(self) -> None:
        # core.EnhancedSecurityValidator ships a second sanitize_filename;
        # it must not return a name its sibling already calls untitled.
        for name in ('CON', 'con.wav', 'NUL.txt', 'com1', 'LPT9.md',
                     'aux.bin.wav', 'com\u00b9', 'console.wav', 'com0.wav',
                     'null.wav', 'acon.wav'):
            with self.subTest(name=name):
                self.assertEqual(
                    EnhancedSecurityValidator.sanitize_filename(name),
                    SecurityValidator.sanitize_filename(name),
                )

    def test_resolve_unique_paths_detects_duplicates(self) -> None:
        wav = _write_sine_wave(self.tmp_path / "dup.wav")
        with self.assertRaises(ValueError):
            SecurityValidator.resolve_unique_paths([str(wav), str(wav)])

    def test_validate_file_path_rejects_missing_for_read(self) -> None:
        validator = SecurityValidator(SecurityConfig(allowed_extensions={".wav"}))
        with self.assertRaises(SecurityError):
            validator.validate_file_path(str(self.tmp_path / "nope.wav"), operation="read")

    def test_extension_policy_enforced(self) -> None:
        bad = self.tmp_path / "script.py"
        bad.write_text("print('x')")
        validator = SecurityValidator(SecurityConfig(allowed_extensions={".wav"}))
        with self.assertRaises(SecurityError):
            validator.validate_file_path(str(bad), operation="read")

    def test_secure_file_operations_roundtrip(self) -> None:
        ops = SecureFileOperations(SecurityValidator(SecurityConfig(allowed_extensions={".log"})))
        log = self.tmp_path / "audit.log"
        with ops.secure_open(log, "a", encoding="utf-8") as handle:
            handle.write("event\n")
        self.assertTrue(log.exists())


if __name__ == "__main__":
    unittest.main()
