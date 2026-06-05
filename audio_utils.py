#!/usr/bin/env python3
"""
Lightweight audio utilities for WAV file operations
No external dependencies required
"""

import struct
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class WAVInfo:
    """WAV file information"""
    file_path: str
    file_size: int
    channels: int
    sample_rate: int
    bits_per_sample: int
    duration_seconds: float
    format_type: str
    data_size: int


class WAVValidator:
    """Validate and analyze WAV files without external dependencies"""

    SUPPORTED_FORMATS = {'.wav', '.wave'}
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

    @staticmethod
    def is_valid_wav_file(file_path: str) -> bool:
        """Check if file is a valid WAV file"""
        try:
            path = Path(file_path)

            # Check file exists
            if not path.exists():
                return False

            # Check extension
            if path.suffix.lower() not in WAVValidator.SUPPORTED_FORMATS:
                return False

            # Check file size
            if path.stat().st_size > WAVValidator.MAX_FILE_SIZE:
                return False

            # Check WAV header
            with open(file_path, 'rb') as f:
                header = f.read(12)
                if len(header) < 12:
                    return False
                if header[:4] != b'RIFF':
                    return False
                if header[8:12] != b'WAVE':
                    return False

            return True
        except Exception:
            return False

    # Hardening limits for the hand-rolled RIFF parser. Declared chunk sizes in
    # a WAV header are attacker-controllable; never trust them beyond the real
    # file size, and bound the chunk-walk so a crafted/looping file cannot hang.
    MAX_CHUNKS = 4096
    VALID_BITS_PER_SAMPLE = {8, 16, 24, 32}
    MAX_CHANNELS = 256

    @staticmethod
    def get_wav_info(file_path: str) -> Optional[WAVInfo]:
        """Extract WAV file information.

        The RIFF chunk walk is bounded against the actual file size (declared
        chunk sizes are validated, never trusted) and honours word alignment, so
        truncated or maliciously-crafted headers yield ``None`` rather than wrong
        values, unbounded seeks, or a hang.
        """
        try:
            if not WAVValidator.is_valid_wav_file(file_path):
                return None

            path = Path(file_path)
            file_size = path.stat().st_size

            with open(file_path, 'rb') as f:
                # Read RIFF header
                riff_header = f.read(12)
                if len(riff_header) < 12:
                    return None
                if riff_header[:4] != b'RIFF' or riff_header[8:12] != b'WAVE':
                    return None

                # Find fmt chunk
                channels = 0
                sample_rate = 0
                bits_per_sample = 0
                format_type = "Unknown"
                data_size = 0

                pos = 12  # byte offset of the next chunk header
                chunks_seen = 0

                while pos + 8 <= file_size and chunks_seen < WAVValidator.MAX_CHUNKS:
                    chunks_seen += 1
                    f.seek(pos)
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8:
                        break

                    chunk_id = chunk_header[:4]
                    chunk_size = struct.unpack('<I', chunk_header[4:8])[0]

                    body_start = pos + 8
                    # Never trust the declared size beyond what the file holds.
                    available = max(0, file_size - body_start)
                    effective_size = min(chunk_size, available)

                    if chunk_id == b'fmt ':
                        fmt_data = f.read(min(effective_size, 16))
                        if len(fmt_data) >= 16:
                            audio_format = struct.unpack('<H', fmt_data[0:2])[0]
                            channels = struct.unpack('<H', fmt_data[2:4])[0]
                            sample_rate = struct.unpack('<I', fmt_data[4:8])[0]
                            bits_per_sample = struct.unpack('<H', fmt_data[14:16])[0]
                            format_type = "PCM" if audio_format == 1 else f"Format {audio_format}"

                    elif chunk_id == b'data':
                        data_size = effective_size
                        break

                    # Advance to the next chunk. RIFF chunks are word-aligned, so
                    # an odd size carries a trailing pad byte. Use the *declared*
                    # size for stride (capped to the file) and require forward
                    # progress to defeat zero-size loops.
                    stride = chunk_size + (chunk_size & 1)
                    next_pos = body_start + min(stride, available + 1)
                    if next_pos <= pos:
                        break
                    pos = next_pos

                # Reject implausible format fields rather than computing nonsense.
                if channels > WAVValidator.MAX_CHANNELS:
                    return None
                if bits_per_sample and bits_per_sample not in WAVValidator.VALID_BITS_PER_SAMPLE:
                    return None

                # Calculate duration
                if sample_rate > 0 and channels > 0 and bits_per_sample > 0:
                    bytes_per_sample = bits_per_sample // 8
                    frame_size = channels * bytes_per_sample
                    total_samples = data_size // frame_size if frame_size else 0
                    duration_seconds = total_samples / sample_rate
                else:
                    duration_seconds = 0.0

                return WAVInfo(
                    file_path=str(path),
                    file_size=file_size,
                    channels=channels,
                    sample_rate=sample_rate,
                    bits_per_sample=bits_per_sample,
                    duration_seconds=duration_seconds,
                    format_type=format_type,
                    data_size=data_size
                )

        except (OSError, ValueError, struct.error):
            return None



class SimpleWAVWriter:
    """Simple WAV file writer without external dependencies"""

    @staticmethod
    def write_wav(
        file_path: str,
        audio_data: bytes,
        sample_rate: int = 44100,
        channels: int = 1,
        bits_per_sample: int = 16
    ) -> bool:
        """Write WAV file with basic validation"""
        try:
            if bits_per_sample not in {8, 16, 24, 32}:
                return False

            if channels < 1 or channels > 8:
                return False

            if sample_rate < 8000 or sample_rate > 192000:
                return False

            bytes_per_sample = bits_per_sample // 8
            byte_rate = sample_rate * channels * bytes_per_sample
            block_align = channels * bytes_per_sample
            data_size = len(audio_data)

            with open(file_path, 'wb') as f:
                # RIFF header
                f.write(b'RIFF')
                f.write(struct.pack('<I', 36 + data_size))
                f.write(b'WAVE')

                # fmt chunk
                f.write(b'fmt ')
                f.write(struct.pack('<I', 16))  # Chunk size
                f.write(struct.pack('<H', 1))   # Audio format (PCM)
                f.write(struct.pack('<H', channels))
                f.write(struct.pack('<I', sample_rate))
                f.write(struct.pack('<I', byte_rate))
                f.write(struct.pack('<H', block_align))
                f.write(struct.pack('<H', bits_per_sample))

                # data chunk
                f.write(b'data')
                f.write(struct.pack('<I', data_size))
                f.write(audio_data)

            return True

        except Exception:
            return False


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.0f}s"


def format_file_size(bytes: int) -> str:
    """Format file size in human-readable format"""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.2f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes / (1024 * 1024 * 1024):.2f} GB"


def analyze_wav_file(file_path: str) -> Dict[str, Any]:
    """Analyze WAV file and return comprehensive information"""
    info = WAVValidator.get_wav_info(file_path)

    if info is None:
        return {
            "valid": False,
            "error": "Invalid or unsupported WAV file"
        }

    return {
        "valid": True,
        "file_path": info.file_path,
        "file_size": info.file_size,
        "file_size_formatted": format_file_size(info.file_size),
        "channels": info.channels,
        "channel_description": "Mono" if info.channels == 1 else f"{info.channels} channels",
        "sample_rate": info.sample_rate,
        "sample_rate_formatted": f"{info.sample_rate} Hz",
        "bits_per_sample": info.bits_per_sample,
        "format_type": info.format_type,
        "duration_seconds": info.duration_seconds,
        "duration_formatted": format_duration(info.duration_seconds),
        "data_size": info.data_size,
        "bitrate": (info.sample_rate * info.channels * info.bits_per_sample) // 1000,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python audio_utils.py <wav_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    result = analyze_wav_file(file_path)

    if result["valid"]:
        print(f"File: {result['file_path']}")
        print(f"Size: {result['file_size_formatted']}")
        print(f"Duration: {result['duration_formatted']}")
        print(f"Format: {result['format_type']}")
        print(f"Channels: {result['channel_description']}")
        print(f"Sample Rate: {result['sample_rate_formatted']}")
        print(f"Bit Depth: {result['bits_per_sample']} bits")
        print(f"Bitrate: {result['bitrate']} kbps")
    else:
        print(f"Error: {result['error']}")
        sys.exit(1)
