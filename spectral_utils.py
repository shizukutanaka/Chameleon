"""
Chameleon Spectral Utilities.

Deterministic spectral analysis helpers that avoid speculative quantum
implementations. NumPy is used when available, while portable Python
fallbacks ensure the toolkit remains lightweight.
"""

from __future__ import annotations

import cmath
import logging
import math
import statistics
from dataclasses import dataclass
from typing import List, Sequence, Tuple

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:  # pragma: no cover - minimal deployments
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpectrumPeak:
    """Dominant frequency component detected in a signal."""

    frequency_hz: float
    magnitude: float


@dataclass(frozen=True)
class SpectrumReport:
    """Summarised view of the analysed spectrum."""

    sample_rate: int
    rms_level: float
    bandwidth: Tuple[float, float]
    dominant_peaks: List[SpectrumPeak]
    dc_offset: float


def _to_float_sequence(samples: Sequence[float]) -> List[float]:
    """Convert a numeric sequence to floats."""

    if not isinstance(samples, Sequence):
        raise TypeError("samples must be a sequence type")

    converted: List[float] = []
    for value in samples:
        try:
            converted.append(float(value))
        except (TypeError, ValueError) as exc:
            raise TypeError("samples must contain numeric values") from exc
    return converted


def _discrete_fourier_transform(values: Sequence[float]) -> List[complex]:
    """Compute a real FFT using NumPy when available."""

    if HAS_NUMPY:
        spectrum = np.fft.rfft(np.asarray(values, dtype=float))
        return spectrum.tolist()

    trimmed = values[:4096] if len(values) > 4096 else values
    length = len(trimmed)
    spectrum: List[complex] = []

    for bin_index in range(length // 2 + 1):
        coefficient = 0j
        angle = -2j * math.pi * bin_index / length
        phase_step = cmath.exp(angle)
        phase = 1 + 0j
        for sample in trimmed:
            coefficient += sample * phase
            phase *= phase_step
        spectrum.append(coefficient)
    return spectrum


def _inverse_real_transform(spectrum: Sequence[complex], length: int) -> List[float]:
    """Recover the time-domain signal from spectral data."""

    if HAS_NUMPY:
        restored = np.fft.irfft(np.asarray(spectrum, dtype=complex), n=length)
        return restored.astype(float).tolist()

    mirrored: List[complex] = list(spectrum)
    for value in reversed(spectrum[1:-1]):
        mirrored.append(value.conjugate())

    size = len(mirrored)
    phase_steps = [cmath.exp(2j * math.pi * index / size) for index in range(size)]
    phases = [1 + 0j] * size

    output: List[float] = []
    for _ in range(length):
        total = 0j
        for coefficient, phase in zip(mirrored, phases):
            total += coefficient * phase
        output.append((total / size).real)
        phases = [phase * step for phase, step in zip(phases, phase_steps)]
    return output


def _compute_bandwidth(magnitudes: Sequence[float], sample_rate: int) -> Tuple[float, float]:
    """Estimate effective bandwidth using cumulative energy thresholds."""

    total_energy = sum(value ** 2 for value in magnitudes)
    if total_energy <= 0:
        return 0.0, 0.0

    cumulative = 0.0
    lower_index = 0
    upper_index = len(magnitudes) - 1
    low_threshold = 0.05 * total_energy
    high_threshold = 0.95 * total_energy

    for index, magnitude in enumerate(magnitudes):
        energy = magnitude ** 2
        cumulative += energy
        if cumulative <= low_threshold:
            lower_index = index
        if cumulative >= high_threshold:
            upper_index = index
            break

    bin_width = sample_rate / (2 * max(len(magnitudes) - 1, 1))
    return lower_index * bin_width, upper_index * bin_width


def _detect_peaks(magnitudes: Sequence[float], sample_rate: int, max_peaks: int) -> List[SpectrumPeak]:
    """Select dominant peaks by simple neighbourhood comparison."""

    peaks: List[SpectrumPeak] = []
    bin_width = sample_rate / (2 * max(len(magnitudes) - 1, 1))

    for index in range(1, len(magnitudes) - 1):
        left = magnitudes[index - 1]
        centre = magnitudes[index]
        right = magnitudes[index + 1]

        if centre >= left and centre >= right and centre > 0:
            peaks.append(SpectrumPeak(frequency_hz=index * bin_width, magnitude=centre))

    peaks.sort(key=lambda peak: peak.magnitude, reverse=True)
    return peaks[:max_peaks]


def analyze_spectrum(
    samples: Sequence[float],
    sample_rate: int,
    *,
    max_peaks: int = 5,
) -> SpectrumReport:
    """Compute spectral statistics for a mono signal."""

    if sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")

    buffer = _to_float_sequence(samples)
    if not buffer:
        raise ValueError("samples cannot be empty")

    spectrum = _discrete_fourier_transform(buffer)
    magnitudes = [abs(value) for value in spectrum]

    rms = math.sqrt(sum(sample ** 2 for sample in buffer) / len(buffer))
    dc_offset = statistics.mean(buffer)
    bandwidth = _compute_bandwidth(magnitudes, sample_rate)
    peaks = _detect_peaks(magnitudes, sample_rate, max_peaks)

    return SpectrumReport(
        sample_rate=sample_rate,
        rms_level=rms,
        bandwidth=bandwidth,
        dominant_peaks=peaks,
        dc_offset=dc_offset,
    )


def normalize_peak(samples: Sequence[float], target_peak: float = 0.95) -> List[float]:
    """Scale a signal to the requested peak value."""

    if target_peak <= 0:
        raise ValueError("target_peak must be positive")

    buffer = _to_float_sequence(samples)
    if not buffer:
        return []

    current_peak = max(abs(sample) for sample in buffer)
    if current_peak == 0:
        return buffer

    scale = target_peak / current_peak
    return [sample * scale for sample in buffer]


def linear_resample(samples: Sequence[float], source_rate: int, target_rate: int) -> List[float]:
    """Resample using linear interpolation."""

    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("sample rates must be positive integers")

    buffer = _to_float_sequence(samples)
    if not buffer or source_rate == target_rate:
        return list(buffer)

    duration = len(buffer) / source_rate
    target_length = max(int(round(duration * target_rate)), 1)
    ratio = (len(buffer) - 1) / max(target_length - 1, 1)

    resampled: List[float] = []
    for index in range(target_length):
        position = index * ratio
        left = int(math.floor(position))
        right = min(left + 1, len(buffer) - 1)
        weight = position - left
        resampled.append((1 - weight) * buffer[left] + weight * buffer[right])

    return resampled


def apply_spectral_mask(
    samples: Sequence[float],
    sample_rate: int,
    *,
    low_gain: float = 1.0,
    mid_gain: float = 1.0,
    high_gain: float = 1.0,
) -> List[float]:
    """Apply a lightweight three-band equaliser."""

    if any(gain < 0 for gain in (low_gain, mid_gain, high_gain)):
        raise ValueError("gain factors must be non-negative")

    buffer = _to_float_sequence(samples)
    if not buffer:
        return []

    spectrum = _discrete_fourier_transform(buffer)
    bin_width = sample_rate / (2 * max(len(spectrum) - 1, 1))

    adjusted: List[complex] = []
    for index, value in enumerate(spectrum):
        frequency = index * bin_width
        if frequency < 200.0:
            gain = low_gain
        elif frequency < 2000.0:
            gain = mid_gain
        else:
            gain = high_gain
        adjusted.append(value * gain)

    processed = _inverse_real_transform(adjusted, len(buffer))
    peak = max(abs(sample) for sample in processed) or 1.0
    return [sample / peak for sample in processed]


def sliding_window_rms(samples: Sequence[float], window_size: int) -> List[float]:
    """Compute RMS levels over a sliding window."""

    if window_size <= 0:
        raise ValueError("window_size must be positive")

    buffer = _to_float_sequence(samples)
    if window_size > len(buffer):
        window_size = len(buffer)

    squared_prefix: List[float] = [0.0]
    for value in buffer:
        squared_prefix.append(squared_prefix[-1] + value * value)

    energies: List[float] = []
    for start in range(0, len(buffer) - window_size + 1):
        end = start + window_size
        squared_sum = squared_prefix[end] - squared_prefix[start]
        energies.append(math.sqrt(squared_sum / window_size))
    return energies


__all__ = [
    "SpectrumPeak",
    "SpectrumReport",
    "analyze_spectrum",
    "apply_spectral_mask",
    "linear_resample",
    "normalize_peak",
    "sliding_window_rms",
]
