"""On digital silence, unmeasurable fields must read null, not 0.0.

librosa guards its internal divisions, so on an all-zero signal
spectral_centroid comes back as mean-of-zeros = 0.0 Hz and beat_track as
0.0 BPM -- fabricated measurements that --export then wrote as real
numbers. The null contract (see _json_export_default) already treats
tempo==0.0 / frequency_range==(0.0,0.0) as "not estimable"; the compute
site now leaves them None too, matching loudness on the same input.
"""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("librosa")

import main


def _analyze_silence():
    proc = main.AudioProcessor()
    return proc.analyze_audio(np.zeros(44100, dtype=np.float32), 44100)


def test_silence_reports_null_for_unmeasurable_fields():
    md = _analyze_silence()

    # Measured quantities stay real: silence's peak/rms/zcr are true zeros.
    assert md.peak_level == 0.0
    assert md.rms_level == 0.0
    assert md.zero_crossing_rate == 0.0

    # Undefined quantities must not masquerade as measurements.
    assert md.spectral_centroid is None
    assert md.tempo is None
    assert md.frequency_range is None


def test_non_silent_signal_still_reports_centroid():
    proc = main.AudioProcessor()
    tone = 0.5 * np.sin(2 * np.pi * 440 * np.arange(44100) / 44100).astype(np.float32)
    md = proc.analyze_audio(tone, 44100)

    assert md.spectral_centroid is not None and np.isfinite(md.spectral_centroid)
    assert md.frequency_range is not None
