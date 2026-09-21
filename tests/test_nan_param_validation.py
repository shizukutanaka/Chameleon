"""NaN defeats every ordered comparison: `x <= 0 or x > 1.0` is False
for NaN, so a non-finite parameter used to sail through validation and
crash mid-transform (`cannot convert float NaN to integer`) or produce
a plausible but wrong "No audio content" failure. The core guards must
reject non-finite values themselves -- the CLI's chained comparisons and
pydantic's bounds are not the contract; the library is."""

import struct
import wave

import pytest

from core import WAVProcessor


def _tone(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<h", 1000) * 8000)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_normalize_rejects_nonfinite_target_peak(tmp_path, bad):
    src = tmp_path / "a.wav"
    out = tmp_path / "o.wav"
    _tone(src)
    result = WAVProcessor().normalize(str(src), str(out), bad)
    assert not result.success
    assert "Invalid target peak" in result.message
    assert not out.exists()


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_trim_silence_rejects_nonfinite_threshold(tmp_path, bad):
    src = tmp_path / "a.wav"
    out = tmp_path / "o.wav"
    _tone(src)
    result = WAVProcessor().trim_silence(str(src), str(out), bad)
    assert not result.success
    # 'Invalid threshold', not the misleading 'No audio content above
    # threshold' that a NaN comparison silently produces.
    assert "Invalid threshold" in result.message
    assert not out.exists()
