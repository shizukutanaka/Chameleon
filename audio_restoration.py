#!/usr/bin/env python3
"""
Audio Restoration and Repair Module
Advanced algorithms for repairing damaged or degraded audio
"""

import warnings
from typing import Optional, Tuple, Dict, List, Any
from dataclasses import dataclass
import numpy as np
from scipy import signal, interpolate
from scipy.ndimage import median_filter

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    warnings.warn("Librosa not installed. Some features limited.")

@dataclass
class RestorationConfig:
    """Configuration for audio restoration"""
    click_removal: bool = True
    decrackle: bool = True
    dehum: bool = True
    denoise: bool = True
    declip: bool = True
    gap_filling: bool = True
    spectral_repair: bool = True
    adaptive_mode: bool = True

class ClickRemover:
    """Remove clicks and pops from audio"""

    def __init__(self):
        self.threshold = 3.0  # Standard deviations
        self.window_size = 128

    def detect_clicks(self, audio: np.ndarray, sample_rate: int) -> List[int]:
        """Detect click positions"""
        # Calculate local statistics
        window = signal.windows.hann(self.window_size)

        # Compute local mean and std
        audio_abs = np.abs(audio)
        local_mean = signal.convolve(audio_abs, window/np.sum(window), mode='same')
        local_std = np.sqrt(signal.convolve((audio_abs - local_mean)**2, window/np.sum(window), mode='same'))

        # Detect outliers
        z_score = np.abs((audio_abs - local_mean) / (local_std + 1e-10))
        click_positions = np.where(z_score > self.threshold)[0]

        # Group nearby clicks
        if len(click_positions) > 0:
            groups = []
            current_group = [click_positions[0]]

            for pos in click_positions[1:]:
                if pos - current_group[-1] <= 3:  # Within 3 samples
                    current_group.append(pos)
                else:
                    groups.append(current_group)
                    current_group = [pos]
            groups.append(current_group)

            # Return center of each group
            click_positions = [int(np.mean(group)) for group in groups]

        return click_positions

    def remove_clicks(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Remove detected clicks"""
        result = audio.copy()
        clicks = self.detect_clicks(audio, sample_rate)

        for click_pos in clicks:
            # Define repair region
            start = max(0, click_pos - 10)
            end = min(len(audio), click_pos + 10)

            if start > 20 and end < len(audio) - 20:
                # Use autoregressive prediction
                before = result[start-20:start]
                after = result[end:end+20]

                # Fit AR model on surrounding data
                surrounding = np.concatenate([before, after])

                # Simple linear interpolation for the click region
                repair_length = end - start
                repaired = np.linspace(result[start-1], result[end], repair_length)

                # Apply windowing for smooth transition
                window = signal.windows.tukey(repair_length, 0.5)
                result[start:end] = repaired * window + result[start:end] * (1 - window)

        return result

class CrackleRemover:
    """Remove crackle noise from vinyl or old recordings"""

    def __init__(self):
        self.median_filter_size = 3
        self.threshold = 0.3

    def remove_crackle(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Remove crackle using median filtering"""
        # Apply median filter to remove impulse noise
        filtered = median_filter(audio, size=self.median_filter_size)

        # Detect crackle regions
        diff = np.abs(audio - filtered)
        crackle_mask = diff > self.threshold * np.std(audio)

        # Replace crackle regions with filtered values
        result = audio.copy()
        result[crackle_mask] = filtered[crackle_mask]

        # Smooth transitions
        if np.any(crackle_mask):
            # Find crackle boundaries
            boundaries = np.diff(np.concatenate(([0], crackle_mask.astype(int), [0])))
            starts = np.where(boundaries == 1)[0]
            ends = np.where(boundaries == -1)[0]

            for start, end in zip(starts, ends):
                if end - start > 1:
                    # Apply crossfade
                    fade_len = min(5, (end - start) // 2)
                    if fade_len > 0:
                        fade_in = np.linspace(0, 1, fade_len)
                        result[start:start+fade_len] = (
                            audio[start:start+fade_len] * (1 - fade_in) +
                            result[start:start+fade_len] * fade_in
                        )

        return result

class HumRemover:
    """Remove electrical hum and buzz"""

    def __init__(self):
        self.base_freqs = [50, 60]  # Common power line frequencies
        self.harmonics = 5
        self.q_factor = 30

    def remove_hum(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Remove hum using notch filters"""
        result = audio.copy()

        for base_freq in self.base_freqs:
            # Detect if hum is present
            if self._detect_hum(audio, sample_rate, base_freq):
                # Apply notch filters for fundamental and harmonics
                for harmonic in range(1, self.harmonics + 1):
                    freq = base_freq * harmonic
                    if freq < sample_rate / 2:
                        # Design notch filter
                        w0 = freq / (sample_rate / 2)
                        b, a = signal.iirnotch(w0, self.q_factor)
                        result = signal.filtfilt(b, a, result)

        return result

    def _detect_hum(self, audio: np.ndarray, sample_rate: int, freq: float) -> bool:
        """Detect if hum is present at given frequency"""
        # Compute FFT
        fft = np.fft.rfft(audio)
        freqs = np.fft.rfftfreq(len(audio), 1/sample_rate)

        # Find bin closest to target frequency
        target_bin = np.argmin(np.abs(freqs - freq))

        # Check if there's a peak at this frequency
        window_size = 10
        start = max(0, target_bin - window_size)
        end = min(len(fft), target_bin + window_size)

        local_mean = np.mean(np.abs(fft[start:end]))
        peak_value = np.abs(fft[target_bin])

        return peak_value > 2 * local_mean

class DeclippingProcessor:
    """Restore clipped audio signals"""

    def __init__(self):
        self.clip_threshold = 0.95
        self.interpolation_method = 'cubic'

    def detect_clipping(self, audio: np.ndarray) -> Tuple[List[int], List[int]]:
        """Detect clipped regions"""
        # Normalize to [-1, 1]
        normalized = audio / (np.max(np.abs(audio)) + 1e-10)

        # Find clipped samples
        clipped = np.abs(normalized) > self.clip_threshold

        # Find clipped regions
        diff = np.diff(np.concatenate(([0], clipped.astype(int), [0])))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        return starts.tolist(), ends.tolist()

    def restore_clipped(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Restore clipped regions using interpolation"""
        result = audio.copy()
        starts, ends = self.detect_clipping(audio)

        for start, end in zip(starts, ends):
            if end - start < 100:  # Only process short clips
                # Get surrounding context
                context_before = max(0, start - 50)
                context_after = min(len(audio), end + 50)

                # Create interpolation points
                x_known = np.concatenate([
                    np.arange(context_before, start),
                    np.arange(end, context_after)
                ])
                y_known = np.concatenate([
                    result[context_before:start],
                    result[end:context_after]
                ])

                if len(x_known) > 3:
                    # Interpolate clipped region
                    x_clip = np.arange(start, end)

                    if self.interpolation_method == 'cubic' and len(x_known) > 3:
                        f = interpolate.interp1d(x_known, y_known, kind='cubic', fill_value='extrapolate')
                        restored = f(x_clip)
                    else:
                        restored = np.interp(x_clip, x_known, y_known)

                    # Blend with original
                    window = signal.windows.tukey(len(restored), 0.5)
                    result[start:end] = restored * window + result[start:end] * (1 - window) * 0.5

        return result

class SpectralRepairer:
    """Repair audio using spectral interpolation"""

    def __init__(self):
        self.fft_size = 2048
        self.hop_size = 512

    def repair_gaps(self, audio: np.ndarray, gap_positions: List[Tuple[int, int]], sample_rate: int) -> np.ndarray:
        """Repair gaps in audio using spectral interpolation"""
        if not HAS_LIBROSA:
            return audio

        # STFT
        stft = librosa.stft(audio, n_fft=self.fft_size, hop_length=self.hop_size)
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        for start, end in gap_positions:
            # Convert to frame indices
            start_frame = start // self.hop_size
            end_frame = end // self.hop_size

            if start_frame > 0 and end_frame < magnitude.shape[1]:
                # Interpolate magnitude
                for freq_bin in range(magnitude.shape[0]):
                    before = magnitude[freq_bin, start_frame-1]
                    after = magnitude[freq_bin, end_frame]

                    # Linear interpolation
                    interp_values = np.linspace(before, after, end_frame - start_frame)
                    magnitude[freq_bin, start_frame:end_frame] = interp_values

                # Phase interpolation (unwrapped)
                for freq_bin in range(phase.shape[0]):
                    phase_unwrapped = np.unwrap(phase[freq_bin, :])
                    before = phase_unwrapped[start_frame-1]
                    after = phase_unwrapped[end_frame]

                    interp_values = np.linspace(before, after, end_frame - start_frame)
                    phase[freq_bin, start_frame:end_frame] = np.angle(np.exp(1j * interp_values))

        # Reconstruct
        stft_repaired = magnitude * np.exp(1j * phase)
        repaired = librosa.istft(stft_repaired, hop_length=self.hop_size, length=len(audio))

        return repaired

class AdaptiveDenoiser:
    """Advanced adaptive denoising"""

    def __init__(self):
        self.noise_profile_duration = 0.5  # seconds
        self.reduction_factor = 0.8

    def estimate_noise_profile(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Estimate noise profile from quiet sections"""
        if not HAS_LIBROSA:
            return np.ones(1025)  # Default profile

        # Find quiet sections
        rms = librosa.feature.rms(y=audio, frame_length=2048, hop_length=512)[0]
        threshold = np.percentile(rms, 10)
        quiet_frames = rms < threshold

        # Extract noise from quiet sections
        stft = librosa.stft(audio)
        noise_spectrum = np.abs(stft[:, quiet_frames]).mean(axis=1) if np.any(quiet_frames) else np.ones(stft.shape[0])

        return noise_spectrum

    def denoise(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply adaptive spectral subtraction"""
        if not HAS_LIBROSA:
            return audio

        # Estimate noise
        noise_profile = self.estimate_noise_profile(audio, sample_rate)

        # STFT
        stft = librosa.stft(audio)
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # Spectral subtraction
        noise_floor = noise_profile[:, np.newaxis] * self.reduction_factor
        denoised_mag = magnitude - noise_floor

        # Prevent over-subtraction
        denoised_mag = np.maximum(denoised_mag, 0.1 * magnitude)

        # Reconstruct
        stft_denoised = denoised_mag * np.exp(1j * phase)
        denoised = librosa.istft(stft_denoised, length=len(audio))

        return denoised

class VinylRestorer:
    """Specialized restoration for vinyl recordings"""

    def __init__(self):
        self.click_remover = ClickRemover()
        self.crackle_remover = CrackleRemover()
        self.hum_remover = HumRemover()
        self.denoiser = AdaptiveDenoiser()

    def restore(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Complete vinyl restoration pipeline"""
        info = {"steps_applied": []}
        result = audio.copy()

        # Remove clicks
        result = self.click_remover.remove_clicks(result, sample_rate)
        info["steps_applied"].append("click_removal")

        # Remove crackle
        result = self.crackle_remover.remove_crackle(result, sample_rate)
        info["steps_applied"].append("crackle_removal")

        # Remove hum
        result = self.hum_remover.remove_hum(result, sample_rate)
        info["steps_applied"].append("hum_removal")

        # Denoise
        result = self.denoiser.denoise(result, sample_rate)
        info["steps_applied"].append("denoising")

        # Calculate improvement metrics
        info["snr_improvement"] = self._calculate_snr_improvement(audio, result)

        return result, info

    def _calculate_snr_improvement(self, original: np.ndarray, restored: np.ndarray) -> float:
        """Calculate SNR improvement"""
        noise_original = np.std(original[np.abs(original) < 0.1])
        noise_restored = np.std(restored[np.abs(restored) < 0.1])

        if noise_original > 0 and noise_restored > 0:
            return 20 * np.log10(noise_original / noise_restored)
        return 0.0

class AudioRestorer:
    """Main audio restoration interface"""

    def __init__(self, config: Optional[RestorationConfig] = None):
        self.config = config or RestorationConfig()
        self.click_remover = ClickRemover()
        self.crackle_remover = CrackleRemover()
        self.hum_remover = HumRemover()
        self.declipper = DeclippingProcessor()
        self.spectral_repairer = SpectralRepairer()
        self.denoiser = AdaptiveDenoiser()
        self.vinyl_restorer = VinylRestorer()

    def restore(self, audio: np.ndarray, sample_rate: int, mode: str = "auto") -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Restore audio with specified mode

        Args:
            audio: Input audio
            sample_rate: Sample rate
            mode: "auto", "vinyl", "digital", "voice", "music"
        """
        info = {
            "mode": mode,
            "applied_processes": [],
            "quality_metrics": {}
        }

        result = audio.copy()

        if mode == "vinyl":
            # Use specialized vinyl restoration
            result, vinyl_info = self.vinyl_restorer.restore(audio, sample_rate)
            info.update(vinyl_info)

        else:
            # Apply selected restoration processes
            if self.config.click_removal:
                result = self.click_remover.remove_clicks(result, sample_rate)
                info["applied_processes"].append("click_removal")

            if self.config.decrackle:
                result = self.crackle_remover.remove_crackle(result, sample_rate)
                info["applied_processes"].append("decrackle")

            if self.config.dehum:
                result = self.hum_remover.remove_hum(result, sample_rate)
                info["applied_processes"].append("dehum")

            if self.config.declip:
                result = self.declipper.restore_clipped(result, sample_rate)
                info["applied_processes"].append("declipping")

            if self.config.denoise:
                result = self.denoiser.denoise(result, sample_rate)
                info["applied_processes"].append("denoising")

        # Calculate quality metrics
        info["quality_metrics"] = self._calculate_metrics(audio, result)

        return result, info

    def _calculate_metrics(self, original: np.ndarray, restored: np.ndarray) -> Dict[str, float]:
        """Calculate restoration quality metrics"""
        metrics = {}

        # SNR improvement
        signal_power = np.mean(restored ** 2)
        noise_power = np.mean((original - restored) ** 2)
        if noise_power > 0:
            metrics["snr_db"] = 10 * np.log10(signal_power / noise_power)

        # Dynamic range
        metrics["dynamic_range_original"] = 20 * np.log10(
            np.max(np.abs(original)) / (np.std(original) + 1e-10)
        )
        metrics["dynamic_range_restored"] = 20 * np.log10(
            np.max(np.abs(restored)) / (np.std(restored) + 1e-10)
        )

        # Clarity (high-frequency preservation)
        if HAS_LIBROSA:
            orig_hf = np.sum(np.abs(np.fft.rfft(original)[len(original)//4:]))
            rest_hf = np.sum(np.abs(np.fft.rfft(restored)[len(restored)//4:]))
            metrics["hf_preservation"] = rest_hf / (orig_hf + 1e-10)

        return metrics

# Example usage
if __name__ == "__main__":
    print("Audio Restoration Module")

    # Create test audio with artifacts
    sample_rate = 44100
    duration = 2
    t = np.linspace(0, duration, sample_rate * duration)

    # Clean signal
    clean = np.sin(2 * np.pi * 440 * t) * 0.5

    # Add artifacts
    noisy = clean.copy()
    # Add clicks
    click_positions = [1000, 5000, 10000, 20000]
    for pos in click_positions:
        noisy[pos:pos+3] = np.random.randn(3) * 0.9

    # Add hum
    noisy += 0.1 * np.sin(2 * np.pi * 60 * t)

    # Add clipping
    noisy = np.clip(noisy, -0.7, 0.7)

    # Restore
    restorer = AudioRestorer()
    restored, info = restorer.restore(noisy, sample_rate)

    print(f"Restoration complete: {info}")