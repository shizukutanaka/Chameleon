"""
Spectrum Analyzer Plugin for Chameleon Audio Processing System
Demonstrates audio analyzer plugin implementation
"""

import math
from typing import List, Dict, Any
from plugin_system import AudioAnalyzerPlugin, PluginMetadata

# The demo DFT is O(N^2); this bounds how many overlapping windows a single
# analyze_audio call will run so the hop from `overlap` cannot multiply the
# cost unboundedly on long buffers.
_MAX_ANALYZED_WINDOWS = 8


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
        window_size = int(params.get('window_size', 1024))
        if window_size <= 0:
            window_size = 1024
        overlap = float(params.get('overlap', 0.5))

        if len(audio_data) < window_size:
            return {"error": "Audio data too short for analysis"}

        # The declared `overlap` parameter now actually drives a hop between
        # analysed windows; previously it was accepted and ignored, so
        # overlap=0.0 and overlap=0.9 returned identical results and only the
        # first window was ever analysed. Work stays bounded: a demo O(N^2)
        # DFT is capped at a handful of windows.
        hop = max(1, int(round(window_size * (1.0 - min(max(overlap, 0.0), 0.9)))))
        windows = []
        for start in range(0, len(audio_data) - window_size + 1, hop):
            windows.append(audio_data[start:start + window_size])
            if len(windows) >= _MAX_ANALYZED_WINDOWS:
                break

        spectra = [self._compute_simple_dft(window) for window in windows]
        per_window_magnitudes = [
            [abs(coefficient) for coefficient in spectrum]
            for spectrum in spectra
        ]

        n_bins = len(per_window_magnitudes[0])
        magnitudes = [
            sum(m[i] for m in per_window_magnitudes) / len(per_window_magnitudes)
            for i in range(n_bins)
        ]

        # Bin k of an N-point DFT sits at k * sr / N; computing N//2 bins
        # covers the whole unique band up to Nyquist. An earlier version
        # computed N//4 bins and then reported only half of those, capping
        # the analysed band at sr/8 (~5.5 kHz at 44.1 kHz): loud content
        # above that came back with peak_frequency 0.0.
        freq_bins = [i * sample_rate / window_size for i in range(n_bins)]

        # Find peaks
        peaks = self._find_peaks(magnitudes, freq_bins)

        # Calculate spectral features
        features = self._calculate_spectral_features(magnitudes, freq_bins)
        features["flux"] = self._spectral_flux(per_window_magnitudes)

        return {
            "sample_rate": sample_rate,
            "window_size": window_size,
            "analyzed_windows": len(windows),
            "frequency_bins": freq_bins[:20],  # First 20 bins for demo
            "magnitude_bins": magnitudes[:20],
            "peaks": peaks[:10],  # Top 10 peaks
            "spectral_centroid": features["centroid"],
            "spectral_rolloff": features["rolloff"],
            "spectral_flux": features["flux"],
            "peak_frequency": peaks[0]["frequency"] if peaks else 0.0,
            "peak_magnitude": peaks[0]["magnitude"] if peaks else 0.0
        }

    def _compute_simple_dft(self, samples: List[float]) -> List[complex]:
        """Simple DFT implementation (for demo - would use FFT in production).

        Computes the first N//2 bins -- the complete unique band for a real
        signal, up to Nyquist -- so the analysis does not silently blind
        itself to content above sample_rate/4.
        """
        N = len(samples)
        dft = []

        for k in range(N // 2):
            real_part = 0.0
            imag_part = 0.0

            for n in range(N):
                angle = -2 * math.pi * k * n / N
                real_part += samples[n] * math.cos(angle)
                imag_part += samples[n] * math.sin(angle)

            dft.append(complex(real_part, imag_part))

        return dft

    def _spectral_flux(self, per_window_magnitudes: List[List[float]]) -> float:
        """Mean frame-to-frame spectral change: RMS bin-magnitude difference
        between consecutive analysis windows, averaged over window pairs.

        Real spectral flux is defined between successive frames -- the
        earlier version reported the mean magnitude of a *single* window
        under this name, which is not a flux at all. With only one analysed
        window there is no change to measure, so the honest value is 0.0.
        """
        if len(per_window_magnitudes) < 2:
            return 0.0

        total = 0.0
        pairs = 0
        for previous, current in zip(per_window_magnitudes,
                                     per_window_magnitudes[1:]):
            squared = sum((c - p) ** 2 for c, p in zip(current, previous))
            total += math.sqrt(squared / len(current))
            pairs += 1
        return total / pairs

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

        return {
            "centroid": centroid,
            "rolloff": rolloff,
        }

def create_plugin():
    return SpectrumAnalyzerPlugin()