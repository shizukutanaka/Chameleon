#!/usr/bin/env python3
"""
Spectrum Analyzer - Advanced audio analysis without heavy dependencies
Pure Python implementation with optional numpy acceleration
"""

import math
import struct
from typing import List, Tuple, Dict, Optional, Any
from collections import defaultdict

class SpectrumAnalyzer:
    """Lightweight spectrum analyzer using pure Python"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.window_size = 2048  # Default FFT window size
        
    def compute_dft(self, samples: List[float], N: Optional[int] = None) -> List[complex]:
        """
        Compute Discrete Fourier Transform (pure Python)
        Slower than FFT but works without numpy
        """
        if N is None:
            N = len(samples)
        
        # Pad or truncate to N samples
        if len(samples) < N:
            samples = samples + [0] * (N - len(samples))
        else:
            samples = samples[:N]
        
        dft = []
        for k in range(N):
            sum_real = 0
            sum_imag = 0
            for n in range(N):
                angle = -2 * math.pi * k * n / N
                sum_real += samples[n] * math.cos(angle)
                sum_imag += samples[n] * math.sin(angle)
            dft.append(complex(sum_real, sum_imag))
        
        return dft
    
    def compute_fft_radix2(self, samples: List[float]) -> List[complex]:
        """
        Compute FFT using Cooley-Tukey radix-2 algorithm (pure Python)
        Much faster than DFT for power-of-2 sizes
        """
        N = len(samples)
        
        # Ensure power of 2
        if N & (N - 1) != 0:
            # Pad to next power of 2
            N = 2 ** math.ceil(math.log2(N))
            samples = samples + [0] * (N - len(samples))
        
        # Base case
        if N <= 1:
            return [complex(samples[0])] if samples else [complex(0)]
        
        # Recursive FFT
        even = self.compute_fft_radix2([samples[i] for i in range(0, N, 2)])
        odd = self.compute_fft_radix2([samples[i] for i in range(1, N, 2)])
        
        # Combine
        T = []
        for k in range(N // 2):
            t = complex(math.cos(-2 * math.pi * k / N), 
                       math.sin(-2 * math.pi * k / N)) * odd[k]
            T.append(t)
        
        return [even[k] + T[k] for k in range(N // 2)] + \
               [even[k] - T[k] for k in range(N // 2)]
    
    def apply_window(self, samples: List[float], window_type: str = 'hann') -> List[float]:
        """Apply window function to reduce spectral leakage"""
        N = len(samples)
        windowed = []
        
        for n in range(N):
            if window_type == 'hann':
                w = 0.5 - 0.5 * math.cos(2 * math.pi * n / (N - 1))
            elif window_type == 'hamming':
                w = 0.54 - 0.46 * math.cos(2 * math.pi * n / (N - 1))
            elif window_type == 'blackman':
                w = 0.42 - 0.5 * math.cos(2 * math.pi * n / (N - 1)) + \
                    0.08 * math.cos(4 * math.pi * n / (N - 1))
            else:  # rectangular
                w = 1.0
            
            windowed.append(samples[n] * w)
        
        return windowed
    
    def compute_spectrum(self, audio_data: bytes, 
                        window_type: str = 'hann',
                        use_fast: bool = True) -> Dict[str, Any]:
        """
        Compute frequency spectrum from audio data
        Returns frequencies and their magnitudes
        """
        # Convert bytes to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Process in windows
        hop_size = self.window_size // 2
        num_windows = max(1, (len(samples) - self.window_size) // hop_size + 1)
        
        all_magnitudes = defaultdict(list)
        
        for w in range(num_windows):
            start = w * hop_size
            end = min(start + self.window_size, len(samples))
            window_samples = samples[start:end]
            
            if len(window_samples) < self.window_size // 2:
                break
            
            # Apply window function
            windowed = self.apply_window(window_samples, window_type)
            
            # Compute FFT or DFT
            if use_fast and len(windowed) >= 64:
                fft_result = self.compute_fft_radix2(windowed)
            else:
                fft_result = self.compute_dft(windowed)
            
            # Compute magnitude spectrum
            N = len(fft_result)
            for k in range(N // 2):  # Only positive frequencies
                freq = k * self.sample_rate / N
                magnitude = abs(fft_result[k]) / N
                all_magnitudes[freq].append(magnitude)
        
        # Average magnitudes across windows
        spectrum = {}
        for freq, mags in all_magnitudes.items():
            spectrum[freq] = sum(mags) / len(mags)
        
        # Find dominant frequencies
        sorted_freqs = sorted(spectrum.items(), key=lambda x: x[1], reverse=True)
        dominant_freqs = sorted_freqs[:10] if sorted_freqs else []
        
        # Compute spectral features
        total_energy = sum(spectrum.values())
        spectral_centroid = 0
        spectral_spread = 0
        
        if total_energy > 0:
            # Spectral centroid (center of mass)
            for freq, mag in spectrum.items():
                spectral_centroid += freq * mag / total_energy
            
            # Spectral spread (standard deviation around centroid)
            for freq, mag in spectrum.items():
                spectral_spread += ((freq - spectral_centroid) ** 2) * mag / total_energy
            spectral_spread = math.sqrt(spectral_spread)
        
        return {
            'spectrum': dict(sorted(spectrum.items())[:100]),  # Top 100 frequencies
            'dominant_frequencies': dominant_freqs,
            'spectral_centroid': spectral_centroid,
            'spectral_spread': spectral_spread,
            'total_energy': total_energy,
            'num_windows': num_windows
        }
    
    def analyze_pitch(self, audio_data: bytes) -> Dict[str, float]:
        """
        Analyze pitch using autocorrelation method
        Returns fundamental frequency and confidence
        """
        # Convert to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Autocorrelation
        N = min(len(samples), 4096)
        samples = samples[:N]
        
        # Search range for fundamental frequency (50 Hz to 500 Hz)
        min_lag = int(self.sample_rate / 500)  # 500 Hz max
        max_lag = int(self.sample_rate / 50)   # 50 Hz min
        
        best_lag = 0
        best_correlation = 0
        
        for lag in range(min_lag, min(max_lag, N // 2)):
            correlation = 0
            for i in range(N - lag):
                correlation += samples[i] * samples[i + lag]
            
            correlation /= (N - lag)
            
            if correlation > best_correlation:
                best_correlation = correlation
                best_lag = lag
        
        # Calculate fundamental frequency
        if best_lag > 0:
            fundamental_freq = self.sample_rate / best_lag
            confidence = min(1.0, best_correlation * 2)  # Normalize confidence
        else:
            fundamental_freq = 0
            confidence = 0
        
        # Detect harmonics
        harmonics = []
        if fundamental_freq > 0:
            for h in range(2, 6):  # First 4 harmonics
                harmonic_freq = fundamental_freq * h
                if harmonic_freq < self.sample_rate / 2:  # Below Nyquist
                    harmonics.append(harmonic_freq)
        
        return {
            'fundamental_frequency': fundamental_freq,
            'confidence': confidence,
            'harmonics': harmonics,
            'pitch_note': self.freq_to_note(fundamental_freq) if fundamental_freq > 0 else 'N/A'
        }
    
    def freq_to_note(self, frequency: float) -> str:
        """Convert frequency to musical note"""
        if frequency <= 0:
            return 'N/A'
        
        A4 = 440.0
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        # Calculate semitones from A4
        semitones = 12 * math.log2(frequency / A4)
        
        # Find octave and note
        octave = 4 + int((semitones + 9) / 12)
        note_index = int(round(semitones) % 12)
        
        return f"{notes[note_index]}{octave}"
    
    def analyze_rhythm(self, audio_data: bytes, 
                      window_ms: int = 50) -> Dict[str, Any]:
        """
        Analyze rhythm and tempo using onset detection
        """
        # Convert to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Calculate energy in windows
        window_size = int(self.sample_rate * window_ms / 1000)
        hop_size = window_size // 2
        
        energies = []
        for i in range(0, len(samples) - window_size, hop_size):
            window = samples[i:i + window_size]
            energy = sum(s ** 2 for s in window) / window_size
            energies.append(energy)
        
        # Detect onsets (sudden energy increases)
        onsets = []
        threshold = sum(energies) / len(energies) * 1.5 if energies else 0
        
        for i in range(1, len(energies)):
            if energies[i] > threshold and energies[i] > energies[i-1] * 1.3:
                onset_time = i * hop_size / self.sample_rate
                onsets.append(onset_time)
        
        # Estimate tempo from onset intervals
        tempo_bpm = 0
        regularity = 0
        
        if len(onsets) > 2:
            intervals = [onsets[i] - onsets[i-1] for i in range(1, len(onsets))]
            
            if intervals:
                # Find most common interval (mode)
                interval_counts = defaultdict(int)
                for interval in intervals:
                    # Quantize to nearest 10ms
                    quantized = round(interval * 100) / 100
                    interval_counts[quantized] += 1
                
                if interval_counts:
                    common_interval = max(interval_counts, key=interval_counts.get)
                    tempo_bpm = 60.0 / common_interval if common_interval > 0 else 0
                    
                    # Calculate regularity (how consistent the tempo is)
                    avg_interval = sum(intervals) / len(intervals)
                    if avg_interval > 0:
                        deviations = [abs(i - avg_interval) / avg_interval for i in intervals]
                        regularity = max(0, 1 - sum(deviations) / len(deviations))
        
        return {
            'tempo_bpm': tempo_bpm,
            'regularity': regularity,
            'onset_count': len(onsets),
            'onset_times': onsets[:20],  # First 20 onsets
            'average_energy': sum(energies) / len(energies) if energies else 0
        }
    
    def get_frequency_bands(self, spectrum: Dict[float, float]) -> Dict[str, float]:
        """
        Organize spectrum into standard frequency bands
        """
        bands = {
            'sub_bass': (20, 60),      # 20-60 Hz
            'bass': (60, 250),          # 60-250 Hz
            'low_mid': (250, 500),      # 250-500 Hz
            'mid': (500, 2000),         # 500-2000 Hz
            'high_mid': (2000, 4000),   # 2-4 kHz
            'presence': (4000, 6000),   # 4-6 kHz
            'brilliance': (6000, 20000) # 6-20 kHz
        }
        
        band_energies = {}
        
        for band_name, (low, high) in bands.items():
            energy = 0
            count = 0
            for freq, mag in spectrum.items():
                if low <= freq <= high:
                    energy += mag
                    count += 1
            
            band_energies[band_name] = energy / count if count > 0 else 0
        
        return band_energies


def analyze_audio_spectrum(audio_file: str, detailed: bool = False) -> Dict[str, Any]:
    """
    High-level function to analyze audio spectrum
    """
    try:
        import wave
        
        # Open audio file
        with wave.open(audio_file, 'rb') as wav:
            sample_rate = wav.getframerate()
            num_frames = wav.getnframes()
            audio_data = wav.readframes(num_frames)
        
        # Create analyzer
        analyzer = SpectrumAnalyzer(sample_rate)
        
        # Compute spectrum
        spectrum_data = analyzer.compute_spectrum(audio_data)
        
        # Analyze pitch
        pitch_data = analyzer.analyze_pitch(audio_data)
        
        # Analyze rhythm
        rhythm_data = analyzer.analyze_rhythm(audio_data)
        
        # Get frequency bands
        bands = analyzer.get_frequency_bands(spectrum_data['spectrum'])
        
        result = {
            'sample_rate': sample_rate,
            'duration': num_frames / sample_rate,
            'dominant_frequencies': spectrum_data['dominant_frequencies'][:5],
            'spectral_centroid': spectrum_data['spectral_centroid'],
            'spectral_spread': spectrum_data['spectral_spread'],
            'fundamental_frequency': pitch_data['fundamental_frequency'],
            'pitch_note': pitch_data['pitch_note'],
            'tempo_bpm': rhythm_data['tempo_bpm'],
            'frequency_bands': bands
        }
        
        if detailed:
            result['full_spectrum'] = spectrum_data['spectrum']
            result['harmonics'] = pitch_data['harmonics']
            result['onset_times'] = rhythm_data['onset_times']
            result['rhythm_regularity'] = rhythm_data['regularity']
        
        return result
        
    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python spectrum_analyzer.py <audio_file> [--detailed]")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    detailed = '--detailed' in sys.argv
    
    print(f"Analyzing spectrum of {audio_file}...")
    result = analyze_audio_spectrum(audio_file, detailed)
    
    if 'error' in result:
        print(f"Error: {result['error']}")
    else:
        print(f"\nSpectrum Analysis Results:")
        print(f"  Sample Rate: {result['sample_rate']} Hz")
        print(f"  Duration: {result['duration']:.2f} seconds")
        print(f"  Fundamental Frequency: {result['fundamental_frequency']:.1f} Hz ({result['pitch_note']})")
        print(f"  Tempo: {result['tempo_bpm']:.1f} BPM")
        print(f"  Spectral Centroid: {result['spectral_centroid']:.1f} Hz")
        
        print(f"\nDominant Frequencies:")
        for freq, mag in result['dominant_frequencies']:
            print(f"    {freq:.1f} Hz: {mag:.4f}")
        
        print(f"\nFrequency Bands:")
        for band, energy in result['frequency_bands'].items():
            print(f"    {band}: {energy:.4f}")