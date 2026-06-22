"""Shared, dependency-light test helpers (standard library only)."""

import math
import struct
import wave
from pathlib import Path


def write_sine_wave(path, duration: float = 0.3, frequency: float = 440.0,
                    sample_rate: int = 44100, amplitude: int = 12000) -> Path:
    """Write a mono 16-bit PCM sine-wave WAV file and return its path."""
    path = Path(path)
    count = int(sample_rate * duration)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = [int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
                  for i in range(count)]
        handle.writeframes(struct.pack("<" + "h" * len(frames), *frames))
    return path
