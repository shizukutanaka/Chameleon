#!/usr/bin/env python3
"""
Core Performance Optimizations for Chameleon Audio Processing Framework
High-performance implementations of critical audio processing functions with advanced optimization techniques.
"""

import os
import sys
import math
import time
import struct
import mmap
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any, Union
from functools import lru_cache, partial
from dataclasses import dataclass
import numpy as np

# Import performance monitoring
try:
    from .performance import (
        performance_monitor, memory_efficient, PerformanceCache,
        monitor, cache, resource_manager, profiler
    )
    from .core import (
        AudioData, logger, validate_audio_data, _create_wav_header,
        AudioConstants, TYPES_AVAILABLE, SECURITY_AVAILABLE
    )
    PERFORMANCE_AVAILABLE = True
    NUMPY_AVAILABLE = True
except ImportError:
    try:
        import numpy as np
        NUMPY_AVAILABLE = True
    except ImportError:
        NUMPY_AVAILABLE = False
    
    # Fallback types and functions
    AudioData = Tuple[bytes, int, int, int]
    PERFORMANCE_AVAILABLE = False
    TYPES_AVAILABLE = False
    SECURITY_AVAILABLE = False
    
    # Minimal logging fallback
    import logging
    logger = logging.getLogger('chameleon.core_optimized')

@dataclass
class OptimizationConfig:
    """Configuration for performance optimizations"""
    use_numpy_acceleration: bool = NUMPY_AVAILABLE
    use_memory_mapping: bool = True
    use_vectorized_operations: bool = NUMPY_AVAILABLE
    use_parallel_processing: bool = False  # Conservative default
    cache_size: int = 1024
    chunk_size: int = 8192
    lut_size: int = 16384  # Increased LUT size
    enable_profiling: bool = True

# Global optimization configuration
_OPT_CONFIG = OptimizationConfig()

# Enhanced caching system
class AdvancedCache:
    """High-performance cache with optimization-specific features"""
    
    def __init__(self, max_size: int = 1024):
        self.max_size = max_size
        self._cache = {}
        self._access_count = defaultdict(int)
        self._lock = threading.RLock()
    
    def get(self, key: str, compute_func=None):
        """Get value from cache or compute if missing"""
        with self._lock:
            if key in self._cache:
                self._access_count[key] += 1
                return self._cache[key]
            
            if compute_func:
                value = compute_func()
                self.put(key, value)
                return value
            
            return None
    
    def put(self, key: str, value: Any):
        """Store value in cache with intelligent eviction"""
        with self._lock:
            if len(self._cache) >= self.max_size:
                # Evict least frequently used item
                lfu_key = min(self._access_count.keys(), key=lambda k: self._access_count[k])
                del self._cache[lfu_key]
                del self._access_count[lfu_key]
            
            self._cache[key] = value
            self._access_count[key] = 1
    
    def clear(self):
        """Clear cache"""
        with self._lock:
            self._cache.clear()
            self._access_count.clear()
    
    def get_stats(self):
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': sum(self._access_count.values()) / max(1, len(self._access_count))
            }

# Global cache instances
_sine_cache = AdvancedCache(512)
_waveform_cache = AdvancedCache(256)
_filter_cache = AdvancedCache(128)

# Enhanced Lookup Tables
class OptimizedLUT:
    """Optimized lookup table with multiple interpolation methods"""
    
    def __init__(self, size: int = 16384):
        self.size = size
        self.sine_table = None
        self.cosine_table = None
        self.initialized = False
        self._lock = threading.Lock()
    
    def initialize(self):
        """Initialize lookup tables with thread safety"""
        if self.initialized:
            return
        
        with self._lock:
            if self.initialized:  # Double-check after lock
                return
            
            if NUMPY_AVAILABLE:
                # Vectorized initialization
                indices = np.arange(self.size, dtype=np.float64)
                angles = 2.0 * np.pi * indices / self.size
                self.sine_table = np.sin(angles)
                self.cosine_table = np.cos(angles)
            else:
                # Fallback to Python lists
                self.sine_table = [
                    math.sin(2.0 * math.pi * i / self.size) 
                    for i in range(self.size)
                ]
                self.cosine_table = [
                    math.cos(2.0 * math.pi * i / self.size)
                    for i in range(self.size)
                ]
            
            self.initialized = True
            logger.info(f"Optimized LUT initialized: {self.size} entries")
    
    def sin(self, phase: float) -> float:
        """Fast sine lookup with linear interpolation"""
        if not self.initialized:
            self.initialize()
        
        # Normalize phase to [0, 1)
        phase = phase % 1.0
        
        # Calculate index with fractional part
        exact_index = phase * self.size
        base_index = int(exact_index)
        fraction = exact_index - base_index
        
        # Linear interpolation
        next_index = (base_index + 1) % self.size
        
        if NUMPY_AVAILABLE:
            return float(
                self.sine_table[base_index] * (1.0 - fraction) +
                self.sine_table[next_index] * fraction
            )
        else:
            return (
                self.sine_table[base_index] * (1.0 - fraction) +
                self.sine_table[next_index] * fraction
            )
    
    def cos(self, phase: float) -> float:
        """Fast cosine lookup with linear interpolation"""
        if not self.initialized:
            self.initialize()
        
        # Use sine-cosine relationship: cos(x) = sin(x + π/2)
        return self.sin(phase + 0.25)

# Global optimized LUT
_optimized_lut = OptimizedLUT(_OPT_CONFIG.lut_size)

# Vectorized Operations
class VectorizedOps:
    """Vectorized audio processing operations using NumPy when available"""
    
    @staticmethod
    def generate_sine_wave_vectorized(frequency: float, duration: float, 
                                    sample_rate: int, amplitude: float = 32767.0) -> Optional[bytes]:
        """Generate sine wave using vectorized operations"""
        if not NUMPY_AVAILABLE:
            return None
        
        try:
            frames = int(duration * sample_rate)
            if frames <= 0:
                return None
            
            # Vectorized sine wave generation
            t = np.linspace(0, duration, frames, dtype=np.float64)
            samples = amplitude * np.sin(2.0 * np.pi * frequency * t)
            
            # Convert to 16-bit integers with proper clipping
            samples_int16 = np.clip(samples, -32768, 32767).astype(np.int16)
            
            # Convert to bytes
            return samples_int16.tobytes()
            
        except Exception as e:
            logger.error(f"Vectorized sine wave generation failed: {e}")
            return None
    
    @staticmethod
    def normalize_audio_vectorized(data: bytes, target_amplitude: float = 0.8) -> Optional[bytes]:
        """Normalize audio using vectorized operations"""
        if not NUMPY_AVAILABLE or not data:
            return None
        
        try:
            # Convert bytes to numpy array
            samples = np.frombuffer(data, dtype=np.int16)
            
            if len(samples) == 0:
                return data
            
            # Find maximum amplitude
            max_amplitude = np.max(np.abs(samples))
            
            if max_amplitude == 0:
                return data
            
            # Calculate normalization factor
            scale_factor = (32767 * target_amplitude) / max_amplitude
            
            # Apply normalization with clipping
            normalized_samples = np.clip(samples * scale_factor, -32768, 32767).astype(np.int16)
            
            return normalized_samples.tobytes()
            
        except Exception as e:
            logger.error(f"Vectorized normalization failed: {e}")
            return None
    
    @staticmethod
    def mix_audio_vectorized(data1: bytes, data2: bytes, ratio: float = 0.5) -> Optional[bytes]:
        """Mix audio using vectorized operations"""
        if not NUMPY_AVAILABLE or not data1 or not data2:
            return None
        
        try:
            samples1 = np.frombuffer(data1, dtype=np.int16)
            samples2 = np.frombuffer(data2, dtype=np.int16)
            
            # Use minimum length
            min_len = min(len(samples1), len(samples2))
            if min_len == 0:
                return None
            
            samples1 = samples1[:min_len]
            samples2 = samples2[:min_len]
            
            # Vectorized mixing
            mixed_samples = (samples1 * ratio + samples2 * (1.0 - ratio))
            mixed_samples = np.clip(mixed_samples, -32768, 32767).astype(np.int16)
            
            return mixed_samples.tobytes()
            
        except Exception as e:
            logger.error(f"Vectorized mixing failed: {e}")
            return None

# Memory Management Optimizations
class OptimizedMemoryManager:
    """Advanced memory management for audio processing"""
    
    def __init__(self):
        self.buffer_pools = defaultdict(list)
        self.max_pool_size = 10
        self._lock = threading.Lock()
    
    def get_buffer(self, size: int) -> Optional[bytearray]:
        """Get reusable buffer from pool"""
        with self._lock:
            pool = self.buffer_pools[size]
            if pool:
                return pool.pop()
            else:
                try:
                    return bytearray(size)
                except MemoryError:
                    logger.error(f"Failed to allocate buffer of size {size}")
                    return None
    
    def return_buffer(self, buffer: bytearray):
        """Return buffer to pool for reuse"""
        if not buffer:
            return
        
        size = len(buffer)
        with self._lock:
            pool = self.buffer_pools[size]
            if len(pool) < self.max_pool_size:
                buffer[:] = b'\x00' * len(buffer)  # Clear buffer
                pool.append(buffer)
    
    def clear_pools(self):
        """Clear all buffer pools"""
        with self._lock:
            self.buffer_pools.clear()

# Global memory manager
_memory_manager = OptimizedMemoryManager()

# Optimized Core Functions
if PERFORMANCE_AVAILABLE:
    @performance_monitor("optimized_sine_generation")
else:
    def performance_monitor(name):
        def decorator(func):
            return func
        return decorator

@performance_monitor("optimized_sine_generation")
def generate_sine_wave_optimized(frequency: float, duration: float, 
                               sample_rate: int = 44100, use_vectorized: bool = None) -> Optional[AudioData]:
    """Highly optimized sine wave generation with multiple acceleration techniques"""
    
    # Determine acceleration method
    if use_vectorized is None:
        use_vectorized = _OPT_CONFIG.use_vectorized_operations and duration > 0.1
    
    try:
        # Parameter validation (cached)
        cache_key = f"validation_{frequency}_{duration}_{sample_rate}"
        is_valid = _sine_cache.get(cache_key)
        
        if is_valid is None:
            is_valid = (
                20.0 <= frequency <= 20000.0 and
                0.001 <= duration <= 300.0 and
                8000 <= sample_rate <= 192000
            )
            _sine_cache.put(cache_key, is_valid)
        
        if not is_valid:
            logger.warning(f"Invalid parameters: freq={frequency}, dur={duration}, sr={sample_rate}")
            return None
        
        frames = int(duration * sample_rate)
        if frames <= 0:
            return None
        
        # Try vectorized approach for better performance
        if use_vectorized and NUMPY_AVAILABLE:
            data = VectorizedOps.generate_sine_wave_vectorized(frequency, duration, sample_rate)
            if data:
                return (data, sample_rate, 1, 2)
        
        # Optimized LUT-based generation
        _optimized_lut.initialize()
        
        # Pre-calculate constants
        angular_frequency = frequency / sample_rate
        amplitude = 32767.0
        
        # Check for memory requirements
        estimated_size = frames * 2
        if estimated_size > 100 * 1024 * 1024:  # 100MB limit
            logger.error(f"Audio size too large: {estimated_size / 1024 / 1024:.1f}MB")
            return None
        
        # Use buffer pool for memory efficiency
        buffer = _memory_manager.get_buffer(frames * 2)
        if not buffer:
            logger.error("Failed to allocate audio buffer")
            return None
        
        try:
            # Optimized sample generation
            phase = 0.0
            
            # Process in chunks for better cache performance
            chunk_size = min(_OPT_CONFIG.chunk_size, frames)
            
            for chunk_start in range(0, frames, chunk_size):
                chunk_end = min(chunk_start + chunk_size, frames)
                chunk_size_actual = chunk_end - chunk_start
                
                # Generate chunk samples
                for i in range(chunk_size_actual):
                    sample_value = int(amplitude * _optimized_lut.sin(phase))
                    # Clamp to 16-bit range
                    sample_value = max(-32768, min(32767, sample_value))
                    
                    # Pack directly into buffer
                    offset = (chunk_start + i) * 2
                    struct.pack_into('<h', buffer, offset, sample_value)
                    
                    phase += angular_frequency
                    if phase >= 1.0:
                        phase -= 1.0
            
            # Convert buffer to bytes
            data = bytes(buffer)
            
            return (data, sample_rate, 1, 2)
            
        finally:
            # Return buffer to pool
            _memory_manager.return_buffer(buffer)
    
    except Exception as e:
        logger.error(f"Optimized sine wave generation failed: {e}")
        return None

@performance_monitor("optimized_normalization")
def normalize_audio_optimized(audio_data: AudioData, target_amplitude: float = 0.8) -> Optional[AudioData]:
    """Highly optimized audio normalization"""
    if not audio_data:
        return None
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if sample_width != 2 or not (0.1 <= target_amplitude <= 1.0):
            return None
        
        # Try vectorized approach first
        if _OPT_CONFIG.use_vectorized_operations:
            normalized_data = VectorizedOps.normalize_audio_vectorized(data, target_amplitude)
            if normalized_data:
                return (normalized_data, sample_rate, channels, sample_width)
        
        # Fallback to optimized scalar approach
        if len(data) % 2 != 0:
            return None
        
        num_samples = len(data) // 2
        
        # Use buffer pool
        buffer = _memory_manager.get_buffer(len(data))
        if not buffer:
            return None
        
        try:
            # Find max amplitude in chunks for better cache performance
            max_amplitude = 0
            chunk_size = min(8192, num_samples)
            
            for chunk_start in range(0, num_samples, chunk_size):
                chunk_end = min(chunk_start + chunk_size, num_samples)
                chunk_data = data[chunk_start * 2:chunk_end * 2]
                
                # Unpack chunk
                samples = struct.unpack('<' + 'h' * (len(chunk_data) // 2), chunk_data)
                chunk_max = max(abs(s) for s in samples) if samples else 0
                max_amplitude = max(max_amplitude, chunk_max)
            
            if max_amplitude == 0:
                return audio_data
            
            # Calculate scale factor
            scale_factor = (32767 * target_amplitude) / max_amplitude
            
            # Apply normalization in chunks
            for chunk_start in range(0, num_samples, chunk_size):
                chunk_end = min(chunk_start + chunk_size, num_samples)
                chunk_data = data[chunk_start * 2:chunk_end * 2]
                
                samples = struct.unpack('<' + 'h' * (len(chunk_data) // 2), chunk_data)
                normalized_samples = [
                    max(-32768, min(32767, int(sample * scale_factor)))
                    for sample in samples
                ]
                
                # Pack directly into buffer
                offset = chunk_start * 2
                for i, sample in enumerate(normalized_samples):
                    struct.pack_into('<h', buffer, offset + i * 2, sample)
            
            return (bytes(buffer), sample_rate, channels, sample_width)
            
        finally:
            _memory_manager.return_buffer(buffer)
    
    except Exception as e:
        logger.error(f"Optimized normalization failed: {e}")
        return None

@performance_monitor("optimized_file_io")
def read_wav_file_optimized(filename: str, use_mmap: bool = None) -> Optional[Tuple[AudioData, Dict[str, Any]]]:
    """Optimized WAV file reading with memory mapping for large files"""
    
    if not filename or not os.path.exists(filename):
        return None
    
    if use_mmap is None:
        file_size = os.path.getsize(filename)
        use_mmap = _OPT_CONFIG.use_memory_mapping and file_size > 10 * 1024 * 1024  # 10MB threshold
    
    try:
        import wave
        
        if use_mmap and file_size > 50 * 1024 * 1024:  # 50MB+ files
            # Use memory mapping for very large files
            with open(filename, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    # Read WAV header from memory map
                    with wave.open(mm, 'rb') as wav_file:
                        channels = wav_file.getnchannels()
                        sample_width = wav_file.getsampwidth()
                        sample_rate = wav_file.getframerate()
                        frames = wav_file.getnframes()
                        
                        # Validate parameters
                        if not (1 <= channels <= 8 and sample_width in [1, 2, 4] and 
                               8000 <= sample_rate <= 192000):
                            return None
                        
                        # Read frames in chunks to manage memory
                        chunk_frames = min(frames, sample_rate)  # 1 second chunks
                        all_data = bytearray()
                        
                        for start_frame in range(0, frames, chunk_frames):
                            chunk_size = min(chunk_frames, frames - start_frame)
                            chunk_data = wav_file.readframes(chunk_size)
                            all_data.extend(chunk_data)
                        
                        data = bytes(all_data)
        else:
            # Standard approach for smaller files
            with wave.open(filename, 'rb') as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                frames = wav_file.getnframes()
                
                if not (1 <= channels <= 8 and sample_width in [1, 2, 4] and 
                       8000 <= sample_rate <= 192000):
                    return None
                
                data = wav_file.readframes(frames)
        
        audio_data = (data, sample_rate, channels, sample_width)
        audio_info = {
            'filename': filename,
            'duration': float(frames) / sample_rate if sample_rate > 0 else 0,
            'frames': frames,
            'size_bytes': len(data),
            'channels': channels,
            'sample_rate': sample_rate,
            'sample_width': sample_width
        }
        
        return (audio_data, audio_info)
    
    except Exception as e:
        logger.error(f"Optimized WAV file reading failed for {filename}: {e}")
        return None

@performance_monitor("optimized_audio_processing")
def process_audio_batch_optimized(audio_list: List[AudioData], 
                                operations: List[str]) -> List[Optional[AudioData]]:
    """Batch process multiple audio files with optimized operations"""
    if not audio_list or not operations:
        return []
    
    results = []
    
    try:
        # Pre-warm caches and initialize LUTs
        _optimized_lut.initialize()
        
        # Process each audio file
        for audio_data in audio_list:
            if not audio_data:
                results.append(None)
                continue
            
            current_audio = audio_data
            
            # Apply operations in sequence
            for operation in operations:
                if current_audio is None:
                    break
                
                if operation == 'normalize':
                    current_audio = normalize_audio_optimized(current_audio)
                elif operation == 'trim':
                    # Use optimized trim function if available
                    current_audio = trim_silence_optimized(current_audio)
                elif operation.startswith('volume_'):
                    # Extract volume factor
                    try:
                        factor = float(operation.split('_')[1])
                        current_audio = adjust_volume_optimized(current_audio, factor)
                    except (ValueError, IndexError):
                        pass
            
            results.append(current_audio)
    
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
    
    return results

def trim_silence_optimized(audio_data: AudioData, threshold: float = 0.01) -> Optional[AudioData]:
    """Optimized silence trimming with vectorized operations"""
    if not audio_data or not (0.001 <= threshold <= 0.1):
        return None
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if sample_width != 2 or len(data) % 2 != 0:
            return None
        
        # Try vectorized approach
        if NUMPY_AVAILABLE and len(data) > 8192:  # Use numpy for larger audio
            samples = np.frombuffer(data, dtype=np.int16)
            threshold_abs = int(32767 * threshold)
            
            # Find non-silent regions using vectorized operations
            non_silent = np.abs(samples) > threshold_abs
            non_silent_indices = np.where(non_silent)[0]
            
            if len(non_silent_indices) == 0:
                return audio_data  # All silent
            
            start_idx = non_silent_indices[0]
            end_idx = non_silent_indices[-1]
            
            # Extract trimmed samples
            trimmed_samples = samples[start_idx:end_idx + 1]
            return (trimmed_samples.tobytes(), sample_rate, channels, sample_width)
        
        else:
            # Fallback to optimized scalar approach
            samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            threshold_abs = int(32767 * threshold)
            
            # Find start position
            start_idx = 0
            for i, sample in enumerate(samples):
                if abs(sample) > threshold_abs:
                    start_idx = i
                    break
            else:
                return audio_data
            
            # Find end position (reverse search)
            end_idx = len(samples) - 1
            for i in range(len(samples) - 1, start_idx - 1, -1):
                if abs(samples[i]) > threshold_abs:
                    end_idx = i
                    break
            
            if start_idx == 0 and end_idx == len(samples) - 1:
                return audio_data
            
            trimmed_samples = samples[start_idx:end_idx + 1]
            trimmed_data = struct.pack('<' + 'h' * len(trimmed_samples), *trimmed_samples)
            
            return (trimmed_data, sample_rate, channels, sample_width)
    
    except Exception as e:
        logger.error(f"Optimized silence trimming failed: {e}")
        return None

def adjust_volume_optimized(audio_data: AudioData, volume_factor: float) -> Optional[AudioData]:
    """Optimized volume adjustment"""
    if not audio_data or volume_factor <= 0:
        return None
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if sample_width != 2:
            return None
        
        # Try vectorized approach
        if _OPT_CONFIG.use_vectorized_operations and len(data) > 4096:
            adjusted_data = VectorizedOps.mix_audio_vectorized(data, b'\x00' * len(data), volume_factor)
            if adjusted_data:
                return (adjusted_data, sample_rate, channels, sample_width)
        
        # Fallback to optimized scalar
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        adjusted_samples = [
            max(-32768, min(32767, int(sample * volume_factor)))
            for sample in samples
        ]
        
        adjusted_data = struct.pack('<' + 'h' * len(adjusted_samples), *adjusted_samples)
        return (adjusted_data, sample_rate, channels, sample_width)
    
    except Exception as e:
        logger.error(f"Optimized volume adjustment failed: {e}")
        return None

# Performance monitoring and reporting
def get_optimization_stats() -> Dict[str, Any]:
    """Get comprehensive optimization performance statistics"""
    stats = {
        'numpy_available': NUMPY_AVAILABLE,
        'performance_monitoring': PERFORMANCE_AVAILABLE,
        'optimization_config': {
            'vectorized_ops': _OPT_CONFIG.use_vectorized_operations,
            'memory_mapping': _OPT_CONFIG.use_memory_mapping,
            'cache_size': _OPT_CONFIG.cache_size,
            'lut_size': _OPT_CONFIG.lut_size
        },
        'cache_stats': {
            'sine_cache': _sine_cache.get_stats(),
            'waveform_cache': _waveform_cache.get_stats(),
            'filter_cache': _filter_cache.get_stats()
        },
        'lut_stats': {
            'initialized': _optimized_lut.initialized,
            'size': _optimized_lut.size
        }
    }
    
    # Add performance monitoring stats if available
    if PERFORMANCE_AVAILABLE:
        stats['performance_monitoring'] = {
            'monitor_active': monitor.monitoring,
            'cache_hit_rate': cache.get_hit_rate(),
            'profiler_stats': len(profiler.profiles)
        }
    
    return stats

def optimize_system_for_performance():
    """Apply system-wide performance optimizations"""
    logger.info("Applying system performance optimizations...")
    
    # Initialize caches and LUTs
    _optimized_lut.initialize()
    
    # Configure optimization settings based on system capabilities
    if NUMPY_AVAILABLE:
        _OPT_CONFIG.use_vectorized_operations = True
        logger.info("NumPy acceleration enabled")
    
    # Start performance monitoring if available
    if PERFORMANCE_AVAILABLE:
        if not monitor.monitoring:
            monitor.start_monitoring(interval=5.0)
            logger.info("Performance monitoring started")
        
        # Apply resource optimizations
        resource_manager.optimize_for_performance()
    
    # Clear old cache entries
    _sine_cache.clear()
    _waveform_cache.clear()
    _filter_cache.clear()
    _memory_manager.clear_pools()
    
    logger.info("System optimization completed")

# Auto-optimize on import
optimize_system_for_performance()

if __name__ == '__main__':
    # Performance benchmark
    import time
    
    print("🚀 Performance Optimization Benchmark")
    
    # Test parameters
    frequency = 440.0
    duration = 2.0
    sample_rate = 44100
    
    print(f"\nTest: {frequency}Hz sine wave, {duration}s duration, {sample_rate}Hz sample rate")
    
    # Benchmark standard generation
    start_time = time.perf_counter()
    try:
        from core import generate_sine_wave as standard_generate
        audio_standard = standard_generate(frequency, duration, sample_rate)
        standard_time = time.perf_counter() - start_time
        print(f"Standard generation: {standard_time:.3f}s")
    except ImportError:
        print("Standard generation: Not available")
        standard_time = float('inf')
    
    # Benchmark optimized generation
    start_time = time.perf_counter()
    audio_optimized = generate_sine_wave_optimized(frequency, duration, sample_rate)
    optimized_time = time.perf_counter() - start_time
    print(f"Optimized generation: {optimized_time:.3f}s")
    
    # Calculate improvement
    if standard_time != float('inf'):
        improvement = (standard_time - optimized_time) / standard_time * 100
        print(f"Performance improvement: {improvement:.1f}%")
    
    # Display optimization stats
    stats = get_optimization_stats()
    print(f"\nOptimization Statistics:")
    print(f"- NumPy acceleration: {'✅' if stats['numpy_available'] else '❌'}")
    print(f"- Vectorized operations: {'✅' if stats['optimization_config']['vectorized_ops'] else '❌'}")
    print(f"- LUT initialized: {'✅' if stats['lut_stats']['initialized'] else '❌'}")
    print(f"- Cache hit rate: {stats['cache_stats']['sine_cache']['hit_rate']:.2f}")