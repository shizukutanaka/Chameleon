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


# GUIDs used by WAVE_FORMAT_EXTENSIBLE to identify the actual sample format.
PCM_SUBFORMAT_GUID = (b'\x01\x00\x00\x00\x00\x00\x10\x00'
                      b'\x80\x00\x00\xaa\x00\x38\x9b\x71')
FLOAT_SUBFORMAT_GUID = (b'\x03\x00\x00\x00\x00\x00\x10\x00'
                        b'\x80\x00\x00\xaa\x00\x38\x9b\x71')


def _encode_pcm_sample(value, bits: int) -> bytes:
    if bits == 8:
        return bytes([max(0, min(255, int(value) + 128))])
    if bits == 16:
        return struct.pack('<h', max(-32768, min(32767, int(value))))
    if bits == 24:
        clamped = max(-8388608, min(8388607, int(value)))
        return int(clamped).to_bytes(4, 'little', signed=True)[:3]
    if bits == 32:
        return struct.pack('<i', max(-2147483648, min(2147483647, int(value))))
    raise ValueError(f"unsupported bits: {bits}")


def build_wav_bytes(*, frames, sample_rate: int = 44100, channels: int = 1,
                    bits: int = 16, fmt_variant: str = "16", format_tag: int = 1,
                    pre_data_chunks=(), post_data_chunks=()):
    """Hand-assemble a RIFF/WAVE byte blob for parser robustness tests.

    *frames* is a flat interleaved list — ints for PCM, floats for tag 3.
    *fmt_variant*: "16" (classic), "18" (cbSize=0), or "extensible" (40-byte
    fmt with a subformat GUID chosen from *format_tag*).
    *pre_data_chunks*/*post_data_chunks*: sequences of ``(chunk_id, payload)``
    placed before/after the data chunk; odd payloads get the RIFF pad byte.

    Returns ``(blob: bytes, data_offset: int)`` where data_offset is the file
    offset of the first data payload byte.
    """
    if format_tag == 3:
        data = b''.join(struct.pack('<f', float(v)) for v in frames)
        bits = 32
    else:
        data = b''.join(_encode_pcm_sample(v, bits) for v in frames)

    block_align = channels * (bits // 8)
    byte_rate = sample_rate * block_align
    base_fmt = struct.pack('<HHIIHH',
                           0xFFFE if fmt_variant == "extensible" else format_tag,
                           channels, sample_rate, byte_rate, block_align, bits)
    if fmt_variant == "16":
        fmt_body = base_fmt
    elif fmt_variant == "18":
        fmt_body = base_fmt + struct.pack('<H', 0)
    elif fmt_variant == "extensible":
        guid = FLOAT_SUBFORMAT_GUID if format_tag == 3 else PCM_SUBFORMAT_GUID
        fmt_body = base_fmt + struct.pack('<HHI', 22, bits, 0) + guid
    else:
        raise ValueError(f"unknown fmt_variant: {fmt_variant}")

    def chunk(cid: bytes, payload: bytes) -> bytes:
        pad = b'\x00' if len(payload) % 2 else b''
        return cid + struct.pack('<I', len(payload)) + payload + pad

    body = chunk(b'fmt ', fmt_body)
    for cid, payload in pre_data_chunks:
        body += chunk(cid, payload)
    data_offset = 12 + len(body) + 8
    body += chunk(b'data', data)
    for cid, payload in post_data_chunks:
        body += chunk(cid, payload)

    blob = b'RIFF' + struct.pack('<I', 4 + len(body)) + b'WAVE' + body
    return blob, data_offset


def write_wav_raw(path, **kwargs):
    """Write a hand-assembled WAV (see build_wav_bytes); returns (Path, data_offset)."""
    blob, data_offset = build_wav_bytes(**kwargs)
    path = Path(path)
    path.write_bytes(blob)
    return path, data_offset


def sine_frames(count: int = 4410, frequency: float = 440.0,
                sample_rate: int = 44100, amplitude: int = 12000,
                channels: int = 1):
    """Interleaved int16-range sine samples for build_wav_bytes."""
    frames = []
    for i in range(count):
        value = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
        frames.extend([value] * channels)
    return frames
