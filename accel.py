"""Optional Rust acceleration for the BS.1770 compute kernels.

Chameleon's contract is a zero-third-party-dependency core (CHARTER.md
§1/§3): the default install is pure standard library and stays that way.
The Rust kernels (rust/chameleon-accel/, built into the optional
`_chameleon_accel` extension module) are an accelerator only, in the same
sense as the `[audio]` extra -- layered on top, never required:

* importable + `CHAMELEON_ACCEL` on (the default) -> the functions below
  route to Rust;
* module missing (a normal install -- the .so is a local build artifact,
  never shipped), `CHAMELEON_ACCEL=0`, or *any* failure inside a native
  call -> every function here returns None and the caller runs the
  original pure-Python implementation instead.

The native kernels re-implement the Python primitives
operation-for-operation (bit-identical results -- see
rust/chameleon-accel/README.md), so which path ran is invisible in the
numbers, only in the timing. Nothing here raises: the fallback decision
is made by the callers on the None return.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Sequence, Tuple, TypeVar

try:
    import _chameleon_accel
except ImportError:
    _chameleon_accel = None  # type: ignore[assignment]

# Evaluated once at import: the switch is a startup-time setting like
# every other CHAMELEON_* variable, and the kernels sit in per-sample hot
# loops, so it must not be re-read per call.
_DISABLED = os.environ.get("CHAMELEON_ACCEL", "").strip().lower() in (
    "0",
    "false",
    "no",
    "off",
)
_ENABLED: bool = _chameleon_accel is not None and not _DISABLED

_R = TypeVar("_R")

# (b0, b1, b2, a1, a2) -- the shape of bs1770_loudness.BiquadCoefficients.
Coeffs = Tuple[float, float, float, float, float]


def _call(func: Callable[..., _R], *args: object) -> Optional[_R]:
    """One guarded native call: any failure degrades to the fallback.

    The broad catch is the contract, not sloppiness -- a native bug must
    never take down a measurement that pure Python can serve.
    """
    try:
        return func(*args)
    except Exception:
        return None


def available() -> bool:
    """True when the native kernels are present and enabled."""
    return _ENABLED


def k_weight(
    samples: Sequence[float], stage1: Coeffs, stage2: Coeffs
) -> Optional[List[float]]:
    """Two-stage K-weighting via Rust, or None to use the Python biquads."""
    native = _chameleon_accel
    if native is None or not _ENABLED:
        return None
    return _call(native.k_weight, list(samples), stage1, stage2)


def block_mean_squares(
    weighted: Sequence[float], block_size: int, hop: int
) -> Optional[List[float]]:
    """Per-block mean squares via Rust, or None to use the Python loop."""
    native = _chameleon_accel
    if native is None or not _ENABLED:
        return None
    return _call(native.block_mean_squares, list(weighted), block_size, hop)


def block_summed_mean_squares(
    channels: Sequence[Sequence[float]],
    weights: Sequence[float],
    block_size: int,
    hop: int,
) -> Optional[List[float]]:
    """Per-block cross-channel energy sums via Rust, or None for Python."""
    native = _chameleon_accel
    if native is None or not _ENABLED:
        return None
    return _call(
        native.block_summed_mean_squares,
        [list(channel) for channel in channels],
        list(weights),
        block_size,
        hop,
    )


def oversampled_abs_peak(
    samples: Sequence[float], phases: Sequence[Sequence[Tuple[int, float]]]
) -> Optional[float]:
    """Oversampled absolute peak via Rust, or None to use the Python loop."""
    native = _chameleon_accel
    if native is None or not _ENABLED:
        return None
    return _call(native.oversampled_abs_peak, list(samples), phases)


__all__ = [
    "available",
    "k_weight",
    "block_mean_squares",
    "block_summed_mean_squares",
    "oversampled_abs_peak",
]
