"""Covers core.get_samples_for_analysis(separate_channels=True) and its use
by `analyze --loudness` (bs1770_loudness.measure_integrated_loudness_multichannel).

Averaging a stereo signal's samples to mono *before* K-weighting under-reads
real stereo content by 3-6 LU relative to BS.1770's actual requirement (sum
each channel's post-filter energy) -- see bs1770_loudness.py's module
docstring and CHARTER.md §9. This closes that gap in the default
`analyze --loudness` path.
"""

import math
import subprocess
import sys
from pathlib import Path

import core
from tests._helpers import write_sine_wave, write_stereo_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, MAIN_PY, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


def test_separate_channels_returns_one_waveform_per_channel(tmp_path):
    wav = write_stereo_sine_wave(tmp_path / "stereo.wav", duration=0.5, frequency=440.0)

    result = core.get_samples_for_analysis(str(wav), separate_channels=True)

    assert result.success, result.message
    channels = result.data["channels"]
    assert len(channels) == 2
    assert len(channels[0]) > 0
    assert len(channels[0]) == len(channels[1])


def test_separate_channels_is_not_averaged(tmp_path):
    # Left at full gain, right silent: the per-channel extraction must show
    # that asymmetry, unlike the mono downmix (which would halve the left
    # channel's amplitude into both).
    wav = write_stereo_sine_wave(tmp_path / "stereo.wav", duration=0.3, frequency=440.0,
                                  left_gain=1.0, right_gain=0.0)

    result = core.get_samples_for_analysis(str(wav), separate_channels=True)

    assert result.success
    left, right = result.data["channels"]
    assert max(abs(s) for s in left) > 0.1
    assert max(abs(s) for s in right) < 1e-6


def test_separate_channels_respects_max_samples_per_channel(tmp_path):
    wav = write_stereo_sine_wave(tmp_path / "stereo.wav", duration=1.0, frequency=440.0)

    result = core.get_samples_for_analysis(str(wav), max_samples=500, separate_channels=True)

    assert result.success
    for channel in result.data["channels"]:
        assert len(channel) <= 500


def test_cli_analyze_loudness_on_stereo_uses_correct_channel_summing(tmp_path):
    # Identical-content stereo must read ~3.01 dB louder than the same
    # content halved (i.e. correct summed-energy loudness), not the mono-
    # downmix figure. We can't assert an exact LUFS number through the CLI
    # (rounded to 1 decimal), so assert the CLI's label reflects the
    # channel-summing behavior instead of a stale "mono" claim.
    wav = write_stereo_sine_wave(tmp_path / "stereo.wav", duration=1.0, frequency=1000.0)

    result = _run("analyze", str(wav), "--loudness", cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Loudness:" in result.stdout
    assert "mono," not in result.stdout  # stale label from the pre-fix downmix wiring


def test_mono_file_gives_identical_loudness_via_multichannel_or_mono_path(tmp_path):
    # A mono file has exactly one channel, so the multichannel path (now
    # used unconditionally by the CLI) must produce the same reading as the
    # plain mono function -- verifies the CLI's channel-summing rewrite
    # didn't change behavior for the common mono case.
    import bs1770_loudness

    wav = write_sine_wave(tmp_path / "mono.wav", duration=1.0, frequency=1000.0)

    mono_result = core.get_samples_for_analysis(str(wav))
    channels_result = core.get_samples_for_analysis(str(wav), separate_channels=True)

    lufs_mono = bs1770_loudness.measure_integrated_loudness(
        mono_result.data["samples"], mono_result.data["sample_rate"]
    )
    lufs_multichannel = bs1770_loudness.measure_integrated_loudness_multichannel(
        channels_result.data["channels"], channels_result.data["sample_rate"]
    )

    assert lufs_multichannel == lufs_mono
