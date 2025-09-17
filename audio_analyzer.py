#!/usr/bin/env python3
"""
Audio Analysis Module - Spectrum, frequency detection, and analysis tools
"""

import array
import math
from typing import List, Tuple, Dict, Optional

class AudioAnalyzer:
    """Audio analysis tools without external dependencies"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

    def get_rms(self, samples: array.array) -> float:
        """Calculate Root Mean Square (volume level)"""
        if not samples:
            return 0.0
        sum_squares = sum(s * s for s in samples)
        return math.sqrt(sum_squares / len(samples))

    def get_peak(self, samples: array.array) -> int:
        """Get peak amplitude"""
        if not samples:
            return 0
        return max(abs(min(samples)), abs(max(samples)))

    def get_zero_crossings(self, samples: array.array) -> int:
        """Count zero crossings (rough frequency indicator)"""
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

    def estimate_frequency(self, samples: array.array) -> float:
        """Estimate fundamental frequency using zero-crossing rate"""
        crossings = self.get_zero_crossings(samples)
        duration = len(samples) / self.sample_rate
        if duration > 0:
            return (crossings / 2) / duration
        return 0.0

    def autocorrelation(self, samples: array.array, max_lag: Optional[int] = None) -> List[float]:
        """Calculate autocorrelation for pitch detection"""
        if not samples:
            return []

        n = len(samples)
        if max_lag is None:
            max_lag = n // 2

        result = []
        for lag in range(max_lag):
            if lag >= n:
                break

            sum_product = 0
            for i in range(n - lag):
                sum_product += samples[i] * samples[i + lag]

            result.append(sum_product / (n - lag))

        return result

    def detect_pitch(self, samples: array.array) -> float:
        """Detect pitch using autocorrelation"""
        if len(samples) < 100:
            return 0.0

        # Calculate autocorrelation
        min_period = int(self.sample_rate / 800)   # 800 Hz max
        max_period = int(self.sample_rate / 50)     # 50 Hz min
        autocorr = self.autocorrelation(samples, max_period)

        # Find peak after first zero crossing
        best_period = 0
        best_correlation = 0

        for period in range(min_period, min(max_period, len(autocorr))):
            if autocorr[period] > best_correlation:
                best_correlation = autocorr[period]
                best_period = period

        if best_period > 0:
            return self.sample_rate / best_period
        return 0.0

    def simple_fft(self, samples: array.array, size: int = 512) -> List[float]:
        """Simple DFT for spectrum analysis (not optimized FFT)"""
        if len(samples) < size:
            # Pad with zeros
            samples = array.array('h', samples)
            samples.extend([0] * (size - len(samples)))

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

    def get_spectrum_bands(self, samples: array.array, bands: int = 8) -> List[float]:
        """Get simplified spectrum in frequency bands"""
        if not samples:
            return [0] * bands

        # Use simplified DFT
        spectrum_size = 256
        spectrum = self.simple_fft(samples[:spectrum_size], spectrum_size)

        # Group into bands
        band_values = []
        band_size = len(spectrum) // bands

        for i in range(bands):
            start = i * band_size
            end = start + band_size
            if i == bands - 1:
                end = len(spectrum)

            band_avg = sum(spectrum[start:end]) / (end - start) if end > start else 0
            band_values.append(band_avg)

        return band_values

    def detect_silence(self, samples: array.array, threshold_db: float = -40) -> bool:
        """Detect if audio is silence"""
        if not samples:
            return True

        rms = self.get_rms(samples)
        if rms == 0:
            return True

        db = 20 * math.log10(rms / 32767)
        return db < threshold_db

    def get_energy(self, samples: array.array) -> float:
        """Calculate audio energy"""
        if not samples:
            return 0.0
        return sum(s * s for s in samples)

    def get_dynamics(self, samples: array.array, window_size: int = 1024) -> Dict[str, float]:
        """Analyze dynamic range"""
        if not samples:
            return {'min': 0, 'max': 0, 'range': 0, 'crest_factor': 0}

        rms_values = []
        peak_values = []

        for i in range(0, len(samples), window_size):
            window = samples[i:i + window_size]
            if window:
                rms_values.append(self.get_rms(window))
                peak_values.append(self.get_peak(window))

        if not rms_values:
            return {'min': 0, 'max': 0, 'range': 0, 'crest_factor': 0}

        min_rms = min(rms_values)
        max_rms = max(rms_values)
        avg_rms = sum(rms_values) / len(rms_values)
        max_peak = max(peak_values)

        return {
            'min_rms': min_rms,
            'max_rms': max_rms,
            'dynamic_range': max_rms - min_rms if max_rms > 0 else 0,
            'crest_factor': max_peak / avg_rms if avg_rms > 0 else 0
        }

    def detect_clipping(self, samples: array.array, threshold: int = 32700) -> List[int]:
        """Detect clipping points in audio"""
        clipping_points = []
        for i, sample in enumerate(samples):
            if abs(sample) >= threshold:
                clipping_points.append(i)
        return clipping_points

    def get_loudness(self, samples: array.array) -> float:
        """Estimate perceived loudness (simplified)"""
        if not samples:
            return 0.0

        # A-weighting approximation for perceived loudness
        # Simplified: emphasize 1-6 kHz range
        bands = self.get_spectrum_bands(samples, 16)

        # Weight different frequency ranges
        weights = [0.1, 0.2, 0.4, 0.7, 1.0, 1.2, 1.2, 1.0,
                  0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]

        weighted_sum = sum(band * weight for band, weight in zip(bands, weights))
        return weighted_sum / len(bands)

    def detect_onset(self, samples: array.array, window_size: int = 512) -> List[int]:
        """Detect audio onsets (start of notes/beats)"""
        onsets = []
        prev_energy = 0
        threshold_ratio = 1.5

        for i in range(0, len(samples) - window_size, window_size):
            window = samples[i:i + window_size]
            energy = self.get_energy(window)

            if prev_energy > 0 and energy > prev_energy * threshold_ratio:
                onsets.append(i)

            prev_energy = energy

        return onsets


class VoiceActivityDetector:
    """Simple Voice Activity Detection"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.analyzer = AudioAnalyzer(sample_rate)

    def detect_voice(self, samples: array.array) -> bool:
        """Detect if samples contain voice"""
        if not samples:
            return False

        # Check multiple indicators
        energy = self.analyzer.get_energy(samples)
        zero_crossings = self.analyzer.get_zero_crossings(samples)
        frequency = self.analyzer.estimate_frequency(samples)

        # Voice characteristics
        # - Energy above threshold
        # - Zero crossing rate in speech range
        # - Fundamental frequency in voice range (85-255 Hz male, 165-255 Hz female)

        energy_threshold = 1000000
        zcr = zero_crossings / len(samples)
        voice_zcr_range = (0.01, 0.1)  # Typical for speech

        has_energy = energy > energy_threshold
        has_voice_zcr = voice_zcr_range[0] < zcr < voice_zcr_range[1]
        has_voice_freq = 85 < frequency < 400

        return has_energy and (has_voice_zcr or has_voice_freq)

    def get_voice_segments(self, samples: array.array, frame_size: int = 1024) -> List[Tuple[int, int]]:
        """Get start and end points of voice segments"""
        segments = []
        in_voice = False
        segment_start = 0

        for i in range(0, len(samples) - frame_size, frame_size):
            frame = samples[i:i + frame_size]
            is_voice = self.detect_voice(frame)

            if is_voice and not in_voice:
                # Voice starts
                segment_start = i
                in_voice = True
            elif not is_voice and in_voice:
                # Voice ends
                segments.append((segment_start, i))
                in_voice = False

        # Handle last segment
        if in_voice:
            segments.append((segment_start, len(samples)))

        return segments


def demo_analysis():
    """Demo analysis functionality"""
    print("Audio Analysis Demo")

    # Create test signal
    samples = array.array('h')
    for i in range(44100):  # 1 second
        # Mix of frequencies
        t = i / 44100
        sample = int(5000 * math.sin(2 * math.pi * 440 * t) +
                     3000 * math.sin(2 * math.pi * 880 * t))
        samples.append(sample)

    analyzer = AudioAnalyzer()

    # Basic analysis
    print(f"\nBasic Analysis:")
    print(f"  RMS: {analyzer.get_rms(samples):.2f}")
    print(f"  Peak: {analyzer.get_peak(samples)}")
    print(f"  Zero crossings: {analyzer.get_zero_crossings(samples)}")
    print(f"  Estimated frequency: {analyzer.estimate_frequency(samples):.2f} Hz")
    print(f"  Detected pitch: {analyzer.detect_pitch(samples):.2f} Hz")

    # Spectrum analysis
    bands = analyzer.get_spectrum_bands(samples, 8)
    print(f"\nSpectrum bands: {[f'{b:.0f}' for b in bands]}")

    # Dynamics
    dynamics = analyzer.get_dynamics(samples)
    print(f"\nDynamics:")
    for key, value in dynamics.items():
        print(f"  {key}: {value:.2f}")

    # Voice detection
    vad = VoiceActivityDetector()
    has_voice = vad.detect_voice(samples)
    print(f"\nVoice detected: {has_voice}")

    print("\nAnalysis demo completed")


if __name__ == '__main__':
    demo_analysis()