#!/usr/bin/env python3
"""
Audio Mastering Chain for Chameleon
EQ, compressor, lookahead limiter, and a loudness meter that is real
ITU-R BS.1770-4 (reusing bs1770_loudness.py's coefficients) when SciPy is
available, falling back to a rough RMS-based approximation otherwise -- see
LoudnessMeter's docstring for the exact conditions and remaining honest
limitations (no true-peak, no surround-channel weighting). Requires NumPy;
scipy is optional within individual stages.
"""

import os
import sys
import copy
import math
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

# bs1770_loudness.py is pure standard library (no third-party deps) and
# provides the exact ITU-R BS.1770-4 K-weighting coefficients, verified
# against the standard's published reference table. LoudnessMeter reuses
# them (via scipy.signal.lfilter, since that's already available whenever
# HAS_SCIPY is True) instead of its own approximate band-pass, so it can be
# a real, standard-conformant meter rather than a labelled-approximate one.
try:
    import bs1770_loudness
    HAS_BS1770 = True
except ImportError:
    HAS_BS1770 = False

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
    # NOT IMPLEMENTED -- nothing reads this field. Stereo width is controlled
    # by StereoConfig.width (0.0 mono, 1.0 normal, >1.0 wider), which
    # StereoProcessor actually applies. Wiring this one up would give the
    # chain two competing width knobs, so it is left inert and documented
    # rather than implemented. Kept only because removing a public config
    # field is a breaking change; see PRODUCT_ANALYSIS.md.
    stereo_enhancement: float = 0.0  # 0.0-1.0 (inert)

    # Dithering
    dither_enabled: bool = True
    dither_type: str = "tpdf"  # tpdf, rpdf ("shaped" is not implemented; falls back to tpdf)

class LoudnessMeter:
    """Integrated loudness (LUFS) and loudness range (LRA) measurement.

    When SciPy and bs1770_loudness are both available (the common case --
    SciPy is required for the rest of the mastering chain; bs1770_loudness
    is pure standard library), this reuses bs1770_loudness's exact ITU-R
    BS.1770-4 K-weighting coefficients -- verified against the standard's
    published reference table -- via a single-pass scipy.signal.lfilter.
    BS.1770 filtering is causal; an earlier version of this meter used
    filtfilt, whose zero-phase double pass roughly doubles the K-weighting
    shelf's gain. It follows the standard's block/gating structure: 400ms
    blocks with 75% overlap for integrated loudness (3s window / 100ms hop
    for loudness range), the absolute -70 LUFS gate applied *before* the relative gate
    (an earlier version had this order backwards), and per-channel energy
    *summed* rather than averaged (averaging under-reads real stereo content
    by ~3 dB for identical L/R, more for uncorrelated content -- see
    bs1770_loudness.py's module docstring for the general form of this
    error). Values are then real LUFS/LU, not an approximation.

    Falls back to a simple RMS-based estimate (clearly not LUFS, and with no
    principled loudness-range figure) if SciPy is unavailable, if
    bs1770_loudness somehow isn't importable, or if the sample rate is below
    bs1770_loudness's ~8kHz K-weighting stability floor.

    Remaining honest limitations: no true-peak oversampling (see
    measure_peak) and no surround-channel weighting (every channel is
    weighted equally, which is correct for mono/stereo but not layouts with
    rear/side channels).
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.block_size = int(0.4 * sample_rate)  # 400ms blocks (integrated loudness)
        self.setup_filters()

    def setup_filters(self):
        """Prepare the exact BS.1770 K-weighting coefficients, if available."""
        self._bs1770_ready = False
        if not (HAS_SCIPY and HAS_BS1770):
            return
        # Validate explicitly rather than relying on an exception: the
        # coefficient functions below (bs1770_loudness's private stage
        # helpers) do NOT themselves check the sample rate -- only the
        # public apply_k_weighting() wrapper does. Below this floor the
        # stage-1 shelving filter's pole leaves the unit circle and
        # scipy.signal.lfilter diverges to inf/NaN rather than merely being
        # inaccurate, so this must be caught before filtering, not after.
        if self.sample_rate < bs1770_loudness._MIN_SAMPLE_RATE_HZ:
            return
        stage1 = bs1770_loudness._stage1_head_effects(self.sample_rate)
        stage2 = bs1770_loudness._stage2_high_pass(self.sample_rate)
        self._stage1_ba = (np.array([stage1.b0, stage1.b1, stage1.b2]),
                            np.array([1.0, stage1.a1, stage1.a2]))
        self._stage2_ba = (np.array([stage2.b0, stage2.b1, stage2.b2]),
                            np.array([1.0, stage2.a1, stage2.a2]))
        self._bs1770_ready = True

    def _apply_k_weighting(self, audio: np.ndarray) -> np.ndarray:
        """Single-pass (causal) K-weighting on a (channels, samples) array."""
        filtered = np.zeros_like(audio, dtype=float)
        for ch in range(audio.shape[0]):
            stage1_out = signal.lfilter(self._stage1_ba[0], self._stage1_ba[1], audio[ch])
            filtered[ch] = signal.lfilter(self._stage2_ba[0], self._stage2_ba[1], stage1_out)
        return filtered

    def _block_summed_energies(self, weighted: np.ndarray, block_seconds: float,
                               hop_seconds: float) -> np.ndarray:
        """Per-block energy summed across channels (BS.1770 channel weighting)."""
        block_size = max(1, int(round(block_seconds * self.sample_rate)))
        hop = max(1, int(round(hop_seconds * self.sample_rate)))
        n = weighted.shape[1]
        if n < block_size:
            return np.array([])

        energies = []
        for start in range(0, n - block_size + 1, hop):
            block = weighted[:, start:start + block_size]
            channel_energy = np.mean(block ** 2, axis=1)  # mean-square per channel
            energies.append(float(np.sum(channel_energy)))  # summed across channels
        return np.array(energies)

    @staticmethod
    def _gate_absolute_then_relative(energies: np.ndarray, relative_gate_db: float) -> np.ndarray:
        """BS.1770 two-stage gating: the absolute -70 LUFS gate first, then a
        relative gate `relative_gate_db` below the mean of the
        absolute-gated set. Returns the doubly-gated energies (possibly
        empty)."""
        if energies.size == 0:
            return energies
        absolute_threshold = 10.0 ** ((-70.0 + 0.691) / 10.0)
        passed_absolute = energies[energies >= absolute_threshold]
        if passed_absolute.size == 0:
            return passed_absolute
        relative_threshold = np.mean(passed_absolute) * 10.0 ** (-relative_gate_db / 10.0)
        return passed_absolute[passed_absolute >= relative_threshold]

    def measure_lufs(self, audio: np.ndarray) -> float:
        """Integrated (gated) loudness in LUFS -- real ITU-R BS.1770-4 when
        SciPy + bs1770_loudness are available; otherwise a rough, explicitly
        non-standard RMS-based approximation (see class docstring).

        Returns NaN if the input contains any NaN sample: the gate-and-average
        algorithm would otherwise silently drop whichever 400ms blocks the
        NaN(s) contaminate (a block failing the ">=" absolute-gate comparison
        looks identical to a block that's genuinely too quiet), which can
        produce a plausible-looking but badly wrong LUFS figure from only the
        uncorrupted remainder of the signal, with no other indication
        anything was wrong.
        """
        if audio.ndim == 1:
            audio = audio.reshape(1, -1)

        if np.isnan(audio).any():
            return float('nan')

        if not self._bs1770_ready:
            rms = np.sqrt(np.mean(audio ** 2))
            return 20 * np.log10(rms + 1e-10) + 3.0  # Rough, non-standard approximation

        weighted = self._apply_k_weighting(audio)
        energies = self._block_summed_energies(weighted, block_seconds=0.4, hop_seconds=0.1)
        gated = self._gate_absolute_then_relative(energies, relative_gate_db=10.0)
        if gated.size == 0:
            return -float('inf')
        return -0.691 + 10.0 * np.log10(np.mean(gated))

    def measure_peak(self, audio: np.ndarray) -> float:
        """Return the sample-peak level in dBFS (NOT true peak).

        True-peak measurement requires >=4x oversampling to catch inter-sample
        peaks; this returns the raw sample peak, which can under-read by up to
        ~3 dB on heavily limited material. See measure_true_peak.
        """
        return 20 * np.log10(np.abs(audio).max() + 1e-10)

    def measure_true_peak(self, audio: np.ndarray) -> float:
        """Return the true-peak level in dBTP, following ITU-R BS.1770-4
        Annex 2's oversample-then-peak method: reconstruct the inter-sample
        waveform at 4x the sample rate and take its maximum absolute value.

        Inter-sample peaks (the continuous waveform between samples) can
        exceed the highest actual sample by up to ~3 dB on heavily limited
        material -- so a signal that reads -0.1 dBFS at the sample grid can
        still clip a D/A converter or lossy encoder that reconstructs the
        analog waveform. dBTP is what streaming loudness specs (e.g. -1 dBTP
        ceilings) are actually written against.

        The 4x oversampling uses scipy's polyphase resampler
        (`resample_poly`, a Kaiser-windowed-sinc anti-imaging filter) rather
        than transcribing BS.1770-4 Annex 2's specific *example* FIR
        coefficients; the standard defines the method (>=4x oversample, then
        peak) and treats those coefficients as one example that meets its
        accuracy bound, not as the only conformant filter. This is therefore
        an accurate true-peak *estimate*, not a certified-coefficient
        measurement -- consistent with this module's other honestly-scoped
        meters.

        Returns NaN for NaN input. Falls back to the raw sample peak
        (measure_peak) if SciPy is unavailable, which under-reads
        inter-sample peaks -- documented here rather than silently wrong.
        """
        if audio.ndim == 1:
            audio = audio.reshape(1, -1)
        if np.isnan(audio).any():
            return float('nan')
        if not HAS_SCIPY:
            return self.measure_peak(audio)

        oversampled_peak = 0.0
        for ch in range(audio.shape[0]):
            upsampled = signal.resample_poly(audio[ch], up=4, down=1)
            channel_peak = float(np.abs(upsampled).max())
            if channel_peak > oversampled_peak:
                oversampled_peak = channel_peak
        # Guard against the resampler nudging a genuine full-scale peak a hair
        # below the sample grid: true peak can never be *below* the sample
        # peak, so report the larger of the two.
        sample_peak = float(np.abs(audio).max())
        return 20 * np.log10(max(oversampled_peak, sample_peak) + 1e-10)

    def measure_range(self, audio: np.ndarray) -> float:
        """Loudness range (LRA) in LU, approximating EBU Tech 3342: the
        spread (95th minus 10th percentile) of gated short-term (3s window,
        100ms hop, matching the standard's short-term-loudness update rate)
        loudness values. Real BS.1770 K-weighting when available; 0.0 (no
        principled range estimate) if not -- an earlier version returned the
        integrated LUFS figure here, which is not a range at all and was
        corrected as part of the same accuracy pass that fixed measure_lufs.

        Returns NaN if the input contains any NaN sample (see measure_lufs's
        docstring for why this needs an explicit check rather than trusting
        the gate to surface it).
        """
        if audio.ndim == 1:
            audio = audio.reshape(1, -1)

        if np.isnan(audio).any():
            return float('nan')

        if not self._bs1770_ready:
            return 0.0

        weighted = self._apply_k_weighting(audio)
        energies = self._block_summed_energies(weighted, block_seconds=3.0, hop_seconds=0.1)
        gated = self._gate_absolute_then_relative(energies, relative_gate_db=20.0)
        if gated.size == 0:
            return 0.0

        loudness_values = -0.691 + 10.0 * np.log10(gated)
        p10 = np.percentile(loudness_values, 10)
        p95 = np.percentile(loudness_values, 95)
        return float(p95 - p10)

# --- RBJ biquad designs ------------------------------------------------------
#
# Peaking and shelving EQ coefficients follow the standard "Audio EQ Cookbook"
# (Robert Bristow-Johnson) bilinear-transform designs. They are written out
# here rather than assembled from scipy primitives because scipy's iirpeak is a
# *band-pass* resonator, not a peaking EQ: the earlier code filtered with it and
# then scaled, which replaced the signal with its own narrow band and threw away
# everything outside. Designing the biquad directly is both correct and keeps
# the design step dependency-free (only the filtering needs scipy).
#
# These are verified numerically rather than taken on trust -- see
# tests/test_eq_quality.py, which pins the three properties that define a
# correct peaking EQ: the requested gain lands at the centre frequency, DC and
# Nyquist stay at unity, and a +G boost followed by a -G cut restores the
# original signal.


def design_peaking_eq(frequency: float, sample_rate: int, gain_db: float,
                      q_factor: float = 1.0):
    """RBJ peaking (bell) EQ biquad. Returns (b, a) coefficient lists."""

    amplitude = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * math.pi * frequency / sample_rate
    alpha = math.sin(omega) / (2.0 * max(q_factor, 1e-6))
    cos_omega = math.cos(omega)

    b = [1.0 + alpha * amplitude, -2.0 * cos_omega, 1.0 - alpha * amplitude]
    a = [1.0 + alpha / amplitude, -2.0 * cos_omega, 1.0 - alpha / amplitude]
    return [coefficient / a[0] for coefficient in b], [coefficient / a[0] for coefficient in a]


def design_shelf_eq(frequency: float, sample_rate: int, gain_db: float,
                    high: bool, slope: float = 1.0):
    """RBJ low/high shelving biquad. Returns (b, a) coefficient lists."""

    amplitude = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * math.pi * frequency / sample_rate
    cos_omega = math.cos(omega)
    alpha = (math.sin(omega) / 2.0) * math.sqrt(
        (amplitude + 1.0 / amplitude) * (1.0 / max(slope, 1e-6) - 1.0) + 2.0
    )
    sqrt_gain_alpha = 2.0 * math.sqrt(amplitude) * alpha
    plus, minus = amplitude + 1.0, amplitude - 1.0

    if high:
        b = [
            amplitude * (plus + minus * cos_omega + sqrt_gain_alpha),
            -2.0 * amplitude * (minus + plus * cos_omega),
            amplitude * (plus + minus * cos_omega - sqrt_gain_alpha),
        ]
        a = [
            plus - minus * cos_omega + sqrt_gain_alpha,
            2.0 * (minus - plus * cos_omega),
            plus - minus * cos_omega - sqrt_gain_alpha,
        ]
    else:
        b = [
            amplitude * (plus - minus * cos_omega + sqrt_gain_alpha),
            2.0 * amplitude * (minus - plus * cos_omega),
            amplitude * (plus - minus * cos_omega - sqrt_gain_alpha),
        ]
        a = [
            plus + minus * cos_omega + sqrt_gain_alpha,
            -2.0 * (minus + plus * cos_omega),
            plus + minus * cos_omega - sqrt_gain_alpha,
        ]

    return [coefficient / a[0] for coefficient in b], [coefficient / a[0] for coefficient in a]


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

        # Bell and shelving bands use RBJ biquads, whose coefficients already
        # encode the requested gain -- there is no separate scale factor. The
        # previous design filtered with a band-pass (scipy.iirpeak) and then
        # scaled, which discarded everything outside the band: asking for
        # +6 dB at 1 kHz measured 0.00 dB at 1 kHz and -27 dB at 200 Hz.
        if band.filter_type == "bell":
            if abs(band.gain) > 0.1:  # Only add if significant gain
                b, a = design_peaking_eq(band.frequency, self.sample_rate,
                                         band.gain, band.q_factor)
                self.filters.append((b, a, band.filter_type))

        elif band.filter_type == "highpass":
            b, a = signal.butter(2, freq_norm, 'high')
            self.filters.append((b, a, band.filter_type))

        elif band.filter_type == "lowpass":
            b, a = signal.butter(2, freq_norm, 'low')
            self.filters.append((b, a, band.filter_type))

        elif band.filter_type == "highshelf":
            if abs(band.gain) > 0.1:
                b, a = design_shelf_eq(band.frequency, self.sample_rate,
                                       band.gain, high=True)
                self.filters.append((b, a, band.filter_type))

        elif band.filter_type == "lowshelf":
            if abs(band.gain) > 0.1:
                b, a = design_shelf_eq(band.frequency, self.sample_rate,
                                       band.gain, high=False)
                self.filters.append((b, a, band.filter_type))

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply EQ to audio"""
        if not self.filters or not HAS_SCIPY:
            return audio

        result = audio.copy()

        # RBJ bands are applied with a single forward pass. filtfilt runs the
        # filter twice, which squares the magnitude response and would deliver
        # double the requested dB gain; the high/low-pass bands keep filtfilt
        # because they have unity passband gain, so zero-phase costs nothing.
        for b, a, filter_type in self.filters:
            single_pass = filter_type in ("bell", "highshelf", "lowshelf")
            apply = signal.lfilter if single_pass else signal.filtfilt

            if audio.ndim == 1:
                result = apply(b, a, result)
            else:
                for ch in range(audio.shape[0]):
                    result[ch] = apply(b, a, result[ch])

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

    def _gain_reduction_db(self, envelope: float) -> float:
        """Static soft-knee gain computer: gain reduction (<= 0 dB) for a level.

        This is the standard quadratic soft knee (Giannoulis, Massberg & Reiss,
        "Digital Dynamic Range Compressor Design", JAES 2012), with the knee
        centred on the threshold: compression eases in starting knee/2 below the
        threshold and reaches full ratio knee/2 above it.

        The previous version placed the knee entirely above the threshold but
        kept the above-knee formula for a centred knee, so the two pieces did
        not meet -- the transfer curve jumped downward by (knee/2)(1 - 1/ratio)
        dB at the knee boundary and was non-monotonic there (a 1 dB rise in
        input could drop the output 2 dB). Centring the knee makes the quadratic
        and linear pieces continuous, which is what removes that kink.
        """
        if envelope <= 1e-12:
            return 0.0

        overshoot_db = 20.0 * np.log10(envelope) - self.config.threshold
        slope = (1.0 / self.config.ratio) - 1.0  # <= 0
        knee = self.config.knee

        if knee > 0 and -knee / 2.0 <= overshoot_db <= knee / 2.0:
            return slope * (overshoot_db + knee / 2.0) ** 2 / (2.0 * knee)
        if overshoot_db > knee / 2.0:
            return slope * overshoot_db
        return 0.0

    def _process_mono(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Process mono audio"""
        output = np.zeros_like(audio)
        gain_reduction_curve = np.zeros_like(audio)

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

            # Calculate gain reduction from the static soft-knee curve.
            target_gain_reduction = self._gain_reduction_db(self.envelope)

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

        makeup_gain_linear = 10**(self.config.makeup_gain / 20)

        for i in range(audio.shape[1]):
            # Stereo linking - use maximum level of both channels
            level = max(abs(audio[0, i]), abs(audio[1, i]))

            # Envelope follower
            if level > self.envelope:
                self.envelope += (level - self.envelope) / self.attack_samples
            else:
                self.envelope += (level - self.envelope) / self.release_samples

            # Calculate gain reduction from the static soft-knee curve.
            target_gain_reduction = self._gain_reduction_db(self.envelope)

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

        # Bass mono ("elliptical EQ"): strip the low end out of the side
        # channel so bass plays from the centre. Out-of-phase bass is what
        # cancels on mono playback, so removing it is the point; whatever bass
        # is already centred stays untouched in mid.
        if self.config.bass_mono and HAS_SCIPY:
            side_bass = signal.filtfilt(self.mono_b, self.mono_a, side)
            side = side - side_bass
            # mid needs no work here. The previous version split it into
            # mid_bass + mid_high and added them straight back, which
            # reconstructs mid exactly -- a no-op, and the variable holding
            # the side's low band was misleadingly named `side_high`.

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
        analysis['true_peak_db'] = self.loudness_meter.measure_true_peak(audio)
        analysis['range'] = self.loudness_meter.measure_range(audio)

        # Basic stats
        analysis['rms_db'] = 20 * np.log10(np.sqrt(np.mean(audio**2)) + 1e-10)
        analysis['crest_factor'] = analysis['peak_db'] - analysis['rms_db']

        # 'dynamic_range' previously used a P95/P10-of-|samples| ratio, which
        # reads as ~180dB nonsense whenever the signal has near-silent
        # stretches (P10 -> ~0, blowing up the ratio). crest_factor (peak
        # minus RMS, both already numerically stable dB figures) is a more
        # honest, standard dynamics estimate.
        analysis['dynamic_range'] = analysis['crest_factor']

        return analysis

    def auto_adjust(self, audio: np.ndarray) -> MasteringConfig:
        """Automatically adjust mastering settings based on audio analysis"""
        analysis = self.analyze(audio)
        # Deep copy, not a bare reference: self.config's nested dataclasses
        # (e.g. compressor) would otherwise be mutated in place below,
        # silently accumulating makeup gain across repeated process() calls
        # on the same MasteringChain instance.
        adjusted_config = copy.deepcopy(self.config)

        if self.config.auto_gain:
            # Adjust for target LUFS. current_lufs is -inf whenever the clip
            # is too short/quiet to form a single gated measurement block
            # (e.g. under 400ms) -- target_lufs - (-inf) is +inf, which would
            # otherwise propagate into an infinite makeup_gain and then NaN
            # audio through the compressor/limiter. Skip the adjustment
            # rather than adjust by an undefined amount.
            current_lufs = analysis['lufs']
            if math.isfinite(current_lufs) and adjusted_config.compressor_enabled:
                lufs_difference = self.config.target_lufs - current_lufs
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

        # Calculate processing metrics. lufs_change is NaN (not a bug -- the
        # mathematically honest result) whenever either side is -inf, i.e.
        # either the input or output audio was too short/quiet to form a
        # single gated 400ms loudness block; -inf - -inf is undefined.
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
        """Apply dithering for bit depth reduction.

        dither_type accepts "tpdf" or "rpdf". "shaped" (noise-shaped dither)
        is documented on MasteringConfig.dither_type but not implemented; an
        earlier version of this method silently applied no dither at all for
        "shaped" or any other unrecognized value, which is a worse-than-tpdf
        outcome (undithered truncation) delivered without any indication.
        Any unrecognized value now falls back to tpdf with a logged warning
        instead of silently skipping dither.
        """
        if dither_type not in ("tpdf", "rpdf"):
            self.logger.warning(
                f"Unknown or unimplemented dither_type {dither_type!r} "
                f"(supported: 'tpdf', 'rpdf'); falling back to 'tpdf' rather "
                f"than silently applying no dither."
            )
            dither_type = "tpdf"

        if dither_type == "tpdf":
            # Triangular PDF dither
            dither = np.random.uniform(-1, 1, audio.shape) + np.random.uniform(-1, 1, audio.shape)
            dither = dither / 65536  # For 16-bit
        else:
            # Rectangular PDF dither
            dither = np.random.uniform(-1, 1, audio.shape) / 65536

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