"""The dependency-free signal paths in spectral_utils must actually
work -- they are the documented fallback when numpy/scipy are absent."""

import math

from spectral_utils import apply_spectral_mask, linear_resample


def _sine(freq, sr, n, amp=0.5):
    return [math.sin(2 * math.pi * freq * i / sr) * amp for i in range(n)]


def _zero_crossing_freq(samples, rate):
    crossings = sum(
        1 for i in range(1, len(samples))
        if samples[i - 1] < 0 <= samples[i])
    return crossings * rate / len(samples)


def _rms(samples):
    return math.sqrt(sum(v * v for v in samples) / len(samples))


class TestLinearResample:
    def test_upsample_preserves_frequency_and_peak(self):
        sr = 22050
        sig = _sine(440, sr, sr)
        up = linear_resample(sig, sr, 44100)
        assert len(up) == 44100
        assert abs(_zero_crossing_freq(up, 44100) - 440) < 5
        assert abs(max(map(abs, up)) - max(map(abs, sig))) < 0.01

    def test_downsample_preserves_frequency(self):
        sr = 22050
        sig = _sine(440, sr, sr)
        down = linear_resample(sig, sr, 11025)
        assert len(down) == 11025
        assert abs(_zero_crossing_freq(down, 11025) - 440) < 5


class TestThreeBandEq:
    def test_high_gain_zero_removes_high_content(self):
        sr = 22050
        n = 4096
        lo = _sine(200, sr, n, 0.4)
        hi = _sine(8000, sr, n, 0.4)
        mix = [a + b for a, b in zip(lo, hi)]
        out = apply_spectral_mask(mix, sr, high_gain=0.0)
        assert abs(_rms(out) - _rms(lo)) < 0.05

    def test_low_gain_zero_removes_low_content(self):
        sr = 22050
        n = 4096
        lo = _sine(200, sr, n, 0.4)
        hi = _sine(8000, sr, n, 0.4)
        mix = [a + b for a, b in zip(lo, hi)]
        out = apply_spectral_mask(mix, sr, low_gain=0.0)
        assert abs(_rms(out) - _rms(hi)) < 0.05

    def test_negative_gain_rejected(self):
        import pytest
        with pytest.raises(ValueError, match="non-negative"):
            apply_spectral_mask([0.0, 1.0], 22050, mid_gain=-1.0)
