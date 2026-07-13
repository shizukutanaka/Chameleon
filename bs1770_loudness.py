"""Chameleon BS.1770 loudness meter.

A pure standard-library implementation of the ITU-R BS.1770-4/5 K-weighting
filter and gated integrated-loudness algorithm ("Algorithms to measure audio
programme loudness and true-peak audio level", most recently revised
2023-11). No third-party dependencies: deterministic and auditable, which is
this project's differentiator (see CHARTER.md §1).

Scope, stated honestly (this is not a certified loudness meter):
- Mono signals only. The standard's multi-channel weighting (e.g. a +1.5 dB
  boost for surround channels) is not implemented; a stereo/mono-downmixed
  signal is treated as a single equally-weighted channel. Note this is
  stricter than "just no surround weighting": BS.1770 sums each channel's
  post-filter mean-square energy, while averaging samples to mono *before*
  filtering (as main.py's caller does) under-reads a real stereo signal by
  roughly 3 LU (identical L/R) up to 6 LU (uncorrelated, equal-power L/R),
  and can read far too quiet for anti-phase content. Per-channel measurement
  is a tracked follow-up (see CHARTER.md §9).
- No true-peak oversampling. This module reports integrated (gated) loudness
  only; sample-peak reporting is left to existing callers.
- Callers are responsible for bounding how many samples are passed in, for
  predictable memory/time regardless of file length (see main.py's
  `analyze --loudness`, which analyzes a bounded prefix of the file).
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


def measure_integrated_loudness(samples: Sequence[float], sample_rate: int) -> float:
    """Gated integrated loudness (LUFS) per ITU-R BS.1770-4, mono only.

    Returns float('-inf') if the signal is silent, all-gated, or too short
    to form a single 400ms measurement block.
    """

    if not samples:
        return float('-inf')

    weighted = apply_k_weighting(samples, sample_rate)
    blocks = _block_mean_squares(weighted, sample_rate)
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


__all__ = [
    "BiquadCoefficients",
    "apply_k_weighting",
    "measure_integrated_loudness",
]
