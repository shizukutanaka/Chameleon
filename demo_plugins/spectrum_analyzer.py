"""
Spectrum Analyzer Plugin for Chameleon Audio Processing System
Demonstrates audio analyzer plugin implementation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
from typing import List, Dict, Any
from plugin_system import AudioAnalyzerPlugin, PluginMetadata

class SpectrumAnalyzerPlugin(AudioAnalyzerPlugin):
    """
    Spectrum analyzer with basic FFT analysis
    """

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="SpectrumAnalyzer",
            version="1.0.0",
            author="Chameleon Team",
            description="Basic spectrum analysis with frequency bins and peak detection",
            category="analyzer",
            tags=["spectrum", "fft", "analyzer"],
            parameters={
                "window_size": {
                    "type": "int",
                    "default": 1024,
                    "min": 256,
                    "max": 4096,
                    "description": "FFT window size"
                },
                "overlap": {
                    "type": "float",
                    "default": 0.5,
                    "min": 0.0,
                    "max": 0.9,
                    "description": "Window overlap factor"
                }
            }
        )

    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the spectrum analyzer"""
        self.logger.info("Initializing SpectrumAnalyzer plugin")
        return True

    def cleanup(self):
        """Cleanup plugin resources"""
        self.logger.info("Cleaning up SpectrumAnalyzer plugin")

    def analyze_audio(self, audio_data: List[float], sample_rate: int, **params) -> Dict[str, Any]:
        """Analyze audio spectrum"""
        window_size = params.get('window_size', 1024)
        overlap = params.get('overlap', 0.5)

        if len(audio_data) < window_size:
            return {"error": "Audio data too short for analysis"}

        # Simple DFT implementation (would use FFT in production)
        spectrum = self._compute_simple_dft(audio_data[:window_size])

        # Convert to magnitude spectrum
        magnitudes = [abs(complex_val) for complex_val in spectrum]

        # Find frequency bins
        freq_bins = [i * sample_rate / window_size for i in range(len(magnitudes) // 2)]
        mag_bins = magnitudes[:len(magnitudes) // 2]

        # Find peaks
        peaks = self._find_peaks(mag_bins, freq_bins)

        # Calculate spectral features
        features = self._calculate_spectral_features(mag_bins, freq_bins)

        return {
            "sample_rate": sample_rate,
            "window_size": window_size,
            "frequency_bins": freq_bins[:20],  # First 20 bins for demo
            "magnitude_bins": mag_bins[:20],
            "peaks": peaks[:10],  # Top 10 peaks
            "spectral_centroid": features["centroid"],
            "spectral_rolloff": features["rolloff"],
            "spectral_flux": features["flux"],
            "peak_frequency": peaks[0]["frequency"] if peaks else 0.0,
            "peak_magnitude": peaks[0]["magnitude"] if peaks else 0.0
        }

    def _compute_simple_dft(self, samples: List[float]) -> List[complex]:
        """Simple DFT implementation (for demo - would use FFT in production)"""
        N = len(samples)
        dft = []

        for k in range(N // 4):  # Only compute first quarter for speed
            real_part = 0.0
            imag_part = 0.0

            for n in range(N):
                angle = -2 * math.pi * k * n / N
                real_part += samples[n] * math.cos(angle)
                imag_part += samples[n] * math.sin(angle)

            dft.append(complex(real_part, imag_part))

        return dft

    def _find_peaks(self, magnitudes: List[float], frequencies: List[float]) -> List[Dict[str, float]]:
        """Find spectral peaks"""
        if len(magnitudes) < 3:
            return []

        peaks = []
        threshold = max(magnitudes) * 0.1  # 10% of maximum

        for i in range(1, len(magnitudes) - 1):
            if (magnitudes[i] > magnitudes[i-1] and
                magnitudes[i] > magnitudes[i+1] and
                magnitudes[i] > threshold):
                peaks.append({
                    "frequency": frequencies[i],
                    "magnitude": magnitudes[i],
                    "bin": i
                })

        # Sort by magnitude (descending)
        peaks.sort(key=lambda x: x["magnitude"], reverse=True)
        return peaks

    def _calculate_spectral_features(self, magnitudes: List[float], frequencies: List[float]) -> Dict[str, float]:
        """Calculate basic spectral features"""
        if not magnitudes or sum(magnitudes) == 0:
            return {"centroid": 0.0, "rolloff": 0.0, "flux": 0.0}

        total_magnitude = sum(magnitudes)

        # Spectral centroid (weighted average frequency)
        centroid = sum(freq * mag for freq, mag in zip(frequencies, magnitudes)) / total_magnitude

        # Spectral rolloff (frequency below which 85% of energy lies)
        cumulative = 0
        rolloff_threshold = total_magnitude * 0.85
        rolloff = frequencies[-1] if frequencies else 0.0

        for i, mag in enumerate(magnitudes):
            cumulative += mag
            if cumulative >= rolloff_threshold:
                rolloff = frequencies[i] if i < len(frequencies) else 0.0
                break

        # Spectral flux (measure of rate of change)
        flux = sum(abs(mag) for mag in magnitudes) / len(magnitudes)

        return {
            "centroid": centroid,
            "rolloff": rolloff,
            "flux": flux
        }

def create_plugin():
    return SpectrumAnalyzerPlugin()