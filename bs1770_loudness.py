"""Chameleon BS.1770 loudness meter.

A pure standard-library implementation of the ITU-R BS.1770-4/5 K-weighting
filter and gated integrated-loudness algorithm ("Algorithms to measure audio
programme loudness and true-peak audio level", most recently revised
2023-11). No third-party dependencies: deterministic and auditable, which is
this project's differentiator (see CHARTER.md §1).

Scope, stated honestly (this is not a certified loudness meter):
- `measure_integrated_loudness` is mono-only; `measure_integrated_loudness_multichannel`
  sums per-channel energy (correct for mono/stereo). Neither implements the
  standard's surround-channel weighting (e.g. a +1.5 dB boost for Ls/Rs) --
  every channel is weighted equally. A caller that averages samples to mono
  *before* filtering (rather than using the multichannel entry point)
  under-reads a real stereo signal by roughly 3 LU (identical L/R) up to
  6 LU (uncorrelated, equal-power L/R), and can read far too quiet for
  anti-phase content -- see each function's docstring.
- True-peak (dBTP) is available via `measure_true_peak` /
  `measure_true_peak_multichannel` (BS.1770-4 Annex 2 oversample-then-peak,
  4x windowed-sinc polyphase interpolation, pure stdlib). It is scoped as an
  accurate *estimate* -- it generates its own interpolation filter rather
  than transcribing the standard's example FIR table (see the comment above
  those functions).
- Callers are responsible for bounding how many samples are passed in, for
  predictable memory/time regardless of file length (see main.py's
  `analyze --loudness`, which analyzes a bounded prefix of the file). The
  true-peak path costs ~0.4s per 65k samples in pure Python, so the same
  bound applies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence

# Absolute gate per BS.1770-4: blocks quieter than -70 LUFS are discarded
# outright before the relative gate is computed.
_ABSOLUTE_GATE_LUFS = -70.0
# Relative gate: blocks more than 10 dB below the (absolute-gated) mean are
# discarded.
_RELATIVE_GATE_OFFSET_DB = 10.0
# 400 ms blocks with 75% overlap (100 ms hop), per BS.1770-4.
_BLOCK_SECONDS = 0.4
_HOP_SECONDS = 0.1
_LUFS_CALIBRATION_OFFSET = -0.691


@dataclass(frozen=True)
class BiquadCoefficients:
    """Direct-form-1 biquad coefficients, with a0 already normalized to 1."""

    b0: float
    b1: float
    b2: float
    a1: float
    a2: float


def _stage1_head_effects(sample_rate: int) -> BiquadCoefficients:
    """High-frequency shelving stage of K-weighting (BS.1770-4 Annex 1)."""

    f0 = 1681.9744509555319
    gain_db = 3.99984385397
    q = 0.7071752369554193

    k = math.tan(math.pi * f0 / sample_rate)
    vh = 10.0 ** (gain_db / 20.0)
    vb = vh ** 0.4996667741545416

    a0 = 1.0 + k / q + k * k
    b0 = (vh + vb * k / q + k * k) / a0
    b1 = 2.0 * (k * k - vh) / a0
    b2 = (vh - vb * k / q + k * k) / a0
    a1 = 2.0 * (k * k - 1.0) / a0
    a2 = (1.0 - k / q + k * k) / a0
    return BiquadCoefficients(b0, b1, b2, a1, a2)


def _stage2_high_pass(sample_rate: int) -> BiquadCoefficients:
    """RLB-weighting high-pass stage of K-weighting (BS.1770-4 Annex 1).

    Matches the reference table (and the widely-used libebur128
    implementation) exactly: only the denominator (a1, a2) is normalized by
    a0; the numerator is left as the raw [1.0, -2.0, 1.0] from the
    bilinear-transform algebra. Dividing the numerator by a0 as well (as an
    earlier version of this module did) is mathematically a valid alternate
    normalization but does not reproduce the standard's published
    coefficients, so it was reverted to preserve BS.1770 conformance.
    """

    f0 = 38.13547087602
    q = 0.5003270373238

    k = math.tan(math.pi * f0 / sample_rate)
    a0 = 1.0 + k / q + k * k
    b0 = 1.0
    b1 = -2.0
    b2 = 1.0
    a1 = 2.0 * (k * k - 1.0) / a0
    a2 = (1.0 - k / q + k * k) / a0
    return BiquadCoefficients(b0, b1, b2, a1, a2)


def _apply_biquad(samples: Sequence[float], coeffs: BiquadCoefficients) -> List[float]:
    """Direct-form-1 IIR filtering, sample by sample (pure Python, no NumPy)."""

    b0, b1, b2, a1, a2 = coeffs.b0, coeffs.b1, coeffs.b2, coeffs.a1, coeffs.a2
    x1 = x2 = y1 = y2 = 0.0
    output: List[float] = [0.0] * len(samples)
    for i, x0 in enumerate(samples):
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        output[i] = y0
        x2, x1 = x1, x0
        y2, y1 = y1, y0
    return output


# Below this rate, the stage-1 shelving filter's pole (derived from a fixed
# 1681.97 Hz analog corner via the bilinear transform) leaves the unit
# circle and the filter becomes unstable, so measurements would be garbage
# rather than merely inaccurate. 8 kHz keeps a wide safety margin above the
# ~3.36 kHz instability point while covering realistic audio sample rates.
_MIN_SAMPLE_RATE_HZ = 8000


def apply_k_weighting(samples: Sequence[float], sample_rate: int) -> List[float]:
    """Apply the two-stage ITU-R BS.1770 K-weighting filter to a mono signal.

    Raises ValueError below `_MIN_SAMPLE_RATE_HZ`, where the shelving stage
    becomes numerically unstable rather than just inaccurate.
    """

    if sample_rate < _MIN_SAMPLE_RATE_HZ:
        raise ValueError(
            f"sample_rate must be >= {_MIN_SAMPLE_RATE_HZ} Hz for stable "
            f"K-weighting (got {sample_rate})"
        )
    stage1 = _apply_biquad(samples, _stage1_head_effects(sample_rate))
    stage2 = _apply_biquad(stage1, _stage2_high_pass(sample_rate))
    return stage2


def _block_mean_squares(weighted: Sequence[float], sample_rate: int) -> List[float]:
    """Mean-square energy per overlapping 400ms block (100ms hop)."""

    block_size = max(1, int(round(_BLOCK_SECONDS * sample_rate)))
    hop = max(1, int(round(_HOP_SECONDS * sample_rate)))
    if len(weighted) < block_size:
        return []

    blocks: List[float] = []
    for start in range(0, len(weighted) - block_size + 1, hop):
        block = weighted[start:start + block_size]
        blocks.append(sum(s * s for s in block) / block_size)
    return blocks


def _block_summed_mean_squares(weighted_channels: Sequence[Sequence[float]], sample_rate: int) -> List[float]:
    """Per-block energy summed across channels (equal weight 1.0 each).

    This is what BS.1770 actually requires for multi-channel content: sum
    each channel's mean-square energy per block, not average the channels'
    *samples* together before filtering (which is what a mono downmix does,
    and which under-reads real stereo content -- see module docstring).
    """

    if not weighted_channels:
        return []

    block_size = max(1, int(round(_BLOCK_SECONDS * sample_rate)))
    hop = max(1, int(round(_HOP_SECONDS * sample_rate)))
    length = min(len(channel) for channel in weighted_channels)
    if length < block_size:
        return []

    blocks: List[float] = []
    for start in range(0, length - block_size + 1, hop):
        total = 0.0
        for channel in weighted_channels:
            block = channel[start:start + block_size]
            total += sum(s * s for s in block) / block_size
        blocks.append(total)
    return blocks


def _gate_and_convert_to_lufs(blocks: Sequence[float]) -> float:
    """Apply BS.1770's two-stage gating to per-block energies and convert to LUFS."""

    if not blocks:
        return float('-inf')

    absolute_threshold = 10.0 ** ((_ABSOLUTE_GATE_LUFS - _LUFS_CALIBRATION_OFFSET) / 10.0)
    passed_absolute = [z for z in blocks if z >= absolute_threshold]
    if not passed_absolute:
        return float('-inf')

    ungated_mean = sum(passed_absolute) / len(passed_absolute)
    relative_threshold = ungated_mean * 10.0 ** (-_RELATIVE_GATE_OFFSET_DB / 10.0)

    gated = [z for z in passed_absolute if z >= relative_threshold]
    if not gated:
        return float('-inf')

    final_mean = sum(gated) / len(gated)
    if final_mean <= 0:
        return float('-inf')
    return _LUFS_CALIBRATION_OFFSET + 10.0 * math.log10(final_mean)


def measure_integrated_loudness(samples: Sequence[float], sample_rate: int) -> float:
    """Gated integrated loudness (LUFS) per ITU-R BS.1770-4, mono only.

    Returns float('-inf') if the signal is silent, all-gated, or too short
    to form a single 400ms measurement block.
    """

    if not samples:
        return float('-inf')

    weighted = apply_k_weighting(samples, sample_rate)
    blocks = _block_mean_squares(weighted, sample_rate)
    return _gate_and_convert_to_lufs(blocks)


def measure_integrated_loudness_multichannel(channels: Sequence[Sequence[float]], sample_rate: int) -> float:
    """Gated integrated loudness (LUFS) per ITU-R BS.1770-4, summing energy
    across channels with equal weight 1.0 each -- correct for mono/stereo.

    Unlike `measure_integrated_loudness` fed a mono downmix, this does not
    under-read stereo content (see the module docstring for the magnitude of
    that error). Standard multi-channel weighting for layouts beyond L/R
    (e.g. a +1.5 dB boost for surround channels) is not implemented; every
    channel here is weighted equally.

    Returns float('-inf') if there are no channels, the signal is silent,
    all-gated, or too short to form a single 400ms measurement block.
    """

    if not channels:
        return float('-inf')

    weighted_channels = [apply_k_weighting(channel, sample_rate) for channel in channels]
    blocks = _block_summed_mean_squares(weighted_channels, sample_rate)
    return _gate_and_convert_to_lufs(blocks)


# --- True-peak (dBTP), BS.1770-4 Annex 2 oversample-then-peak method --------
#
# Annex 2 measures the true (inter-sample) peak by reconstructing the signal
# at >=4x the sample rate and taking the maximum absolute value -- catching
# peaks in the continuous waveform *between* samples that the raw sample peak
# misses (up to ~3 dB on limited material). The standard gives one example
# FIR; it explicitly treats that table as an example meeting its accuracy
# bound, not the only conformant filter. This module generates its own
# windowed-sinc polyphase interpolation from first principles (below) rather
# than transcribing that table -- an honest, verifiable true-peak *estimate*
# (validated to agree with scipy's polyphase resampler to <0.05 dB), not a
# certified-coefficient measurement.

_TRUE_PEAK_OVERSAMPLE = 4
# Taps per side per phase. 12 -> a 24-tap subfilter; matches the standard's
# 48-tap / 4-phase example length and keeps the pure-Python cost modest
# (~0.4s for a 65536-sample bounded analysis prefix).
_TRUE_PEAK_HALF_TAPS = 12


def _build_polyphase_sinc(oversample: int, half_taps: int):
    """Windowed-sinc polyphase interpolation taps, generated from first
    principles (not transcribed from any published coefficient table).

    Returns a list of `oversample` phases; each phase is a list of
    (input_offset, coefficient) pairs. Phase 0 is the identity (so the
    original samples pass through unchanged and true peak can never read
    below sample peak). Each phase is normalized to unit DC gain, so a
    constant signal reconstructs exactly.
    """

    phases = []
    offsets = list(range(-half_taps + 1, half_taps + 1))
    for p in range(oversample):
        frac = p / oversample
        taps = []
        for k in offsets:
            t = k - frac
            if abs(t) < 1e-9:
                sinc = 1.0
            else:
                sinc = math.sin(math.pi * t) / (math.pi * t)
            # Blackman window across the [-half_taps, half_taps] support.
            x = min(1.0, max(0.0, (t + half_taps) / (2 * half_taps)))
            window = 0.42 - 0.5 * math.cos(2 * math.pi * x) + 0.08 * math.cos(4 * math.pi * x)
            taps.append(sinc * window)
        total = sum(taps)
        if total:
            taps = [c / total for c in taps]
        phases.append(list(zip(offsets, taps)))
    return phases


_TRUE_PEAK_PHASES = _build_polyphase_sinc(_TRUE_PEAK_OVERSAMPLE, _TRUE_PEAK_HALF_TAPS)


def _oversampled_abs_peak(samples: Sequence[float]) -> float:
    """Maximum absolute value of the 4x-oversampled reconstruction (linear)."""

    n = len(samples)
    if n == 0:
        return 0.0
    peak = 0.0
    for i in range(n):
        for phase in _TRUE_PEAK_PHASES:
            acc = 0.0
            for k, c in phase:
                j = i + k
                if 0 <= j < n:
                    acc += samples[j] * c
            a = acc if acc >= 0 else -acc
            if a > peak:
                peak = a
    return peak


def measure_true_peak(samples: Sequence[float]) -> float:
    """True-peak level in dBTP via the BS.1770-4 Annex 2 oversample-then-peak
    method (4x windowed-sinc polyphase interpolation, pure standard library).

    Returns float('-inf') for empty/silent input and float('nan') if any
    sample is NaN. See the module comment above for how this is scoped
    (accurate estimate, not certified coefficients).
    """

    if not samples:
        return float('-inf')
    if any(s != s for s in samples):  # NaN != NaN
        return float('nan')
    peak = _oversampled_abs_peak(samples)
    if peak <= 0.0:
        return float('-inf')
    return 20.0 * math.log10(peak)


def measure_true_peak_multichannel(channels: Sequence[Sequence[float]]) -> float:
    """True-peak (dBTP) across channels: the loudest single-channel true peak
    (true peak is a per-channel maximum, not summed like loudness energy).

    Returns float('-inf') if there are no channels or all are empty/silent,
    and float('nan') if any channel contains a NaN sample.
    """

    if not channels:
        return float('-inf')
    peak = 0.0
    for channel in channels:
        if not channel:
            continue
        if any(s != s for s in channel):
            return float('nan')
        channel_peak = _oversampled_abs_peak(channel)
        if channel_peak > peak:
            peak = channel_peak
    if peak <= 0.0:
        return float('-inf')
    return 20.0 * math.log10(peak)


__all__ = [
    "BiquadCoefficients",
    "apply_k_weighting",
    "measure_integrated_loudness",
    "measure_integrated_loudness_multichannel",
    "measure_true_peak",
    "measure_true_peak_multichannel",
]
