#!/usr/bin/env python3
"""
Optimized Audio Processing with NumPy support
Falls back to pure Python if NumPy not available
"""

import array
import math
from typing import Union, Optional

# Try to import numpy for optimized operations
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

class OptimizedProcessor:
    """Audio processor with NumPy optimization when available"""

    def __init__(self):
        self.use_numpy = HAS_NUMPY

    def to_numpy(self, samples: Union[array.array, 'np.ndarray']) -> 'np.ndarray':
        """Convert to numpy array if numpy available"""
        if not HAS_NUMPY:
            return samples
        if isinstance(samples, np.ndarray):
            return samples
        return np.frombuffer(samples, dtype=np.int16)

    def from_numpy(self, data: Union[array.array, 'np.ndarray']) -> array.array:
        """Convert from numpy to array.array"""
        if not HAS_NUMPY or isinstance(data, array.array):
            return data
        return array.array('h', data.astype(np.int16))

    def normalize_fast(self, samples: Union[array.array, 'np.ndarray'],
                      target_peak: float = 0.95) -> Union[array.array, 'np.ndarray']:
        """Fast normalize with numpy if available"""
        if HAS_NUMPY:
            data = self.to_numpy(samples)
            peak = np.abs(data).max()
            if peak == 0:
                return samples
            scale = (target_peak * 32767) / peak
            result = (data * scale).clip(-32767, 32767).astype(np.int16)
            return self.from_numpy(result)
        else:
            # Fallback to pure Python
            if not samples:
                return samples
            peak = max(abs(min(samples)), abs(max(samples)))
            if peak == 0:
                return samples
            scale = (target_peak * 32767) / peak
            return array.array('h', [int(max(min(s * scale, 32767), -32767)) for s in samples])

    def apply_gain_fast(self, samples: Union[array.array, 'np.ndarray'],
                       gain_db: float) -> Union[array.array, 'np.ndarray']:
        """Fast gain application"""
        gain_linear = 10 ** (gain_db / 20)

        if HAS_NUMPY:
            data = self.to_numpy(samples)
            result = (data * gain_linear).clip(-32767, 32767).astype(np.int16)
            return self.from_numpy(result)
        else:
            result = array.array('h')
            for s in samples:
                amplified = int(s * gain_linear)
                result.append(max(min(amplified, 32767), -32767))
            return result

    def mix_fast(self, samples1: Union[array.array, 'np.ndarray'],
                samples2: Union[array.array, 'np.ndarray'],
                ratio: float = 0.5) -> Union[array.array, 'np.ndarray']:
        """Fast mixing of two signals"""
        if HAS_NUMPY:
            data1 = self.to_numpy(samples1)
            data2 = self.to_numpy(samples2)
            min_len = min(len(data1), len(data2))
            mixed = (data1[:min_len] * ratio + data2[:min_len] * (1 - ratio))
            result = mixed.clip(-32767, 32767).astype(np.int16)
            return self.from_numpy(result)
        else:
            length = min(len(samples1), len(samples2))
            result = array.array('h')
            for i in range(length):
                mixed = int(samples1[i] * ratio + samples2[i] * (1 - ratio))
                result.append(max(min(mixed, 32767), -32767))
            return result

    def rms_fast(self, samples: Union[array.array, 'np.ndarray']) -> float:
        """Fast RMS calculation"""
        if HAS_NUMPY:
            data = self.to_numpy(samples)
            return np.sqrt(np.mean(data.astype(np.float32) ** 2))
        else:
            if not samples:
                return 0.0
            sum_squares = sum(s * s for s in samples)
            return math.sqrt(sum_squares / len(samples))

    def fft_fast(self, samples: Union[array.array, 'np.ndarray']) -> list:
        """Fast FFT using numpy if available"""
        if HAS_NUMPY:
            data = self.to_numpy(samples)
            # Pad to power of 2 for faster FFT
            n = len(data)
            n_fft = 2 ** int(math.ceil(math.log2(n)))
            padded = np.pad(data, (0, n_fft - n), mode='constant')
            fft_result = np.fft.fft(padded)
            magnitude = np.abs(fft_result[:n_fft // 2])
            return magnitude.tolist()
        else:
            # Fallback to simple DFT
            size = min(512, len(samples))
            spectrum = []
            for k in range(size // 2):
                real = 0
                imag = 0
                for n in range(size):
                    angle = -2 * math.pi * k * n / size
                    real += samples[n] * math.cos(angle)
                    imag += samples[n] * math.sin(angle)
                magnitude = math.sqrt(real * real + imag * imag)
                spectrum.append(magnitude)
            return spectrum

    def convolve_fast(self, samples: Union[array.array, 'np.ndarray'],
                     kernel: list) -> Union[array.array, 'np.ndarray']:
        """Fast convolution for filters"""
        if HAS_NUMPY:
            data = self.to_numpy(samples)
            result = np.convolve(data, kernel, mode='same')
            return self.from_numpy(result.clip(-32767, 32767).astype(np.int16))
        else:
            # Simple convolution
            result = array.array('h')
            k_len = len(kernel)
            k_center = k_len // 2

            for i in range(len(samples)):
                sum_val = 0
                for j, k_val in enumerate(kernel):
                    idx = i - k_center + j
                    if 0 <= idx < len(samples):
                        sum_val += samples[idx] * k_val
                result.append(int(max(min(sum_val, 32767), -32767)))
            return result

    def resample_fast(self, samples: Union[array.array, 'np.ndarray'],
                     orig_rate: int, target_rate: int) -> Union[array.array, 'np.ndarray']:
        """Fast resampling"""
        if orig_rate == target_rate:
            return samples

        ratio = target_rate / orig_rate

        if HAS_NUMPY:
            data = self.to_numpy(samples)
            # Use linear interpolation
            old_indices = np.arange(len(data))
            new_length = int(len(data) * ratio)
            new_indices = np.linspace(0, len(data) - 1, new_length)
            resampled = np.interp(new_indices, old_indices, data)
            return self.from_numpy(resampled.astype(np.int16))
        else:
            result = array.array('h')
            for i in range(int(len(samples) * ratio)):
                pos = i / ratio
                idx = int(pos)
                frac = pos - idx
                if idx + 1 < len(samples):
                    sample = samples[idx] * (1 - frac) + samples[idx + 1] * frac
                else:
                    sample = samples[min(idx, len(samples) - 1)]
                result.append(int(sample))
            return result

    def correlate_fast(self, samples1: Union[array.array, 'np.ndarray'],
                      samples2: Union[array.array, 'np.ndarray']) -> list:
        """Fast cross-correlation"""
        if HAS_NUMPY:
            data1 = self.to_numpy(samples1)
            data2 = self.to_numpy(samples2)
            correlation = np.correlate(data1, data2, mode='same')
            return correlation.tolist()
        else:
            # Simple correlation
            result = []
            n = len(samples1)
            m = len(samples2)
            for lag in range(-m // 2, m // 2):
                sum_val = 0
                count = 0
                for i in range(max(0, -lag), min(n, m - lag)):
                    sum_val += samples1[i] * samples2[i + lag]
                    count += 1
                result.append(sum_val / count if count > 0 else 0)
            return result

    def envelope_fast(self, samples: Union[array.array, 'np.ndarray'],
                     window_size: int = 512) -> Union[array.array, 'np.ndarray']:
        """Fast envelope detection"""
        if HAS_NUMPY:
            data = self.to_numpy(samples)
            # Simple envelope using moving maximum
            envelope = np.zeros_like(data)
            for i in range(len(data)):
                start = max(0, i - window_size // 2)
                end = min(len(data), i + window_size // 2)
                envelope[i] = np.abs(data[start:end]).max()
            return self.from_numpy(envelope.astype(np.int16))
        else:
            result = array.array('h')
            for i in range(len(samples)):
                start = max(0, i - window_size // 2)
                end = min(len(samples), i + window_size // 2)
                window_max = max(abs(samples[j]) for j in range(start, end))
                result.append(window_max)
            return result

    def zero_pad(self, samples: Union[array.array, 'np.ndarray'],
                target_length: int) -> Union[array.array, 'np.ndarray']:
        """Pad with zeros to target length"""
        current_length = len(samples)
        if current_length >= target_length:
            return samples

        if HAS_NUMPY:
            data = self.to_numpy(samples)
            padded = np.pad(data, (0, target_length - current_length), mode='constant')
            return self.from_numpy(padded)
        else:
            result = array.array('h', samples)
            result.extend([0] * (target_length - current_length))
            return result


def benchmark():
    """Benchmark optimized vs standard operations"""
    import time

    processor = OptimizedProcessor()

    # Create test data
    test_size = 44100 * 10  # 10 seconds
    test_samples = array.array('h', [int(10000 * math.sin(2 * math.pi * 440 * i / 44100))
                                     for i in range(test_size)])

    print("Performance Benchmark")
    print(f"NumPy available: {HAS_NUMPY}")
    print(f"Test data: {test_size} samples\n")

    operations = [
        ('Normalize', lambda: processor.normalize_fast(test_samples)),
        ('Apply Gain', lambda: processor.apply_gain_fast(test_samples, 6.0)),
        ('RMS', lambda: processor.rms_fast(test_samples)),
        ('FFT (first 4096)', lambda: processor.fft_fast(test_samples[:4096])),
        ('Resample', lambda: processor.resample_fast(test_samples[:44100], 44100, 22050)),
    ]

    for name, operation in operations:
        start = time.time()
        result = operation()
        elapsed = time.time() - start
        print(f"{name}: {elapsed*1000:.2f} ms")

    print("\nBenchmark complete")


if __name__ == '__main__':
    benchmark()