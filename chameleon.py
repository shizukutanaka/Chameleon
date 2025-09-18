#!/usr/bin/env python3
"""
Chameleon Audio System - Unified Optimized Edition
High-performance audio processing with automatic optimization
"""

import array
import json
import logging
import math
import os
import sys
import time
import wave
import multiprocessing
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union
from functools import lru_cache
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

# Try to import numpy for optimized operations
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Setup logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Audio constants
SAMPLE_RATE = 44100
CHANNELS = 1
SAMPLE_WIDTH = 2
MAX_INT16 = 32767

# Standard sample rates
STANDARD_SAMPLE_RATES = [8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000]

# Audio quality presets
QUALITY_PRESETS = {
    'phone': {'sample_rate': 8000, 'channels': 1, 'bit_depth': 16},
    'voice': {'sample_rate': 16000, 'channels': 1, 'bit_depth': 16},
    'radio': {'sample_rate': 22050, 'channels': 2, 'bit_depth': 16},
    'cd': {'sample_rate': 44100, 'channels': 2, 'bit_depth': 16},
    'studio': {'sample_rate': 48000, 'channels': 2, 'bit_depth': 24},
    'hifi': {'sample_rate': 96000, 'channels': 2, 'bit_depth': 24}
}

class AudioProcessor:
    """High-performance audio processor with automatic optimization"""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.use_numpy = HAS_NUMPY
        self._cache = {}  # Cache for repeated operations
        self._error_count = 0
        self._last_error = None
        self._operation_cache = {}  # Cache for operation results
        self._cache_hits = 0
        self._cache_misses = 0

    @staticmethod
    def db_to_linear(db: float) -> float:
        """Convert dB to linear scale"""
        return 10 ** (db / 20)

    @staticmethod
    def linear_to_db(linear: float) -> float:
        """Convert linear to dB scale"""
        if linear <= 0:
            return -float('inf')
        return 20 * math.log10(linear)

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration as MM:SS or HH:MM:SS"""
        if seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _to_numpy(self, samples: Union[array.array, 'np.ndarray']) -> 'np.ndarray':
        """Convert to numpy array if available"""
        if not HAS_NUMPY:
            return samples
        if isinstance(samples, np.ndarray):
            return samples
        return np.frombuffer(samples, dtype=np.int16)

    def _from_numpy(self, data: Union[array.array, 'np.ndarray']) -> array.array:
        """Convert from numpy to array.array"""
        if not HAS_NUMPY or isinstance(data, array.array):
            return data
        return array.array('h', data.astype(np.int16))

    @lru_cache(maxsize=32)
    def _get_file_info(self, filepath: str) -> Optional[Dict]:
        """Get cached file information"""
        try:
            with wave.open(filepath, 'rb') as wav:
                params = wav.getparams()
                return {
                    'channels': params.nchannels,
                    'sample_rate': params.framerate,
                    'duration': params.nframes / params.framerate,
                    'nframes': params.nframes,
                    'sample_width': params.sampwidth
                }
        except Exception:
            return None

    def get_optimal_chunk_size(self, file_size: int, available_memory: int = None) -> int:
        """Calculate optimal chunk size for processing"""
        if available_memory is None:
            available_memory = 64 * 1024 * 1024  # Default 64MB
        target_memory = available_memory // 4
        samples_per_chunk = target_memory // 2
        samples_per_chunk = (samples_per_chunk // 44100) * 44100
        return max(44100, min(samples_per_chunk, 44100 * 60))

    def detect_format(self, filepath: str) -> Optional[str]:
        """Enhanced audio format detection with more formats"""
        try:
            with open(filepath, 'rb') as f:
                header = f.read(16)

                # WAV format
                if header.startswith(b'RIFF') and len(header) >= 12 and header[8:12] == b'WAVE':
                    return 'wav'
                # MP3 format
                elif header.startswith(b'ID3') or header.startswith(b'\xff\xfb') or header.startswith(b'\xff\xf3'):
                    return 'mp3'
                # FLAC format
                elif header.startswith(b'fLaC'):
                    return 'flac'
                # OGG/Vorbis format
                elif header.startswith(b'OggS'):
                    return 'ogg'
                # AIFF format
                elif header.startswith(b'FORM') and header[8:12] == b'AIFF':
                    return 'aiff'
                # AU format
                elif header.startswith(b'.snd'):
                    return 'au'
                # Raw PCM (heuristic)
                elif all(b < 128 for b in header[:4]):
                    return 'raw'

                return None
        except:
            return None

    def load_wav(self, filepath: str) -> Tuple[array.array, Dict]:
        """Load WAV file with caching and error recovery"""
        try:
            # Quick format check
            if self.detect_format(filepath) != 'wav':
                logger.warning(f"File {filepath} may not be a valid WAV file")

            # Check cache first
            cache_key = f"load_{filepath}_{os.path.getmtime(filepath)}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            with wave.open(filepath, 'rb') as wav:
                params = wav.getparams()
                frames = wav.readframes(params.nframes)
                samples = array.array('h', frames)

                info = {
                    'channels': params.nchannels,
                    'sample_rate': params.framerate,
                    'duration': params.nframes / params.framerate,
                    'nframes': params.nframes,
                    'sample_width': params.sampwidth
                }

                # Cache if file is small enough
                if len(samples) < 10 * self.sample_rate:  # Cache files < 10 seconds
                    self._cache[cache_key] = (array.array('h', samples), info.copy())

                return samples, info

        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            self._error_count += 1
            self._last_error = str(e)

            # Try recovery with raw PCM
            try:
                with open(filepath, 'rb') as f:
                    data = f.read()
                    samples = array.array('h', data)
                    info = {'channels': 1, 'sample_rate': self.sample_rate,
                           'duration': len(samples) / self.sample_rate}
                    return samples, info
            except:
                return array.array('h'), {}

    def save_wav(self, filepath: str, samples: Union[array.array, 'np.ndarray'],
                 sample_rate: Optional[int] = None, channels: int = CHANNELS) -> bool:
        """Save samples to WAV file with automatic format conversion"""
        try:
            rate = sample_rate or self.sample_rate

            # Convert numpy array if needed
            if HAS_NUMPY and isinstance(samples, np.ndarray):
                samples = self._from_numpy(samples)

            with wave.open(filepath, 'wb') as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(SAMPLE_WIDTH)
                wav.setframerate(rate)
                wav.writeframes(samples.tobytes())
            return True

        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")
            self._error_count += 1
            self._last_error = str(e)

            # Try alternative save method
            try:
                # Save as raw PCM
                with open(filepath + '.raw', 'wb') as f:
                    f.write(samples.tobytes())
                logger.info(f"Saved as raw PCM: {filepath}.raw")
                return True
            except:
                return False

    def normalize(self, samples: Union[array.array, 'np.ndarray'],
                  target_peak: float = 0.95) -> Union[array.array, 'np.ndarray']:
        """Normalize audio with automatic optimization and caching"""
        if not samples or len(samples) == 0:
            return samples

        # Cache key based on first/last samples and length
        cache_key = ('normalize', len(samples), samples[0] if samples else 0,
                     samples[-1] if samples else 0, target_peak)

        if cache_key in self._operation_cache:
            self._cache_hits += 1
            return self._operation_cache[cache_key]

        self._cache_misses += 1

        # Use numpy if available for faster processing
        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            peak = np.abs(data).max()
            if peak == 0:
                return samples
            scale = (target_peak * MAX_INT16) / peak
            result = (data * scale).clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            result = self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            # Pure Python fallback with optimized list comprehension
            peak = max(abs(min(samples)), abs(max(samples)))
            if peak == 0:
                return samples
            scale = (target_peak * MAX_INT16) / peak
            result = array.array('h', [max(min(int(s * scale), MAX_INT16), -MAX_INT16) for s in samples])

        # Cache result if small enough
        if len(samples) < 100000:  # Cache only small operations
            self._operation_cache[cache_key] = result

        return result

    def amplify(self, samples: Union[array.array, 'np.ndarray'], gain_db: float) -> Union[array.array, 'np.ndarray']:
        """Apply gain with optimization"""
        gain_linear = 10 ** (gain_db / 20)

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            result = (data * gain_linear).clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            result = array.array('h')
            for s in samples:
                amplified = int(s * gain_linear)
                result.append(max(min(amplified, MAX_INT16), -MAX_INT16))
            return result

    def fade(self, samples: Union[array.array, 'np.ndarray'],
             fade_in_ms: int = 0, fade_out_ms: int = 0) -> Union[array.array, 'np.ndarray']:
        """Apply fade with optimization"""
        if not samples:
            return samples

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples).astype(np.float32)

            # Fade in
            if fade_in_ms > 0:
                fade_samples = int((fade_in_ms / 1000) * self.sample_rate)
                fade_samples = min(fade_samples, len(data))
                fade_curve = np.linspace(0, 1, fade_samples)
                data[:fade_samples] *= fade_curve

            # Fade out
            if fade_out_ms > 0:
                fade_samples = int((fade_out_ms / 1000) * self.sample_rate)
                fade_samples = min(fade_samples, len(data))
                fade_curve = np.linspace(1, 0, fade_samples)
                data[-fade_samples:] *= fade_curve

            result = data.clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            result = array.array('h', samples)

            # Fade in
            if fade_in_ms > 0:
                fade_samples = int((fade_in_ms / 1000) * self.sample_rate)
                for i in range(min(fade_samples, len(result))):
                    factor = i / fade_samples
                    result[i] = int(result[i] * factor)

            # Fade out
            if fade_out_ms > 0:
                fade_samples = int((fade_out_ms / 1000) * self.sample_rate)
                start = len(result) - fade_samples
                for i in range(max(0, start), len(result)):
                    factor = (len(result) - i) / fade_samples
                    result[i] = int(result[i] * factor)

            return result

    def trim_silence(self, samples: Union[array.array, 'np.ndarray'],
                     threshold_db: float = -40) -> Union[array.array, 'np.ndarray']:
        """Remove silence with optimization"""
        if not samples:
            return samples

        threshold = MAX_INT16 * (10 ** (threshold_db / 20))

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            mask = np.abs(data) > threshold
            indices = np.where(mask)[0]
            if len(indices) == 0:
                return samples[:0]  # Return empty array of same type
            return data[indices[0]:indices[-1]+1]
        else:
            # Find start
            start = 0
            for i, s in enumerate(samples):
                if abs(s) > threshold:
                    start = i
                    break

            # Find end
            end = len(samples)
            for i in range(len(samples) - 1, -1, -1):
                if abs(samples[i]) > threshold:
                    end = i + 1
                    break

            return samples[start:end]

    def reverse(self, samples: Union[array.array, 'np.ndarray']) -> Union[array.array, 'np.ndarray']:
        """Reverse audio"""
        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            return data[::-1]
        else:
            return array.array('h', reversed(samples))

    def change_speed(self, samples: Union[array.array, 'np.ndarray'],
                     speed_factor: float) -> Union[array.array, 'np.ndarray']:
        """Change playback speed with optimization"""
        if speed_factor == 1.0:
            return samples

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            # High-quality linear interpolation
            old_length = len(data)
            new_length = int(old_length / speed_factor)
            old_indices = np.arange(0, old_length)
            new_indices = np.linspace(0, old_length - 1, new_length)
            result = np.interp(new_indices, old_indices, data).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            # Improved linear interpolation fallback
            if not samples:
                return array.array('h')

            ratio = speed_factor
            output_length = int(len(samples) / ratio)
            result = array.array('h')

            for i in range(output_length):
                source_pos = i * ratio
                source_index = int(source_pos)
                fraction = source_pos - source_index

                if source_index >= len(samples) - 1:
                    result.append(samples[-1])
                else:
                    # Linear interpolation
                    sample1 = samples[source_index]
                    sample2 = samples[source_index + 1]
                    interpolated = int(sample1 + (sample2 - sample1) * fraction)
                    result.append(max(-32767, min(32767, interpolated)))

            return result

    def detect_voice_activity(self, samples: Union[array.array, 'np.ndarray'],
                            window_size: int = 1024) -> List[Tuple[int, int]]:
        """Detect voice activity segments in audio"""
        if not samples or len(samples) == 0:
            return []

        segments = []
        in_voice = False
        segment_start = 0

        # Energy and zero-crossing thresholds
        energy_threshold = 0.01 * MAX_INT16 * MAX_INT16
        zcr_low = 0.01
        zcr_high = 0.1

        for i in range(0, len(samples) - window_size, window_size):
            window = samples[i:i + window_size]

            # Calculate energy
            energy = sum(s * s for s in window)

            # Calculate zero crossing rate
            zero_crossings = sum(1 for j in range(1, len(window))
                                if (window[j-1] >= 0) != (window[j] >= 0))
            zcr = zero_crossings / len(window)

            # Voice detection logic
            is_voice = energy > energy_threshold and zcr_low < zcr < zcr_high

            if is_voice and not in_voice:
                segment_start = i
                in_voice = True
            elif not is_voice and in_voice:
                segments.append((segment_start, i))
                in_voice = False

        if in_voice:
            segments.append((segment_start, len(samples)))

        return segments

    def resample(self, samples: Union[array.array, 'np.ndarray'],
                 original_rate: int, target_rate: int) -> Union[array.array, 'np.ndarray']:
        """High-quality resampling with optimization"""
        if original_rate == target_rate:
            return samples

        speed_factor = original_rate / target_rate
        return self.change_speed(samples, speed_factor)

    def mix(self, samples1: Union[array.array, 'np.ndarray'],
            samples2: Union[array.array, 'np.ndarray'],
            ratio: float = 0.5) -> Union[array.array, 'np.ndarray']:
        """Mix two audio signals with optimization"""
        if self.use_numpy and HAS_NUMPY:
            data1 = self._to_numpy(samples1)
            data2 = self._to_numpy(samples2)
            min_len = min(len(data1), len(data2))
            mixed = (data1[:min_len] * ratio + data2[:min_len] * (1 - ratio))
            result = mixed.clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples1, array.array) else result
        else:
            length = min(len(samples1), len(samples2))
            result = array.array('h')
            for i in range(length):
                mixed = int(samples1[i] * ratio + samples2[i] * (1 - ratio))
                result.append(max(min(mixed, MAX_INT16), -MAX_INT16))
            return result

    def validate_audio(self, samples: Union[array.array, 'np.ndarray']) -> Dict:
        """Comprehensive audio quality validation"""
        if not samples or len(samples) == 0:
            return {'valid': False, 'issues': ['Empty audio']}

        issues = []

        # Check for clipping
        max_val = 32767 * 0.98
        clipped_samples = sum(1 for s in samples if abs(s) >= max_val)
        clip_ratio = clipped_samples / len(samples)

        if clip_ratio > 0.01:  # More than 1% clipped
            issues.append(f"High clipping detected: {clip_ratio:.2%}")
        elif clip_ratio > 0:
            issues.append(f"Minor clipping detected: {clip_ratio:.2%}")

        # Check for silence
        silent_threshold = 32767 * (10 ** (-60 / 20))  # -60dB
        silent_samples = sum(1 for s in samples if abs(s) < silent_threshold)
        silence_ratio = silent_samples / len(samples)

        if silence_ratio > 0.95:
            issues.append(f"Excessive silence: {silence_ratio:.1%}")

        # Check dynamic range
        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples).astype(np.float32)
            rms = np.sqrt(np.mean(data ** 2))
            peak = np.abs(data).max()
        else:
            squared_sum = sum(s * s for s in samples)
            rms = math.sqrt(squared_sum / len(samples))
            peak = max(abs(min(samples)), abs(max(samples)))

        if rms > 0:
            dynamic_range = 20 * math.log10(peak / rms)
            if dynamic_range < 3:
                issues.append(f"Poor dynamic range: {dynamic_range:.1f}dB")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'clip_ratio': clip_ratio,
            'silence_ratio': silence_ratio,
            'dynamic_range': dynamic_range if rms > 0 else 0
        }

    def get_statistics(self, samples: Union[array.array, 'np.ndarray']) -> Dict:
        """Get audio statistics with optimization"""
        if not samples or len(samples) == 0:
            return {'rms': 0, 'peak': 0, 'avg': 0, 'duration': 0}

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples).astype(np.float32)
            rms = np.sqrt(np.mean(data ** 2))
            peak = np.abs(data).max()
            avg = np.mean(np.abs(data))
        else:
            squared_sum = sum(s * s for s in samples)
            rms = math.sqrt(squared_sum / len(samples))
            peak = max(abs(min(samples)), abs(max(samples)))
            avg = sum(abs(s) for s in samples) / len(samples)

        # Add quality metrics
        validation = self.validate_audio(samples)

        # Add frequency analysis
        zero_crossings = self._count_zero_crossings(samples)
        estimated_freq = self._estimate_frequency(samples, zero_crossings)

        return {
            'rms': float(rms),
            'peak': float(peak),
            'avg': float(avg),
            'duration': len(samples) / self.sample_rate,
            'samples': len(samples),
            'rms_db': 20 * math.log10(rms / 32767) if rms > 0 else -float('inf'),
            'peak_db': 20 * math.log10(peak / 32767) if peak > 0 else -float('inf'),
            'zero_crossings': zero_crossings,
            'estimated_frequency': estimated_freq,
            'quality': validation
        }

    def _count_zero_crossings(self, samples: Union[array.array, 'np.ndarray']) -> int:
        """Count zero crossings for frequency estimation"""
        if len(samples) < 2:
            return 0

        crossings = 0
        prev_sign = samples[0] >= 0

        for sample in samples[1:]:
            current_sign = sample >= 0
            if current_sign != prev_sign:
                crossings += 1
            prev_sign = current_sign

        return crossings

    def _estimate_frequency(self, samples: Union[array.array, 'np.ndarray'], zero_crossings: int) -> float:
        """Estimate fundamental frequency using zero-crossing rate"""
        duration = len(samples) / self.sample_rate
        if duration > 0 and zero_crossings > 0:
            return (zero_crossings / 2) / duration
        return 0.0

    def detect_voice_simple(self, samples: Union[array.array, 'np.ndarray']) -> Dict:
        """Simple voice detection returning a dictionary"""
        if not samples or len(samples) == 0:
            return {'voice_detected': False, 'confidence': 0.0}

        stats = self.get_statistics(samples)

        # Voice detection heuristics
        freq = stats.get('estimated_frequency', 0)
        rms = stats.get('rms', 0)
        zero_crossings = stats.get('zero_crossings', 0)

        # Voice frequency range (roughly 80-500 Hz for fundamental)
        freq_score = 1.0 if 80 <= freq <= 500 else 0.0

        # Energy level check
        energy_score = min(1.0, rms / 5000) if rms > 100 else 0.0

        # Zero crossing rate check (voice has moderate crossing rate)
        zcr = zero_crossings / len(samples) if len(samples) > 0 else 0
        zcr_score = 1.0 if 0.01 <= zcr <= 0.2 else 0.0

        confidence = (freq_score + energy_score + zcr_score) / 3.0

        return {
            'voice_detected': confidence > 0.5,
            'confidence': confidence,
            'frequency': freq,
            'energy': rms,
            'zero_crossing_rate': zcr
        }

    def convert_channels(self, samples: Union[array.array, 'np.ndarray'],
                        orig_channels: int, target_channels: int) -> Union[array.array, 'np.ndarray']:
        """Convert between mono and stereo"""
        if orig_channels == target_channels:
            return samples

        is_numpy = HAS_NUMPY and isinstance(samples, np.ndarray)
        result = [] if is_numpy else array.array('h')

        if orig_channels == 1 and target_channels == 2:
            # Mono to stereo: duplicate channel
            if is_numpy:
                result = np.repeat(samples, 2)
            else:
                for s in samples:
                    result.append(s)
                    result.append(s)

        elif orig_channels == 2 and target_channels == 1:
            # Stereo to mono: average channels
            if is_numpy:
                result = ((samples[::2] + samples[1::2]) / 2).astype(np.int16)
            else:
                for i in range(0, len(samples) - 1, 2):
                    mono = (samples[i] + samples[i + 1]) // 2
                    result.append(mono)

        return np.array(result) if is_numpy else result

    def split_stereo(self, stereo_samples: Union[array.array, 'np.ndarray']) -> Tuple[Union[array.array, 'np.ndarray'], Union[array.array, 'np.ndarray']]:
        """Split stereo audio into left and right channels"""
        is_numpy = HAS_NUMPY and isinstance(stereo_samples, np.ndarray)

        if is_numpy:
            left = stereo_samples[::2]
            right = stereo_samples[1::2]
        else:
            left = array.array('h', [stereo_samples[i] for i in range(0, len(stereo_samples), 2)])
            right = array.array('h', [stereo_samples[i] for i in range(1, len(stereo_samples), 2)])

        return left, right

    def merge_channels(self, left: Union[array.array, 'np.ndarray'],
                      right: Union[array.array, 'np.ndarray']) -> Union[array.array, 'np.ndarray']:
        """Merge left and right channels into stereo"""
        is_numpy = HAS_NUMPY and isinstance(left, np.ndarray)

        if is_numpy:
            stereo = np.empty(len(left) * 2, dtype=left.dtype)
            stereo[::2] = left
            stereo[1::2] = right
            return stereo
        else:
            stereo = array.array('h')
            for l, r in zip(left, right):
                stereo.append(l)
                stereo.append(r)
            return stereo

    def apply_echo(self, samples: Union[array.array, 'np.ndarray'],
                   delay_ms: int = 500, decay: float = 0.5) -> Union[array.array, 'np.ndarray']:
        """Add echo effect with automatic optimization"""
        delay_samples = int((delay_ms / 1000) * self.sample_rate)

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            result = data.copy()

            # Vectorized echo application
            if delay_samples < len(data):
                echo_part = data[:-delay_samples] * decay
                result[delay_samples:] += echo_part.astype(np.int16)
                # Prevent clipping
                result = np.clip(result, -MAX_INT16, MAX_INT16)

            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            # Pure Python fallback
            result = array.array('h', samples)
            for i in range(delay_samples, len(samples)):
                echo_sample = int(samples[i - delay_samples] * decay)
                mixed = result[i] + echo_sample
                result[i] = max(min(mixed, MAX_INT16), -MAX_INT16)
            return result

    def apply_low_pass_filter(self, samples: Union[array.array, 'np.ndarray'],
                             cutoff_hz: float = 1000) -> Union[array.array, 'np.ndarray']:
        """Simple low-pass filter for noise reduction"""
        rc = 1.0 / (2 * math.pi * cutoff_hz)
        dt = 1.0 / self.sample_rate
        alpha = dt / (rc + dt)

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples).astype(np.float32)
            result = np.zeros_like(data)
            result[0] = data[0]

            # Vectorized filter computation
            for i in range(1, len(data)):
                result[i] = alpha * data[i] + (1 - alpha) * result[i-1]

            result = np.clip(result, -MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            # Pure Python fallback
            result = array.array('h')
            prev_output = samples[0] if samples else 0
            result.append(prev_output)

            for sample in samples[1:]:
                output = alpha * sample + (1 - alpha) * prev_output
                prev_output = int(max(min(output, MAX_INT16), -MAX_INT16))
                result.append(prev_output)

            return result

    def reduce_noise(self, samples: Union[array.array, 'np.ndarray'],
                     noise_floor_db: float = -40) -> Union[array.array, 'np.ndarray']:
        """Simple noise reduction using spectral gating"""
        if not samples or len(samples) == 0:
            return samples

        # Convert noise floor to linear
        noise_threshold = self.db_to_linear(noise_floor_db) * MAX_INT16

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            # Apply soft gating
            mask = np.abs(data) > noise_threshold
            result = data * mask
            # Smooth transitions
            for i in range(1, len(result) - 1):
                if not mask[i] and (mask[i-1] or mask[i+1]):
                    result[i] = data[i] * 0.5
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            result = array.array('h')
            for i, s in enumerate(samples):
                if abs(s) > noise_threshold:
                    result.append(s)
                elif i > 0 and i < len(samples) - 1:
                    # Smooth transition
                    if abs(samples[i-1]) > noise_threshold or abs(samples[i+1]) > noise_threshold:
                        result.append(s // 2)
                    else:
                        result.append(0)
                else:
                    result.append(0)
            return result

    def apply_compressor(self, samples: Union[array.array, 'np.ndarray'],
                        threshold_db: float = -20, ratio: float = 0.3) -> Union[array.array, 'np.ndarray']:
        """Dynamic range compressor for volume control"""
        threshold = MAX_INT16 * (10 ** (threshold_db / 20))

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples).astype(np.float32)
            abs_data = np.abs(data)

            # Apply compression where signal exceeds threshold
            mask = abs_data > threshold
            compressed = np.where(mask,
                                 np.sign(data) * (threshold + (abs_data - threshold) * ratio),
                                 data)

            result = np.clip(compressed, -MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            # Pure Python fallback
            result = array.array('h')
            for sample in samples:
                abs_sample = abs(sample)
                if abs_sample > threshold:
                    sign = 1 if sample > 0 else -1
                    compressed = sign * (threshold + (abs_sample - threshold) * ratio)
                    result.append(int(max(min(compressed, MAX_INT16), -MAX_INT16)))
                else:
                    result.append(sample)
            return result


class BatchProcessor:
    """Optimized batch processor with parallel execution"""

    def __init__(self, num_workers: Optional[int] = None):
        self.num_workers = num_workers or max(1, multiprocessing.cpu_count() - 1)
        self.processor = AudioProcessor()
        self.results = []
        self.errors = []

    @staticmethod
    def get_optimal_chunk_size(file_size: int, available_memory: int = None) -> int:
        """Calculate optimal chunk size for processing large files"""
        if available_memory is None:
            # Default to 64MB chunks for large files
            available_memory = 64 * 1024 * 1024

        # Target using 25% of available memory
        target_memory = available_memory // 4

        # Each sample is 2 bytes (int16)
        samples_per_chunk = target_memory // 2

        # Align to second boundaries (44100 samples = 1 second at 44.1kHz)
        samples_per_chunk = (samples_per_chunk // 44100) * 44100

        # Minimum 1 second, maximum 60 seconds
        return max(44100, min(samples_per_chunk, 44100 * 60))

    def scan_directory(self, directory: str, recursive: bool = True) -> List[Dict]:
        """Scan directory for audio files"""
        audio_files = []
        directory_path = Path(directory)

        if not directory_path.exists():
            return []

        pattern = "**/*.wav" if recursive else "*.wav"

        try:
            for file_path in directory_path.glob(pattern):
                if file_path.is_file():
                    fmt = self.processor.detect_format(str(file_path))
                    if fmt == 'wav':
                        stat = os.stat(file_path)
                        audio_files.append({
                            'path': str(file_path),
                            'size': stat.st_size,
                            'format': fmt,
                            'supported': True,
                            'modified': stat.st_mtime
                        })
        except Exception as e:
            logger.error(f"Error scanning directory: {e}")

        return audio_files

    def process_file(self, task: Dict) -> Dict:
        """Process single file with error recovery"""
        filepath = task['file']
        operation = task['operation']
        params = task.get('params', {})
        output_path = task.get('output_path')

        result = {
            'file': filepath,
            'operation': operation,
            'status': 'pending',
            'start_time': time.time()
        }

        try:
            # Load audio
            samples, info = self.processor.load_wav(filepath)
            if not samples:
                raise ValueError("Failed to load audio file")

            # Apply operation
            if operation == 'normalize':
                processed = self.processor.normalize(samples, params.get('peak', 0.95))
            elif operation == 'amplify':
                processed = self.processor.amplify(samples, params.get('gain', 0))
            elif operation == 'fade':
                processed = self.processor.fade(samples,
                                               params.get('fade_in', 0),
                                               params.get('fade_out', 0))
            elif operation == 'trim':
                processed = self.processor.trim_silence(samples, params.get('threshold', -40))
            elif operation == 'reverse':
                processed = self.processor.reverse(samples)
            elif operation == 'speed':
                processed = self.processor.change_speed(samples, params.get('factor', 1.0))
            elif operation == 'statistics':
                result['statistics'] = self.processor.get_statistics(samples)
                result['status'] = 'success'
                result['duration'] = time.time() - result['start_time']
                return result
            else:
                raise ValueError(f"Unknown operation: {operation}")

            # Save output
            if output_path:
                success = self.processor.save_wav(output_path, processed, info['sample_rate'])
                result['output'] = output_path
                result['status'] = 'success' if success else 'failed'
            else:
                result['status'] = 'success'

            result['duration'] = time.time() - result['start_time']

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['duration'] = time.time() - result['start_time']
            self.errors.append(result)
            logger.error(f"Error processing {filepath}: {e}")

        return result

    def process_directory(self, input_dir: str, output_dir: str = None,
                         operation: str = 'normalize', params: Dict = None,
                         pattern: str = '*.wav', parallel: bool = True) -> List[Dict]:
        """Process all files in directory with parallel execution"""
        input_path = Path(input_dir)
        if not input_path.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return []

        # Find all matching files
        files = list(input_path.glob(pattern))
        if not files:
            logger.warning(f"No files matching pattern {pattern} in {input_dir}")
            return []

        # Prepare output directory
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

        # Create tasks
        tasks = []
        for file_path in files:
            task = {
                'file': str(file_path),
                'operation': operation,
                'params': params or {}
            }

            if output_dir:
                output_file = output_path / f"{file_path.stem}_{operation}{file_path.suffix}"
                task['output_path'] = str(output_file)

            tasks.append(task)

        # Process files
        logger.info(f"Processing {len(tasks)} files with {self.num_workers} workers")

        if parallel and len(tasks) > 1:
            # Parallel processing
            with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
                results = list(executor.map(self.process_file, tasks))
        else:
            # Sequential processing
            results = [self.process_file(task) for task in tasks]

        # Summary
        successful = sum(1 for r in results if r['status'] == 'success')
        failed = sum(1 for r in results if r['status'] != 'success')

        logger.info(f"Batch processing complete: {successful} successful, {failed} failed")

        self.results = results
        return results

    def process_chain(self, filepath: str, operations: List[Dict],
                      output_path: str = None) -> Dict:
        """Apply chain of operations to single file"""
        result = {
            'file': filepath,
            'operations': operations,
            'status': 'pending',
            'start_time': time.time()
        }

        try:
            # Load audio
            samples, info = self.processor.load_wav(filepath)
            if not samples:
                raise ValueError("Failed to load audio file")

            # Apply each operation in sequence
            processed = samples
            for op in operations:
                operation = op['type']
                params = op.get('params', {})

                if operation == 'normalize':
                    processed = self.processor.normalize(processed, params.get('peak', 0.95))
                elif operation == 'amplify':
                    processed = self.processor.amplify(processed, params.get('gain', 0))
                elif operation == 'fade':
                    processed = self.processor.fade(processed,
                                                   params.get('fade_in', 0),
                                                   params.get('fade_out', 0))
                elif operation == 'trim':
                    processed = self.processor.trim_silence(processed, params.get('threshold', -40))
                elif operation == 'reverse':
                    processed = self.processor.reverse(processed)
                elif operation == 'speed':
                    processed = self.processor.change_speed(processed, params.get('factor', 1.0))

            # Save output
            if output_path:
                success = self.processor.save_wav(output_path, processed, info['sample_rate'])
                result['output'] = output_path
                result['status'] = 'success' if success else 'failed'
            else:
                result['status'] = 'success'

            result['duration'] = time.time() - result['start_time']

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['duration'] = time.time() - result['start_time']
            logger.error(f"Error in processing chain for {filepath}: {e}")

        return result

    def generate_report(self, output_file: str = None) -> Dict:
        """Generate processing report"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_files': len(self.results),
            'successful': sum(1 for r in self.results if r['status'] == 'success'),
            'failed': sum(1 for r in self.results if r['status'] != 'success'),
            'total_duration': sum(r.get('duration', 0) for r in self.results),
            'errors': self.errors,
            'details': self.results
        }

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {output_file}")

        return report


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(description='Chameleon Audio Processor')
    parser.add_argument('command', choices=['process', 'batch', 'info', 'chain', 'resample', 'scan'],
                       help='Command to execute')
    parser.add_argument('input', help='Input WAV file or directory')
    parser.add_argument('-o', '--output', help='Output file or directory')
    parser.add_argument('--operation', default='normalize',
                       choices=['normalize', 'amplify', 'fade', 'trim', 'reverse', 'speed', 'mix', 'statistics', 'validate'],
                       help='Processing operation')
    parser.add_argument('--gain', type=float, default=0, help='Gain in dB (for amplify)')
    parser.add_argument('--fade-in', type=int, default=0, help='Fade in duration (ms)')
    parser.add_argument('--fade-out', type=int, default=0, help='Fade out duration (ms)')
    parser.add_argument('--threshold', type=float, default=-40, help='Silence threshold (dB)')
    parser.add_argument('--speed', type=float, default=1.0, help='Speed factor')
    parser.add_argument('--peak', type=float, default=0.95, help='Target peak for normalize')
    parser.add_argument('--pattern', default='*.wav', help='File pattern for batch processing')
    parser.add_argument('--parallel', action='store_true', help='Enable parallel processing')
    parser.add_argument('--workers', type=int, help='Number of parallel workers')
    parser.add_argument('--report', help='Generate report file')
    parser.add_argument('--target-rate', type=int, help='Target sample rate for resample')
    parser.add_argument('--recursive', action='store_true', help='Recursive directory scan')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    processor = AudioProcessor()
    batch_processor = BatchProcessor(num_workers=args.workers)

    if args.command == 'process':
        # Single file processing
        samples, info = processor.load_wav(args.input)
        if not samples:
            logger.error(f"Failed to load {args.input}")
            sys.exit(1)

        # Apply operation
        if args.operation == 'normalize':
            result = processor.normalize(samples, args.peak)
        elif args.operation == 'amplify':
            result = processor.amplify(samples, args.gain)
        elif args.operation == 'fade':
            result = processor.fade(samples, args.fade_in, args.fade_out)
        elif args.operation == 'trim':
            result = processor.trim_silence(samples, args.threshold)
        elif args.operation == 'reverse':
            result = processor.reverse(samples)
        elif args.operation == 'speed':
            result = processor.change_speed(samples, args.speed)
        elif args.operation == 'statistics':
            stats = processor.get_statistics(samples)
            print(json.dumps(stats, indent=2))
            sys.exit(0)
        elif args.operation == 'validate':
            validation = processor.validate_audio(samples)
            print(f"Valid: {validation['valid']}")
            if validation['issues']:
                print("Issues:")
                for issue in validation['issues']:
                    print(f"  - {issue}")
            else:
                print("No quality issues detected")
            sys.exit(0)
        else:
            logger.error(f"Unknown operation: {args.operation}")
            sys.exit(1)

        # Save output
        if args.output:
            if processor.save_wav(args.output, result, info['sample_rate']):
                logger.info(f"Saved to {args.output}")
            else:
                logger.error(f"Failed to save {args.output}")
                sys.exit(1)

    elif args.command == 'batch':
        # Batch processing
        params = {
            'peak': args.peak,
            'gain': args.gain,
            'fade_in': args.fade_in,
            'fade_out': args.fade_out,
            'threshold': args.threshold,
            'factor': args.speed
        }

        results = batch_processor.process_directory(
            args.input,
            args.output,
            args.operation,
            params,
            args.pattern,
            args.parallel
        )

        if args.report:
            batch_processor.generate_report(args.report)

    elif args.command == 'info':
        # Display file information
        fmt = processor.detect_format(args.input)
        print(f"Format: {fmt or 'Unknown'}")

        if fmt == 'wav':
            info = processor._get_file_info(args.input)
            if info:
                samples, _ = processor.load_wav(args.input)
                stats = processor.get_statistics(samples)
                info.update(stats)

                print(f"Sample Rate: {info.get('sample_rate')} Hz")
                print(f"Channels: {info.get('channels')}")
                print(f"Duration: {info.get('duration', 0):.2f} seconds")
                print(f"RMS Level: {stats.get('rms_db', 0):.1f} dB")
                print(f"Peak Level: {stats.get('peak_db', 0):.1f} dB")

                quality = stats.get('quality', {})
                if quality.get('issues'):
                    print("Quality Issues:")
                    for issue in quality['issues']:
                        print(f"  - {issue}")
                else:
                    print("Quality: Good")

                if args.verbose:
                    print(json.dumps(info, indent=2))
            else:
                logger.error(f"Failed to read {args.input}")
                sys.exit(1)
        else:
            print("Unsupported format for detailed analysis")

    elif args.command == 'resample':
        # Resample audio file
        if not args.output or not args.target_rate:
            logger.error("Resample command requires --output and --target-rate")
            sys.exit(1)

        samples, info = processor.load_wav(args.input)
        if not samples:
            logger.error(f"Failed to load {args.input}")
            sys.exit(1)

        # Resample
        resampled = processor.resample(samples, info['sample_rate'], args.target_rate)

        # Save
        if processor.save_wav(args.output, resampled, args.target_rate):
            logger.info(f"Resampled {args.input} -> {args.output}")
            logger.info(f"Rate: {info['sample_rate']} -> {args.target_rate} Hz")
        else:
            logger.error(f"Failed to save {args.output}")
            sys.exit(1)

    elif args.command == 'scan':
        # Scan directory for audio files
        batch_processor = BatchProcessor(num_workers=args.workers)
        files = batch_processor.scan_directory(args.input, args.recursive)

        print(f"Found {len(files)} audio files:")
        for file_info in files:
            size_mb = file_info['size'] / (1024 * 1024)
            print(f"  {file_info['path']} ({size_mb:.1f} MB)")

        if args.verbose:
            total_size = sum(f['size'] for f in files)
            print(f"\nTotal size: {total_size / (1024 * 1024):.1f} MB")

    elif args.command == 'chain':
        # Chain processing (read operations from JSON)
        if args.output and os.path.exists(args.output):
            with open(args.output, 'r') as f:
                operations = json.load(f)
            result = batch_processor.process_chain(args.input, operations)
            print(json.dumps(result, indent=2))
        else:
            logger.error("Chain command requires operations JSON file")
            sys.exit(1)

    # Display performance info if numpy is available
    if args.verbose:
        if HAS_NUMPY:
            logger.info("NumPy optimization: ENABLED")
        else:
            logger.info("NumPy optimization: DISABLED (install numpy for better performance)")

        if processor._error_count > 0:
            logger.warning(f"Total errors encountered: {processor._error_count}")
            if processor._last_error:
                logger.warning(f"Last error: {processor._last_error}")


if __name__ == '__main__':
    main()