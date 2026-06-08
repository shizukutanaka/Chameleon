#!/usr/bin/env python3
"""CLI contract tests (see docs/SPECIFICATION.md).

Exercises the command-line surface as a subprocess so exit codes and stdout are
verified exactly as a user/script would see them.
"""

from __future__ import annotations

import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAIN = REPO / "main.py"


def _run(*args: str):
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _make_wav(path: Path, seconds: float = 0.2, rate: int = 8000) -> None:
    n = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = [int(10000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(n)]
        w.writeframes(struct.pack("<" + "h" * n, *frames))


class CliContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.wav = Path(self.tmp.name) / "in.wav"
        _make_wav(self.wav)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_version_exits_zero_and_prints_version(self):
        r = _run("--version")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("chameleon 1.0.0", r.stdout + r.stderr)

    def test_no_command_exits_one(self):
        r = _run()
        self.assertEqual(r.returncode, 1)

    def test_unimplemented_ml_op_exits_unavailable(self):
        # separate has no model in this build -> exit code 2 (not 0).
        r = _run("ml", "separate", "--input", str(self.wav))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Not implemented", r.stdout)

    def test_transcribe_exits_unavailable(self):
        r = _run("ml", "transcribe", "--input", str(self.wav))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_unknown_command_is_usage_error(self):
        r = _run("definitely-not-a-command")
        # argparse rejects invalid choice with exit code 2.
        self.assertEqual(r.returncode, 2)

    def test_analyze_json_emits_machine_readable_output(self):
        import json
        r = _run("analyze", str(self.wav), "--json")
        # stdout must be pure JSON (human lines are suppressed in --json mode).
        payload = json.loads(r.stdout)
        self.assertEqual(payload["command"], "analyze")
        self.assertIsInstance(payload["results"], list)
        self.assertGreaterEqual(len(payload["results"]), 1)
        self.assertIn("file", payload["results"][0])

    def test_batch_dry_run_writes_nothing(self):
        src = Path(self.tmp.name) / "src"
        out = Path(self.tmp.name) / "out"
        src.mkdir()
        out.mkdir()
        _make_wav(src / "a.wav")
        _make_wav(src / "b.wav")
        r = _run("batch", str(src), "normalize", "--output-dir", str(out), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[dry-run]", r.stdout)
        self.assertEqual(list(out.iterdir()), [])  # no files written

    def test_midi_generate_dry_run_writes_nothing(self):
        out = Path(self.tmp.name) / "demo.mid"
        r = _run("midi", "generate", "--output", str(out), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[dry-run]", r.stdout)
        self.assertFalse(out.exists())  # no MIDI file written

    def test_non_wav_without_backend_reports_clearly(self):
        # A non-WAV file is now accepted by the filter; without a decode backend
        # it must produce a handled, actionable per-file error (not a crash or a
        # silent skip). When a backend IS installed it may instead fail to decode
        # the bogus bytes — either way it is reported, never a traceback.
        flac = Path(self.tmp.name) / "fake.flac"
        flac.write_bytes(self.wav.read_bytes())  # WAV bytes under a .flac name
        r = _run("analyze", str(flac))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Error processing", r.stdout)

    def test_unsupported_extension_is_not_processed(self):
        bogus = Path(self.tmp.name) / "file.xyz"
        bogus.write_bytes(self.wav.read_bytes())
        r = _run("analyze", str(bogus))
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
