#!/usr/bin/env python3
"""
Loudness measurement and normalization (ITU-R BS.1770 / EBU R128).

Peak normalization ignores perceived loudness; this module implements
loudness-matched gain to a target integrated loudness in LUFS, using the
validated ``pyloudnorm`` meter when available. It degrades gracefully: callers
get a clear :class:`LoudnessUnavailable` error instead of a crash when the
optional dependency is missing.

Audio is accepted in Chameleon's internal layout (mono 1-D, or 2-D shaped
``(channels, samples)``) and returned in the same layout.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

try:  # optional dependency
    import numpy as np
except ImportError:  # pragma: no cover - numpy is required for audio paths anyway
    np = None  # type: ignore

try:
    import pyloudnorm as _pyln
    HAS_PYLOUDNORM = True
except ImportError:
    _pyln = None
    HAS_PYLOUDNORM = False


# Common streaming/broadcast integrated-loudness targets (LUFS).
PLATFORM_TARGETS = {
    "streaming": -14.0,
    "spotify": -14.0,
    "youtube": -14.0,
    "apple": -16.0,
    "ebu": -23.0,
    "broadcast": -23.0,
}

DEFAULT_TARGET_LUFS = -14.0
DEFAULT_PEAK_CEILING = 0.97  # sample-peak ceiling applied after loudness gain


class LoudnessUnavailable(RuntimeError):
    """Raised when loudness features are requested without ``pyloudnorm``."""


def _to_samples_first(audio):
    """Return audio shaped (samples,) or (samples, channels) for pyloudnorm."""
    if audio.ndim == 1:
        return audio
    # Internal layout is (channels, samples); pyloudnorm wants samples-first.
    if audio.shape[0] < audio.shape[1]:
        return audio.T
    return audio


def measure_lufs(audio, sr: int) -> float:
    """Measure integrated loudness (LUFS) of *audio* at sample rate *sr*."""
    if not HAS_PYLOUDNORM or np is None:
        raise LoudnessUnavailable(
            "Loudness measurement requires 'pyloudnorm' (pip install pyloudnorm)."
        )
    data = _to_samples_first(np.asarray(audio, dtype=np.float64))
    meter = _pyln.Meter(int(sr))
    return float(meter.integrated_loudness(data))


def loudness_normalize(
    audio,
    sr: int,
    target_lufs: float = DEFAULT_TARGET_LUFS,
    peak_ceiling: float = DEFAULT_PEAK_CEILING,
) -> Tuple[Any, Dict[str, Any]]:
    """Loudness-normalize *audio* to *target_lufs*.

    Measures integrated loudness, applies the matching gain, then limits the
    sample peak to *peak_ceiling* to avoid clipping. Returns
    ``(normalized_audio, info)`` in the input layout. ``info`` includes the
    measured input loudness, applied gain (dB), the achieved loudness, and the
    output peak.
    """
    if not HAS_PYLOUDNORM or np is None:
        raise LoudnessUnavailable(
            "Loudness normalization requires 'pyloudnorm' (pip install pyloudnorm)."
        )

    arr = np.asarray(audio, dtype=np.float64)
    if arr.size == 0:
        return audio, {"measured_lufs": None, "gain_db": 0.0,
                       "target_lufs": target_lufs, "output_peak": 0.0}

    measured = measure_lufs(arr, sr)
    info: Dict[str, Any] = {
        "measured_lufs": round(measured, 2),
        "target_lufs": float(target_lufs),
        "gain_db": 0.0,
        "limited": False,
    }

    # -inf loudness (digital silence) cannot be normalized.
    if not np.isfinite(measured):
        info["output_peak"] = float(np.abs(arr).max())
        return audio, info

    gain_db = float(target_lufs) - measured
    gain_lin = 10.0 ** (gain_db / 20.0)
    out = arr * gain_lin

    peak = float(np.abs(out).max())
    if peak > peak_ceiling and peak > 0:
        out = out * (peak_ceiling / peak)
        info["limited"] = True

    info["gain_db"] = round(gain_db, 2)
    info["output_peak"] = round(float(np.abs(out).max()), 4)
    try:
        info["achieved_lufs"] = round(measure_lufs(out, sr), 2)
    except LoudnessUnavailable:  # pragma: no cover
        pass

    return out.astype(arr.dtype), info


__all__ = [
    "HAS_PYLOUDNORM",
    "LoudnessUnavailable",
    "PLATFORM_TARGETS",
    "DEFAULT_TARGET_LUFS",
    "measure_lufs",
    "loudness_normalize",
]
