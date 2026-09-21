"""A transform must consume the whole file, not a capped prefix.

_calculate_levels_safe used to stop after 1M channel-samples, so a peak
later in the file was invisible to normalize's gain computation (silent
wrong answer). _apply_gain_safe used to raise past 10M channel-samples,
rejecting ordinary stereo files longer than ~113s while the declared
limit is file size (500MB). Both loops are chunked reads bounded by
data_size; the caps protected nothing and produced wrong/failed results.
"""

import os
import struct
import wave

from core import WAVProcessor


def _write_mono_wav(path, sampwidth, rate, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(samples)


def test_peak_measured_on_whole_file(tmp_path):
    """A loud sample past the old 1M-sample read prefix must be seen."""
    src = tmp_path / "late_peak.wav"
    quiet = struct.pack("<h", 1000) * 1_050_000
    _write_mono_wav(src, 2, 8000, quiet + struct.pack("<h", 32767))

    w = WAVProcessor()
    info = w._read_wav_header(str(src))
    assert info is not None
    peak, _rms = w._calculate_levels_safe(str(src), info)
    assert peak > 0.9, f"peak {peak} measured on a prefix, not the file"


def test_normalize_past_former_sample_cap(tmp_path):
    """A file past the old 10M channel-sample cap must normalize, not fail."""
    src = tmp_path / "long.wav"
    out = tmp_path / "long_out.wav"
    # 8-bit mono: 10.2M channel-samples, all slightly above centre.
    _write_mono_wav(src, 1, 8000, bytes([130]) * 10_200_000)

    result = WAVProcessor().normalize(str(src), str(out), 0.95)
    assert result.success, result.message
    info = WAVProcessor()._read_wav_header(str(out))
    assert info is not None
    assert info.data_size == 10_200_000
    assert os.path.getsize(str(out)) > 10_000_000
