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

# The pure-Python DFT is O(n^2): analysis runs in 4096-sample windows,
# tiled across the buffer and capped so a huge input stays bounded.
_DFT_BLOCK = 4096
_DFT_MAX_WINDOWS = 16


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
    # Samples that actually fed the transform. The pure-Python DFT path is
    # bounded (see _DFT_MAX_WINDOWS), so this can be lower than the input
    # length -- a report that hides partial coverage reads as whole-signal
    # when it is not.
    analyzed_samples: int


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
    # An even-length source ends on the real Nyquist bin, which has no
    # conjugate twin; an odd-length source has no Nyquist bin at all, so
    # every bin past DC needs its mirror. Dropping the last bin either way
    # loses the top of the spectrum and mis-normalises by the wrong N.
    inner = spectrum[1:-1] if len(spectrum) % 2 == 1 else spectrum[1:]
    for value in reversed(inner):
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


def _compute_bandwidth(magnitudes: Sequence[float], sample_rate: int, transform_length: int) -> Tuple[float, float]:
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

    # Bin k of a real transform of length N sits at k * sr / N for both
    # parities; deriving N as 2*(bins-1) is exact only for even N and
    # stretches every label ~1/(N-1) on odd input.
    bin_width = sample_rate / max(transform_length, 1)
    return lower_index * bin_width, upper_index * bin_width


def _hann_window(length: int) -> List[float]:
    """Return a Hann window of the requested length.

    A rectangular (no) window leaks energy from a tone across many bins;
    the Hann window is the de-facto default for general spectral analysis
    because it trades a little main-lobe width for far lower side-lobes.
    """

    if length <= 1:
        return [1.0] * max(length, 0)
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * n / (length - 1)) for n in range(length)]


def _detect_peaks(magnitudes: Sequence[float], sample_rate: int, max_peaks: int, transform_length: int) -> List[SpectrumPeak]:
    """Select dominant peaks by neighbourhood comparison with sub-bin refinement.

    Each local maximum is refined with parabolic (quadratic) interpolation over
    the three points around the peak, which recovers the true frequency to a
    fraction of a bin instead of snapping it to the nearest bin centre.
    """

    peaks: List[SpectrumPeak] = []
    bin_width = sample_rate / max(transform_length, 1)

    for index in range(1, len(magnitudes) - 1):
        left = magnitudes[index - 1]
        centre = magnitudes[index]
        right = magnitudes[index + 1]

        if centre >= left and centre >= right and centre > 0:
            # Parabolic interpolation: delta in (-0.5, 0.5) bins.
            denominator = left - 2.0 * centre + right
            if denominator != 0:
                delta = 0.5 * (left - right) / denominator
            else:
                delta = 0.0
            # Guard against numerical excursions from near-flat peaks.
            if delta < -0.5 or delta > 0.5:
                delta = 0.0
            frequency = (index + delta) * bin_width
            peaks.append(SpectrumPeak(frequency_hz=frequency, magnitude=centre))

    peaks.sort(key=lambda peak: peak.magnitude, reverse=True)
    return peaks[:max_peaks]


def _dft_window_starts(n: int) -> List[int]:
    """Start offsets of 4096-sample analysis windows covering ``[0, n)``.

    Contiguous tiling; a partial tail is covered by anchoring the final
    window at ``n - 4096`` (overlap is fine -- it keeps the bin grid uniform
    and the tail samples in scope). Coverage is capped at
    ``_DFT_MAX_WINDOWS`` to bound the O(n^2) fallback; whatever the cap
    leaves uncovered is disclosed via ``SpectrumReport.analyzed_samples``.
    """
    if n <= _DFT_BLOCK:
        return [0]
    starts = list(range(0, n - _DFT_BLOCK + 1, _DFT_BLOCK))[:_DFT_MAX_WINDOWS]
    tail = n - _DFT_BLOCK
    if len(starts) < _DFT_MAX_WINDOWS and starts[-1] != tail:
        starts.append(tail)
    return starts


def analyze_spectrum(
    samples: Sequence[float],
    sample_rate: int,
    *,
    max_peaks: int = 5,
) -> SpectrumReport:
    """Compute spectral statistics for a mono signal.

    Without NumPy the transform is the O(n^2) pure-Python DFT, so the
    spectrum is built from up to ``_DFT_MAX_WINDOWS`` 4096-sample windows
    (contiguous, tail-anchored) whose magnitudes are averaged -- every
    sample feeds the report whenever the input fits the bound rather than
    only the first 4096. ``analyzed_samples`` in the report says how many
    samples were actually transformed.
    """

    if sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")

    buffer = _to_float_sequence(samples)
    if not buffer:
        raise ValueError("samples cannot be empty")

    # Window before the transform to suppress spectral leakage. RMS and DC
    # are measured on the raw (unwindowed) buffer so those time-domain
    # statistics are unaffected by the window taper.
    if HAS_NUMPY:
        window = _hann_window(len(buffer))
        spectrum = _discrete_fourier_transform(
            [sample * weight for sample, weight in zip(buffer, window)])
        magnitudes = [abs(value) for value in spectrum]
        transform_length = len(buffer)
        analyzed_samples = len(buffer)
    else:
        starts = _dft_window_starts(len(buffer))
        magnitudes: List[float] = []
        transform_length = min(len(buffer), _DFT_BLOCK)
        for start in starts:
            block = buffer[start:start + transform_length]
            window = _hann_window(len(block))
            spectrum = _discrete_fourier_transform(
                [sample * weight for sample, weight in zip(block, window)])
            if not magnitudes:
                magnitudes = [abs(value) for value in spectrum]
            else:
                for index, value in enumerate(spectrum):
                    magnitudes[index] += abs(value)
        magnitudes = [value / len(starts) for value in magnitudes]
        analyzed_samples = starts[-1] + transform_length

    rms = math.sqrt(sum(sample ** 2 for sample in buffer) / len(buffer))
    dc_offset = statistics.mean(buffer)
    bandwidth = _compute_bandwidth(magnitudes, sample_rate, transform_length)
    peaks = _detect_peaks(magnitudes, sample_rate, max_peaks, transform_length)

    return SpectrumReport(
        sample_rate=sample_rate,
        rms_level=rms,
        bandwidth=bandwidth,
        dominant_peaks=peaks,
        dc_offset=dc_offset,
        analyzed_samples=analyzed_samples,
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
    """Resample using linear interpolation.

    Note: this applies no anti-aliasing filter. When downsampling
    (target_rate < source_rate), content above the new Nyquist frequency is
    not removed first and will alias back into the audible band. It is
    intended for light rate changes / previews, not high-fidelity conversion;
    use scipy/librosa (the ``[audio]`` extra) for band-limited resampling.
    """

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


def _apply_band_gains(
    spectrum: Sequence[complex],
    sample_rate: int,
    low_gain: float,
    mid_gain: float,
    high_gain: float,
    transform_length: int,
) -> List[complex]:
    # k * sr / N, as in the meter helpers -- the 2*(bins-1) shortcut only
    # holds for even-length transforms.
    bin_width = sample_rate / max(transform_length, 1)
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
    return adjusted


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

    # The pure-Python DFT only transforms 4096 samples per call; without
    # NumPy, process in blocks so input past that point is not dropped.
    step = len(buffer) if HAS_NUMPY else 4096
    processed: List[float] = []
    for start in range(0, len(buffer), step):
        block = buffer[start:start + step]
        spectrum = _discrete_fourier_transform(block)
        adjusted = _apply_band_gains(
            spectrum, sample_rate, low_gain, mid_gain, high_gain, len(block))
        processed.extend(_inverse_real_transform(adjusted, len(block)))
    return processed


def sliding_window_rms(samples: Sequence[float], window_size: int) -> List[float]:
    """Compute RMS levels over a sliding window."""

    if window_size <= 0:
        raise ValueError("window_size must be positive")

    buffer = _to_float_sequence(samples)
    if not buffer:
        return []
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
