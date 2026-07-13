#!/usr/bin/env python3
"""
Performance Optimization Module for Chameleon Audio System
Provides parallel processing, SIMD-like operations (via the array module,
not real vector instructions -- see SIMDOperations), and memory efficiency
"""

import os
import sys
import array
import struct
import multiprocessing as mp
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import lru_cache
import logging

logger = logging.getLogger("chameleon.performance")


def get_optimal_worker_count() -> int:
    """Determine optimal number of workers based on CPU count"""
    cpu_count = os.cpu_count() or 1
    env_max = os.getenv("CHAMELEON_MAX_WORKERS")

    if env_max:
        try:
            return max(1, min(int(env_max), cpu_count))
        except ValueError:
            pass

    # Use 75% of available cores for audio processing
    return max(1, int(cpu_count * 0.75))


class ParallelProcessor:
    """Parallel processing utilities for batch operations"""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or get_optimal_worker_count()

    def process_files_parallel(
        self,
        files: List[Path],
        process_func: Callable,
        use_processes: bool = False
    ) -> List[Any]:
        """Process multiple files in parallel

        Args:
            files: List of file paths to process
            process_func: Function to apply to each file
            use_processes: Use processes instead of threads for CPU-bound work

        Returns:
            List of results
        """
        if len(files) <= 1:
            return [process_func(f) for f in files]

        executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

        with executor_class(max_workers=self.max_workers) as executor:
            results = list(executor.map(process_func, files))

        return results

    def process_chunks_parallel(
        self,
        data: bytes,
        chunk_size: int,
        process_func: Callable[[bytes], bytes]
    ) -> bytes:
        """Process data in parallel chunks

        Args:
            data: Input data
            chunk_size: Size of each chunk
            process_func: Function to apply to each chunk

        Returns:
            Processed data
        """
        chunks = [
            data[i:i+chunk_size]
            for i in range(0, len(data), chunk_size)
        ]

        if len(chunks) <= 1:
            return b''.join(process_func(c) for c in chunks)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            processed = list(executor.map(process_func, chunks))

        return b''.join(processed)


class SIMDOperations:
    """SIMD-like operations using array module and optimized loops"""

    @staticmethod
    def normalize_int16(samples: array.array, target_peak: float = 0.95) -> array.array:
        """Fast normalization for int16 samples"""
        if not samples:
            return samples

        # Find peak using max/min
        peak = max(abs(max(samples)), abs(min(samples)))
        if peak == 0:
            return samples

        # Calculate scale factor
        scale = int((target_peak * 32767) / peak)

        # Apply scaling
        result = array.array('h', (min(32767, max(-32768, s * scale)) for s in samples))
        return result

    @staticmethod
    def mix_int16(samples1: array.array, samples2: array.array) -> array.array:
        """Fast mixing of two int16 sample arrays"""
        min_len = min(len(samples1), len(samples2))

        # Average mix with clipping
        result = array.array('h', (
            min(32767, max(-32768, (samples1[i] + samples2[i]) // 2))
            for i in range(min_len)
        ))

        # Append remaining samples
        if len(samples1) > min_len:
            result.extend(samples1[min_len:])
        elif len(samples2) > min_len:
            result.extend(samples2[min_len:])

        return result

    @staticmethod
    def apply_gain_int16(samples: array.array, gain: float) -> array.array:
        """Apply gain to int16 samples"""
        scale = int(gain * 256)  # Fixed-point scale

        result = array.array('h', (
            min(32767, max(-32768, (s * scale) >> 8))
            for s in samples
        ))

        return result

    @staticmethod
    def calculate_rms(samples: array.array) -> float:
        """Fast RMS calculation"""
        if not samples:
            return 0.0

        sum_squares = sum(s * s for s in samples)
        return (sum_squares / len(samples)) ** 0.5 / 32768.0

    @staticmethod
    def detect_silence(
        samples: array.array,
        threshold: float = 0.01,
        window_size: int = 2048
    ) -> List[Tuple[int, int]]:
        """Detect silent regions using windowed RMS"""
        silence_regions = []
        threshold_int = int(threshold * 32767)

        i = 0
        while i < len(samples):
            window = samples[i:i+window_size]
            if not window:
                break

            # Check if window is silent
            if all(abs(s) < threshold_int for s in window):
                start = i
                # Extend silence region
                while i < len(samples):
                    window = samples[i:i+window_size]
                    if not window or not all(abs(s) < threshold_int for s in window):
                        break
                    i += window_size

                silence_regions.append((start, i))
            else:
                i += window_size

        return silence_regions


class MemoryOptimizer:
    """Memory optimization utilities"""

    @staticmethod
    def estimate_memory_usage(file_path: Path) -> int:
        """Estimate memory needed to process file"""
        file_size = file_path.stat().st_size
        # Typical overhead: 2x for processing buffer
        return file_size * 2

    @staticmethod
    def can_process_in_memory(file_path: Path) -> bool:
        """Check if file can be processed in memory"""
        import psutil

        available = psutil.virtual_memory().available
        required = MemoryOptimizer.estimate_memory_usage(file_path)

        # Use only 50% of available memory
        return required < (available * 0.5)

    @staticmethod
    def stream_large_file(
        file_path: Path,
        chunk_size: int,
        process_func: Callable[[bytes], bytes],
        output_path: Path
    ) -> None:
        """Stream processing for large files"""
        with open(file_path, 'rb') as infile, open(output_path, 'wb') as outfile:
            # Copy WAV header
            header = infile.read(44)
            outfile.write(header)

            # Process chunks
            while True:
                chunk = infile.read(chunk_size)
                if not chunk:
                    break

                processed = process_func(chunk)
                outfile.write(processed)


class CacheManager:
    """LRU cache for analysis results and intermediate data"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: dict = {}
        self._access_order: List[str] = []

    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if key in self._cache:
            # Update access order
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set cached value"""
        if key in self._cache:
            # Update existing
            self._access_order.remove(key)
        elif len(self._cache) >= self.max_size:
            # Evict oldest
            oldest = self._access_order.pop(0)
            del self._cache[oldest]

        self._cache[key] = value
        self._access_order.append(key)

    def clear(self) -> None:
        """Clear cache"""
        self._cache.clear()
        self._access_order.clear()


@lru_cache(maxsize=128)
def get_optimal_chunk_size(file_size: int) -> int:
    """Calculate optimal chunk size based on file size"""
    if file_size < 1024 * 1024:  # < 1MB
        return 8192
    elif file_size < 10 * 1024 * 1024:  # < 10MB
        return 65536
    elif file_size < 100 * 1024 * 1024:  # < 100MB
        return 262144
    else:
        return 1048576  # 1MB chunks for very large files


if __name__ == "__main__":
    print("Testing Performance Optimizer...")

    # Test parallel processing
    processor = ParallelProcessor(max_workers=4)
    test_files = [Path(f"test{i}.wav") for i in range(10)]

    def mock_process(path):
        return f"Processed {path}"

    # Note: Would fail with actual files, but demonstrates API
    # results = processor.process_files_parallel(test_files, mock_process)

    # Test SIMD operations
    samples = array.array('h', [1000, 2000, -1000, -2000, 0, 500])
    normalized = SIMDOperations.normalize_int16(samples)
    print(f"Normalized samples: {list(normalized)[:6]}")

    rms = SIMDOperations.calculate_rms(samples)
    print(f"RMS: {rms:.4f}")

    # Test silence detection
    silent_samples = array.array('h', [10, -10, 5, -5] * 100)
    loud_samples = array.array('h', [10000, -10000] * 100)
    mixed = array.array('h')
    mixed.extend(silent_samples)
    mixed.extend(loud_samples)
    mixed.extend(silent_samples)

    silence_regions = SIMDOperations.detect_silence(mixed, threshold=0.01)
    print(f"Silence regions: {silence_regions[:3]}")

    # Test cache
    cache = CacheManager(max_size=5)
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    print(f"Cache get: {cache.get('key1')}")

    print("Performance optimizer tests completed")
