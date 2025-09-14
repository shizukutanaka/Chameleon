#!/usr/bin/env python3
"""
Voice Quality Optimizer
Advanced audio quality enhancement and artifact reduction for voice processing

Techniques implemented:
- Perceptual Quality Enhancement
- Artifact Reduction Algorithms  
- Naturalness Optimization
- Psychoacoustic Processing
- Adaptive Quality Control
"""

import numpy as np
import scipy.signal
import scipy.fft
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from functools import lru_cache
import warnings

warnings.filterwarnings('ignore')

@dataclass
class QualityConfig:
    """Configuration for quality optimization"""
    sample_rate: int = 44100
    
    # Quality enhancement parameters
    noise_floor_db: float = -60.0       # Noise floor threshold
    dynamic_range_db: float = 40.0      # Target dynamic range
    spectral_smoothing: float = 0.3     # Spectral smoothing factor
    
    # Artifact reduction
    artifact_threshold: float = 0.1     # Artifact detection threshold
    declick_strength: float = 0.5       # Click/pop removal strength
    dehiss_strength: float = 0.3        # Hiss removal strength
    
    # Naturalness enhancement
    formant_enhancement: bool = True    # Enhance formant clarity
    harmonic_enhancement: bool = True   # Enhance harmonic structure
    transient_preservation: bool = True # Preserve attack/decay
    
    # Adaptive processing
    adaptive_processing: bool = True    # Enable adaptive algorithms
    quality_target: float = 0.85        # Target quality score (0-1)

class PsychoacousticProcessor:
    """Psychoacoustic processing for perceptually optimized enhancement"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.bark_scale = self._create_bark_scale()
        self.masking_threshold = self._create_masking_model()
        
    def _create_bark_scale(self) -> np.ndarray:
        """Create Bark scale frequency mapping"""
        # Bark scale: critical bands of human auditory system
        max_freq = self.sample_rate / 2
        n_bins = 1024
        
        freqs = np.linspace(0, max_freq, n_bins)
        bark_freqs = 13 * np.arctan(0.00076 * freqs) + 3.5 * np.arctan((freqs / 7500) ** 2)
        
        return bark_freqs
    
    def _create_masking_model(self) -> np.ndarray:
        """Create psychoacoustic masking model"""
        # Simplified masking threshold calculation
        # In reality, this would be more complex
        n_bark_bands = 24
        masking_threshold = np.zeros(n_bark_bands)
        
        # Quiet threshold in dB SPL for each Bark band
        quiet_thresholds = [
            4, -9, -9, -9, -9, -11, -12, -13, -12, -12,
            -10, -7, -4, -2, 0, 2, 5, 7, 8, 10,
            12, 13, 15, 17
        ]
        
        masking_threshold[:len(quiet_thresholds)] = quiet_thresholds
        
        return masking_threshold
    
    def apply_psychoacoustic_enhancement(self, audio: np.ndarray) -> np.ndarray:
        """Apply psychoacoustic enhancement"""
        # STFT
        f, t, stft = scipy.fft.stft(audio, fs=self.sample_rate, nperseg=2048)
        
        # Convert to perceptual domain
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Apply perceptual weighting
        enhanced_magnitude = self._apply_perceptual_weighting(magnitude, f)
        
        # Reconstruct signal
        enhanced_stft = enhanced_magnitude * np.exp(1j * phase)
        _, enhanced_audio = scipy.fft.istft(enhanced_stft, fs=self.sample_rate)
        
        return enhanced_audio[:len(audio)]
    
    def _apply_perceptual_weighting(self, magnitude: np.ndarray, 
                                  freqs: np.ndarray) -> np.ndarray:
        """Apply perceptual frequency weighting"""
        # A-weighting curve approximation
        a_weight = np.zeros_like(freqs)
        
        for i, freq in enumerate(freqs):
            if freq > 0:
                # A-weighting formula
                f2 = freq ** 2
                a_weight[i] = (12194**2 * f2**2) / (
                    (f2 + 20.6**2) * 
                    np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * 
                    (f2 + 12194**2)
                )
            
        # Normalize
        a_weight = a_weight / np.max(a_weight)
        
        # Apply weighting to magnitude
        weighted_magnitude = magnitude * a_weight[:, np.newaxis]
        
        return weighted_magnitude

class ArtifactReducer:
    """Advanced artifact reduction algorithms"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        
    def reduce_artifacts(self, audio: np.ndarray, config: QualityConfig) -> np.ndarray:
        """Main artifact reduction pipeline"""
        processed = audio.copy()
        
        # Remove clicks and pops
        processed = self._declick(processed, config.declick_strength)
        
        # Remove hiss and high-frequency noise
        processed = self._dehiss(processed, config.dehiss_strength)
        
        # Remove processing artifacts
        processed = self._remove_processing_artifacts(processed, config.artifact_threshold)
        
        # Spectral smoothing
        processed = self._spectral_smoothing(processed, config.spectral_smoothing)
        
        return processed
    
    def _declick(self, audio: np.ndarray, strength: float) -> np.ndarray:
        """Remove clicks and pops"""
        if strength <= 0:
            return audio
            
        # Detect clicks using derivative
        diff = np.abs(np.diff(audio))
        threshold = np.percentile(diff, 99) * (1 + strength)
        
        click_indices = np.where(diff > threshold)[0]
        
        # Interpolate over clicks
        processed = audio.copy()
        for idx in click_indices:
            # Interpolate over small region around click
            start = max(0, idx - 5)
            end = min(len(audio), idx + 6)
            
            if end > start + 1:
                # Linear interpolation
                x = np.array([start, end-1])
                y = np.array([audio[start], audio[end-1]])
                interp_indices = np.arange(start, end)
                processed[start:end] = np.interp(interp_indices, x, y)
                
        return processed
    
    def _dehiss(self, audio: np.ndarray, strength: float) -> np.ndarray:
        """Remove hiss and high-frequency noise"""
        if strength <= 0:
            return audio
            
        # Spectral subtraction approach
        f, t, stft = scipy.fft.stft(audio, fs=self.sample_rate)
        
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Estimate noise spectrum from quieter parts
        power = magnitude ** 2
        noise_estimate = np.percentile(power, 10, axis=1, keepdims=True)
        
        # Spectral subtraction
        alpha = strength * 2.0
        enhanced_power = power - alpha * noise_estimate
        
        # Prevent over-subtraction
        enhanced_power = np.maximum(enhanced_power, 0.1 * power)
        
        # Reconstruct magnitude
        enhanced_magnitude = np.sqrt(enhanced_power)
        
        # Reconstruct signal
        enhanced_stft = enhanced_magnitude * np.exp(1j * phase)
        _, processed = scipy.fft.istft(enhanced_stft, fs=self.sample_rate)
        
        return processed[:len(audio)]
    
    def _remove_processing_artifacts(self, audio: np.ndarray, 
                                   threshold: float) -> np.ndarray:
        """Remove artifacts from processing algorithms"""
        # Identify and reduce aliasing artifacts
        processed = self._reduce_aliasing(audio)
        
        # Reduce quantization noise
        processed = self._reduce_quantization_noise(processed, threshold)
        
        return processed
    
    def _reduce_aliasing(self, audio: np.ndarray) -> np.ndarray:
        """Reduce aliasing artifacts"""
        # Anti-aliasing filter
        nyquist = self.sample_rate / 2
        cutoff = 0.8 * nyquist  # 80% of Nyquist frequency
        
        # Butterworth low-pass filter
        sos = scipy.signal.butter(8, cutoff / nyquist, btype='low', output='sos')
        filtered = scipy.signal.sosfilt(sos, audio)
        
        return filtered
    
    def _reduce_quantization_noise(self, audio: np.ndarray, 
                                  threshold: float) -> np.ndarray:
        """Reduce quantization noise"""
        # Add small amount of triangular dither
        dither_amplitude = threshold * 0.1
        dither = np.random.triangular(-dither_amplitude, 0, dither_amplitude, len(audio))
        
        # Apply dither only to low-level signals
        audio_level = np.abs(audio)
        dither_mask = audio_level < threshold
        
        processed = audio.copy()
        processed[dither_mask] += dither[dither_mask]
        
        return processed
    
    def _spectral_smoothing(self, audio: np.ndarray, smoothing: float) -> np.ndarray:
        """Apply spectral smoothing to reduce roughness"""
        if smoothing <= 0:
            return audio
            
        # STFT
        f, t, stft = scipy.fft.stft(audio, fs=self.sample_rate)
        
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Smooth magnitude spectrum
        for t_idx in range(magnitude.shape[1]):
            # Moving average smoothing
            kernel_size = max(3, int(smoothing * 10))
            kernel = np.ones(kernel_size) / kernel_size
            
            smoothed_mag = np.convolve(magnitude[:, t_idx], kernel, mode='same')
            magnitude[:, t_idx] = (1 - smoothing) * magnitude[:, t_idx] + smoothing * smoothed_mag
            
        # Reconstruct
        smoothed_stft = magnitude * np.exp(1j * phase)
        _, smoothed_audio = scipy.fft.istft(smoothed_stft, fs=self.sample_rate)
        
        return smoothed_audio[:len(audio)]

class NaturalnessEnhancer:
    """Enhance naturalness of processed voice"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.formant_detector = FormantDetector(sample_rate)
        
    def enhance_naturalness(self, audio: np.ndarray, config: QualityConfig) -> np.ndarray:
        """Main naturalness enhancement pipeline"""
        processed = audio.copy()
        
        if config.formant_enhancement:
            processed = self._enhance_formants(processed)
            
        if config.harmonic_enhancement:
            processed = self._enhance_harmonics(processed)
            
        if config.transient_preservation:
            processed = self._preserve_transients(processed, audio)
            
        return processed
    
    def _enhance_formants(self, audio: np.ndarray) -> np.ndarray:
        """Enhance formant clarity"""
        # Detect formants
        formants = self.formant_detector.detect_formants(audio)
        
        if len(formants) == 0:
            return audio
            
        # STFT processing
        f, t, stft = scipy.fft.stft(audio, fs=self.sample_rate)
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Enhance formant regions
        for formant_freq in formants:
            # Find frequency bin
            formant_bin = int(formant_freq * len(f) / (self.sample_rate / 2))
            
            if 0 <= formant_bin < len(magnitude):
                # Enhance formant and nearby frequencies
                enhance_range = max(1, len(f) // 100)  # 1% of spectrum
                start_bin = max(0, formant_bin - enhance_range)
                end_bin = min(len(magnitude), formant_bin + enhance_range)
                
                # Gentle enhancement
                enhancement = np.hanning(end_bin - start_bin) * 0.2 + 1.0
                magnitude[start_bin:end_bin] *= enhancement[:, np.newaxis]
                
        # Reconstruct
        enhanced_stft = magnitude * np.exp(1j * phase)
        _, enhanced = scipy.fft.istft(enhanced_stft, fs=self.sample_rate)
        
        return enhanced[:len(audio)]
    
    def _enhance_harmonics(self, audio: np.ndarray) -> np.ndarray:
        """Enhance harmonic structure"""
        # Detect fundamental frequency
        f0 = self._estimate_f0(audio)
        
        if f0 <= 0:
            return audio
            
        # STFT processing
        f, t, stft = scipy.fft.stft(audio, fs=self.sample_rate)
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Enhance harmonics
        for harmonic in range(2, 8):  # Enhance up to 7th harmonic
            harmonic_freq = f0 * harmonic
            
            if harmonic_freq < self.sample_rate / 2:
                harmonic_bin = int(harmonic_freq * len(f) / (self.sample_rate / 2))
                
                if 0 <= harmonic_bin < len(magnitude):
                    # Gentle harmonic enhancement
                    enhance_width = max(1, len(f) // 200)
                    start_bin = max(0, harmonic_bin - enhance_width)
                    end_bin = min(len(magnitude), harmonic_bin + enhance_width)
                    
                    enhancement_strength = 1.0 + 0.1 / harmonic  # Weaker for higher harmonics
                    magnitude[start_bin:end_bin] *= enhancement_strength
                    
        # Reconstruct
        enhanced_stft = magnitude * np.exp(1j * phase)
        _, enhanced = scipy.fft.istft(enhanced_stft, fs=self.sample_rate)
        
        return enhanced[:len(audio)]
    
    def _preserve_transients(self, processed: np.ndarray, original: np.ndarray) -> np.ndarray:
        """Preserve transient characteristics"""
        if len(processed) != len(original):
            return processed
            
        # Detect transients in original
        transient_mask = self._detect_transients(original)
        
        # Blend original transients back into processed signal
        blend_factor = 0.3  # 30% of original transients
        result = processed.copy()
        result[transient_mask] = (
            (1 - blend_factor) * processed[transient_mask] + 
            blend_factor * original[transient_mask]
        )
        
        return result
    
    def _detect_transients(self, audio: np.ndarray) -> np.ndarray:
        """Detect transient regions"""
        # High-frequency energy detection
        # Butterworth high-pass filter
        nyquist = self.sample_rate / 2
        cutoff = 2000 / nyquist  # 2 kHz
        
        sos = scipy.signal.butter(4, cutoff, btype='high', output='sos')
        hf_signal = scipy.signal.sosfilt(sos, audio)
        
        # Energy envelope
        envelope = np.abs(scipy.signal.hilbert(hf_signal))
        
        # Smooth envelope
        smooth_envelope = scipy.signal.savgol_filter(envelope, 21, 3)
        
        # Detect rapid increases in energy
        energy_diff = np.diff(smooth_envelope)
        threshold = np.percentile(energy_diff, 90)
        
        transient_mask = np.zeros_like(audio, dtype=bool)
        transient_indices = np.where(energy_diff > threshold)[0]
        
        # Expand transient regions
        for idx in transient_indices:
            start = max(0, idx - 50)
            end = min(len(transient_mask), idx + 51)
            transient_mask[start:end] = True
            
        return transient_mask
    
    def _estimate_f0(self, audio: np.ndarray) -> float:
        """Estimate fundamental frequency"""
        # Autocorrelation-based F0 estimation
        frame_size = min(2048, len(audio))
        frame = audio[:frame_size]
        
        # Apply window
        windowed = frame * np.hanning(len(frame))
        
        # Autocorrelation
        corr = np.correlate(windowed, windowed, mode='full')
        corr = corr[len(corr)//2:]
        
        # Find peak in F0 range
        min_period = int(self.sample_rate / 800)  # 800 Hz max
        max_period = int(self.sample_rate / 50)   # 50 Hz min
        
        if max_period < len(corr):
            search_range = corr[min_period:max_period]
            if len(search_range) > 0:
                peak_idx = np.argmax(search_range) + min_period
                return self.sample_rate / peak_idx
                
        return 0.0

class FormantDetector:
    """Detect formant frequencies in speech"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        
    def detect_formants(self, audio: np.ndarray, n_formants: int = 4) -> List[float]:
        """Detect formant frequencies using LPC"""
        # Linear Prediction Coding for formant detection
        frame_size = min(1024, len(audio))
        frame = audio[:frame_size]
        
        # Pre-emphasis
        pre_emphasized = np.append(frame[0], frame[1:] - 0.97 * frame[:-1])
        
        # Window
        windowed = pre_emphasized * np.hanning(len(pre_emphasized))
        
        # LPC analysis
        lpc_order = 12
        autocorr = np.correlate(windowed, windowed, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        # Levinson-Durbin algorithm
        lpc_coeffs = self._levinson_durbin(autocorr, lpc_order)
        
        # Find formants from LPC polynomial roots
        formants = self._lpc_to_formants(lpc_coeffs)
        
        return formants[:n_formants]
    
    def _levinson_durbin(self, autocorr: np.ndarray, order: int) -> np.ndarray:
        """Levinson-Durbin algorithm for LPC coefficients"""
        a = np.zeros(order + 1)
        a[0] = 1.0
        
        if len(autocorr) <= order:
            return a
            
        e = autocorr[0]
        
        for i in range(1, order + 1):
            if e == 0:
                break
                
            k = autocorr[i]
            for j in range(1, i):
                k -= a[j] * autocorr[i - j]
            k /= e
            
            a_new = np.zeros_like(a)
            a_new[0] = 1.0
            a_new[i] = k
            
            for j in range(1, i):
                a_new[j] = a[j] - k * a[i - j]
                
            a = a_new
            e *= (1 - k * k)
            
        return a
    
    def _lpc_to_formants(self, lpc_coeffs: np.ndarray) -> List[float]:
        """Extract formant frequencies from LPC coefficients"""
        # Find roots of LPC polynomial
        roots = np.roots(lpc_coeffs)
        
        # Extract formant frequencies from roots
        formants = []
        
        for root in roots:
            if np.imag(root) > 0:  # Only positive imaginary parts
                # Convert to frequency
                angle = np.angle(root)
                freq = angle * self.sample_rate / (2 * np.pi)
                
                # Check if within reasonable formant range
                if 100 <= freq <= 4000:
                    formants.append(freq)
                    
        # Sort formants
        formants.sort()
        
        return formants

class VoiceQualityOptimizer:
    """Main voice quality optimization system"""
    
    def __init__(self, config: Optional[QualityConfig] = None):
        self.config = config or QualityConfig()
        
        # Initialize processors
        self.psychoacoustic = PsychoacousticProcessor(self.config.sample_rate)
        self.artifact_reducer = ArtifactReducer(self.config.sample_rate)
        self.naturalness_enhancer = NaturalnessEnhancer(self.config.sample_rate)
        
        print(f"Voice Quality Optimizer initialized:")
        print(f"  - Sample rate: {self.config.sample_rate} Hz")
        print(f"  - Quality target: {self.config.quality_target}")
        print(f"  - Adaptive processing: {self.config.adaptive_processing}")
    
    def optimize_quality(self, audio: np.ndarray, 
                        processing_artifacts: Optional[Dict[str, float]] = None) -> np.ndarray:
        """Main quality optimization pipeline"""
        processed = audio.copy().astype(np.float32)
        
        # Normalize input
        processed = self._normalize_audio(processed)
        
        # 1. Artifact reduction
        processed = self.artifact_reducer.reduce_artifacts(processed, self.config)
        
        # 2. Psychoacoustic enhancement
        processed = self.psychoacoustic.apply_psychoacoustic_enhancement(processed)
        
        # 3. Naturalness enhancement
        processed = self.naturalness_enhancer.enhance_naturalness(processed, self.config)
        
        # 4. Dynamic range optimization
        processed = self._optimize_dynamic_range(processed)
        
        # 5. Final polishing
        processed = self._final_polish(processed)
        
        # Adaptive adjustment if enabled
        if self.config.adaptive_processing:
            quality_score = self._assess_quality(audio, processed)
            if quality_score < self.config.quality_target:
                processed = self._adaptive_enhancement(processed, quality_score)
                
        return processed
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio amplitude"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            return audio / max_val * 0.95
        return audio
    
    def _optimize_dynamic_range(self, audio: np.ndarray) -> np.ndarray:
        """Optimize dynamic range"""
        # Calculate current dynamic range
        rms = np.sqrt(np.mean(audio**2))
        peak = np.max(np.abs(audio))
        
        if rms > 0:
            current_dr = 20 * np.log10(peak / rms)
            target_dr = self.config.dynamic_range_db
            
            if current_dr > target_dr:
                # Apply gentle compression
                ratio = target_dr / current_dr
                compressed = np.sign(audio) * np.abs(audio) ** ratio
                return compressed
                
        return audio
    
    def _final_polish(self, audio: np.ndarray) -> np.ndarray:
        """Final polishing pass"""
        # Gentle high-frequency enhancement
        nyquist = self.config.sample_rate / 2
        sos = scipy.signal.butter(2, 3000 / nyquist, btype='high', output='sos')
        hf_signal = scipy.signal.sosfilt(sos, audio)
        
        # Add subtle high-frequency enhancement
        polished = audio + 0.05 * hf_signal
        
        # Final limiting to prevent clipping
        return np.clip(polished, -0.99, 0.99)
    
    def _assess_quality(self, original: np.ndarray, processed: np.ndarray) -> float:
        """Assess quality of processed audio"""
        if len(original) != len(processed):
            return 0.5
            
        # Multiple quality metrics
        metrics = []
        
        # Signal correlation
        correlation = np.corrcoef(original, processed)[0, 1]
        if not np.isnan(correlation):
            metrics.append(correlation)
            
        # RMS preservation
        original_rms = np.sqrt(np.mean(original**2))
        processed_rms = np.sqrt(np.mean(processed**2))
        
        if original_rms > 0:
            rms_ratio = processed_rms / original_rms
            rms_quality = 1.0 - abs(rms_ratio - 1.0)
            metrics.append(max(0, rms_quality))
            
        # Spectral similarity
        original_fft = np.abs(np.fft.rfft(original))
        processed_fft = np.abs(np.fft.rfft(processed))
        
        # Normalize spectra
        original_fft = original_fft / (np.sum(original_fft) + 1e-10)
        processed_fft = processed_fft / (np.sum(processed_fft) + 1e-10)
        
        # Spectral correlation
        spectral_corr = np.corrcoef(original_fft, processed_fft)[0, 1]
        if not np.isnan(spectral_corr):
            metrics.append(spectral_corr)
            
        # Combined quality score
        return np.mean(metrics) if metrics else 0.5
    
    def _adaptive_enhancement(self, audio: np.ndarray, current_quality: float) -> np.ndarray:
        """Apply adaptive enhancement based on quality score"""
        quality_deficit = self.config.quality_target - current_quality
        
        if quality_deficit <= 0:
            return audio
            
        # Additional enhancement based on quality deficit
        enhancement_strength = min(1.0, quality_deficit * 2)
        
        # Spectral enhancement
        f, t, stft = scipy.fft.stft(audio, fs=self.config.sample_rate)
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Adaptive spectral shaping
        freq_weights = self._create_adaptive_weights(f, enhancement_strength)
        enhanced_magnitude = magnitude * freq_weights[:, np.newaxis]
        
        # Reconstruct
        enhanced_stft = enhanced_magnitude * np.exp(1j * phase)
        _, enhanced = scipy.fft.istft(enhanced_stft, fs=self.config.sample_rate)
        
        return enhanced[:len(audio)]
    
    def _create_adaptive_weights(self, freqs: np.ndarray, strength: float) -> np.ndarray:
        """Create adaptive frequency weights"""
        weights = np.ones_like(freqs)
        
        # Enhance speech-important frequencies
        for freq in [500, 1000, 2000, 3000]:  # Important for speech clarity
            freq_idx = np.argmin(np.abs(freqs - freq))
            
            # Gaussian enhancement around important frequencies
            sigma = len(freqs) / 20  # Width of enhancement
            enhancement = strength * 0.2 * np.exp(
                -((np.arange(len(freqs)) - freq_idx) ** 2) / (2 * sigma ** 2)
            )
            weights += enhancement
            
        return weights

# Demo and testing functions
def demo_quality_optimization():
    """Demonstrate voice quality optimization"""
    print("=== Voice Quality Optimization Demo ===\n")
    
    # Configuration
    config = QualityConfig(
        sample_rate=44100,
        quality_target=0.9,
        adaptive_processing=True,
        formant_enhancement=True,
        harmonic_enhancement=True
    )
    
    # Initialize optimizer
    optimizer = VoiceQualityOptimizer(config)
    
    # Create test signal with some artifacts
    duration = 2.0
    t = np.linspace(0, duration, int(config.sample_rate * duration))
    
    # Base signal: harmonic series
    f0 = 150  # Hz
    clean_signal = (np.sin(2 * np.pi * f0 * t) + 
                   0.7 * np.sin(2 * np.pi * f0 * 2 * t) +
                   0.5 * np.sin(2 * np.pi * f0 * 3 * t) +
                   0.3 * np.sin(2 * np.pi * f0 * 4 * t))
    
    # Add artifacts
    noisy_signal = clean_signal.copy()
    
    # Add noise
    noisy_signal += 0.05 * np.random.normal(0, 1, len(t))
    
    # Add some clicks
    click_positions = np.random.choice(len(t), 10, replace=False)
    for pos in click_positions:
        if pos < len(noisy_signal) - 1:
            noisy_signal[pos] += 0.5 * np.random.choice([-1, 1])
            
    # Add hiss (high-frequency noise)
    hiss = 0.03 * np.random.normal(0, 1, len(t))
    hiss_filtered = scipy.signal.lfilter([1], [1, -0.5], hiss)  # High-pass characteristics
    noisy_signal += hiss_filtered
    
    print("Test signals created:")
    print(f"  Clean signal RMS: {np.sqrt(np.mean(clean_signal**2)):.3f}")
    print(f"  Noisy signal RMS: {np.sqrt(np.mean(noisy_signal**2)):.3f}")
    
    # Optimize quality
    print("\nApplying quality optimization...")
    optimized_signal = optimizer.optimize_quality(noisy_signal)
    
    # Calculate quality metrics
    clean_rms = np.sqrt(np.mean(clean_signal**2))
    noisy_rms = np.sqrt(np.mean(noisy_signal**2))
    optimized_rms = np.sqrt(np.mean(optimized_signal**2))
    
    # Quality assessment
    original_quality = optimizer._assess_quality(clean_signal, noisy_signal)
    final_quality = optimizer._assess_quality(clean_signal, optimized_signal)
    
    print(f"\nOptimization completed:")
    print(f"  Original quality score: {original_quality:.3f}")
    print(f"  Final quality score: {final_quality:.3f}")
    print(f"  Quality improvement: {final_quality - original_quality:.3f}")
    
    print(f"\nRMS values:")
    print(f"  Clean: {clean_rms:.3f}")
    print(f"  Noisy: {noisy_rms:.3f}")
    print(f"  Optimized: {optimized_rms:.3f}")
    
    return optimized_signal, final_quality

if __name__ == "__main__":
    demo_quality_optimization()