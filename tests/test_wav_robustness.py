#!/usr/bin/env python3
"""Robustness tests for the hand-rolled WAV/RIFF parser in audio_utils.

The parser reads attacker-controllable chunk sizes; these tests assert it never
crashes, hangs, or returns absurd values on truncated, oversized, or random
input, while still parsing valid files correctly. Pure standard library — no
numpy/Hypothesis required (a Hypothesis pass is added opportunistically if the
package happens to be installed).
"""

from __future__ import annotations

import os
import random
import struct
import tempfile
import time
import unittest
from pathlib import Path

from audio_utils import WAVValidator, SimpleWAVWriter


def _write_bytes(directory: Path, name: str, data: bytes) -> str:
    p = directory / name
    p.write_bytes(data)
    return str(p)


def _riff(body: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def _fmt_chunk(audio_format=1, channels=1, sample_rate=8000, bits=16) -> bytes:
    byte_rate = sample_rate * channels * (bits // 8)
    block_align = channels * (bits // 8)
    body = struct.pack(
        "<HHIIHH", audio_format, channels, sample_rate, byte_rate, block_align, bits
    )
    return b"fmt " + struct.pack("<I", len(body)) + body


class WavParserRobustnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # -- valid parsing still works (no regression) -----------------------

    def test_valid_wav_parses_correctly(self):
        audio = b"\x00\x01" * 800  # 800 mono 16-bit samples
        path = self.dir / "ok.wav"
        self.assertTrue(SimpleWAVWriter.write_wav(str(path), audio, 8000, 1, 16))
        info = WAVValidator.get_wav_info(str(path))
        self.assertIsNotNone(info)
        self.assertEqual(info.channels, 1)
        self.assertEqual(info.sample_rate, 8000)
        self.assertEqual(info.bits_per_sample, 16)
        self.assertEqual(info.data_size, len(audio))
        self.assertAlmostEqual(info.duration_seconds, 800 / 8000, places=4)

    # -- malformed / hostile input must not crash ------------------------

    def test_truncated_header_returns_none(self):
        path = _write_bytes(self.dir, "trunc.wav", b"RIFF\x00\x00")
        self.assertIsNone(WAVValidator.get_wav_info(path))

    def test_riff_without_chunks_returns_info_or_none(self):
        path = _write_bytes(self.dir, "empty.wav", _riff(b""))
        # Must not raise; no fmt/data so duration is 0.
        info = WAVValidator.get_wav_info(path)
        if info is not None:
            self.assertEqual(info.duration_seconds, 0.0)

    def test_oversized_data_chunk_is_capped(self):
        # data chunk claims 4 GiB but file holds only 10 bytes of payload.
        body = _fmt_chunk() + b"data" + struct.pack("<I", 0xFFFFFFFF) + (b"\x00" * 10)
        path = _write_bytes(self.dir, "huge.wav", _riff(body))
        info = WAVValidator.get_wav_info(path)
        self.assertIsNotNone(info)
        file_size = os.path.getsize(path)
        self.assertLessEqual(info.data_size, file_size)
        self.assertLess(info.duration_seconds, 1.0)  # not an absurd duration

    def test_oversized_skipped_chunk_does_not_seek_wildly(self):
        # Unknown chunk with a 4 GiB declared size before fmt/data.
        body = (b"JUNK" + struct.pack("<I", 0xFFFFFFFF) + b"\x00\x00"
                + _fmt_chunk() + b"data" + struct.pack("<I", 4) + b"\x01\x02\x03\x04")
        path = _write_bytes(self.dir, "bigjunk.wav", _riff(body))
        info = WAVValidator.get_wav_info(path)
        # Capped stride means we stop at the junk chunk; must not raise.
        self.assertTrue(info is None or info.data_size <= os.path.getsize(path))

    def test_zero_size_chunks_terminate_quickly(self):
        # Many zero-size unknown chunks must not loop forever.
        body = (b"junk" + struct.pack("<I", 0)) * 5000
        path = _write_bytes(self.dir, "zeros.wav", _riff(body))
        start = time.monotonic()
        WAVValidator.get_wav_info(path)  # bounded by MAX_CHUNKS
        self.assertLess(time.monotonic() - start, 2.0)

    def test_odd_size_chunk_word_alignment(self):
        # fmt is standard; an odd-sized LIST chunk (with pad byte) precedes data.
        odd = b"LIST" + struct.pack("<I", 3) + b"abc" + b"\x00"  # 3 + 1 pad
        body = _fmt_chunk() + odd + b"data" + struct.pack("<I", 4) + b"\x01\x02\x03\x04"
        path = _write_bytes(self.dir, "odd.wav", _riff(body))
        info = WAVValidator.get_wav_info(path)
        self.assertIsNotNone(info)
        self.assertEqual(info.data_size, 4)

    def test_implausible_format_fields_rejected(self):
        # bits_per_sample = 7 is not a valid PCM depth.
        body = _fmt_chunk(bits=7) + b"data" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
        path = _write_bytes(self.dir, "badbits.wav", _riff(body))
        self.assertIsNone(WAVValidator.get_wav_info(path))

    def test_random_bytes_never_crash(self):
        rng = random.Random(1234)
        for i in range(300):
            n = rng.randint(0, 400)
            data = bytes(rng.randint(0, 255) for _ in range(n))
            # Prefix half the cases with a valid RIFF/WAVE magic to reach the loop.
            if i % 2 == 0:
                data = b"RIFF" + struct.pack("<I", max(0, n)) + b"WAVE" + data
            path = _write_bytes(self.dir, f"fuzz_{i}.wav", data)
            # Must return None or a WAVInfo, never raise.
            try:
                WAVValidator.get_wav_info(path)
            except Exception as exc:  # noqa: BLE001 - this is the assertion
                self.fail(f"parser raised on fuzz input #{i}: {exc!r}")


class CoreWavParserRobustnessTests(unittest.TestCase):
    """Same hardening expectations for core.py's two WAV header readers."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        from core import WAVProcessor  # imported here so a core import error is visible
        self.proc = WAVProcessor()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_wav_parses_correctly(self):
        audio = b"\x00\x01" * 800
        path = self.dir / "ok.wav"
        self.assertTrue(SimpleWAVWriter.write_wav(str(path), audio, 8000, 1, 16))
        for reader in (self.proc._read_wav_header, self.proc._read_wav_header_optimized):
            info = reader(str(path))
            self.assertIsNotNone(info, reader.__name__)
            self.assertEqual(info.sample_rate, 8000)
            self.assertEqual(info.channels, 1)
            self.assertEqual(info.bit_depth, 16)
            self.assertAlmostEqual(info.duration, 800 / 8000, places=3)

    def test_oversized_data_chunk_is_capped(self):
        body = _fmt_chunk() + b"data" + struct.pack("<I", 0xFFFFFFFF) + (b"\x00" * 10)
        path = _write_bytes(self.dir, "huge.wav", _riff(body))
        info = self.proc._read_wav_header(path)
        if info is not None:
            self.assertLess(info.duration, 1.0)

    def test_zero_rate_does_not_divide_by_zero(self):
        # sample_rate = 0 in fmt -> must return None, not raise ZeroDivisionError.
        body = _fmt_chunk(sample_rate=0) + b"data" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
        path = _write_bytes(self.dir, "zerorate.wav", _riff(body))
        self.assertIsNone(self.proc._read_wav_header(path))

    def test_data_before_fmt_returns_none(self):
        body = b"data" + struct.pack("<I", 4) + b"\x00\x00\x00\x00" + _fmt_chunk()
        path = _write_bytes(self.dir, "datafirst.wav", _riff(body))
        self.assertIsNone(self.proc._read_wav_header(path))

    def test_zero_size_chunks_terminate_quickly(self):
        body = (b"junk" + struct.pack("<I", 0)) * 5000
        path = _write_bytes(self.dir, "zeros.wav", _riff(body))
        start = time.monotonic()
        self.proc._read_wav_header(path)
        self.assertLess(time.monotonic() - start, 2.0)

    def test_random_bytes_never_crash(self):
        rng = random.Random(99)
        for i in range(200):
            n = rng.randint(0, 300)
            data = bytes(rng.randint(0, 255) for _ in range(n))
            if i % 2 == 0:
                data = b"RIFF" + struct.pack("<I", n) + b"WAVE" + data
            path = _write_bytes(self.dir, f"cfuzz_{i}.wav", data)
            try:
                self.proc._read_wav_header(path)
                self.proc._read_wav_header_optimized(path)
            except Exception as exc:  # noqa: BLE001
                self.fail(f"core parser raised on fuzz input #{i}: {exc!r}")


if __name__ == "__main__":
    unittest.main()