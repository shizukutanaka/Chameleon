#!/usr/bin/env python3
"""
Chameleon FFT Analysis - Fast frequency domain analysis
Simple FFT implementation without external dependencies
"""

import math
import cmath
import array
from typing import List, Tuple, Dict, Any, Optional

def next_power_of_2(n: int) -> int:
    """Find next power of 2 greater than or equal to n"""
    power = 1
    while power < n:
        power *= 2
    return power

def bit_reverse(data: List[complex], n: int) -> List[complex]:
    """Bit-reverse the input data for FFT"""
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            data[i], data[j] = data[j], data[i]
    return data

def fft(data: List[complex]) -> List[complex]:
    """Fast Fourier Transform - Cooley-Tukey algorithm"""
    n = len(data)
    if n <= 1:
        return data
    
    # Ensure n is power of 2
    if n & (n - 1) != 0:
        # Pad with zeros to next power of 2
        next_n = next_power_of_2(n)
        data.extend([0] * (next_n - n))
        n = next_n
    
    # Bit-reverse the data
    data = bit_reverse(data, n)
    
    # FFT computation
    length = 2
    while length <= n:
        # Calculate the principal nth root of unity
        w = cmath.exp(-2j * math.pi / length)
        
        for i in range(0, n, length):
            wn = 1
            for j in range(length // 2):
                u = data[i + j]
                v = data[i + j + length // 2] * wn
                
                data[i + j] = u + v
                data[i + j + length // 2] = u - v
                wn *= w
        
        length *= 2
    
    return data

def magnitude_spectrum(fft_result: List[complex]) -> List[float]:
    """Convert FFT result to magnitude spectrum"""
    return [abs(x) for x in fft_result]

def power_spectrum(fft_result: List[complex]) -> List[float]:
    """Convert FFT result to power spectrum"""
    return [abs(x) ** 2 for x in fft_result]

def phase_spectrum(fft_result: List[complex]) -> List[float]:
    """Convert FFT result to phase spectrum"""
    return [math.atan2(x.imag, x.real) for x in fft_result]

def analyze_frequency_spectrum(audio: bytes, sample_rate: int = 44100, 
                             window_size: int = 1024) -> Dict[str, Any]:
    """Analyze frequency spectrum of audio signal"""
    samples = array.array('h')
    samples.frombytes(audio)
    
    if len(samples) < window_size:
        return {'error': 'Audio too short for analysis'}
    
    # Use the first window for analysis
    window = samples[:window_size]
    
    # Apply Hann window to reduce spectral leakage
    windowed = []
    for i, sample in enumerate(window):
        # Hann window
        hann_factor = 0.5 * (1 - math.cos(2 * math.pi * i / (window_size - 1)))
        windowed.append(complex(sample * hann_factor / 32768.0, 0))  # Normalize to [-1, 1]
    
    # Perform FFT
    fft_result = fft(windowed)
    
    # Calculate spectra (only first half due to symmetry)
    half_size = len(fft_result) // 2
    magnitude = magnitude_spectrum(fft_result[:half_size])
    power = power_spectrum(fft_result[:half_size])
    
    # Find dominant frequency
    max_magnitude_index = magnitude.index(max(magnitude[1:]))  # Skip DC component
    dominant_freq = (max_magnitude_index * sample_rate) / len(fft_result)
    
    # Calculate frequency bins
    freq_bins = [(i * sample_rate) / len(fft_result) for i in range(half_size)]
    
    # Calculate spectral features
    spectral_centroid = calculate_spectral_centroid(magnitude, freq_bins)
    spectral_rolloff = calculate_spectral_rolloff(magnitude, freq_bins, 0.85)
    spectral_bandwidth = calculate_spectral_bandwidth(magnitude, freq_bins, spectral_centroid)
    
    # Frequency band analysis
    bands = analyze_frequency_bands(magnitude, freq_bins)
    
    return {
        'dominant_frequency': dominant_freq,
        'magnitude_spectrum': magnitude,
        'power_spectrum': power,
        'frequency_bins': freq_bins,
        'spectral_centroid': spectral_centroid,
        'spectral_rolloff': spectral_rolloff,
        'spectral_bandwidth': spectral_bandwidth,
        'frequency_bands': bands,
        'sample_rate': sample_rate,
        'window_size': window_size
    }

def calculate_spectral_centroid(magnitude: List[float], freq_bins: List[float]) -> float:
    """Calculate spectral centroid (brightness measure)"""
    if not magnitude or not freq_bins:
        return 0.0
    
    weighted_sum = sum(mag * freq for mag, freq in zip(magnitude, freq_bins))
    total_magnitude = sum(magnitude)
    
    return weighted_sum / total_magnitude if total_magnitude > 0 else 0.0

def calculate_spectral_rolloff(magnitude: List[float], freq_bins: List[float], 
                              threshold: float = 0.85) -> float:
    """Calculate spectral rolloff point"""
    total_energy = sum(magnitude)
    target_energy = total_energy * threshold
    
    cumulative_energy = 0
    for mag, freq in zip(magnitude, freq_bins):
        cumulative_energy += mag
        if cumulative_energy >= target_energy:
            return freq
    
    return freq_bins[-1] if freq_bins else 0.0

def calculate_spectral_bandwidth(magnitude: List[float], freq_bins: List[float], 
                               centroid: float) -> float:
    """Calculate spectral bandwidth"""
    if not magnitude or not freq_bins:
        return 0.0
    
    total_magnitude = sum(magnitude)
    if total_magnitude == 0:
        return 0.0
    
    weighted_variance = sum(mag * (freq - centroid) ** 2 
                          for mag, freq in zip(magnitude, freq_bins))
    
    return math.sqrt(weighted_variance / total_magnitude)

def analyze_frequency_bands(magnitude: List[float], freq_bins: List[float]) -> Dict[str, float]:
    """Analyze energy in different frequency bands"""
    if not magnitude or not freq_bins:
        return {}
    
    total_energy = sum(magnitude)
    if total_energy == 0:
        return {}
    
    bands = {
        'sub_bass': (20, 60),      # Sub bass
        'bass': (60, 250),         # Bass
        'low_mid': (250, 500),     # Low midrange
        'mid': (500, 2000),        # Midrange
        'high_mid': (2000, 4000),  # High midrange
        'presence': (4000, 6000),  # Presence
        'brilliance': (6000, 20000) # Brilliance
    }
    
    band_energies = {}
    
    for band_name, (low_freq, high_freq) in bands.items():
        band_energy = 0
        for mag, freq in zip(magnitude, freq_bins):
            if low_freq <= freq <= high_freq:
                band_energy += mag
        
        band_energies[band_name] = band_energy / total_energy
    
    return band_energies

def find_peaks(magnitude: List[float], freq_bins: List[float], 
               threshold: float = 0.1, min_distance: int = 10) -> List[Tuple[float, float]]:
    """Find peaks in frequency spectrum"""
    if len(magnitude) < 3:
        return []
    
    max_magnitude = max(magnitude)
    threshold_value = max_magnitude * threshold
    
    peaks = []
    
    for i in range(1, len(magnitude) - 1):
        # Check if it's a local maximum above threshold
        if (magnitude[i] > magnitude[i-1] and 
            magnitude[i] > magnitude[i+1] and 
            magnitude[i] > threshold_value):
            
            # Check minimum distance from other peaks
            freq = freq_bins[i]
            too_close = False
            
            for peak_freq, _ in peaks:
                if abs(freq - peak_freq) < min_distance:
                    too_close = True
                    break
            
            if not too_close:
                peaks.append((freq, magnitude[i]))
    
    # Sort by magnitude (highest first)
    peaks.sort(key=lambda x: x[1], reverse=True)
    
    return peaks

def detect_harmonics(fundamental: float, peaks: List[Tuple[float, float]], 
                    tolerance: float = 0.05) -> List[Tuple[int, float, float]]:
    """Detect harmonic series based on fundamental frequency"""
    harmonics = []
    
    for peak_freq, magnitude in peaks:
        # Check if this peak is a harmonic of the fundamental
        harmonic_ratio = peak_freq / fundamental
        nearest_harmonic = round(harmonic_ratio)
        
        if nearest_harmonic > 1:  # Skip fundamental itself
            error = abs(harmonic_ratio - nearest_harmonic) / nearest_harmonic
            
            if error <= tolerance:
                harmonics.append((nearest_harmonic, peak_freq, magnitude))
    
    # Sort by harmonic number
    harmonics.sort(key=lambda x: x[0])
    
    return harmonics

def analyze_audio_spectrum(audio: bytes, sample_rate: int = 44100) -> Dict[str, Any]:
    """Complete spectral analysis of audio"""
    # Basic frequency analysis
    spectrum_data = analyze_frequency_spectrum(audio, sample_rate)
    
    if 'error' in spectrum_data:
        return spectrum_data
    
    # Find peaks
    peaks = find_peaks(spectrum_data['magnitude_spectrum'], 
                      spectrum_data['frequency_bins'])
    
    # Detect harmonics if we have a strong fundamental
    harmonics = []
    if peaks and peaks[0][0] > 50:  # Reasonable fundamental frequency
        fundamental = peaks[0][0]
        harmonics = detect_harmonics(fundamental, peaks[1:])  # Skip fundamental from peaks
    
    # Add to results
    spectrum_data['peaks'] = peaks[:10]  # Top 10 peaks
    spectrum_data['harmonics'] = harmonics
    
    return spectrum_data

def spectral_analysis_summary(analysis: Dict[str, Any]) -> str:
    """Generate human-readable summary of spectral analysis"""
    if 'error' in analysis:
        return f"Analysis error: {analysis['error']}"
    
    lines = []
    lines.append("=== Spectral Analysis Summary ===")
    
    # Basic info
    lines.append(f"Dominant frequency: {analysis['dominant_frequency']:.1f} Hz")
    lines.append(f"Spectral centroid: {analysis['spectral_centroid']:.1f} Hz")
    lines.append(f"Spectral rolloff: {analysis['spectral_rolloff']:.1f} Hz")
    lines.append(f"Spectral bandwidth: {analysis['spectral_bandwidth']:.1f} Hz")
    
    # Frequency bands
    lines.append("\nFrequency band distribution:")
    for band, ratio in analysis['frequency_bands'].items():
        lines.append(f"  {band}: {ratio:.1%}")
    
    # Peaks
    if 'peaks' in analysis and analysis['peaks']:
        lines.append(f"\nTop peaks:")
        for i, (freq, mag) in enumerate(analysis['peaks'][:5]):
            lines.append(f"  {i+1}. {freq:.1f} Hz (magnitude: {mag:.0f})")
    
    # Harmonics
    if 'harmonics' in analysis and analysis['harmonics']:
        lines.append(f"\nDetected harmonics:")
        for harmonic_num, freq, mag in analysis['harmonics'][:5]:
            lines.append(f"  H{harmonic_num}: {freq:.1f} Hz")
    
    return '\n'.join(lines)

# Test function
def test_fft_analysis():
    """Test FFT analysis with generated tones"""
    import audio_utils
    
    print("Testing FFT analysis...")
    
    # Test with 440Hz tone
    print("\n1. Testing 440Hz tone:")
    tone_440 = audio_core.generate_tone(440, 1.0)
    analysis = analyze_audio_spectrum(tone_440)
    print(spectral_analysis_summary(analysis))
    
    # Test with complex tone (440 + 880 Hz)
    print("\n2. Testing complex tone (440 + 880 Hz):")
    tone_complex = audio_core.mix_audio(
        audio_core.generate_tone(440, 1.0),
        audio_core.generate_tone(880, 1.0),
        0.5
    )
    analysis = analyze_audio_spectrum(tone_complex)
    print(spectral_analysis_summary(analysis))

if __name__ == "__main__":
    test_fft_analysis()