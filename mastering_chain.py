#!/usr/bin/env python3
"""
Professional Audio Mastering Chain for Chameleon
Complete mastering pipeline with industry-standard processing
"""

import os
import sys
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging
import warnings

# Audio processing libraries
try:
    import scipy.signal as signal
    import scipy.fft as fft
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    # Normal state under a minimal install — log at debug, don't warn on
    # import. Each processor degrades individually when scipy is absent.
    logging.getLogger("chameleon.optional_deps").debug(
        "SciPy not available. Advanced mastering features disabled.")

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

@dataclass
class EQBand:
    """Single EQ band configuration"""
    frequency: float
    gain: float
    q_factor: float = 1.0
    filter_type: str = "bell"  # bell, highpass, lowpass, highshelf, lowshelf

@dataclass
class CompressorConfig:
    """Compressor configuration"""
    threshold: float = -20.0  # dB
    ratio: float = 4.0
    attack: float = 5.0  # ms
    release: float = 50.0  # ms
    knee: float = 2.0  # dB
    makeup_gain: float = 0.0  # dB

@dataclass
class LimiterConfig:
    """Limiter configuration"""
    threshold: float = -1.0  # dB
    release: float = 50.0  # ms
    lookahead: float = 5.0  # ms

@dataclass
class StereoConfig:
    """Stereo enhancement configuration"""
    width: float = 1.0  # 0.0 = mono, 1.0 = normal, >1.0 = wider
    bass_mono: bool = True
    mono_freq: float = 120.0  # Hz below which to mono

@dataclass
class MasteringConfig:
    """Complete mastering chain configuration"""
    # Analysis
    auto_gain: bool = True
    target_lufs: float = -14.0  # LUFS for streaming

    # EQ
    eq_enabled: bool = True
    eq_bands: List[EQBand] = field(default_factory=list)

    # Dynamics
    compressor_enabled: bool = True
    compressor: CompressorConfig = field(default_factory=CompressorConfig)

    limiter_enabled: bool = True
    limiter: LimiterConfig = field(default_factory=LimiterConfig)

    # Stereo
    stereo_enabled: bool = True
    stereo: StereoConfig = field(default_factory=StereoConfig)

    # Enhancement
    harmonic_enhancement: float = 0.0  # 0.0-1.0
    stereo_enhancement: float = 0.0  # 0.0-1.0

    # Dithering
    dither_enabled: bool = True
    dither_type: str = "tpdf"  # tpdf, rpdf, shaped

class LoudnessMeter:
    """Approximate loudness measurement — NOT ITU-R BS.1770 compliant.

    This meter borrows the block/gating structure of BS.1770 but uses a plain
    200-2000 Hz Butterworth band-pass in place of true K-weighting (BS.1770-5
    K-weighting is a ~high-pass "stage 1" filter plus a +4 dB high-shelf at
    2 kHz). It also omits true-peak oversampling and multi-channel weighting.
    Values are useful as a relative loudness indicator, not as certified LUFS.
    A dependency-free, standard-conformant implementation is tracked as a
    follow-up (see CHARTER §9).
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.block_size = int(0.4 * sample_rate)  # 400ms blocks
        self.setup_filters()

    def setup_filters(self):
        """Set up the approximate weighting filters (not true K-weighting)."""
        if not HAS_SCIPY:
            return

        # Pre-filter (high-pass at 20Hz)
        self.pre_b, self.pre_a = signal.butter(2, 20 / (self.sample_rate / 2), 'high')

        # Approximate weighting: a 200-2000 Hz band-pass. This is NOT the
        # BS.1770 K-weighting curve (which is a high-pass + 2 kHz high-shelf);
        # it only crudely de-emphasises very low and very high energy.
        self.k_b, self.k_a = signal.butter(2, [200, 2000], 'band', fs=self.sample_rate)

    def measure_lufs(self, audio: np.ndarray) -> float:
        """Return an approximate loudness figure (relative, not certified LUFS)."""
        if not HAS_SCIPY:
            # Fallback to simple RMS measurement
            rms = np.sqrt(np.mean(audio**2))
            return 20 * np.log10(rms + 1e-10) + 3.0  # Rough conversion

        # Apply the approximate band-pass weighting (not true K-weighting)
        if audio.ndim == 1:
            audio = audio.reshape(1, -1)

        # Pre-filter
        filtered = np.zeros_like(audio)
        for ch in range(audio.shape[0]):
            filtered[ch] = signal.filtfilt(self.pre_b, self.pre_a, audio[ch])
            filtered[ch] = signal.filtfilt(self.k_b, self.k_a, filtered[ch])

        # Calculate mean square for each block
        blocks = []
        for i in range(0, audio.shape[1] - self.block_size, self.block_size):
            block = filtered[:, i:i + self.block_size]

            # Channel weighting (L and R channels get weight 1.0)
            if audio.shape[0] == 1:
                mean_square = np.mean(block**2)
            elif audio.shape[0] == 2:
                mean_square = np.mean(block**2)
            else:
                # More complex channel weighting for surround
                mean_square = np.mean(block**2)

            if mean_square > 0:
                blocks.append(mean_square)

        if not blocks:
            return -float('inf')

        # Gating
        relative_threshold = 0.1 * np.mean(blocks)  # -10dB relative gate
        gated_blocks = [b for b in blocks if b >= relative_threshold]

        if not gated_blocks:
            return -float('inf')

        absolute_threshold = 10**(-70/10)  # -70 LUFS absolute gate
        final_blocks = [b for b in gated_blocks if b >= absolute_threshold]

        if not final_blocks:
            return -float('inf')

        # Calculate final loudness
        mean_square = np.mean(final_blocks)
        lufs = -0.691 + 10 * np.log10(mean_square)

        return lufs

    def measure_peak(self, audio: np.ndarray) -> float:
        """Return the sample-peak level in dBFS (NOT true peak).

        True-peak measurement requires >=4x oversampling to catch inter-sample
        peaks; this returns the raw sample peak, which can under-read by up to
        ~3 dB on heavily limited material.
        """
        return 20 * np.log10(np.abs(audio).max() + 1e-10)

    def measure_range(self, audio: np.ndarray) -> float:
        """Placeholder loudness range (LRA) — returns integrated loudness.

        A real LRA needs the distribution of short-term (3 s) loudness values;
        this simply echoes the integrated figure and should not be read as LRA.
        """
        if not HAS_SCIPY:
            return 0.0

        return self.measure_lufs(audio)  # Placeholder, not a true LRA

class ParametricEQ:
    """Professional parametric equalizer"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.filters = []

    def add_band(self, band: EQBand):
        """Add EQ band"""
        if not HAS_SCIPY:
            return

        nyquist = self.sample_rate / 2
        freq_norm = band.frequency / nyquist

        if freq_norm >= 1.0:
            return

        if band.filter_type == "bell":
            # Peaking filter
            if abs(band.gain) > 0.1:  # Only add if significant gain
                b, a = signal.iirpeak(freq_norm, band.q_factor)
                gain_linear = 10**(band.gain / 20)
                self.filters.append((b, a, gain_linear, band.filter_type))

        elif band.filter_type == "highpass":
            b, a = signal.butter(2, freq_norm, 'high')
            self.filters.append((b, a, 1.0, band.filter_type))

        elif band.filter_type == "lowpass":
            b, a = signal.butter(2, freq_norm, 'low')
            self.filters.append((b, a, 1.0, band.filter_type))

        elif band.filter_type == "highshelf":
            # Simplified high shelf
            b, a = signal.butter(1, freq_norm, 'high')
            gain_linear = 10**(band.gain / 20)
            self.filters.append((b, a, gain_linear, band.filter_type))

        elif band.filter_type == "lowshelf":
            # Simplified low shelf
            b, a = signal.butter(1, freq_norm, 'low')
            gain_linear = 10**(band.gain / 20)
            self.filters.append((b, a, gain_linear, band.filter_type))

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply EQ to audio"""
        if not self.filters or not HAS_SCIPY:
            return audio

        result = audio.copy()

        for b, a, gain, filter_type in self.filters:
            if audio.ndim == 1:
                if filter_type == "bell":
                    # Apply gain only to filtered signal
                    filtered = signal.filtfilt(b, a, result)
                    result = result + (filtered - result) * (gain - 1)
                else:
                    result = signal.filtfilt(b, a, result) * gain
            else:
                for ch in range(audio.shape[0]):
                    if filter_type == "bell":
                        filtered = signal.filtfilt(b, a, result[ch])
                        result[ch] = result[ch] + (filtered - result[ch]) * (gain - 1)
                    else:
                        result[ch] = signal.filtfilt(b, a, result[ch]) * gain

        return result

class Compressor:
    """Professional audio compressor with advanced features"""

    def __init__(self, config: CompressorConfig, sample_rate: int = 44100):
        self.config = config
        self.sample_rate = sample_rate

        # Convert time constants to samples
        self.attack_samples = max(1, int(config.attack * sample_rate / 1000))
        self.release_samples = max(1, int(config.release * sample_rate / 1000))

        # State variables
        self.envelope = 0.0
        self.gain_reduction = 0.0

    def process(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Process audio through compressor, return (audio, gain_reduction)"""
        if audio.ndim == 1:
            return self._process_mono(audio)
        else:
            # Stereo-linked compression
            return self._process_stereo(audio)

    def _process_mono(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Process mono audio"""
        output = np.zeros_like(audio)
        gain_reduction_curve = np.zeros_like(audio)

        threshold_linear = 10**(self.config.threshold / 20)
        makeup_gain_linear = 10**(self.config.makeup_gain / 20)

        for i, sample in enumerate(audio):
            # Detect level
            level = abs(sample)

            # Envelope follower
            if level > self.envelope:
                # Attack
                self.envelope += (level - self.envelope) / self.attack_samples
            else:
                # Release
                self.envelope += (level - self.envelope) / self.release_samples

            # Calculate gain reduction
            if self.envelope > threshold_linear:
                # Above threshold - apply compression
                overshoot = self.envelope / threshold_linear
                overshoot_db = 20 * np.log10(overshoot)

                # Soft knee
                if overshoot_db < self.config.knee:
                    # In knee region
                    reduction_db = overshoot_db**2 / (2 * self.config.knee) * (1/self.config.ratio - 1)
                else:
                    # Above knee
                    reduction_db = overshoot_db * (1/self.config.ratio - 1)

                target_gain_reduction = -abs(reduction_db)
            else:
                target_gain_reduction = 0.0

            # Smooth gain reduction changes
            if target_gain_reduction < self.gain_reduction:
                # Attack
                self.gain_reduction += (target_gain_reduction - self.gain_reduction) / self.attack_samples
            else:
                # Release
                self.gain_reduction += (target_gain_reduction - self.gain_reduction) / self.release_samples

            # Apply gain reduction and makeup gain
            gain_linear = 10**(self.gain_reduction / 20) * makeup_gain_linear
            output[i] = sample * gain_linear
            gain_reduction_curve[i] = self.gain_reduction

        return output, gain_reduction_curve

    def _process_stereo(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Process stereo audio with linking"""
        output = np.zeros_like(audio)
        gain_reduction_curve = np.zeros(audio.shape[1])

        threshold_linear = 10**(self.config.threshold / 20)
        makeup_gain_linear = 10**(self.config.makeup_gain / 20)

        for i in range(audio.shape[1]):
            # Stereo linking - use maximum level of both channels
            level = max(abs(audio[0, i]), abs(audio[1, i]))

            # Envelope follower
            if level > self.envelope:
                self.envelope += (level - self.envelope) / self.attack_samples
            else:
                self.envelope += (level - self.envelope) / self.release_samples

            # Calculate gain reduction (same as mono)
            if self.envelope > threshold_linear:
                overshoot = self.envelope / threshold_linear
                overshoot_db = 20 * np.log10(overshoot)

                if overshoot_db < self.config.knee:
                    reduction_db = overshoot_db**2 / (2 * self.config.knee) * (1/self.config.ratio - 1)
                else:
                    reduction_db = overshoot_db * (1/self.config.ratio - 1)

                target_gain_reduction = -abs(reduction_db)
            else:
                target_gain_reduction = 0.0

            # Smooth gain reduction
            if target_gain_reduction < self.gain_reduction:
                self.gain_reduction += (target_gain_reduction - self.gain_reduction) / self.attack_samples
            else:
                self.gain_reduction += (target_gain_reduction - self.gain_reduction) / self.release_samples

            # Apply same gain reduction to both channels
            gain_linear = 10**(self.gain_reduction / 20) * makeup_gain_linear
            output[0, i] = audio[0, i] * gain_linear
            output[1, i] = audio[1, i] * gain_linear
            gain_reduction_curve[i] = self.gain_reduction

        return output, gain_reduction_curve

class Limiter:
    """Professional brick-wall limiter"""

    def __init__(self, config: LimiterConfig, sample_rate: int = 44100):
        self.config = config
        self.sample_rate = sample_rate

        self.lookahead_samples = int(config.lookahead * sample_rate / 1000)
        self.release_samples = int(config.release * sample_rate / 1000)

        # Delay buffer for lookahead
        self.delay_buffer = np.zeros(self.lookahead_samples)
        self.gain_reduction = 1.0

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio through limiter"""
        if audio.ndim == 1:
            return self._process_mono(audio)
        else:
            return self._process_stereo(audio)

    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio"""
        output = np.zeros_like(audio)
        threshold_linear = 10**(self.config.threshold / 20)

        # Extend audio with delay buffer
        extended_audio = np.concatenate([self.delay_buffer, audio])

        for i in range(len(audio)):
            # Look ahead to find peak
            lookahead_start = i
            lookahead_end = i + self.lookahead_samples
            lookahead_peak = np.abs(extended_audio[lookahead_start:lookahead_end]).max()

            # Calculate required gain reduction
            if lookahead_peak > threshold_linear:
                required_gain = threshold_linear / lookahead_peak
            else:
                required_gain = 1.0

            # Smooth gain changes
            if required_gain < self.gain_reduction:
                # Attack (instant for limiter)
                self.gain_reduction = required_gain
            else:
                # Release
                self.gain_reduction += (required_gain - self.gain_reduction) / self.release_samples

            # Apply gain to delayed signal
            output[i] = extended_audio[i] * self.gain_reduction

        # Update delay buffer
        self.delay_buffer = audio[-self.lookahead_samples:] if len(audio) >= self.lookahead_samples else audio

        return output

    def _process_stereo(self, audio: np.ndarray) -> np.ndarray:
        """Process stereo audio"""
        output = np.zeros_like(audio)
        threshold_linear = 10**(self.config.threshold / 20)

        # Extend with delay buffer
        if hasattr(self, 'delay_buffer_stereo'):
            extended_audio = np.concatenate([self.delay_buffer_stereo, audio], axis=1)
        else:
            self.delay_buffer_stereo = np.zeros((audio.shape[0], self.lookahead_samples))
            extended_audio = np.concatenate([self.delay_buffer_stereo, audio], axis=1)

        for i in range(audio.shape[1]):
            # Look ahead - use maximum of both channels
            lookahead_start = i
            lookahead_end = i + self.lookahead_samples
            lookahead_peak = np.abs(extended_audio[:, lookahead_start:lookahead_end]).max()

            # Calculate gain reduction
            if lookahead_peak > threshold_linear:
                required_gain = threshold_linear / lookahead_peak
            else:
                required_gain = 1.0

            # Smooth gain changes
            if required_gain < self.gain_reduction:
                self.gain_reduction = required_gain
            else:
                self.gain_reduction += (required_gain - self.gain_reduction) / self.release_samples

            # Apply to both channels
            output[0, i] = extended_audio[0, i] * self.gain_reduction
            output[1, i] = extended_audio[1, i] * self.gain_reduction

        # Update delay buffer
        if audio.shape[1] >= self.lookahead_samples:
            self.delay_buffer_stereo = audio[:, -self.lookahead_samples:]

        return output

class StereoProcessor:
    """Stereo width and enhancement processing"""

    def __init__(self, config: StereoConfig, sample_rate: int = 44100):
        self.config = config
        self.sample_rate = sample_rate
        self.setup_filters()

    def setup_filters(self):
        """Setup filters for bass mono processing"""
        if HAS_SCIPY and self.config.bass_mono:
            nyquist = self.sample_rate / 2
            cutoff = self.config.mono_freq / nyquist
            self.mono_b, self.mono_a = signal.butter(2, cutoff, 'low')

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process stereo audio"""
        if audio.ndim == 1:
            # Mono input - create stereo
            return np.array([audio, audio])

        if audio.shape[0] != 2:
            # More than 2 channels - just return first 2
            return audio[:2]

        left, right = audio[0], audio[1]

        # Mid/Side processing
        mid = (left + right) / 2
        side = (left - right) / 2

        # Apply width adjustment
        side = side * self.config.width

        # Bass mono processing
        if self.config.bass_mono and HAS_SCIPY:
            # Filter bass frequencies
            mid_bass = signal.filtfilt(self.mono_b, self.mono_a, mid)
            mid_high = mid - mid_bass
            side_high = signal.filtfilt(self.mono_b, self.mono_a, side)
            side = side - side_high  # Remove bass from side

            # Reconstruct
            mid = mid_bass + mid_high

        # Convert back to L/R
        left_out = mid + side
        right_out = mid - side

        return np.array([left_out, right_out])

class MasteringChain:
    """Complete professional mastering chain"""

    def __init__(self, config: MasteringConfig, sample_rate: int = 44100):
        self.config = config
        self.sample_rate = sample_rate
        self.logger = logging.getLogger(__name__)

        # Initialize processors
        self.loudness_meter = LoudnessMeter(sample_rate)

        if config.eq_enabled:
            self.eq = ParametricEQ(sample_rate)
            for band in config.eq_bands:
                self.eq.add_band(band)

        if config.compressor_enabled:
            self.compressor = Compressor(config.compressor, sample_rate)

        if config.limiter_enabled:
            self.limiter = Limiter(config.limiter, sample_rate)

        if config.stereo_enabled:
            self.stereo_processor = StereoProcessor(config.stereo, sample_rate)

    def analyze(self, audio: np.ndarray) -> Dict[str, float]:
        """Analyze audio before mastering"""
        analysis = {}

        # Loudness analysis
        analysis['lufs'] = self.loudness_meter.measure_lufs(audio)
        analysis['peak_db'] = self.loudness_meter.measure_peak(audio)
        analysis['range'] = self.loudness_meter.measure_range(audio)

        # Basic stats
        analysis['rms_db'] = 20 * np.log10(np.sqrt(np.mean(audio**2)) + 1e-10)
        analysis['crest_factor'] = analysis['peak_db'] - analysis['rms_db']

        # Dynamic range estimate
        sorted_samples = np.sort(np.abs(audio.flatten()))
        percentile_95 = sorted_samples[int(0.95 * len(sorted_samples))]
        percentile_10 = sorted_samples[int(0.10 * len(sorted_samples))]
        analysis['dynamic_range'] = 20 * np.log10(percentile_95 / (percentile_10 + 1e-10))

        return analysis

    def auto_adjust(self, audio: np.ndarray) -> MasteringConfig:
        """Automatically adjust mastering settings based on audio analysis"""
        analysis = self.analyze(audio)
        adjusted_config = self.config

        if self.config.auto_gain:
            # Adjust for target LUFS
            current_lufs = analysis['lufs']
            lufs_difference = self.config.target_lufs - current_lufs

            # Adjust compressor makeup gain
            if adjusted_config.compressor_enabled:
                adjusted_config.compressor.makeup_gain += lufs_difference * 0.7

            # Suggest EQ adjustments based on content
            if adjusted_config.eq_enabled and not adjusted_config.eq_bands:
                # Auto-generate basic mastering EQ
                adjusted_config.eq_bands = [
                    EQBand(frequency=80, gain=0.5, q_factor=0.7, filter_type="highpass"),  # HPF
                    EQBand(frequency=100, gain=1.0, q_factor=1.0),  # Low boost
                    EQBand(frequency=3000, gain=0.5, q_factor=1.5),  # Presence
                    EQBand(frequency=10000, gain=1.0, q_factor=0.8),  # Air
                ]

        return adjusted_config

    def process(self, audio: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Process audio through complete mastering chain"""
        # Initial analysis
        input_analysis = self.analyze(audio)
        processing_info = {"input_analysis": input_analysis}

        processed = audio.copy()

        # Auto-adjust if enabled
        if self.config.auto_gain:
            adjusted_config = self.auto_adjust(audio)
            # Apply adjusted settings
            if adjusted_config.compressor_enabled:
                self.compressor.config = adjusted_config.compressor

        # 1. EQ
        if self.config.eq_enabled and hasattr(self, 'eq'):
            processed = self.eq.process(processed)
            self.logger.debug("Applied EQ")

        # 2. Compression
        if self.config.compressor_enabled and hasattr(self, 'compressor'):
            processed, gain_reduction = self.compressor.process(processed)
            processing_info['compression_gain_reduction'] = np.mean(gain_reduction)
            self.logger.debug(f"Applied compression (avg GR: {processing_info['compression_gain_reduction']:.1f}dB)")

        # 3. Stereo processing
        if self.config.stereo_enabled and hasattr(self, 'stereo_processor'):
            processed = self.stereo_processor.process(processed)
            self.logger.debug("Applied stereo processing")

        # 4. Harmonic enhancement (simplified)
        if self.config.harmonic_enhancement > 0:
            processed = self._apply_harmonic_enhancement(processed, self.config.harmonic_enhancement)

        # 5. Limiting
        if self.config.limiter_enabled and hasattr(self, 'limiter'):
            processed = self.limiter.process(processed)
            self.logger.debug("Applied limiting")

        # 6. Dithering (if reducing bit depth)
        if self.config.dither_enabled:
            processed = self._apply_dither(processed, self.config.dither_type)

        # Final analysis
        output_analysis = self.analyze(processed)
        processing_info['output_analysis'] = output_analysis

        # Calculate processing metrics
        processing_info['lufs_change'] = output_analysis['lufs'] - input_analysis['lufs']
        processing_info['peak_change'] = output_analysis['peak_db'] - input_analysis['peak_db']

        return processed, processing_info

    def _apply_harmonic_enhancement(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """Apply subtle harmonic enhancement"""
        # Simple harmonic enhancement using soft saturation
        enhanced = audio.copy()

        # Soft clipping for harmonic generation
        enhanced = np.tanh(enhanced * (1 + amount * 2)) / (1 + amount * 2)

        # Mix with original
        return audio * (1 - amount) + enhanced * amount

    def _apply_dither(self, audio: np.ndarray, dither_type: str) -> np.ndarray:
        """Apply dithering for bit depth reduction"""
        if dither_type == "tpdf":
            # Triangular PDF dither
            dither = np.random.uniform(-1, 1, audio.shape) + np.random.uniform(-1, 1, audio.shape)
            dither = dither / 65536  # For 16-bit
        elif dither_type == "rpdf":
            # Rectangular PDF dither
            dither = np.random.uniform(-1, 1, audio.shape) / 65536
        else:
            # No dither
            dither = 0

        return audio + dither

def create_mastering_preset(preset_name: str) -> MasteringConfig:
    """Create mastering presets for different purposes"""

    if preset_name == "streaming":
        # Optimized for streaming platforms
        return MasteringConfig(
            target_lufs=-14.0,
            eq_bands=[
                EQBand(frequency=30, gain=0, q_factor=0.7, filter_type="highpass"),
                EQBand(frequency=100, gain=0.5, q_factor=1.0),
                EQBand(frequency=3000, gain=0.3, q_factor=1.5),
                EQBand(frequency=10000, gain=0.8, q_factor=0.8),
            ],
            compressor=CompressorConfig(
                threshold=-18.0,
                ratio=3.0,
                attack=10.0,
                release=100.0,
                makeup_gain=2.0
            ),
            limiter=LimiterConfig(threshold=-1.0, release=50.0),
            stereo=StereoConfig(width=1.1, bass_mono=True)
        )

    elif preset_name == "cd":
        # CD mastering
        return MasteringConfig(
            target_lufs=-9.0,
            eq_bands=[
                EQBand(frequency=20, gain=0, q_factor=0.7, filter_type="highpass"),
                EQBand(frequency=80, gain=0.3, q_factor=1.2),
                EQBand(frequency=2500, gain=0.5, q_factor=1.0),
                EQBand(frequency=12000, gain=1.0, q_factor=0.8),
            ],
            compressor=CompressorConfig(
                threshold=-15.0,
                ratio=4.0,
                attack=5.0,
                release=50.0,
                makeup_gain=3.0
            ),
            limiter=LimiterConfig(threshold=-0.3, release=30.0),
            stereo=StereoConfig(width=1.0, bass_mono=True)
        )

    elif preset_name == "vinyl":
        # Vinyl mastering
        return MasteringConfig(
            target_lufs=-16.0,
            eq_bands=[
                EQBand(frequency=40, gain=0, q_factor=0.7, filter_type="highpass"),
                EQBand(frequency=150, gain=-0.5, q_factor=1.0),
                EQBand(frequency=2000, gain=0.3, q_factor=1.5),
                EQBand(frequency=15000, gain=-1.0, q_factor=0.8, filter_type="lowpass"),
            ],
            compressor=CompressorConfig(
                threshold=-20.0,
                ratio=2.5,
                attack=20.0,
                release=150.0,
                makeup_gain=1.0
            ),
            limiter=LimiterConfig(threshold=-2.0, release=100.0),
            stereo=StereoConfig(width=0.9, bass_mono=True, mono_freq=150.0)
        )

    else:
        # Default/gentle mastering
        return MasteringConfig()

def demo_mastering():
    """Demonstrate mastering chain capabilities"""
    print("🎚️ Chameleon Professional Mastering Demo")
    print("=" * 50)

    # Show available presets
    presets = ["streaming", "cd", "vinyl"]
    print("Available presets:")
    for preset in presets:
        config = create_mastering_preset(preset)
        print(f"  📀 {preset.upper()}: Target {config.target_lufs} LUFS")

    # Show mastering chain components
    print(f"\nMastering Chain Components:")
    print(f"  🎛️ Parametric EQ: {'✓' if HAS_SCIPY else '✗'}")
    print(f"  🗜️ Compressor: ✓")
    print(f"  🚧 Limiter: ✓")
    print(f"  🔊 Loudness Meter: {'✓' if HAS_SCIPY else '✗'}")
    print(f"  🎵 Stereo Processor: ✓")

if __name__ == "__main__":
    demo_mastering()