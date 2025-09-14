#!/usr/bin/env python3
"""
Audio Utilities - Consolidated audio processing utilities
Combines all utility functions for audio processing with optimization
"""

import array
import math
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Tuple, Optional, Union, Dict, Any
from collections import deque
from functools import lru_cache

# Use compatibility layer for optional dependencies
try:
    from compatibility import jit, safe_normalize, safe_tone_generation, safe_rms_calculation
    from compatibility import HAS_NUMPY, HAS_NUMBA
except ImportError:
    # Fallback if compatibility module not available
    HAS_NUMPY = False
    HAS_NUMBA = False
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


# Audio Constants
SAMPLE_RATE_DEFAULT = 44100
CHANNELS_DEFAULT = 1
SAMPLE_WIDTH_DEFAULT = 2  # 16-bit
MAX_INT16 = 32767
MIN_INT16 = -32768

# Additional sample rates for compatibility
SAMPLE_RATES = [8000, 16000, 22050, 44100, 48000, 96000]

# Performance optimization lookup tables
SIN_TABLE_SIZE = 4096
SIN_TABLE = [math.sin(2 * math.pi * i / SIN_TABLE_SIZE) for i in range(SIN_TABLE_SIZE)]
COS_TABLE = [math.cos(2 * math.pi * i / SIN_TABLE_SIZE) for i in range(SIN_TABLE_SIZE)]

# LRU Cache for tone generation with optional optimization
@lru_cache(maxsize=128)
def generate_tone_cached(frequency: float, duration: float, sample_rate: int = SAMPLE_RATE_DEFAULT) -> bytes:
    """Generate tone with caching and optional optimization"""
    if HAS_NUMPY and HAS_NUMBA:
        # Use optimized version if available
        return safe_tone_generation(frequency, duration, sample_rate)
    else:
        # Pure Python fallback
        samples = []
        num_samples = int(duration * sample_rate)
        phase_increment = 2 * math.pi * frequency / sample_rate
        
        for i in range(num_samples):
            phase = i * phase_increment
            # Use fast lookup table if available
            if i < len(SIN_TABLE):
                table_index = int((phase % (2 * math.pi)) * SIN_TABLE_SIZE / (2 * math.pi))
                value = SIN_TABLE[table_index % SIN_TABLE_SIZE]
            else:
                value = math.sin(phase)
            samples.append(int(value * MAX_INT16 * 0.5))
        
        arr = array.array('h', samples)
        return arr.tobytes()

# WAV file operations
def read_wav_simple(filename: str) -> Tuple[bytes, Dict[str, Any]]:
    """Simple WAV file reader"""
    import wave
    try:
        with wave.open(filename, 'rb') as wav:
            frames = wav.readframes(-1)
            metadata = {
                'sample_rate': wav.getframerate(),
                'channels': wav.getnchannels(),
                'sample_width': wav.getsampwidth(),
                'duration': len(frames) / (wav.getframerate() * wav.getnchannels() * wav.getsampwidth())
            }
            return frames, metadata
    except Exception as e:
        raise IOError(f"Cannot read WAV file {filename}: {e}")

def write_wav_simple(filename: str, audio_data: bytes, sample_rate: int = SAMPLE_RATE_DEFAULT, 
                    channels: int = CHANNELS_DEFAULT) -> bool:
    """Simple WAV file writer"""
    import wave
    try:
        with wave.open(filename, 'wb') as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(audio_data)
        return True
    except Exception as e:
        print(f"Cannot write WAV file {filename}: {e}")
        return False


class TempFileManager:
    """Manage temporary files with automatic cleanup"""
    
    def __init__(self):
        self.temp_files = []
        self.cleanup_on_exit = True
        
    def create_temp_file(self, suffix: str = '.wav', prefix: str = 'chameleon_') -> str:
        """Create temporary file"""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        self.temp_files.append(path)
        return path
    
    def cleanup(self):
        """Clean up all temporary files"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
        self.temp_files.clear()
    
    def __del__(self):
        if self.cleanup_on_exit:
            self.cleanup()


# Fast mathematical functions
def fast_sin(phase: float) -> float:
    """Fast sine lookup with linear interpolation"""
    index = phase * SIN_TABLE_SIZE / (2 * math.pi)
    index = index % SIN_TABLE_SIZE
    i0 = int(index)
    i1 = (i0 + 1) % SIN_TABLE_SIZE
    frac = index - i0
    return SIN_TABLE[i0] * (1 - frac) + SIN_TABLE[i1] * frac


def fast_cos(phase: float) -> float:
    """Fast cosine lookup with linear interpolation"""
    index = phase * SIN_TABLE_SIZE / (2 * math.pi)
    index = index % SIN_TABLE_SIZE
    i0 = int(index)
    i1 = (i0 + 1) % SIN_TABLE_SIZE
    frac = index - i0
    return COS_TABLE[i0] * (1 - frac) + COS_TABLE[i1] * frac


# Audio format conversion utilities
def bytes_to_samples(audio_data: bytes) -> List[int]:
    """Convert bytes to sample list"""
    samples = array.array('h')
    samples.frombytes(audio_data)
    return list(samples)


def samples_to_bytes(samples: List[int]) -> bytes:
    """Convert sample list to bytes"""
    arr = array.array('h', samples)
    return arr.tobytes()


def normalize_audio(samples: Union[bytes, array.array, List[int]], target_max: float = 0.95) -> bytes:
    """Normalize audio to target maximum amplitude"""
    if HAS_NUMPY:
        # Use optimized version if available
        normalized = safe_normalize(samples, target_max)
        if hasattr(normalized, 'tobytes'):
            return normalized.tobytes()
        else:
            # Convert list back to bytes
            arr = array.array('h', normalized)
            return arr.tobytes()
    else:
        # Pure Python fallback
        if isinstance(samples, bytes):
            arr = array.array('h')
            arr.frombytes(samples)
        elif isinstance(samples, list):
            arr = array.array('h', samples)
        else:
            arr = samples
        
        if not arr:
            return b''
        
        # Find maximum amplitude
        max_val = max(abs(s) for s in arr)
        if max_val == 0:
            return arr.tobytes()
        
        # Calculate scaling factor
        scale = (MAX_INT16 * target_max) / max_val
        
        # Apply scaling
        normalized = array.array('h', [int(s * scale) for s in arr])
        return normalized.tobytes()


def clip_audio(samples: List[int], threshold: float = 0.99) -> List[int]:
    """Soft clipping to prevent harsh distortion"""
    max_val = int(MAX_INT16 * threshold)
    result = []
    
    for s in samples:
        if s > max_val:
            # Soft clipping using tanh-like curve
            excess = (s - max_val) / MAX_INT16
            clipped = max_val + int(1000 * math.tanh(excess))
            result.append(min(MAX_INT16, clipped))
        elif s < -max_val:
            excess = (s + max_val) / MAX_INT16
            clipped = -max_val + int(1000 * math.tanh(excess))
            result.append(max(MIN_INT16, clipped))
        else:
            result.append(s)
    
    return result


# Audio analysis functions
def calculate_rms(samples: Union[bytes, array.array, List[int]]) -> float:
    """Calculate RMS (Root Mean Square) of audio samples"""
    if HAS_NUMPY:
        return safe_rms_calculation(samples)
    else:
        # Pure Python fallback
        if isinstance(samples, bytes):
            arr = array.array('h')
            arr.frombytes(samples)
        elif isinstance(samples, list):
            arr = samples
        else:
            arr = list(samples)
        
        if not arr:
            return 0.0
        
        sum_squares = sum(s * s for s in arr)
        return math.sqrt(sum_squares / len(arr))


def detect_peak(audio_data: bytes) -> float:
    """Detect peak amplitude in audio"""
    samples = array.array('h')
    samples.frombytes(audio_data)
    
    if not samples:
        return 0.0
    
    peak = max(abs(s) for s in samples)
    return peak / MAX_INT16


def detect_silence(samples: Union[bytes, array.array, List[int]], threshold: float = 0.01) -> bool:
    """Detect if audio is silence based on RMS threshold"""
    rms = calculate_rms(samples)
    max_val = MAX_INT16
    return (rms / max_val) < threshold


def count_zero_crossings(samples: Union[bytes, List[int]]) -> int:
    """Count zero crossings in audio signal"""
    if isinstance(samples, bytes):
        arr = array.array('h')
        arr.frombytes(samples)
        samples = list(arr)
    
    crossings = 0
    for i in range(1, len(samples)):
        if (samples[i-1] >= 0) != (samples[i] >= 0):
            crossings += 1
    return crossings


# Audio processing utilities
def apply_window(samples: List[int], window_type: str = 'hann') -> List[int]:
    """Apply window function to samples"""
    n = len(samples)
    if n == 0:
        return samples
    
    if window_type == 'hann':
        window = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]
    elif window_type == 'hamming':
        window = [0.54 - 0.46 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]
    elif window_type == 'blackman':
        window = [0.42 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) + 
                 0.08 * math.cos(4 * math.pi * i / (n - 1)) for i in range(n)]
    else:  # rectangular
        window = [1.0] * n
    
    return [int(s * w) for s, w in zip(samples, window)]


def crossfade(samples1: List[int], samples2: List[int], overlap: int) -> List[int]:
    """Crossfade between two sample arrays"""
    if overlap <= 0 or not samples1 or not samples2:
        return samples1 + samples2
    
    overlap = min(overlap, len(samples1), len(samples2))
    result = samples1[:-overlap] if overlap < len(samples1) else []
    
    # Crossfade region
    for i in range(overlap):
        factor1 = (overlap - i) / overlap
        factor2 = i / overlap
        idx1 = len(samples1) - overlap + i
        val = int(samples1[idx1] * factor1 + samples2[i] * factor2)
        result.append(val)
    
    # Append remaining samples2
    result.extend(samples2[overlap:])
    return result


def resample_linear(samples: List[int], old_rate: int, new_rate: int) -> List[int]:
    """Simple linear resampling"""
    if old_rate == new_rate or not samples:
        return samples
    
    ratio = old_rate / new_rate
    new_length = int(len(samples) / ratio)
    result = []
    
    for i in range(new_length):
        src_pos = i * ratio
        src_idx = int(src_pos)
        frac = src_pos - src_idx
        
        if src_idx < len(samples) - 1:
            val = samples[src_idx] * (1 - frac) + samples[src_idx + 1] * frac
            result.append(int(val))
        elif src_idx < len(samples):
            result.append(samples[src_idx])
    
    return result


def remove_dc_offset(samples: List[int]) -> List[int]:
    """Remove DC offset from audio samples"""
    if not samples:
        return samples
    
    mean = sum(samples) / len(samples)
    return [int(s - mean) for s in samples]


# Decibel conversion utilities
def db_to_linear(db: float) -> float:
    """Convert decibels to linear amplitude"""
    return 10 ** (db / 20.0)


def linear_to_db(linear: float) -> float:
    """Convert linear amplitude to decibels"""
    if linear <= 0:
        return -float('inf')
    return 20 * math.log10(linear)


# File and path utilities
def ensure_extension(filename: str, extension: str) -> str:
    """Ensure filename has the correct extension"""
    path = Path(filename)
    if not extension.startswith('.'):
        extension = '.' + extension
    
    if path.suffix.lower() != extension.lower():
        return str(path.with_suffix(extension))
    return filename


def get_file_info(filename: str) -> Dict[str, Any]:
    """Get basic file information"""
    path = Path(filename)
    if not path.exists():
        return {}
    
    stat = path.stat()
    return {
        'size_bytes': stat.st_size,
        'size_mb': stat.st_size / (1024 * 1024),
        'modified': stat.st_mtime,
        'extension': path.suffix.lower(),
        'name': path.name,
        'stem': path.stem
    }


# Performance utilities moved to performance.py
# Import from centralized module to avoid duplication
try:
    from performance import Performance as Timer
except ImportError:
    # Fallback minimal implementation if performance.py not available
    class Timer:
        def __init__(self):
            self.start_time = None
        
        def start(self):
            self.start_time = time.perf_counter()
            return self
        
        def stop(self) -> float:
            if self.start_time:
                return time.perf_counter() - self.start_time
            return 0.0
        
        def __enter__(self):
            self.start()
            return self
        
        def __exit__(self, *args):
            self.stop()


# Memory management
class CircularBuffer:
    """Circular buffer for audio data"""
    
    def __init__(self, size: int):
        self.size = size
        self.buffer = [0] * size
        self.write_pos = 0
        self.read_pos = 0
        self.count = 0
    
    def write(self, data: List[int]) -> int:
        """Write data to buffer, return number of items written"""
        written = 0
        for item in data:
            if self.count < self.size:
                self.buffer[self.write_pos] = item
                self.write_pos = (self.write_pos + 1) % self.size
                self.count += 1
                written += 1
            else:
                # Buffer full, overwrite oldest
                self.buffer[self.write_pos] = item
                self.write_pos = (self.write_pos + 1) % self.size
                self.read_pos = (self.read_pos + 1) % self.size
                written += 1
        return written
    
    def read(self, num_items: int) -> List[int]:
        """Read data from buffer"""
        result = []
        for _ in range(min(num_items, self.count)):
            result.append(self.buffer[self.read_pos])
            self.read_pos = (self.read_pos + 1) % self.size
            self.count -= 1
        return result
    
    def peek(self, num_items: int) -> List[int]:
        """Peek at data without removing it"""
        result = []
        pos = self.read_pos
        for _ in range(min(num_items, self.count)):
            result.append(self.buffer[pos])
            pos = (pos + 1) % self.size
        return result
    
    def available(self) -> int:
        """Get number of available items"""
        return self.count
    
    def space(self) -> int:
        """Get available space"""
        return self.size - self.count
    
    def clear(self):
        """Clear buffer"""
        self.read_pos = 0
        self.write_pos = 0
        self.count = 0


# Error handling utilities - using centralized error classes
try:
    from error_handler import AudioError, ProcessingError, ConfigurationError as FormatError
except ImportError:
    # Fallback if error_handler.py not available
    class AudioError(Exception):
        pass
    
    class ProcessingError(AudioError):
        pass
    
    class FormatError(AudioError):
        pass


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """Safe division with default value"""
    if b == 0:
        return default
    return a / b


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max"""
    return max(min_val, min(max_val, value))


# Global instances
temp_file_manager = TempFileManager()