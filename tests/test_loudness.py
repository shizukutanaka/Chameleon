#!/usr/bin/env python3
"""Tests for loudness measurement / EBU R128 normalization.

Skipped automatically when the optional pyloudnorm/numpy stack is absent, so the
dependency-light CI stays green; when present, they verify the normalization
actually hits the requested LUFS target and respects the peak ceiling.
"""

import unittest

try:
    import numpy as np
    import pyloudnorm  # noqa: F401
    import loudness
    _HAVE_DEPS = True
except ImportError:  # pragma: no cover - environment dependent
    _HAVE_DEPS = False


@unittest.skipUnless(_HAVE_DEPS, "numpy/pyloudnorm not installed")


def _sine(seconds=2.0, freq=1000.0, sr=44100, amp=0.2):
    t = np.arange(int(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float64)


class LoudnessTests(unittest.TestCase):
    def test_normalize_hits_target(self):
        audio = _sine(amp=0.1)  # quiet source
        out, info = loudness.loudness_normalize(audio, 44100, target_lufs=-16.0)
        # Achieved loudness should be within ~0.5 LU of the target.
        self.assertAlmostEqual(info["achieved_lufs"], -16.0, delta=0.5)
        self.assertAlmostEqual(loudness.measure_lufs(out, 44100), -16.0, delta=0.5)

    def test_peak_ceiling_respected(self):
        audio = _sine(amp=0.1)
        # Aggressive target would exceed 0 dBFS; peak limiting must cap it.
        out, info = loudness.loudness_normalize(
            audio, 44100, target_lufs=0.0, peak_ceiling=0.97
        )
        self.assertLessEqual(float(np.abs(out).max()), 0.97 + 1e-6)
        self.assertTrue(info["limited"])

    def test_silence_is_handled(self):
        audio = np.zeros(44100, dtype=np.float64)
        out, info = loudness.loudness_normalize(audio, 44100, target_lufs=-14.0)
        # Digital silence has no finite loudness; must not raise or amplify noise.
        self.assertEqual(float(np.abs(out).max()), 0.0)

    def test_stereo_channels_first_layout(self):
        mono = _sine(amp=0.1)
        stereo = np.stack([mono, mono])  # (channels, samples)
        out, info = loudness.loudness_normalize(stereo, 44100, target_lufs=-18.0)
        self.assertEqual(out.shape, stereo.shape)
        self.assertAlmostEqual(info["achieved_lufs"], -18.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
