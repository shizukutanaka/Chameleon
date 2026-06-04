"""Smoke tests: the core modules import and the basic audio API works.

These are intentionally dependency-light so they run in CI without numpy,
scipy, librosa, fastapi, etc.
"""

import importlib
import math
import struct
import wave
from pathlib import Path

import pytest

# Modules that must import cleanly with only the standard library available.
CORE_MODULES = [
    "security_validator",
    "audio_utils",
    "config_manager",
    "plugin_system",
    "core",
    "main",
    "batch_automation",
]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_core_modules_import(module_name):
    assert importlib.import_module(module_name) is not None


def _write_sine_wave(path: Path, duration: float = 0.3, frequency: float = 440.0) -> Path:
    sample_rate = 44100
    count = int(sample_rate * duration)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = [int(12000 * math.sin(2 * math.pi * frequency * i / sample_rate))
                  for i in range(count)]
        handle.writeframes(struct.pack("<" + "h" * len(frames), *frames))
    return path


def test_core_analyze_roundtrip(tmp_path):
    from core import analyze

    wav = _write_sine_wave(tmp_path / "tone.wav")
    result = analyze(str(wav))
    assert result.success, result.message
    assert result.data.sample_rate == 44100
    assert result.data.duration > 0


def test_security_validator_rejects_duplicates(tmp_path):
    from security_validator import SecurityValidator

    wav = _write_sine_wave(tmp_path / "dup.wav")
    with pytest.raises(ValueError):
        SecurityValidator.resolve_unique_paths([str(wav), str(wav)])
