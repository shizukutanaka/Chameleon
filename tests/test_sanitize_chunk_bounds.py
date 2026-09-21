"""sanitize_wav_metadata must reject a chunk whose declared size runs
past EOF -- otherwise it writes an output header claiming bytes that
were never copied (and reads an attacker-declared length)."""
import struct
import wave

import pytest

from advanced_validation import SanitizationEngine


def _valid_wav(path, frames=b"\x00\x00" * 64):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(frames)


def _corrupt_data_size(path, claimed):
    """Rewrite the data chunk's declared size without touching bytes."""
    data = bytearray(path.read_bytes())
    idx = data.find(b"data")
    assert idx > 0
    struct.pack_into("<I", data, idx + 4, claimed)
    path.write_bytes(bytes(data))


def test_oversized_declared_chunk_rejected(tmp_path):
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    _valid_wav(src)
    _corrupt_data_size(src, 0xFFFFFFF0)

    with pytest.raises(ValueError, match="exceeds remaining"):
        SanitizationEngine.sanitize_wav_metadata(src, dst)


def test_oversized_declared_chunk_preserves_destination(tmp_path):
    """On rejection the pre-existing destination must stay untouched."""
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    _valid_wav(src)
    _corrupt_data_size(src, 0xFFFFFFF0)
    dst.write_bytes(b"previous content")

    with pytest.raises(ValueError):
        SanitizationEngine.sanitize_wav_metadata(src, dst)
    assert dst.read_bytes() == b"previous content"


def test_valid_file_still_sanitizes(tmp_path):
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    _valid_wav(src)

    SanitizationEngine.sanitize_wav_metadata(src, dst)
    assert dst.exists()
    with wave.open(str(dst), "rb") as w:
        assert w.getnframes() == 64
