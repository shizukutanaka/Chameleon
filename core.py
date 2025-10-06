#!/usr/bin/env python3
"""
Chameleon Audio Tool - Lightweight, Fast, Practical Audio Processing
Designed with Carmack's simplicity, Clean Code principles, and Pike's minimalism.

Usage:
    python core.py analyze file.wav
    python core.py normalize input.wav output.wav
    python core.py mono input.wav output.wav
    python core.py trim input.wav output.wav
    python core.py batch directory operation
"""

import os
import sys
import time
import json
import datetime
import struct
import hashlib
import secrets
import tempfile
import threading
import argparse
import gc
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass
from functools import lru_cache
import logging

VERSION = "2.1.0"
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB - practical limit
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64KB chunks
MIN_CHUNK_SIZE = 4 * 1024
MAX_CHUNK_SIZE = 4 * 1024 * 1024
DEFAULT_OPERATION_TIMEOUT = 30  # seconds
ALLOWED_BATCH_OPERATIONS = ("analyze", "normalize", "mono", "trim")


def _determine_chunk_size() -> int:
    """Resolve streaming chunk size from configuration."""

    env_value = os.getenv("CHAMELEON_CHUNK_SIZE")
    if env_value:
        try:
            parsed = int(env_value)
        except (TypeError, ValueError):
            parsed = DEFAULT_CHUNK_SIZE
        else:
            if parsed < MIN_CHUNK_SIZE or parsed > MAX_CHUNK_SIZE:
                parsed = DEFAULT_CHUNK_SIZE
        return parsed

    mode = os.getenv("CHAMELEON_PERFORMANCE_MODE", "auto").lower()
    if mode == "fast":
        return min(MAX_CHUNK_SIZE, DEFAULT_CHUNK_SIZE * 2)
    if mode == "safe":
        return max(MIN_CHUNK_SIZE, DEFAULT_CHUNK_SIZE // 2)

    return DEFAULT_CHUNK_SIZE


def _determine_timeout() -> int:
    """Resolve overall operation timeout from configuration."""

    env_value = os.getenv("CHAMELEON_TIMEOUT")
    if env_value:
        try:
            parsed = int(env_value)
        except (TypeError, ValueError):
            return DEFAULT_OPERATION_TIMEOUT
        else:
            if parsed <= 0:
                return DEFAULT_OPERATION_TIMEOUT
            return parsed

    return DEFAULT_OPERATION_TIMEOUT

CHUNK_SIZE = _determine_chunk_size()
OPERATION_TIMEOUT = _determine_timeout()
SAMPLE_RATES = {8000, 16000, 22050, 44100, 48000, 96000}
SUPPORTED_FORMATS = {'.wav', '.wave'}


def open_secure(path: Union[str, Path], mode: str = "wb", *, encoding: Optional[str] = None):
    """Open a file for writing with restrictive permissions (0o600)."""

    if "w" not in mode and "a" not in mode:
        raise ValueError("open_secure only supports write/append modes")

    flags = os.O_WRONLY
    if "a" in mode:
        flags |= os.O_CREAT | os.O_APPEND
    else:
        flags |= os.O_CREAT | os.O_TRUNC

    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    fd = os.open(os.fspath(path), flags, 0o600)
    return os.fdopen(fd, mode, encoding=encoding)


@dataclass
class AudioInfo:
    """Essential audio information - no bloat."""
    duration: float
    sample_rate: int
    channels: int
    bit_depth: int
    size_bytes: int
    peak_level: float = 0.0
    rms_level: float = 0.0

@dataclass
class ProcessingResult:
    """Structured result returned by processing routines."""
    success: bool
    message: str
    data: Any = None
    duration_ms: int = 0


class SecurityValidator:
    """Security-focused helpers for validating file and directory inputs."""

    BLOCKED_PATTERNS = [
        '../', '..\\', '\x00', '/etc/', '/proc/', '/sys/',
        '%2e%2e%2f', '%2e%2e%5c',
        'cmd.exe', 'powershell.exe', 'bash', 'sh',
        '<script', 'javascript:', 'vbscript:', 'onload=',
        'eval(', 'exec(', 'system(', 'popen(', 'subprocess',
        '\r', '\n', '\t', '\f', '\v'
    ]

    FORBIDDEN_ROOTS = [
        '/etc', '/proc', '/sys', '/dev',
        'C:/Windows', 'C:/Program Files'
    ]

    MAX_PATH_LENGTH = 4096
    MAX_FILENAME_LENGTH = 255
    ALLOWED_EXTENSIONS = {'.wav', '.wave'}

    _resolved_forbidden_roots: Optional[List[Path]] = None

    @classmethod
    def _has_blocked_pattern(cls, value: str) -> bool:
        lowered = value.lower()
        return any(pattern in lowered for pattern in cls.BLOCKED_PATTERNS)

    @classmethod
    def _has_control_chars(cls, value: str) -> bool:
        return any(ord(char) < 32 for char in value)

    @classmethod
    def _normalize_path(cls, value: str) -> Optional[Path]:
        try:
            return Path(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _forbidden_roots(cls) -> List[Path]:
        if cls._resolved_forbidden_roots is None:
            roots: List[Path] = []
            for root in cls.FORBIDDEN_ROOTS:
                try:
                    roots.append(Path(root).resolve(strict=False))
                except (OSError, RuntimeError):
                    continue
            cls._resolved_forbidden_roots = roots
        return cls._resolved_forbidden_roots

    @classmethod
    def _is_forbidden_target(cls, resolved_path: Path) -> bool:
        try:
            target = resolved_path.resolve(strict=False)
        except (OSError, RuntimeError):
            return True

        if not target.is_absolute():
            return False

        normalized = target
        for root in cls._forbidden_roots():
            try:
                if normalized == root or root in normalized.parents:
                    return True
            except RuntimeError:
                return True
        return False

    @classmethod
    def _contains_symlink(cls, path_obj: Path) -> bool:
        try:
            for candidate in (path_obj, *path_obj.parents):
                if candidate.exists() and candidate.is_symlink():
                    return True
        except OSError:
            return True
        return False

    @classmethod
    def validate_path(cls, path: str) -> bool:
        if not path or not isinstance(path, str):
            return False

        if len(path) > cls.MAX_PATH_LENGTH:
            return False

        if cls._has_blocked_pattern(path) or cls._has_control_chars(path):
            return False

        path_obj = cls._normalize_path(path)
        if path_obj is None:
            return False

        if cls._contains_symlink(path_obj):
            return False

        if len(path_obj.name) > cls.MAX_FILENAME_LENGTH:
            return False

        if any(part == '..' for part in path_obj.parts):
            return False

        if path_obj.suffix.lower() not in cls.ALLOWED_EXTENSIONS:
            return False

        try:
            resolved = path_obj.resolve(strict=False)
        except (OSError, RuntimeError):
            return False

        if cls._is_forbidden_target(resolved):
            return False

        return True

    @classmethod
    def validate_directory(cls, path: str) -> bool:
        if not path or not isinstance(path, str):
            return False

        if len(path) > cls.MAX_PATH_LENGTH:
            return False

        if cls._has_blocked_pattern(path) or cls._has_control_chars(path):
            return False

        path_obj = cls._normalize_path(path)
        if path_obj is None:
            return False

        if cls._contains_symlink(path_obj):
            return False

        if any(part == '..' for part in path_obj.parts):
            return False

        try:
            resolved = path_obj.resolve(strict=False)
        except (OSError, RuntimeError):
            return False

        if cls._is_forbidden_target(resolved):
            return False

        if resolved.exists() and not resolved.is_dir():
            return False

        return True

    @staticmethod
    def validate_file_size(file_path: str) -> bool:
        """Check file size is reasonable and safe."""
        try:
            size = os.path.getsize(file_path)
            return 0 < size <= MAX_FILE_SIZE
        except OSError:
            return False

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe operations."""
        if not filename:
            return "untitled.wav"

        # Remove dangerous characters
        safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- .')
        sanitized = ''.join(c if c in safe_chars else '_' for c in filename)

        # Ensure it has proper extension
        if not sanitized.lower().endswith('.wav'):
            sanitized += '.wav'

        # Truncate if too long
        if len(sanitized) > SecurityValidator.MAX_FILENAME_LENGTH:
            name_part, ext = os.path.splitext(sanitized)
            max_name_length = SecurityValidator.MAX_FILENAME_LENGTH - len(ext)
            sanitized = name_part[:max_name_length] + ext

        return sanitized

    @staticmethod
    def validate_audio_content(file_path: str) -> bool:
        """Validate audio file content for corruption and security."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(44)  # Standard WAV header size

                if len(header) != 44:
                    return False

                # Check RIFF signature
                if header[:4] != b'RIFF':
                    return False

                # Check WAVE signature
                if header[8:12] != b'WAVE':
                    return False

                # Check format chunk
                if header[12:16] != b'fmt ':
                    return False

                # Check data chunk exists
                f.seek(0, 2)  # Go to end
                file_size = f.tell()
                f.seek(36)  # Skip to data chunk position

                if f.tell() >= file_size:
                    return False

                data_header = f.read(8)
                if len(data_header) != 8 or data_header[:4] != b'data':
                    return False

                # Additional security checks
                # Check for unusually large chunks that could cause memory issues
                chunk_size = struct.unpack('<I', data_header[4:8])[0]
                if chunk_size > MAX_FILE_SIZE:
                    return False

                # Check for negative chunk sizes
                if chunk_size < 0:
                    return False

                return True

        except Exception:
            return False

    @staticmethod
    def resolve_unique_paths(paths: List[str]) -> List[Path]:
        """Resolve multiple paths, ensuring uniqueness and rejecting duplicates."""

        resolved_entries: Dict[str, Path] = {}
        resolved_paths: List[Path] = []

        for original in paths:
            try:
                resolved = Path(original).expanduser().resolve(strict=False)
            except Exception as exc:
                raise ValueError(f"Could not resolve path '{original}': {exc}") from exc

            key = str(resolved)
            if key in resolved_entries:
                duplicate = resolved_entries[key]
                raise ValueError(
                    f"Duplicate paths detected: '{original}' and '{duplicate}' refer to the same location"
                )

            resolved_entries[key] = original
            resolved_paths.append(resolved)

        return resolved_paths

    @staticmethod
    def safe_open_file(file_path: str, mode: str) -> Optional[Any]:
        """Safely open file with comprehensive validation."""
        try:
            if not SecurityValidator.validate_path(file_path):
                return None

            if not SecurityValidator.validate_file_size(file_path):
                return None

            if not SecurityValidator.validate_audio_content(file_path):
                return None

            # Check file permissions
            if not os.access(file_path, os.R_OK):
                return None

            return open(file_path, mode)

        except Exception:
            return None

class MemoryManager:
    """Memory-efficient processing with caching and optimization."""

    def __init__(self):
        self.cache = {}
        self.max_cache_size = 64 * 1024 * 1024  # 64MB cache
        self.current_cache_size = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def get_file_data(self, file_path: str, offset: int = 0, size: int = None) -> bytes:
        """Get file data with intelligent caching and memory mapping."""
        cache_key = f"{file_path}:{offset}:{size}"

        # Check cache first
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]

        self.cache_misses += 1

        if size is None or size > 1024 * 1024:  # Use memory mapping for large reads
            try:
                data = self._memory_map_file(file_path, offset, size)
            except (ImportError, OSError, OverflowError, ValueError):
                with open(file_path, 'rb') as f:
                    if offset > 0:
                        f.seek(offset)
                    data = f.read() if size is None else f.read(size)
        else:
            data = self._chunked_read(file_path, offset, size)

        if isinstance(data, bytearray):
            data = bytes(data)

        self.cache_data(cache_key, data)
        return data

    def _memory_map_file(self, file_path: str, offset: int = 0, size: Optional[int] = None) -> bytes:
        """Memory map file for efficient access."""
        import mmap

        with open(file_path, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                if offset > 0:
                    mm.seek(offset)
                if size is None:
                    available = max(0, mm.size() - mm.tell())
                    data = mm.read(available)
                else:
                    data = mm.read(size)
            finally:
                mm.close()
            return data

    def _chunked_read(self, file_path: str, offset: int, size: int) -> bytes:
        """Read file in optimized chunks with buffering."""
        result = bytearray()
        bytes_read = 0

        with open(file_path, 'rb') as f:
            f.seek(offset)

            while bytes_read < size:
                chunk_size = min(CHUNK_SIZE, size - bytes_read)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                result.extend(chunk)
                bytes_read += len(chunk)

        return bytes(result)

    def cache_data(self, key: str, data: bytes):
        """Cache data with size management."""
        if len(data) > self.max_cache_size // 4:  # Don't cache very large data
            return

        # Remove old entries if cache is full
        while self.current_cache_size + len(data) > self.max_cache_size:
            oldest_key = next(iter(self.cache))
            oldest_data = self.cache.pop(oldest_key)
            self.current_cache_size -= len(oldest_data)

        self.cache[key] = data
        self.current_cache_size += len(data)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'cache_size': self.current_cache_size,
            'max_cache_size': self.max_cache_size,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate
        }

    def clear_cache(self):
        """Clear memory cache."""
        self.cache.clear()
        self.current_cache_size = 0
        self.cache_hits = 0
        self.cache_misses = 0

class PerformanceTracker:
    """Lightweight performance tracking - Carmack style."""

    def __init__(self):
        self.start_time = 0
        self.operations = {}

    def start(self):
        """Start timing."""
        self.start_time = time.perf_counter()

    def end(self, operation: str = "operation") -> int:
        """End timing, return milliseconds."""
        if self.start_time == 0:
            return 0

        duration_ms = int((time.perf_counter() - self.start_time) * 1000)
        self.operations[operation] = duration_ms
        self.start_time = 0
        return duration_ms

    def record(self, operation: str, duration_ms: int):
        """Record an externally measured operation duration."""
        if not operation:
            return

        try:
            duration = int(duration_ms)
        except (TypeError, ValueError):
            duration = 0

        self.operations[operation] = max(0, duration)

    def record_operation(self, operation: str, duration_ms: int):
        """Backward-compatible alias for record()."""
        self.record(operation, duration_ms)

    def get_stats(self) -> Dict[str, int]:
        """Get performance statistics."""
        return self.operations.copy()

class WAVProcessor:
    """Core WAV processing - minimal, fast, reliable with memory optimization."""

    def __init__(self):
        self.perf = PerformanceTracker()
        self.memory_manager = MemoryManager()
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _decode_sample_bytes(sample_bytes: bytes, bit_depth: int) -> Optional[int]:
        if not sample_bytes:
            return None
        if bit_depth == 8:
            return int(sample_bytes[0]) - 128
        if bit_depth == 16 and len(sample_bytes) >= 2:
            return struct.unpack('<h', sample_bytes[:2])[0]
        if bit_depth == 24 and len(sample_bytes) >= 3:
            padding = b'\xff' if sample_bytes[2] & 0x80 else b'\x00'
            return int.from_bytes(sample_bytes[:3] + padding, 'little', signed=True)
        if bit_depth == 32 and len(sample_bytes) >= 4:
            return struct.unpack('<i', sample_bytes[:4])[0]
        return None

    @staticmethod
    def _normalize_amplitude(value: int, bit_depth: int) -> float:
        if bit_depth <= 8:
            scale = 128.0
        else:
            scale = float(1 << (bit_depth - 1))
        if scale == 0:
            return 0.0
        normalized = abs(value) / scale
        return normalized if normalized <= 1.0 else 1.0

    @staticmethod
    def _encode_sample_value(value: int, bit_depth: int) -> bytes:
        if bit_depth == 8:
            clamped = max(-128, min(127, int(value)))
            return bytes([clamped + 128])
        if bit_depth == 16:
            clamped = max(-32768, min(32767, int(value)))
            return struct.pack('<h', clamped)
        if bit_depth == 24:
            clamped = max(-8388608, min(8388607, int(value)))
            return int(clamped).to_bytes(4, 'little', signed=True)[:3]
        if bit_depth == 32:
            clamped = max(-2147483648, min(2147483647, int(value)))
            return struct.pack('<i', clamped)
        return b""

    def _read_wav_header_optimized(self, file_path: str) -> Optional[AudioInfo]:
        """Read WAV header with memory optimization."""
        try:
            # Use memory manager for efficient reading
            header_data = self.memory_manager.get_file_data(file_path, 0, 44)

            if len(header_data) != 44:
                return None

            # Check RIFF signature
            if header_data[:4] != b'RIFF':
                return None

            # Check WAVE signature
            if header_data[8:12] != b'WAVE':
                return None

            # Check format chunk
            if header_data[12:16] != b'fmt ':
                return None

            # Parse format information
            format_tag, channels, sample_rate, byte_rate, block_align, bits_per_sample = \
                struct.unpack('<HHIIHH', header_data[20:36])

            if format_tag != 1:  # Only PCM
                return None

            # Get file size efficiently
            file_size = os.path.getsize(file_path)
            data_size = file_size - 44  # Assume standard header
            duration = data_size / (sample_rate * channels * (bits_per_sample // 8))

            return AudioInfo(
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=bits_per_sample,
                size_bytes=file_size
            )

        except Exception:
            return None

    def analyze(self, file_path: str) -> ProcessingResult:
        """Analyze WAV file - core functionality with enhanced security and error handling."""
        self.perf.start()

        try:
            # Enhanced security checks
            if not SecurityValidator.validate_path(file_path):
                return ProcessingResult(False, "Invalid file path - security violation")

            if not SecurityValidator.validate_file_size(file_path):
                return ProcessingResult(False, "File too large or empty")

            if not SecurityValidator.validate_audio_content(file_path):
                return ProcessingResult(False, "Invalid or corrupted WAV file")

            # Check if file exists and is readable
            if not os.path.exists(file_path):
                return ProcessingResult(False, "File does not exist")

            if not os.access(file_path, os.R_OK):
                return ProcessingResult(False, "File is not readable")

            info = self._read_wav_header_optimized(file_path)
            if info:
                # Calculate audio metrics with memory protection
                try:
                    info.peak_level, info.rms_level = self._calculate_levels_safe(file_path, info)
                except Exception as calc_error:
                    self.logger.warning(f"Level calculation failed: {calc_error}")
                    # Continue without level info rather than failing completely

                duration_ms = self.perf.end("analyze")
                return ProcessingResult(
                    True,
                    f"Analysis complete in {duration_ms}ms",
                    info,
                    duration_ms
                )
            else:
                return ProcessingResult(False, "Invalid WAV file format")

        except PermissionError:
            return ProcessingResult(False, "Permission denied accessing file")
        except OSError as e:
            return ProcessingResult(False, f"File system error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            return ProcessingResult(False, f"Analysis failed: {str(e)}")

    def normalize(self, input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
        """Normalize audio - essential operation with enhanced security."""
        self.perf.start()

        # Enhanced security checks
        if not SecurityValidator.validate_path(input_path):
            return ProcessingResult(False, "Invalid input path")

        if not SecurityValidator.validate_path(output_path):
            return ProcessingResult(False, "Invalid output path")

        if target_peak <= 0 or target_peak > 1.0:
            return ProcessingResult(False, "Invalid target peak (0-1.0)")

        try:
            if not SecurityValidator.validate_file_size(input_path):
                return ProcessingResult(False, "Input file too large or empty")

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Read WAV file
            info = self._read_wav_header(input_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file")

            # Validate audio content
            if not SecurityValidator.validate_audio_content(input_path):
                return ProcessingResult(False, "Corrupted audio file")

            # Calculate current peak with memory protection
            current_peak, _ = self._calculate_levels_safe(input_path, info)
            if current_peak == 0:
                return ProcessingResult(False, "No audio signal found")

            # Calculate gain
            gain = target_peak / current_peak

            # Process audio with security checks
            self._apply_gain_safe(input_path, output_path, info, gain)

            duration_ms = self.perf.end("normalize")
            return ProcessingResult(
                True,
                f"Normalized to {target_peak:.2f} peak in {duration_ms}ms",
                {"gain_applied": gain, "target_peak": target_peak},
                duration_ms
            )

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            return ProcessingResult(False, f"Normalization failed: {str(e)}")

    def convert_to_mono(self, input_path: str, output_path: str) -> ProcessingResult:
        """Convert stereo to mono - practical utility."""
        self.perf.start()

        if not SecurityValidator.validate_path(input_path):
            return ProcessingResult(False, "Invalid input path")

        try:
            info = self._read_wav_header(input_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file")

            if info.channels == 1:
                return ProcessingResult(False, "Already mono")

            self._convert_to_mono(input_path, output_path, info)

            duration_ms = self.perf.end("convert_to_mono")
            return ProcessingResult(
                True,
                f"Converted to mono in {duration_ms}ms",
                {"original_channels": info.channels},
                duration_ms
            )

        except Exception as e:
            self.logger.error(f"Mono conversion failed: {e}")
            return ProcessingResult(False, f"Mono conversion failed: {str(e)}")

    def trim_silence(self, input_path: str, output_path: str, threshold: float = 0.01) -> ProcessingResult:
        """Trim silence - practical utility."""
        self.perf.start()

        if not SecurityValidator.validate_path(input_path):
            return ProcessingResult(False, "Invalid input path")

        if not SecurityValidator.validate_path(output_path):
            return ProcessingResult(False, "Invalid output path")

        if threshold <= 0 or threshold >= 1.0:
            return ProcessingResult(False, "Invalid threshold (0.01-0.99)")

        if not SecurityValidator.validate_file_size(input_path):
            return ProcessingResult(False, "Input file too large or empty")

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            info = self._read_wav_header(input_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file")

            if not SecurityValidator.validate_audio_content(input_path):
                return ProcessingResult(False, "Corrupted audio file")

            start_sample, end_sample = self._find_audio_boundaries(input_path, info, threshold)

            if start_sample >= end_sample:
                return ProcessingResult(False, "No audio content found above threshold")

            self._extract_audio_range(input_path, output_path, info, start_sample, end_sample)

            original_duration = info.duration
            new_duration = (end_sample - start_sample) / info.sample_rate

            duration_ms = self.perf.end("trim_silence")
            return ProcessingResult(
                True,
                f"Trimmed {original_duration - new_duration:.2f}s of silence in {duration_ms}ms",
                {
                    "original_duration": original_duration,
                    "new_duration": new_duration,
                    "removed_seconds": original_duration - new_duration
                },
                duration_ms
            )

        except Exception as e:
            self.logger.error(f"Silence trimming failed: {e}")
            return ProcessingResult(False, f"Silence trimming failed: {str(e)}")

    def _read_wav_header(self, file_path: str) -> Optional[AudioInfo]:
        """Read WAV header efficiently - cached for performance."""
        try:
            with open(file_path, 'rb') as f:
                # Read RIFF header
                riff_header = f.read(12)
                if len(riff_header) != 12 or riff_header[:4] != b'RIFF' or riff_header[8:12] != b'WAVE':
                    return None

                file_size = struct.unpack('<I', riff_header[4:8])[0] + 8

                # Find fmt chunk
                while True:
                    chunk_header = f.read(8)
                    if len(chunk_header) != 8:
                        return None

                    chunk_id = chunk_header[:4]
                    chunk_size = struct.unpack('<I', chunk_header[4:8])[0]

                    if chunk_id == b'fmt ':
                        # Read format chunk
                        fmt_data = f.read(chunk_size)
                        if len(fmt_data) < 16:
                            return None

                        format_tag, channels, sample_rate, byte_rate, block_align, bits_per_sample = \
                            struct.unpack('<HHIIHH', fmt_data[:16])

                        if format_tag != 1:  # Only PCM
                            return None

                        # Find data chunk
                        while True:
                            data_header = f.read(8)
                            if len(data_header) != 8:
                                return None

                            data_id = data_header[:4]
                            data_size = struct.unpack('<I', data_header[4:8])[0]

                            if data_id == b'data':
                                duration = data_size / (sample_rate * channels * (bits_per_sample // 8))

                                return AudioInfo(
                                    duration=duration,
                                    sample_rate=sample_rate,
                                    channels=channels,
                                    bit_depth=bits_per_sample,
                                    size_bytes=file_size
                                )
                            else:
                                # Skip non-data chunk
                                f.seek(data_size, 1)
                    else:
                        # Skip non-fmt chunk
                        f.seek(chunk_size, 1)

        except Exception:
            return None


    def _calculate_levels_safe(self, file_path: str, info: AudioInfo) -> Tuple[float, float]:
        """Calculate peak and RMS levels with enhanced bit depth support and memory protection."""
        try:
            with open(file_path, 'rb') as f:
                # Skip to data chunk safely
                f.seek(44)  # Standard WAV header size

                max_val = 0.0
                sum_squares = 0.0
                sample_count = 0
                max_samples = 1000000  # Limit per-channel samples for safety

                bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
                frame_size = bytes_per_sample * max(1, info.channels)

                if frame_size == 0:
                    return 0.0, 0.0

                while sample_count < max_samples:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    available = (len(chunk) // frame_size) * frame_size
                    if available == 0:
                        continue

                    mv = memoryview(chunk[:available])
                    for frame_offset in range(0, available, frame_size):
                        for channel in range(info.channels):
                            if sample_count >= max_samples:
                                break
                            sample_offset = frame_offset + channel * bytes_per_sample
                            sample_bytes = mv[sample_offset:sample_offset + bytes_per_sample].tobytes()
                            sample_value = self._decode_sample_bytes(sample_bytes, info.bit_depth)
                            if sample_value is None:
                                continue
                            normalized_sample = self._normalize_amplitude(sample_value, info.bit_depth)
                            max_val = max(max_val, normalized_sample)
                            sum_squares += normalized_sample * normalized_sample
                            sample_count += 1

                    del mv

                if sample_count == 0:
                    return 0.0, 0.0

                rms = (sum_squares / sample_count) ** 0.5
                return max_val, rms

        except Exception:
            return 0.0, 0.0

    def _apply_gain_safe(self, input_path: str, output_path: str, info: AudioInfo, gain: float):
        """Apply gain to audio file with enhanced bit depth support and security."""
        with open(input_path, 'rb') as src, open_secure(output_path, 'wb') as dst:
            # Copy header safely
            header = src.read(44)  # Standard WAV header
            if len(header) != 44:
                raise ValueError("Invalid WAV header")

            dst.write(header)

            bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
            frame_size = bytes_per_sample * max(1, info.channels)
            processed_samples = 0
            max_samples = 10000000  # Safety limit per-channel

            if frame_size == 0:
                raise ValueError("Invalid audio format")

            while processed_samples < max_samples:
                chunk = src.read(CHUNK_SIZE)
                if not chunk:
                    break

                available = (len(chunk) // frame_size) * frame_size
                if available == 0:
                    continue

                mv = memoryview(chunk[:available])
                processed_chunk = bytearray()

                for frame_offset in range(0, available, frame_size):
                    for channel in range(info.channels):
                        sample_offset = frame_offset + channel * bytes_per_sample
                        sample_bytes = mv[sample_offset:sample_offset + bytes_per_sample].tobytes()
                        sample_value = self._decode_sample_bytes(sample_bytes, info.bit_depth)

                        if sample_value is None:
                            processed_chunk.extend(sample_bytes)
                        else:
                            new_sample = int(sample_value * gain)
                            processed_chunk.extend(self._encode_sample_value(new_sample, info.bit_depth))

                        processed_samples += 1
                        if processed_samples >= max_samples:
                            raise ValueError("Too many samples processed - possible corruption")

                if processed_chunk:
                    dst.write(processed_chunk)

                if available < len(chunk):
                    dst.write(chunk[available:])

                del mv

    def _convert_to_mono(self, input_path: str, output_path: str, info: AudioInfo):
        """Convert stereo/multi-channel to mono."""
        with open(input_path, 'rb') as src, open_secure(output_path, 'wb') as dst:
            # Read and modify header
            header = bytearray(src.read(44))

            # Update channels to 1
            struct.pack_into('<H', header, 22, 1)

            # Update byte rate and block align
            byte_rate = info.sample_rate * (info.bit_depth // 8)
            block_align = info.bit_depth // 8
            struct.pack_into('<I', header, 28, byte_rate)
            struct.pack_into('<H', header, 32, block_align)

            # Update data chunk size
            original_data_size = struct.unpack('<I', header[40:44])[0]
            new_data_size = original_data_size // info.channels
            struct.pack_into('<I', header, 40, new_data_size)

            # Update file size
            file_size = struct.unpack('<I', header[4:8])[0]
            new_file_size = file_size - original_data_size + new_data_size
            struct.pack_into('<I', header, 4, new_file_size)

            dst.write(header)

            bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
            frame_size = bytes_per_sample * max(1, info.channels)

            if frame_size == 0:
                raise ValueError("Invalid audio format")

            while True:
                chunk = src.read(CHUNK_SIZE)
                if not chunk:
                    break

                available = (len(chunk) // frame_size) * frame_size
                if available == 0:
                    continue

                mv = memoryview(chunk[:available])
                mono_chunk = bytearray()

                for frame_offset in range(0, available, frame_size):
                    samples: List[int] = []
                    for channel in range(info.channels):
                        sample_offset = frame_offset + channel * bytes_per_sample
                        sample_bytes = mv[sample_offset:sample_offset + bytes_per_sample].tobytes()
                        sample_value = self._decode_sample_bytes(sample_bytes, info.bit_depth)
                        if sample_value is None:
                            samples = []
                            break
                        samples.append(sample_value)

                    if not samples:
                        mono_chunk.extend(mv[frame_offset:frame_offset + bytes_per_sample].tobytes())
                        continue

                    avg_sample = int(sum(samples) / len(samples))
                    mono_chunk.extend(self._encode_sample_value(avg_sample, info.bit_depth))

                if mono_chunk:
                    dst.write(mono_chunk)

                if available < len(chunk):
                    dst.write(chunk[available:])

                del mv

    def _find_audio_boundaries(self, file_path: str, info: AudioInfo, threshold: float) -> Tuple[int, int]:
        """Find start and end of audio content above threshold."""
        start_sample = 0
        end_sample = int(info.duration * info.sample_rate)

        try:
            with open(file_path, 'rb') as f:
                f.seek(44)  # Skip header

                bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
                frame_size = bytes_per_sample * max(1, info.channels)
                sample_index = 0
                found_start = False
                last_audio_sample = 0

                if frame_size == 0:
                    return 0, 0

                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    available = (len(chunk) // frame_size) * frame_size
                    if available == 0:
                        continue

                    mv = memoryview(chunk[:available])
                    for frame_offset in range(0, available, frame_size):
                        frame_peak = 0.0
                        for channel in range(info.channels):
                            sample_offset = frame_offset + channel * bytes_per_sample
                            sample_bytes = mv[sample_offset:sample_offset + bytes_per_sample].tobytes()
                            sample_value = self._decode_sample_bytes(sample_bytes, info.bit_depth)
                            if sample_value is None:
                                continue
                            frame_peak = max(frame_peak, self._normalize_amplitude(sample_value, info.bit_depth))

                        if frame_peak >= threshold:
                            if not found_start:
                                start_sample = sample_index
                                found_start = True
                            last_audio_sample = sample_index

                        sample_index += 1

                    del mv

                if found_start:
                    end_sample = last_audio_sample + 1
                else:
                    start_sample = end_sample = 0

        except Exception:
            pass

        return start_sample, end_sample

    def _extract_audio_range(self, input_path: str, output_path: str, info: AudioInfo, start_sample: int, end_sample: int):
        """Extract specific sample range from audio file."""
        with open(input_path, 'rb') as src, open_secure(output_path, 'wb') as dst:
            # Read and modify header
            header = bytearray(src.read(44))

            bytes_per_sample = info.bit_depth // 8
            sample_count = end_sample - start_sample
            new_data_size = sample_count * info.channels * bytes_per_sample
            new_duration = sample_count / info.sample_rate

            original_data_size = struct.unpack('<I', header[40:44])[0]

            # Update data chunk size
            struct.pack_into('<I', header, 40, new_data_size)

            # Update file size
            file_size = struct.unpack('<I', header[4:8])[0]
            new_file_size = file_size - original_data_size + new_data_size
            struct.pack_into('<I', header, 4, new_file_size)

            dst.write(header)

            # Seek to start position
            start_byte = start_sample * info.channels * bytes_per_sample
            src.seek(44 + start_byte)

            # Copy audio data
            bytes_to_copy = new_data_size
            while bytes_to_copy > 0:
                chunk_size = min(CHUNK_SIZE, bytes_to_copy)
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
                bytes_to_copy -= len(chunk)

class RecoveryManager:
    """Automatic recovery handler for essential operations."""

    def __init__(self, max_attempts: int = 3, base_delay: float = 0.5) -> None:
        self.max_attempts = max(1, max_attempts)
        self.base_delay = max(0.0, base_delay)
        self.logger = logging.getLogger(__name__)
        self.metrics: Dict[str, int] = {
            "total_attempts": 0,
            "total_retries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "memory_errors": 0,
            "os_errors": 0,
        }

    def execute(self, operation: str, func: Callable[[], Any]) -> Tuple[Any, int]:
        last_error: Optional[BaseException] = None

        for attempt in range(1, self.max_attempts + 1):
            self.metrics["total_attempts"] += 1
            try:
                result = func()
                if attempt > 1:
                    self.logger.info(
                        "Recovered operation '%s' on attempt %d/%d",
                        operation,
                        attempt,
                        self.max_attempts,
                    )
                    self.metrics["successful_recoveries"] += 1
                return result, attempt
            except MemoryError as error:
                last_error = error
                self.metrics["memory_errors"] += 1
                if attempt == self.max_attempts:
                    self.metrics["failed_recoveries"] += 1
                    raise
                self._handle_memory_error(operation, attempt)
                self.metrics["total_retries"] += 1
            except OSError as error:
                last_error = error
                self.metrics["os_errors"] += 1
                if attempt == self.max_attempts:
                    self.metrics["failed_recoveries"] += 1
                    raise
                self._handle_os_error(operation, attempt, error)
                self.metrics["total_retries"] += 1

        if last_error:
            self.metrics["failed_recoveries"] += 1
            raise last_error
        raise RuntimeError(f"Recovery attempts exhausted for operation '{operation}'")

    def _handle_memory_error(self, operation: str, attempt: int) -> None:
        gc.collect()
        delay = min(self.base_delay * attempt, 5.0)
        self.logger.warning(
            "Memory pressure during '%s'; retrying attempt %d after %.2fs",
            operation,
            attempt + 1,
            delay,
        )
        time.sleep(delay)

    def _handle_os_error(self, operation: str, attempt: int, error: OSError) -> None:
        message = str(error).lower()
        delay = self.base_delay * max(1, attempt)

        if "disk" in message or "space" in message:
            self._cleanup_temp_files()
            delay *= 2
        elif "permission" in message:
            delay *= 1.5

        delay = min(delay, 5.0)
        self.logger.warning(
            "OS error during '%s' (%s); retrying attempt %d after %.2fs",
            operation,
            error,
            attempt + 1,
            delay,
        )
        time.sleep(delay)

    def _cleanup_temp_files(self) -> None:
        temp_root = Path(tempfile.gettempdir())
        for candidate in temp_root.glob("chameleon_*"):
            try:
                if candidate.is_file():
                    candidate.unlink()
                elif candidate.is_dir():
                    for child in candidate.glob("**/*"):
                        if child.is_file():
                            try:
                                child.unlink()
                            except OSError:
                                continue
                    try:
                        candidate.rmdir()
                    except OSError:
                        continue
            except OSError:
                continue

    def export_metrics(self) -> Dict[str, int]:
        return dict(self.metrics)

    def reset_metrics(self) -> None:
        for key in self.metrics:
            self.metrics[key] = 0


class ErrorAnalyzer:
    """Diagnose common failure patterns to aid recovery and reporting."""

    ROOT_CAUSE_MAP = {
        MemoryError: ("insufficient_memory", "critical"),
        TimeoutError: ("operation_timeout", "high"),
    }

    def analyze(self, error: BaseException, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        root_cause, severity = self._determine_root_cause(error)
        recovery_hint = self._suggest_recovery(root_cause)

        return {
            "error_type": type(error).__name__,
            "message": str(error),
            "root_cause": root_cause,
            "severity": severity,
            "context": context,
            "recovery_hint": recovery_hint,
        }

    def _determine_root_cause(self, error: BaseException) -> Tuple[str, str]:
        for exc_type, (cause, severity) in self.ROOT_CAUSE_MAP.items():
            if isinstance(error, exc_type):
                return cause, severity

        if isinstance(error, OSError):
            message = str(error).lower()
            if "permission" in message:
                return "permission_denied", "high"
            if "disk" in message or "space" in message:
                return "disk_space_exhausted", "critical"
            return "io_error", "medium"

        return "unknown_error", "medium"

    def _suggest_recovery(self, root_cause: str) -> str:
        hints = {
            "insufficient_memory": "Reduce batch size or close other applications before retrying.",
            "operation_timeout": "Increase timeout or check system load before re-running.",
            "permission_denied": "Verify directory permissions for the current user.",
            "disk_space_exhausted": "Free disk space or update output directory to a larger volume.",
            "io_error": "Re-run after verifying storage availability and health.",
        }
        return hints.get(root_cause, "Review logs for additional context and retry.")


class ServiceDegradationManager:
    """Adjust service level based on error severity and timeout conditions."""

    LEVEL_ORDER = ("full", "degraded", "basic", "minimal")

    def __init__(self) -> None:
        self.current_level = "full"

    def evaluate(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        target_level = self.current_level
        reasons: List[str] = []

        processed = summary.get("processed", 0)
        failed = summary.get("failed", 0)
        errors = summary.get("errors", []) or []
        timed_out = bool(summary.get("timed_out"))

        failure_rate = (failed / processed) if processed else 0.0
        has_critical = any(err.get("severity") in {"high", "critical"} for err in errors)

        if timed_out:
            target_level = self._worst_level(target_level, "basic")
            reasons.append("timeout")

        if has_critical:
            target_level = self._worst_level(target_level, "basic")
            reasons.append("high_severity_errors")

        if failure_rate >= 0.5:
            target_level = self._worst_level(target_level, "minimal")
            reasons.append("high_failure_rate")
        elif failure_rate >= 0.2:
            target_level = self._worst_level(target_level, "basic")
            reasons.append("elevated_failure_rate")

        if not timed_out and failed == 0 and not errors:
            # Promote service level towards full on clean runs
            target_level = self._best_level(target_level, "full")
            reasons.append("stabilised")

        changed = target_level != self.current_level
        previous_level = self.current_level
        if changed:
            self.current_level = target_level

        return {
            "current_level": self.current_level,
            "previous_level": previous_level,
            "changed": changed,
            "reasons": reasons,
        }

    def _worst_level(self, current: str, candidate: str) -> str:
        return self.LEVEL_ORDER[max(self.LEVEL_ORDER.index(current), self.LEVEL_ORDER.index(candidate))]

    def _best_level(self, current: str, candidate: str) -> str:
        return self.LEVEL_ORDER[min(self.LEVEL_ORDER.index(current), self.LEVEL_ORDER.index(candidate))]


class StateRecoveryManager:
    """Persist batch state snapshots for recovery and diagnostics."""

    def __init__(self, state_dir: Optional[Union[str, Path]] = None, max_backups: int = 10) -> None:
        candidate = state_dir or os.getenv("CHAMELEON_STATE_DIR")
        if candidate:
            self.state_dir = Path(candidate)
        else:
            self.state_dir = Path.home() / ".chameleon_state"

        self.max_backups = max(1, max_backups)
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            fallback = Path(tempfile.gettempdir()) / "chameleon_state"
            fallback.mkdir(parents=True, exist_ok=True)
            self.state_dir = fallback

    def load_last_state(self) -> Optional[Dict[str, Any]]:
        try:
            candidates = sorted(self.state_dir.glob("batch_state_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        except OSError:
            return None

        for file_path in candidates:
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
        return None

    def record_state(self, summary: Dict[str, Any]) -> Optional[Path]:
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        target_path = self.state_dir / f"batch_state_{timestamp}.json"
        payload = {
            "timestamp": timestamp,
            "summary": summary,
        }

        try:
            with target_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError:
            return None

        self._cleanup_old_backups()
        return target_path

    def _cleanup_old_backups(self) -> None:
        try:
            candidates = sorted(self.state_dir.glob("batch_state_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        except OSError:
            return

        for index, file_path in enumerate(candidates, 1):
            if index > self.max_backups:
                try:
                    file_path.unlink()
                except OSError:
                    continue


class BatchProcessor:
    """Lightweight batch processing - practical automation."""

    def __init__(self):
        self.processor = WAVProcessor()
        self.results = []
        self.recovery = RecoveryManager()
        self.error_analyzer = ErrorAnalyzer()
        self.degradation = ServiceDegradationManager()
        self.state_manager = StateRecoveryManager()

    def process_directory(self, directory: str, operation: str, **kwargs) -> List[ProcessingResult]:
        """Process all WAV files in directory."""
        if not SecurityValidator.validate_directory(directory):
            return [ProcessingResult(False, "Invalid directory provided")]

        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return [ProcessingResult(False, "Directory not found")]

        operation_normalized = (operation or "").strip().lower()
        if operation_normalized not in ALLOWED_BATCH_OPERATIONS:
            return [ProcessingResult(False, f"Unsupported operation: {operation}")]

        output_dir = kwargs.get("output_dir")
        target_dir = None
        if output_dir:
            if not SecurityValidator.validate_directory(output_dir):
                return [ProcessingResult(False, "Invalid output directory provided")]
            target_dir = Path(output_dir)
            parent = target_dir.resolve().parent
            if not parent.exists() or not parent.is_dir():
                return [ProcessingResult(False, "Parent directory for output is invalid")]
            target_dir.mkdir(parents=True, exist_ok=True)

        target_peak = kwargs.get("target_peak")
        if target_peak is not None:
            try:
                target_peak = float(target_peak)
            except (TypeError, ValueError):
                return [ProcessingResult(False, "target_peak must be numeric")]
            if not 0.0 <= target_peak <= 1.0:
                return [ProcessingResult(False, "target_peak must be between 0.0 and 1.0")]

        threshold = kwargs.get("threshold")
        if threshold is not None:
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                return [ProcessingResult(False, "threshold must be numeric")]
            if not 0.0 <= threshold <= 1.0:
                return [ProcessingResult(False, "threshold must be between 0.0 and 1.0")]

        skip_errors = kwargs.get("skip_errors", False)
        max_files = kwargs.get("max_files")
        recursive = kwargs.get("recursive", True)
        progress_callback = kwargs.get("progress_callback")

        self.recovery.reset_metrics()
        wav_files: List[Path] = []

        pattern = "**/*.wav" if recursive else "*.wav"
        for candidate in path.glob(pattern):
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_FORMATS:
                try:
                    if candidate.is_symlink():
                        continue
                except OSError:
                    continue
                wav_files.append(candidate)
                if isinstance(max_files, int) and max_files > 0 and len(wav_files) >= max_files:
                    break

        if not wav_files:
            return [ProcessingResult(False, "No WAV files found")]

        results: List[ProcessingResult] = []
        start_time = time.perf_counter()
        timeout_seconds = OPERATION_TIMEOUT
        deadline = start_time + timeout_seconds if timeout_seconds else None
        previous_state = self.state_manager.load_last_state()

        summary = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "operation": operation_normalized,
            "retries": 0,
            "errors": [],
            "timed_out": False,
            "service_level": self.degradation.current_level,
            "previous_state": previous_state,
        }

        for index, file_path in enumerate(wav_files, 1):
            try:
                operation_options = dict(kwargs)
                if target_dir is not None:
                    operation_options["output_dir"] = str(target_dir)
                else:
                    operation_options.pop("output_dir", None)

                if target_peak is not None:
                    operation_options["target_peak"] = target_peak
                else:
                    operation_options.pop("target_peak", None)

                if threshold is not None:
                    operation_options["threshold"] = threshold
                else:
                    operation_options.pop("threshold", None)

                result, attempts = self._execute_operation(
                    operation_normalized,
                    file_path,
                    operation_options,
                )

            except Exception as error:
                sanitized_message = self._format_public_error(Path(file_path), error)
                result = ProcessingResult(False, sanitized_message)
                attempts = 1
                analysis = self.error_analyzer.analyze(
                    error,
                    {"file": str(file_path), "operation": operation}
                )
                analysis["message"] = self._sanitize_message(analysis.get("message", ""), Path(file_path))
                result.data = {
                    "file": str(file_path),
                    "operation": operation,
                    "analysis": analysis,
                }
                summary["errors"].append(analysis)

            if result.message:
                result.message = self._sanitize_message(result.message, Path(file_path))

            if "analysis" not in result.data:
                result.data = {
                    "file": str(file_path),
                    "original_data": result.data,
                    "operation": operation,
                    "attempts": attempts,
                }
            else:
                result.data["attempts"] = attempts
            results.append(result)

            summary["processed"] += 1
            if result.success:
                summary["successful"] += 1
                if attempts > 1:
                    summary["retries"] += attempts - 1
            else:
                summary["failed"] += 1
                if "analysis" in result.data:
                    summary["errors"].append(result.data["analysis"])
                if not skip_errors:
                    break
            if progress_callback:
                try:
                    progress_callback(index, len(wav_files), str(file_path), result)
                except Exception:
                    pass

            if deadline and time.perf_counter() >= deadline:
                summary["timed_out"] = True
                break

        if summary["processed"] < len(wav_files):
            summary["skipped"] = len(wav_files) - summary["processed"]

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        summary["duration_ms"] = duration_ms

        recovery_metrics = self.recovery.export_metrics()
        summary["recovery_metrics"] = recovery_metrics

        try:
            metrics_payload = json.dumps(recovery_metrics, sort_keys=True)
        except TypeError:
            metrics_payload = str(recovery_metrics)

        if recovery_metrics.get("total_retries") or recovery_metrics.get("failed_recoveries"):
            self.recovery.logger.info(
                "Recovery summary for '%s': %s",
                operation,
                metrics_payload,
            )
        else:
            self.recovery.logger.debug(
                "Recovery summary for '%s': %s",
                operation,
                metrics_payload,
            )

        summary_message = (
            f"Batch processed {summary['processed']} file(s) in {duration_ms}ms: "
            f"{summary['successful']} succeeded, {summary['failed']} failed, "
            f"retries: {summary['retries']}"
        )
        if summary["timed_out"]:
            summary_message += f", timed out after {timeout_seconds}s"
        if recovery_metrics.get("total_retries", 0):
            summary_message += f", recovery retries: {recovery_metrics['total_retries']}"

        degradation_info = self.degradation.evaluate(summary)
        summary["service_level"] = degradation_info["current_level"]
        summary["service_transition"] = degradation_info
        if degradation_info["changed"]:
            summary_message += (
                f", service level: {degradation_info['previous_level']} → "
                f"{degradation_info['current_level']}"
            )
        else:
            summary_message += f", service level: {summary['service_level']}"

        state_path: Optional[Path] = None
        try:
            state_path = self.state_manager.record_state(summary)
        except Exception:
            state_path = None

        if state_path:
            summary["state_recorded"] = True
            summary["state_path"] = str(state_path)
            summary_message += f", state saved: {state_path}"
        else:
            summary["state_recorded"] = False

        results.append(
            ProcessingResult(
                summary["failed"] == 0 and not summary["timed_out"],
                summary_message,
                {"summary": summary},
                duration_ms,
            )
        )

        self.processor.perf.record_operation("batch_process", duration_ms)

        return results

    def _execute_operation(self, operation: str, file_path: Path, options: Dict[str, Any]) -> Tuple[ProcessingResult, int]:
        def run_operation() -> ProcessingResult:
            if operation == "analyze":
                return self.processor.analyze(str(file_path))

            output_root = options.get("output_dir")
            if output_root:
                output_path = Path(output_root)
                output_path.mkdir(parents=True, exist_ok=True)
            else:
                output_path = file_path.parent

            if operation == "normalize":
                target_peak = options.get("target_peak", 0.95)
                return self.processor.normalize(
                    str(file_path),
                    str(Path(output_path) / f"normalized_{file_path.name}"),
                    target_peak,
                )

            if operation == "mono":
                return self.processor.convert_to_mono(
                    str(file_path),
                    str(Path(output_path) / f"mono_{file_path.name}"),
                )

            if operation == "trim":
                threshold = options.get("threshold", 0.01)
                return self.processor.trim_silence(
                    str(file_path),
                    str(Path(output_path) / f"trimmed_{file_path.name}"),
                    threshold,
                )

            return ProcessingResult(False, f"Unknown operation: {operation}")

        return self.recovery.execute(operation, run_operation)

    @staticmethod
    def _sanitize_message(message: str, file_path: Path) -> str:
        sanitized = message or ""
        raw_path = str(file_path)
        if raw_path:
            sanitized = sanitized.replace(raw_path, file_path.name)
        try:
            resolved = str(file_path.resolve())
        except OSError:
            resolved = None
        if resolved:
            sanitized = sanitized.replace(resolved, file_path.name)
        cwd = os.getcwd()
        if cwd:
            sanitized = sanitized.replace(cwd, "<cwd>")
        return sanitized

    def _format_public_error(self, file_path: Path, error: BaseException) -> str:
        error_type = type(error).__name__
        sanitized_message = self._sanitize_message(str(error), file_path)
        if sanitized_message and sanitized_message != str(error):
            error_detail = sanitized_message
        else:
            error_detail = error_type
        return f"Error processing {file_path.name}: {error_detail}"

class SimpleLogger:
    """Minimal logging - just what's needed."""

    def __init__(self, level: str = "INFO"):
        self.level = level.upper()
        self.levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        self.current_level = self.levels.get(self.level, 1)

    def _log(self, level: str, message: str):
        if self.levels.get(level, 1) >= self.current_level:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")

    def debug(self, message: str):
        self._log("DEBUG", message)

    def info(self, message: str):
        self._log("INFO", message)

    def warning(self, message: str):
        self._log("WARNING", message)

    def error(self, message: str):
        self._log("ERROR", message)

# Global instances - simple and efficient
_processor = WAVProcessor()
_batch_processor = BatchProcessor()
_logger = SimpleLogger()

def analyze(file_path: str) -> ProcessingResult:
    """Analyze WAV file - main API."""
    return _processor.analyze(file_path)

def normalize(input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
    """Normalize audio - main API."""
    return _processor.normalize(input_path, output_path, target_peak)

def to_mono(input_path: str, output_path: str) -> ProcessingResult:
    """Convert to mono - main API."""
    return _processor.convert_to_mono(input_path, output_path)

def trim_silence(input_path: str, output_path: str, threshold: float = 0.01) -> ProcessingResult:
    """Trim silence - main API."""
    return _processor.trim_silence(input_path, output_path, threshold)

def batch_process(directory: str, operation: str, **kwargs) -> List[ProcessingResult]:
    """Process directory - main API."""
    return _batch_processor.process_directory(directory, operation, **kwargs)

def get_performance_stats() -> Dict[str, int]:
    """Get performance statistics."""
    return _processor.perf.get_stats()


def record_operation(operation: str, duration_ms: int) -> None:
    """Expose performance tracker recording for auxiliary modules."""
    _processor.perf.record_operation(operation, duration_ms)

if __name__ == "__main__":
    # Simple CLI interface
    import sys

    if len(sys.argv) < 2:
        print(f"Chameleon Core {VERSION}")
        print("Usage:")
        print("  python core.py analyze <file.wav>")
        print("  python core.py normalize <input.wav> <output.wav> [peak]")
        print("  python core.py mono <input.wav> <output.wav>")
        print("  python core.py trim <input.wav> <output.wav> [threshold]")
        print("  python core.py batch <directory> <operation>")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "analyze" and len(sys.argv) >= 3:
        result = analyze(sys.argv[2])
        if result.success:
            info = result.data
            print(f"Duration: {info.duration:.2f}s")
            print(f"Sample Rate: {info.sample_rate}Hz")
            print(f"Channels: {info.channels}")
            print(f"Bit Depth: {info.bit_depth}")
            print(f"Peak Level: {info.peak_level:.3f}")
            print(f"RMS Level: {info.rms_level:.3f}")
            print(f"File Size: {info.size_bytes:,} bytes")
        else:
            print(f"Error: {result.message}")

    elif command == "normalize" and len(sys.argv) >= 4:
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        peak = float(sys.argv[4]) if len(sys.argv) > 4 else 0.95

        result = normalize(input_file, output_file, peak)
        print(f"Result: {result.message}")
        if result.success and result.data:
            print(f"Gain applied: {result.data['gain_applied']:.2f}x")

    elif command == "mono" and len(sys.argv) >= 4:
        result = to_mono(sys.argv[2], sys.argv[3])
        print(f"Result: {result.message}")

    elif command == "trim" and len(sys.argv) >= 4:
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.01

        result = trim_silence(input_file, output_file, threshold)
        print(f"Result: {result.message}")
        if result.success and result.data:
            print(f"Removed: {result.data['removed_seconds']:.2f}s")

    elif command == "batch" and len(sys.argv) >= 4:
        directory = sys.argv[2]
        operation = sys.argv[3]

        results = batch_process(directory, operation)
        successful = sum(1 for r in results if r.success)
        total = len(results)
        print(f"Batch processing complete: {successful}/{total} successful")

        for result in results:
            if result.data and "file" in result.data:
                status = "✓" if result.success else "✗"
                print(f"  {status} {Path(result.data['file']).name}: {result.message}")

    else:
        print("Invalid command or missing arguments")
        sys.exit(1)

    # Show performance stats
    stats = get_performance_stats()
    if stats:
        print("\nPerformance:")
        for operation, duration_ms in stats.items():
            print(f"  {operation}: {duration_ms}ms")