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

from __future__ import annotations

import os
import sys
import time
import json
import datetime
import struct
import shutil
import hashlib
import secrets
import tempfile
import threading
import logging
import warnings
from logging.handlers import RotatingFileHandler
import argparse
import gc
from pathlib import Path
import asyncio
from typing import Awaitable, Union, Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass
from functools import lru_cache

from plugin_system import PluginManager, PluginConfig, PluginLoader, SecurityError
from security_validator import SecurityValidator, SecurityConfig

# Module logger. Previously sourced from a separate "advanced_logging" module
# that no longer exists; a standard logger keeps behaviour identical for the
# 170+ call sites below.
logger = logging.getLogger("chameleon")

# Deep file inspection (stdlib-only). Mirrors main.py's guard: validates that
# a file claiming a .wav extension is actually a WAV container before it
# enters the batch pipeline. See BatchProcessor.process_directory.
try:
    from advanced_validation import DeepFileInspector
    HAS_DEEP_INSPECTOR = True
except ImportError:
    HAS_DEEP_INSPECTOR = False

# Quantum computing features removed in 2024 refactor
# Using only practical, proven audio processing techniques
HAS_QUANTUM = False
HAS_QISKIT = False
HAS_PENNYLANE = False

VERSION = "1.0.0"
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
    """Essential audio information - no bloat.

    data_offset/data_size describe where the PCM payload actually lives —
    real-world WAVs carry LIST/JUNK/fact chunks before ``data``, so readers
    and writers must use these instead of assuming the classic 44-byte header.
    fmt_offset is the file offset of the fmt chunk *body* (the ``<HHIIHH``).
    """
    duration: float
    sample_rate: int
    channels: int
    bit_depth: int
    size_bytes: int
    peak_level: float = 0.0
    rms_level: float = 0.0
    data_offset: int = 44
    data_size: int = 0
    fmt_offset: int = 20
    format_tag: int = 1

@dataclass
class ProcessingResult:
    """Structured result returned by processing routines."""
    success: bool
    message: str
    data: Any = None
    duration_ms: int = 0


# Initialize the security validator with a default configuration
security_validator = SecurityValidator(SecurityConfig())


class MemoryManager:
    """Memory-efficient processing with caching and optimization."""

    def __init__(self):
        self.cache = {}
        self.cache_order = []  # For LRU tracking
        self.max_cache_size = 64 * 1024 * 1024  # 64MB cache
        self.current_cache_size = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.max_cache_items = 1000  # Prevent unbounded growth

        # パフォーマンス最適化のための新しいフィールド
        self.memory_pool = {}  # メモリプール管理
        self.vectorized_cache = {}  # ベクター化処理用キャッシュ
        self.chunk_pool = []  # チャンク再利用プール
        self.chunk_pool_size = 100  # プールサイズ制限

    def get_file_data(self, file_path: str, offset: int = 0, size: int = None) -> bytes:
        """Get file data with intelligent caching and memory mapping."""
        cache_key = f"{file_path}:{offset}:{size}"

        # Check cache first
        if cache_key in self.cache:
            self.cache_hits += 1
            # Move to end (most recently used)
            try:
                self.cache_order.remove(cache_key)
                self.cache_order.append(cache_key)
            except ValueError:
                pass
            return self.cache[cache_key]

        self.cache_misses += 1

        # サイズに基づいて最適な読み込み方法を選択
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

        # ベクター化処理用にデータを準備
        if size is not None and size <= 1024 * 1024:
            self._prepare_vectorized_data(data, cache_key)

        self.cache_data(cache_key, data)
        return data

    def _prepare_vectorized_data(self, data: bytes, cache_key: str):
        """ベクター化処理用にデータを準備"""
        try:
            if HAS_LIBROSA and len(data) >= 1024:
                # NumPy配列に変換してベクター化処理を準備
                import numpy as np

                # 16ビットPCMを想定してデータを変換
                if len(data) % 2 == 0:  # ステレオ16ビットの場合
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    # ベクター化処理の準備（実際の処理は後で実行）
                    self.vectorized_cache[cache_key] = {
                        'array': audio_array,
                        'ready': True,
                        'channels': 2 if len(audio_array) % 2 == 0 else 1
                    }
        except Exception:
            # ベクター化準備に失敗しても通常処理を継続
            pass

    def get_vectorized_audio(self, cache_key: str) -> Optional[np.ndarray]:
        """ベクター化されたオーディオデータを取得"""
        if cache_key in self.vectorized_cache:
            return self.vectorized_cache[cache_key]['array']
        return None

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
        """Cache data with LRU eviction and size management."""
        data_size = len(data)
        
        # Don't cache very large data
        if data_size > self.max_cache_size // 4:
            return
        
        # Remove existing entry if present
        if key in self.cache:
            self._remove_from_cache(key)
        
        # Make room for new data
        while (self.current_cache_size + data_size > self.max_cache_size or 
               len(self.cache) >= self.max_cache_items):
            if not self.cache_order:
                break
            oldest_key = self.cache_order.pop(0)
            self._remove_from_cache(oldest_key)
        
        # Add new entry
        self.cache[key] = data
        self.cache_order.append(key)
        self.current_cache_size += data_size

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': self.current_cache_size,
            'max_cache_size': self.max_cache_size,
            'cache_items': len(self.cache),
            'max_cache_items': self.max_cache_items,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
            'lru_order_size': len(self.cache_order)
        }

    def clear_cache(self):
        """Clear memory cache."""
        self.cache.clear()
        self.cache_order.clear()
        self.current_cache_size = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def _remove_from_cache(self, key: str):
        """Remove key from cache and update tracking."""
        if key in self.cache:
            data = self.cache.pop(key)
            self.current_cache_size -= len(data)
            # Remove from order list
            try:
                self.cache_order.remove(key)
            except ValueError:
                pass

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
    def _normalize_amplitude_signed(value: int, bit_depth: int) -> float:
        """Like _normalize_amplitude but preserves sign (waveform, not magnitude)."""
        if bit_depth <= 8:
            scale = 128.0
        else:
            scale = float(1 << (bit_depth - 1))
        if scale == 0:
            return 0.0
        normalized = value / scale
        return max(-1.0, min(1.0, normalized))

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
        """Read the WAV header via the canonical chunk-walking parser.

        Historically this read a fixed 44 bytes and assumed the data chunk
        started right after — wrong for any file with LIST/JUNK/fact chunks or
        a non-16-byte fmt body, which silently corrupted analysis. It now
        delegates to _read_wav_header, the single source of truth.
        """
        return self._read_wav_header(file_path)

    def analyze(self, file_path: str) -> ProcessingResult:
        """Analyze WAV file - core functionality with enhanced security and error handling."""
        self.perf.start()

        try:
            # Enhanced security checks
            if not security_validator.validate_path(file_path):
                return ProcessingResult(False, "Invalid file path - security violation")

            if not security_validator.validate_file_size(file_path):
                return ProcessingResult(False, "File too large or empty")

            if not security_validator.validate_audio_content(file_path):
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
    async def analyze_async(self, file_path: str) -> ProcessingResult:
        """Asynchronously analyze WAV file with enhanced performance and error handling."""
        start = time.perf_counter()
        try:
            # セキュリティチェックを非同期で実行
            security_check = await self._async_security_check(file_path)
            if not security_check:
                return ProcessingResult(False, "Security validation failed")

            # 非同期でファイル情報を取得
            info = await self._async_read_wav_header(file_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file format")

            # 非同期でレベル計算を実行
            peak_level, rms_level = await self._async_calculate_levels(file_path, info)

            duration_ms = int((time.perf_counter() - start) * 1000)
            return ProcessingResult(
                True,
                f"Asynchronous analysis complete in {duration_ms}ms",
                {
                    **info.__dict__,
                    "peak_level": peak_level,
                    "rms_level": rms_level
                },
                duration_ms
            )
        except Exception as e:
            return ProcessingResult(False, f"Analysis failed: {str(e)}")

    async def _async_security_check(self, file_path: str) -> bool:
        """非同期セキュリティチェックを実行"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, security_validator.validate_path, file_path)

    async def _async_read_wav_header(self, file_path: str) -> Optional[AudioInfo]:
        """非同期でWAVヘッダーを読み込み"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_wav_header_optimized, file_path)

    async def _async_calculate_levels(self, file_path: str, info: AudioInfo) -> Tuple[float, float]:
        """非同期でレベルを計算"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._calculate_levels_safe, file_path, info)

    async def normalize_async(self, input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
        """Asynchronously normalize audio file."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.normalize, input_path, output_path, target_peak)

    async def convert_to_mono_async(self, input_path: str, output_path: str) -> ProcessingResult:
        """Asynchronously convert to mono."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.convert_to_mono, input_path, output_path)

    async def trim_silence_async(self, input_path: str, output_path: str, threshold: float = 0.01) -> ProcessingResult:
        """Asynchronously trim silence."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.trim_silence, input_path, output_path, threshold)

    def normalize(self, input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
        """Normalize audio - essential operation with enhanced security."""
        self.perf.start()

        # Enhanced security checks
        if not security_validator.validate_path(input_path):
            return ProcessingResult(False, "Invalid input path")

        if not security_validator.validate_path(output_path):
            return ProcessingResult(False, "Invalid output path")

        if target_peak <= 0 or target_peak > 1.0:
            return ProcessingResult(False, "Invalid target peak (0-1.0)")

        try:
            if not security_validator.validate_file_size(input_path):
                return ProcessingResult(False, "Input file too large or empty")

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Read WAV file
            info = self._read_wav_header(input_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file")

            # Validate audio content
            if not security_validator.validate_audio_content(input_path):
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

        if not security_validator.validate_path(input_path):
            return ProcessingResult(False, "Invalid input path")

        try:
            info = self._read_wav_header(input_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file")

            if info.channels == 1:
                # Asking a mono file to be mono is a satisfied request, not a
                # failure. Reporting it as one made `--mono` non-idempotent:
                # a batch over mixed material printed "Error: Already mono",
                # wrote no output, and still exited 0 -- so a pipeline saw
                # success and then could not find the file. Copy it through
                # instead, so the output exists and means what it says.
                shutil.copyfile(input_path, output_path)
                duration_ms = self.perf.end("convert_to_mono")
                return ProcessingResult(
                    True,
                    f"Already mono; copied unchanged in {duration_ms}ms",
                    {"original_channels": 1, "already_mono": True},
                    duration_ms
                )

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

        if not security_validator.validate_path(input_path):
            return ProcessingResult(False, "Invalid input path")

        if not security_validator.validate_path(output_path):
            return ProcessingResult(False, "Invalid output path")

        if threshold <= 0 or threshold >= 1.0:
            return ProcessingResult(False, "Invalid threshold (0.01-0.99)")

        if not security_validator.validate_file_size(input_path):
            return ProcessingResult(False, "Input file too large or empty")

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            info = self._read_wav_header(input_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file")

            if not security_validator.validate_audio_content(input_path):
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

    # WAVE_FORMAT_EXTENSIBLE subformat GUIDs (little-endian on-disk layout).
    _PCM_SUBFORMAT_GUID = (b'\x01\x00\x00\x00\x00\x00\x10\x00'
                           b'\x80\x00\x00\xaa\x00\x38\x9b\x71')
    _FLOAT_SUBFORMAT_GUID = (b'\x03\x00\x00\x00\x00\x00\x10\x00'
                             b'\x80\x00\x00\xaa\x00\x38\x9b\x71')
    _MAX_WAV_CHUNKS = 256

    def _read_wav_header(self, file_path: str) -> Optional[AudioInfo]:
        """Canonical WAV parser: walks the chunk list instead of assuming the
        classic 44-byte layout.

        Handles fmt bodies of 16/18/40 bytes (including WAVE_FORMAT_EXTENSIBLE,
        whose PCM subformat GUID is treated as plain PCM), skips the RIFF pad
        byte after odd-sized chunks, clamps a lying data-size field to the real
        file size, and records data_offset/data_size/fmt_offset so downstream
        readers and writers stop hardcoding byte 44. PCM-only by design: float
        (tag 3) files are rejected cleanly rather than misdecoded.
        """
        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, 'rb') as f:
                riff_header = f.read(12)
                if len(riff_header) != 12 or riff_header[:4] != b'RIFF' or riff_header[8:12] != b'WAVE':
                    return None

                fmt_seen = False
                data_offset: Optional[int] = None
                data_size = 0
                fmt_offset = 20
                format_tag = channels = sample_rate = bits_per_sample = 0

                for _ in range(self._MAX_WAV_CHUNKS):
                    chunk_header = f.read(8)
                    if len(chunk_header) != 8:
                        break

                    chunk_id = chunk_header[:4]
                    chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
                    if chunk_size > file_size:
                        return None  # corrupt size field

                    if chunk_id == b'fmt ':
                        if chunk_size < 16:
                            return None
                        fmt_offset = f.tell()
                        body = f.read(min(chunk_size, 40))
                        if len(body) < 16:
                            return None
                        format_tag, channels, sample_rate, _byte_rate, _block_align, bits_per_sample = \
                            struct.unpack('<HHIIHH', body[:16])
                        if format_tag == 0xFFFE:
                            if len(body) < 40:
                                return None
                            guid = body[24:40]
                            if guid == self._PCM_SUBFORMAT_GUID:
                                format_tag = 1
                            elif guid == self._FLOAT_SUBFORMAT_GUID:
                                format_tag = 3
                            else:
                                return None
                        remaining = chunk_size - len(body)
                        if remaining > 0:
                            f.seek(remaining, 1)
                        fmt_seen = True
                    elif chunk_id == b'data':
                        data_offset = f.tell()
                        data_size = min(chunk_size, max(0, file_size - data_offset))
                        f.seek(data_size, 1)
                    else:
                        f.seek(chunk_size, 1)

                    if chunk_size % 2 == 1:
                        f.seek(1, 1)  # RIFF chunks are word-aligned

                    if fmt_seen and data_offset is not None:
                        break

                if not fmt_seen or data_offset is None:
                    return None
                if format_tag != 1:  # PCM-only core; float32 rejected cleanly
                    return None
                if channels <= 0 or bits_per_sample not in (8, 16, 24, 32) or sample_rate <= 0:
                    return None

                frame_size = channels * (bits_per_sample // 8)
                duration = data_size / (sample_rate * frame_size) if frame_size else 0.0

                return AudioInfo(
                    duration=duration,
                    sample_rate=sample_rate,
                    channels=channels,
                    bit_depth=bits_per_sample,
                    size_bytes=file_size,
                    data_offset=data_offset,
                    data_size=data_size,
                    fmt_offset=fmt_offset,
                    format_tag=format_tag,
                )

        except Exception:
            return None


    def _calculate_levels_safe(self, file_path: str, info: AudioInfo) -> Tuple[float, float]:
        """Calculate peak and RMS levels with enhanced bit depth support and memory protection."""
        try:
            with open(file_path, 'rb') as f:
                # Seek to the actual data payload (not a hardcoded byte 44).
                f.seek(info.data_offset)
                remaining = info.data_size

                max_val = 0.0
                sum_squares = 0.0
                sample_count = 0
                max_samples = 1000000  # Limit per-channel samples for safety

                bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
                frame_size = bytes_per_sample * max(1, info.channels)

                if frame_size == 0 or remaining <= 0:
                    return 0.0, 0.0

                carry = b''
                while sample_count < max_samples and remaining > 0:
                    data = f.read(min(CHUNK_SIZE, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    chunk = carry + data

                    available = (len(chunk) // frame_size) * frame_size
                    carry = chunk[available:]  # keep the split frame for the next read
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

    def get_samples_for_analysis(self, file_path: str, max_samples: int = 65536,
                                 separate_channels: bool = False) -> "ProcessingResult":
        """Extract a bounded, signed waveform for analysis tooling (e.g.
        spectral_utils.analyze_spectrum, bs1770_loudness). Mirrors
        _calculate_levels_safe's chunked read but keeps the samples instead of
        only their peak/RMS, and preserves sign (spectral/loudness analysis
        needs a real waveform, not magnitude).

        By default returns "samples": a single mono-mixed (per-frame
        averaged) waveform. When separate_channels=True, returns "channels":
        a list of one waveform per channel instead — no downmixing, so
        callers that sum per-channel energy (e.g. BS.1770 loudness, which
        under-reads by 3-6 LU on an averaged-to-mono signal) get accurate
        input.

        Bounded by max_samples (per-frame, not per-channel, in both modes) to
        keep memory and analysis time predictable regardless of file size.
        """
        try:
            if not security_validator.validate_path(file_path):
                return ProcessingResult(False, "Invalid file path - security violation")
            if not security_validator.validate_file_size(file_path):
                return ProcessingResult(False, "File too large or empty")
            if not security_validator.validate_audio_content(file_path):
                return ProcessingResult(False, "Invalid or corrupted WAV file")

            info = self._read_wav_header_optimized(file_path)
            if not info:
                return ProcessingResult(False, "Invalid WAV file format")

            bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
            frame_size = bytes_per_sample * max(1, info.channels)
            if frame_size == 0:
                return ProcessingResult(False, "Invalid audio format")

            if separate_channels:
                channels_out: List[List[float]] = [[] for _ in range(info.channels)]
                frame_count = 0
                with open(file_path, 'rb') as f:
                    f.seek(info.data_offset)
                    remaining = info.data_size

                    carry = b''
                    while frame_count < max_samples and remaining > 0:
                        data = f.read(min(CHUNK_SIZE, remaining))
                        if not data:
                            break
                        remaining -= len(data)
                        chunk = carry + data

                        available = (len(chunk) // frame_size) * frame_size
                        carry = chunk[available:]
                        if available == 0:
                            continue

                        mv = memoryview(chunk[:available])
                        for frame_offset in range(0, available, frame_size):
                            if frame_count >= max_samples:
                                break
                            decoded_this_frame = 0
                            for channel in range(info.channels):
                                sample_offset = frame_offset + channel * bytes_per_sample
                                sample_bytes = mv[sample_offset:sample_offset + bytes_per_sample].tobytes()
                                sample_value = self._decode_sample_bytes(sample_bytes, info.bit_depth)
                                if sample_value is None:
                                    continue
                                channels_out[channel].append(
                                    self._normalize_amplitude_signed(sample_value, info.bit_depth)
                                )
                                decoded_this_frame += 1
                            if decoded_this_frame:
                                frame_count += 1
                        del mv

                if not any(channels_out):
                    return ProcessingResult(False, "No decodable audio samples found")

                return ProcessingResult(
                    True, "Samples extracted",
                    {"channels": channels_out, "sample_rate": info.sample_rate}
                )

            samples: List[float] = []
            with open(file_path, 'rb') as f:
                f.seek(info.data_offset)
                remaining = info.data_size

                carry = b''
                while len(samples) < max_samples and remaining > 0:
                    data = f.read(min(CHUNK_SIZE, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    chunk = carry + data

                    available = (len(chunk) // frame_size) * frame_size
                    carry = chunk[available:]
                    if available == 0:
                        continue

                    mv = memoryview(chunk[:available])
                    for frame_offset in range(0, available, frame_size):
                        if len(samples) >= max_samples:
                            break
                        channel_sum = 0.0
                        channel_count = 0
                        for channel in range(info.channels):
                            sample_offset = frame_offset + channel * bytes_per_sample
                            sample_bytes = mv[sample_offset:sample_offset + bytes_per_sample].tobytes()
                            sample_value = self._decode_sample_bytes(sample_bytes, info.bit_depth)
                            if sample_value is None:
                                continue
                            channel_sum += self._normalize_amplitude_signed(sample_value, info.bit_depth)
                            channel_count += 1
                        if channel_count:
                            samples.append(channel_sum / channel_count)
                    del mv

            if not samples:
                return ProcessingResult(False, "No decodable audio samples found")

            return ProcessingResult(
                True, "Samples extracted",
                {"samples": samples, "sample_rate": info.sample_rate}
            )

        except (OSError, PermissionError) as e:
            return ProcessingResult(False, f"File system error: {e}")

    def _copy_patched_header(self, src, dst, info: AudioInfo, new_data_size: int,
                             *, channels: Optional[int] = None) -> None:
        """Copy the input header prefix verbatim and patch its size fields.

        Copies everything up to the data payload (preserving LIST/JUNK/fact
        chunks and non-16-byte fmt bodies exactly as they were), then patches:
        the data chunk size at data_offset-4, the RIFF size at offset 4, and —
        when *channels* is given (mono conversion) — the channel count, byte
        rate, and block align inside the fmt body at fmt_offset.

        Policy notes (deliberate, documented choices): chunks that trail the
        data payload are dropped from the output — the processed file is a new
        artifact; a fact chunk before data is preserved verbatim without
        recomputing dwSampleLength (informational for PCM).
        """
        header = bytearray(src.read(info.data_offset))
        if len(header) != info.data_offset:
            raise ValueError("Invalid WAV header")

        pad = new_data_size % 2
        struct.pack_into('<I', header, 4, info.data_offset - 8 + new_data_size + pad)
        struct.pack_into('<I', header, info.data_offset - 4, new_data_size)

        if channels is not None:
            bytes_per_sample = max(1, info.bit_depth // 8)
            struct.pack_into('<H', header, info.fmt_offset + 2, channels)
            struct.pack_into('<I', header, info.fmt_offset + 8,
                             info.sample_rate * bytes_per_sample * channels)
            struct.pack_into('<H', header, info.fmt_offset + 12,
                             bytes_per_sample * channels)

        dst.write(bytes(header))

    def _apply_gain_safe(self, input_path: str, output_path: str, info: AudioInfo, gain: float):
        """Apply gain to audio file with enhanced bit depth support and security."""
        bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
        frame_size = bytes_per_sample * max(1, info.channels)
        if frame_size == 0:
            raise ValueError("Invalid audio format")

        # Whole frames only; a trailing sub-frame fragment is dropped, so the
        # size fields written up front are exact.
        new_data_size = (info.data_size // frame_size) * frame_size

        with open(input_path, 'rb') as src, open_secure(output_path, 'wb') as dst:
            self._copy_patched_header(src, dst, info, new_data_size)

            processed_samples = 0
            max_samples = 10000000  # Safety limit per-channel
            to_consume = new_data_size
            carry = b''

            while to_consume > 0 and processed_samples < max_samples:
                data = src.read(min(CHUNK_SIZE, to_consume))
                if not data:
                    break
                to_consume -= len(data)
                chunk = carry + data

                available = (len(chunk) // frame_size) * frame_size
                carry = chunk[available:]
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

                del mv

            if new_data_size % 2:
                dst.write(b'\x00')  # RIFF pad byte

    def _convert_to_mono(self, input_path: str, output_path: str, info: AudioInfo):
        """Convert stereo/multi-channel to mono."""
        bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
        frame_size = bytes_per_sample * max(1, info.channels)
        if frame_size == 0:
            raise ValueError("Invalid audio format")

        frames = info.data_size // frame_size
        new_data_size = frames * bytes_per_sample

        with open(input_path, 'rb') as src, open_secure(output_path, 'wb') as dst:
            self._copy_patched_header(src, dst, info, new_data_size, channels=1)

            to_consume = frames * frame_size
            carry = b''

            while to_consume > 0:
                data = src.read(min(CHUNK_SIZE, to_consume))
                if not data:
                    break
                to_consume -= len(data)
                chunk = carry + data

                available = (len(chunk) // frame_size) * frame_size
                carry = chunk[available:]
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

                del mv

            if new_data_size % 2:
                dst.write(b'\x00')  # RIFF pad byte

    def _find_audio_boundaries(self, file_path: str, info: AudioInfo, threshold: float) -> Tuple[int, int]:
        """Find start and end of audio content above threshold."""
        start_sample = 0
        end_sample = int(info.duration * info.sample_rate)

        try:
            with open(file_path, 'rb') as f:
                f.seek(info.data_offset)
                remaining = info.data_size

                bytes_per_sample = max(1, info.bit_depth // 8) if info.bit_depth != 8 else 1
                frame_size = bytes_per_sample * max(1, info.channels)
                sample_index = 0
                found_start = False
                last_audio_sample = 0

                if frame_size == 0 or remaining <= 0:
                    return 0, 0

                carry = b''
                while remaining > 0:
                    data = f.read(min(CHUNK_SIZE, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    chunk = carry + data

                    available = (len(chunk) // frame_size) * frame_size
                    carry = chunk[available:]
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
        bytes_per_sample = max(1, info.bit_depth // 8)
        frame_size = bytes_per_sample * max(1, info.channels)
        sample_count = end_sample - start_sample

        start_byte = start_sample * frame_size
        # Never read past the actual data payload, whatever the caller asked.
        new_data_size = min(sample_count * frame_size,
                            max(0, info.data_size - start_byte))

        with open(input_path, 'rb') as src, open_secure(output_path, 'wb') as dst:
            self._copy_patched_header(src, dst, info, new_data_size)

            src.seek(info.data_offset + start_byte)

            bytes_to_copy = new_data_size
            while bytes_to_copy > 0:
                chunk = src.read(min(CHUNK_SIZE, bytes_to_copy))
                if not chunk:
                    break
                dst.write(chunk)
                bytes_to_copy -= len(chunk)

            if new_data_size % 2:
                dst.write(b'\x00')  # RIFF pad byte

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
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
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
        inspector = DeepFileInspector() if HAS_DEEP_INSPECTOR else None

        pattern = "**/*.wav" if recursive else "*.wav"
        for candidate in path.glob(pattern):
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_FORMATS:
                try:
                    if candidate.is_symlink():
                        continue
                except OSError:
                    continue

                # Deep format inspection, mirroring main.py's _filter_safe_files:
                # reject a .wav-named file whose bytes are not actually a WAV
                # container. Gate only on is_valid (the magic number);
                # suspicious byte patterns are logged, not rejected, since a
                # WAV's PCM payload can legitimately contain them.
                if inspector is not None:
                    inspection = inspector.validate_for_processing(candidate)
                    if not inspection.is_valid:
                        logger.warning(
                            "Skipping file failing format inspection: %s (%s)",
                            candidate, "; ".join(inspection.errors),
                        )
                        continue
                    for note in inspection.warnings:
                        logger.info("Inspection note for %s: %s", candidate, note)

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

            # result.data is only a dict on the error path (the except block
            # above builds one); a successful operation returns its own data
            # (e.g. analyze -> AudioInfo), which isn't a dict. Guard the
            # membership test with isinstance so success no longer raises
            # "argument of type 'AudioInfo' is not iterable" -- a crash that
            # was masked while every file failed before the operation ran.
            if not isinstance(result.data, dict) or "analysis" not in result.data:
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

    async def process_directory_async(self, directory: str, operation: str, **kwargs) -> List[ProcessingResult]:
        """Asynchronously process all WAV files in directory with concurrency control."""
        # Use asyncio.gather for concurrent processing with semaphore for resource control
        semaphore = asyncio.Semaphore(4)  # Limit concurrent operations

        async def process_file_with_semaphore(file_path: Path) -> ProcessingResult:
            async with semaphore:
                return await self._execute_operation_async(operation, file_path, kwargs)

        # Get file list
        if not SecurityValidator.validate_directory(directory):
            return [ProcessingResult(False, "Invalid directory provided")]

        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return [ProcessingResult(False, "Directory not found")]

        operation_normalized = (operation or "").strip().lower()
        if operation_normalized not in ALLOWED_BATCH_OPERATIONS:
            return [ProcessingResult(False, f"Unsupported operation: {operation}")]

        wav_files: List[Path] = []
        inspector = DeepFileInspector() if HAS_DEEP_INSPECTOR else None
        pattern = "**/*.wav" if kwargs.get("recursive", True) else "*.wav"
        for candidate in path.glob(pattern):
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_FORMATS:
                if inspector is not None:
                    inspection = inspector.validate_for_processing(candidate)
                    if not inspection.is_valid:
                        logger.warning(
                            "Skipping file failing format inspection: %s (%s)",
                            candidate, "; ".join(inspection.errors),
                        )
                        continue
                    for note in inspection.warnings:
                        logger.info("Inspection note for %s: %s", candidate, note)

                wav_files.append(candidate)
                if isinstance(kwargs.get("max_files"), int) and kwargs.get("max_files") > 0 and len(wav_files) >= kwargs["max_files"]:
                    break

        if not wav_files:
            return [ProcessingResult(False, "No WAV files found")]

        # Process files concurrently
        tasks = [process_file_with_semaphore(file_path) for file_path in wav_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions and convert to ProcessingResult
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ProcessingResult(False, f"Error processing {wav_files[i].name}: {str(result)}"))
            else:
                processed_results.append(result)

        return processed_results

    def _build_operation_runner(self, operation: str, file_path: Path,
                                options: Dict[str, Any]) -> Callable[[], ProcessingResult]:
        """Return a zero-arg callable that performs a single batch operation.

        Shared by the sync (_execute_operation) and async
        (_execute_operation_async) paths so their operation dispatch, output
        naming, and output-dir handling can never drift apart.
        """
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

        return run_operation

    def _execute_operation(self, operation: str, file_path: Path,
                           options: Dict[str, Any]) -> Tuple[ProcessingResult, int]:
        """Synchronously execute a single batch operation.

        Returns ``(result, attempts)`` -- the shape the synchronous
        ``process_directory`` loop unpacks. This method previously did not
        exist at all: ``process_directory`` called ``self._execute_operation``,
        which raised ``AttributeError`` that its per-file ``except Exception``
        swallowed, so every file in a synchronous batch was silently reported
        as failed. (Only the async twin existed.)
        """
        return self.recovery.execute(operation, self._build_operation_runner(operation, file_path, options))

    async def _execute_operation_async(self, operation: str, file_path: Path, options: Dict[str, Any]) -> ProcessingResult:
        """Asynchronously execute a single operation.

        Returns the ``ProcessingResult`` only. ``recovery.execute`` returns a
        ``(result, attempts)`` tuple; an earlier version returned that tuple
        verbatim, so ``process_directory_async`` / ``batch_process_async``
        leaked tuples to callers despite their ``List[ProcessingResult]``
        annotation (the async tests had to index ``[0][0]`` to reach
        ``.success``). The attempt count is not surfaced by the async path's
        result list, so it is dropped here.
        """
        result, _attempts = self.recovery.execute(
            operation, self._build_operation_runner(operation, file_path, options)
        )
        return result

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

class EnhancedSecurityValidator:
    """Enhanced security validation with modern best practices."""

    @staticmethod
    def validate_path_secure(file_path: str) -> bool:
        """Enhanced path validation with comprehensive security checks."""
        try:
            path = Path(file_path).resolve()

            # Check for path traversal attempts
            path_str = str(path)
            dangerous_patterns = ['../', '..\\', '/..', '\\..', '%2e%2e', '%2f', '..%2f', '%2e%2e%2f']
            for pattern in dangerous_patterns:
                if pattern in path_str.lower():
                    return False

            # Check path length limits
            if len(path_str) > 4096:  # Reasonable path length limit
                return False

            # Check for suspicious characters
            suspicious_chars = ['<', '>', '|', '"', '?', '*', '\0']
            for char in suspicious_chars:
                if char in path_str:
                    return False

            # Validate parent directories exist and are accessible
            if not path.parent.exists():
                return False

            # Check file size limits (prevent zip bombs)
            if path.exists() and path.is_file():
                size = path.stat().st_size
                if size > 500 * 1024 * 1024:  # 500MB limit
                    return False

            # Check for hidden files or system directories
            if any(part.startswith('.') for part in path.parts if part):
                return False

            # Check if path is within allowed directories (if configured)
            allowed_dirs = os.getenv('ALLOWED_DIRECTORIES', '').split(',')
            if allowed_dirs and allowed_dirs[0]:
                if not any(str(path).startswith(allowed) for allowed in allowed_dirs):
                    return False

            return True

        except (OSError, ValueError, RuntimeError):
            return False

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent injection attacks."""
        import re

        # Remove or replace dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]', '_', filename)

        # Limit length
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:255-len(ext)] + ext

        return sanitized or "untitled"

    @staticmethod
    def validate_audio_content_secure(file_path: str) -> bool:
        """Validate audio file content for security issues."""
        try:
            # Check file header for known audio signatures
            with open(file_path, 'rb') as f:
                header = f.read(12)

            # WAV signature check
            if header.startswith(b'RIFF') and b'WAVE' in header:
                return True

            # Check for embedded scripts or executables
            if b'<?' in header or b'<!' in header or b'<script' in header:
                return False

            # Check for suspicious byte patterns
            suspicious_patterns = [b'\x00\x00\x00\x00', b'\xFF\xFF\xFF\xFF']
            for pattern in suspicious_patterns:
                if pattern in header:
                    return False

            return True

        except (OSError, IOError):
            return False

    @staticmethod
    def check_file_integrity(file_path: str) -> bool:
        """Check file integrity and detect potential tampering."""
        try:
            path = Path(file_path)

            # Check file modification time consistency
            stat = path.stat()
            if stat.st_mtime > time.time():
                return False  # Future modification time

            # Check for suspicious file permissions
            if os.name == 'posix':
                mode = stat.st_mode
                if mode & 0o777 != mode:  # Check for special permissions
                    return False

            # Check file entropy for encrypted/compressed content
            entropy = EnhancedSecurityValidator._calculate_file_entropy(file_path)
            if entropy > 7.5:  # High entropy might indicate encryption
                return False

            return True

        except (OSError, ValueError):
            return False

    @staticmethod
    def _calculate_file_entropy(file_path: str) -> float:
        """Calculate file entropy for security analysis."""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                if not data:
                    return 0.0

                # Count byte frequencies
                byte_counts = [0] * 256
                for byte in data:
                    byte_counts[byte] += 1

                # Calculate entropy
                entropy = 0.0
                length = len(data)
                for count in byte_counts:
                    if count > 0:
                        p = count / length
                        entropy -= p * (p.bit_length() if p > 0 else 0)  # Simplified

                return entropy

        except (OSError, IOError):
            return 0.0


# ---------------------------------------------------------------------------
# Module-level singletons and synchronous public API.
#
# (This block previously existed but had been replaced by a stray placeholder
# token; restored here so the functions below and the ``python core.py`` CLI
# resolve their dependencies.)
# ---------------------------------------------------------------------------
_processor = WAVProcessor()
_batch_processor = BatchProcessor()


def analyze(input_path: str) -> ProcessingResult:
    """Analyze a WAV file - main API."""
    return _processor.analyze(input_path)


def get_samples_for_analysis(input_path: str, max_samples: int = 65536,
                              separate_channels: bool = False) -> ProcessingResult:
    """Extract a bounded, signed waveform for spectral/analysis tooling - main API.

    separate_channels=True returns per-channel waveforms (no mono downmix) --
    see AudioProcessor.get_samples_for_analysis for details.
    """
    return _processor.get_samples_for_analysis(input_path, max_samples, separate_channels)


def normalize(input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
    """Normalize audio - main API."""
    return _processor.normalize(input_path, output_path, target_peak)


def trim_silence(input_path: str, output_path: str, threshold: float = 0.01) -> ProcessingResult:
    """Trim leading/trailing silence - main API."""
    return _processor.trim_silence(input_path, output_path, threshold)


def to_mono(input_path: str, output_path: str) -> ProcessingResult:
    """Convert to mono - main API."""
    return _processor.convert_to_mono(input_path, output_path)

async def analyze_async(input_path: str) -> ProcessingResult:
    """Asynchronously analyze WAV file - main API."""
    return await _processor.analyze_async(input_path)

async def normalize_async(input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
    """Asynchronously normalize audio - main API."""
    return await _processor.normalize_async(input_path, output_path, target_peak)

async def to_mono_async(input_path: str, output_path: str) -> ProcessingResult:
    """Asynchronously convert to mono - main API."""
    return await _processor.convert_to_mono_async(input_path, output_path)

async def trim_silence_async(input_path: str, output_path: str, threshold: float = 0.01) -> ProcessingResult:
    """Asynchronously trim silence - main API."""
    return await _processor.trim_silence_async(input_path, output_path, threshold)

async def batch_process_async(directory: str, operation: str, **kwargs) -> List[ProcessingResult]:
    """Asynchronously process directory - main API."""
    return await _batch_processor.process_directory_async(directory, operation, **kwargs)


def record_operation(operation: str, duration_ms: int) -> None:
    """Expose performance tracker recording for auxiliary modules."""
    _processor.perf.record_operation(operation, duration_ms)

if __name__ == "__main__":
    # Minimal CLI. The full-featured command line lives in main.py; this entry
    # point exposes only the core, dependency-light operations.
    import sys

    if len(sys.argv) < 2:
        print(f"Chameleon Core {VERSION}")
        print("Usage:")
        print("  python core.py analyze <file.wav>")
        print("  python core.py normalize <input.wav> <output.wav> [peak]")
        print("  python core.py mono <input.wav> <output.wav>")
        print("  python core.py trim <input.wav> <output.wav> [threshold]")
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
        peak = float(sys.argv[4]) if len(sys.argv) > 4 else 0.95
        result = normalize(sys.argv[2], sys.argv[3], peak)
        print(f"Result: {result.message}")
        if result.success and result.data:
            print(f"Gain applied: {result.data['gain_applied']:.2f}x")

    elif command == "mono" and len(sys.argv) >= 4:
        result = to_mono(sys.argv[2], sys.argv[3])
        print(f"Result: {result.message}")

    elif command == "trim" and len(sys.argv) >= 4:
        threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.01
        result = trim_silence(sys.argv[2], sys.argv[3], threshold)
        print(f"Result: {result.message}")
        if result.success and result.data:
            print(f"Removed: {result.data['removed_seconds']:.2f}s")

    else:
        print(f"Unknown or incomplete command: {command}")
        sys.exit(1)



class ParallelBatchProcessor:
    """並列バッチ処理でパフォーマンスを最適化"""

    def __init__(self, processor: WAVProcessor, max_workers: int = None):
        self.processor = processor
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.logger = logging.getLogger(__name__)

    async def process_directory_async(self, directory: str, operation: str, **kwargs) -> List[ProcessingResult]:
        """並列でディレクトリを非同期処理"""
        directory_path = Path(directory)
        if not directory_path.exists() or not directory_path.is_dir():
            raise ValueError(f"無効なディレクトリ: {directory}")

        # WAVファイルを収集
        wav_files = list(directory_path.rglob("*.wav")) + list(directory_path.rglob("*.wave"))
        if not wav_files:
            return []

        # ファイルサイズに基づいて優先順位付け（大きいファイルから処理）
        files_with_size = []
        for file_path in wav_files:
            try:
                size = file_path.stat().st_size
                files_with_size.append((file_path, size))
            except OSError:
                files_with_size.append((file_path, 0))

        files_with_size.sort(key=lambda x: x[1], reverse=True)
        prioritized_files = [file_path for file_path, _ in files_with_size]

        # 並列処理でバッチ実行
        semaphore = asyncio.Semaphore(self.max_workers)

        async def process_single_file(file_path: Path) -> ProcessingResult:
            async with semaphore:
                # 処理タイプに基づいて適切な関数を選択
                if operation == "analyze":
                    return await self.processor.analyze_async(str(file_path))
                elif operation == "normalize":
                    output_path = file_path.with_suffix('.normalized.wav')
                    target_peak = kwargs.get('target_peak', 0.95)
                    return await self.processor.normalize_async(str(file_path), str(output_path), target_peak)
                elif operation == "mono":
                    output_path = file_path.with_suffix('.mono.wav')
                    return await self.processor.convert_to_mono_async(str(file_path), str(output_path))
                elif operation == "trim":
                    output_path = file_path.with_suffix('.trimmed.wav')
                    threshold = kwargs.get('threshold', 0.01)
                    return await self.processor.trim_silence_async(str(file_path), str(output_path), threshold)
                else:
                    return ProcessingResult(False, f"未サポートの操作: {operation}")

        # 並列実行
        tasks = [process_single_file(file_path) for file_path in prioritized_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 例外を適切に処理
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"ファイル処理エラー {prioritized_files[i]}: {result}")
                processed_results.append(ProcessingResult(False, f"処理エラー: {str(result)}"))
            else:
                processed_results.append(result)

        return processed_results

    def process_directory_parallel(self, directory: str, operation: str, **kwargs) -> List[ProcessingResult]:
        """並列でディレクトリを同期処理"""
        async def run_async():
            return await self.process_directory_async(directory, operation, **kwargs)

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # 通常経路: 実行中のループが無い同期呼び出し
                return asyncio.run(run_async())
            # 既にループが実行中の場合、新しいループを作成
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(run_async())
            finally:
                new_loop.close()
        except Exception as e:
            logger.error(f"ディレクトリ並列処理エラー: {e}")
            return []


class StructuredLogger:
    """構造化ログ出力でメンテナビリティを向上"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_structured_logging()

    def _setup_structured_logging(self):
        """構造化ログを設定"""
        # 構造化ログフォーマッタ
        class StructuredFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }

                # エラー情報があれば追加
                if record.exc_info:
                    log_entry["exception"] = self.formatException(record.exc_info)

                # パフォーマンス情報があれば追加
                if hasattr(record, 'duration_ms'):
                    log_entry["duration_ms"] = record.duration_ms
                if hasattr(record, 'operation'):
                    log_entry["operation"] = record.operation

                return json.dumps(log_entry, ensure_ascii=False)

        # 構造化ログハンドラ
        structured_handler = logging.StreamHandler()
        structured_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(structured_handler)
        self.logger.setLevel(logging.INFO)

    def log_operation(self, operation: str, duration_ms: int, success: bool = True, **kwargs):
        """操作ログを記録"""
        extra = {
            'operation': operation,
            'duration_ms': duration_ms,
            'success': success,
            **kwargs
        }

        if success:
            self.logger.info(f"Operation completed: {operation}", extra=extra)
        else:
            self.logger.error(f"Operation failed: {operation}", extra=extra)

    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """セキュリティイベントをログ記録"""
        log_entry = {
            "event_type": event_type,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "details": details
        }
        self.logger.warning(f"Security event: {event_type}", extra=log_entry)

    def log_performance_metrics(self, metrics: Dict[str, Any]):
        """パフォーマンスメトリクスをログ記録"""
        log_entry = {
            "metrics_type": "performance",
            "metrics": metrics
        }
        self.logger.info("Performance metrics", extra=log_entry)

# Chameleon has no quantum, neural, GPU or source-separation features, and
# will not grow any -- see CHARTER.md §4. Two gravestone comments for a 2024
# removal used to sit here; this one note replaces both.
