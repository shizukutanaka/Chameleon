#!/usr/bin/env python3
"""Test suite covering Chameleon audio core and CLI façade."""

from __future__ import annotations

import math
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from audio_tool import (
    analyze,
    batch_convert_format,
    batch_process,
    find_duplicates,
    generate_playlist,
    normalize,
    quick_stats,
    to_mono,
    trim_silence,
)


SAMPLE_RATE = 44100


def _write_sine_wave(path: Path, *, duration: float = 0.5, frequency: float = 440.0, channels: int = 1) -> Path:
    """Generate a simple PCM sine wave for testing."""
    sample_count = int(SAMPLE_RATE * duration)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)

        frames = []
        for index in range(sample_count):
            value = int(12000 * math.sin(2 * math.pi * frequency * index / SAMPLE_RATE))
            if channels == 1:
                frames.append(value)
            else:
                frames.extend((value, value))

        handle.writeframes(struct.pack("<" + "h" * len(frames), *frames))

    return path


class ChameleonAudioTests(unittest.TestCase):
    """High-level behaviour checks for the audio façade."""

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
        self.assertAlmostEqual(result.data.sample_rate, SAMPLE_RATE)
        self.assertGreater(result.data.duration, 0)

    def test_normalize_creates_output(self) -> None:
        input_path = _write_sine_wave(self.tmp_path / "input.wav")
        output_path = self.tmp_path / "output.wav"

        result = normalize(str(input_path), str(output_path), 0.8)

        self.assertTrue(result.success, msg=result.message)
        self.assertTrue(output_path.exists())
        self.assertIn("Normalized", result.message)

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

    def test_batch_process_analyze(self) -> None:
        for index in range(3):
            _write_sine_wave(self.tmp_path / f"sample{index}.wav")

        results = batch_process(str(self.tmp_path), "analyze")

        self.assertEqual(len(results), 3)
        self.assertTrue(all(item.success for item in results))

    def test_find_duplicates_detects_identical_files(self) -> None:
        original = _write_sine_wave(self.tmp_path / "orig.wav")
        duplicate = self.tmp_path / "dup.wav"
        duplicate.write_bytes(original.read_bytes())
        _write_sine_wave(self.tmp_path / "unique.wav", frequency=523.25)

        result = find_duplicates(str(self.tmp_path))

        self.assertTrue(result.success, msg=result.message)
        self.assertEqual(len(result.data["duplicates"]), 1)

    def test_quick_stats_reports_summary(self) -> None:
        _write_sine_wave(self.tmp_path / "a.wav")
        _write_sine_wave(self.tmp_path / "b.wav", frequency=523.25)

        result = quick_stats(str(self.tmp_path))

        self.assertTrue(result.success, msg=result.message)
        self.assertEqual(result.data["total_files"], 2)
        self.assertGreater(result.data["total_duration"], 0)

    def test_batch_convert_format_updates_header(self) -> None:
        wav_path = _write_sine_wave(self.tmp_path / "convert.wav")

        result = batch_convert_format(str(self.tmp_path), target_rate=22050)

        self.assertTrue(result.success, msg=result.message)
        with wave.open(str(wav_path), "rb") as handle:
            self.assertEqual(handle.getframerate(), 22050)

    def test_generate_playlist_creates_file(self) -> None:
        _write_sine_wave(self.tmp_path / "one.wav")
        _write_sine_wave(self.tmp_path / "two.wav", frequency=330.0)

        result = generate_playlist(str(self.tmp_path))

        self.assertTrue(result.success, msg=result.message)
        playlist_path = Path(result.data["playlist"])
        self.assertTrue(playlist_path.exists())


if __name__ == "__main__":
    unittest.main()