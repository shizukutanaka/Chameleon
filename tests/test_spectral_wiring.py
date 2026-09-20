"""Covers spectral_utils.py wiring into core.py / main.py.

spectral_utils.py was previously packaged but never imported (CHARTER §9's
orphaned-module punch list). It is real, deterministic (numpy-optional, with a
pure-Python DFT fallback), and non-duplicative — main.py's existing
--detailed frequency_range/spectral_centroid fields only populate when
librosa is installed, so the default stdlib-only install had no spectral
analysis at all. It was wired in via a new core.get_samples_for_analysis
helper (bounded, mono-mixed, *signed* waveform extraction — the existing
_normalize_amplitude discards sign, which is fine for peak/RMS but wrong for
spectral analysis) and a new `analyze --spectrum` CLI flag.
"""

import math
import subprocess
import sys
from pathlib import Path

import core
import spectral_utils
from tests._helpers import write_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, MAIN_PY, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


def test_get_samples_for_analysis_extracts_signed_waveform(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.3, frequency=440.0)

    result = core.get_samples_for_analysis(str(wav))

    assert result.success, result.message
    samples = result.data["samples"]
    assert result.data["sample_rate"] == 44100
    assert len(samples) > 0
    assert min(samples) < 0 < max(samples)  # signed, not abs()-only magnitude


def test_get_samples_for_analysis_respects_max_samples(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=1.0, frequency=440.0)

    result = core.get_samples_for_analysis(str(wav), max_samples=500)

    assert result.success
    assert len(result.data["samples"]) <= 500


def test_get_samples_for_analysis_rejects_missing_file(tmp_path):
    result = core.get_samples_for_analysis(str(tmp_path / "missing.wav"))
    assert not result.success


def test_spectral_analysis_pipeline_detects_known_frequency(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5, frequency=880.0)

    result = core.get_samples_for_analysis(str(wav))
    report = spectral_utils.analyze_spectrum(
        result.data["samples"], result.data["sample_rate"]
    )

    assert report.dominant_peaks
    assert abs(report.dominant_peaks[0].frequency_hz - 880.0) < 5.0


def test_cli_analyze_spectrum_flag(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5, frequency=880.0)

    result = _run("analyze", str(wav), "--spectrum", cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Dominant Frequencies:" in result.stdout
    assert "880." in result.stdout
    line = next(l for l in result.stdout.splitlines() if "Dominant Frequencies:" in l)
    # A pure tone has one dominant component; its level is printed relative
    # to itself so every entry carries a level the reader can judge.
    assert line.count("Hz") == 1, line
    assert "(+0.0 dB)" in line


def test_cli_analyze_without_spectrum_flag_omits_spectrum_output(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")

    result = _run("analyze", str(wav), cwd=str(tmp_path))

    assert result.returncode == 0
    assert "Dominant Frequencies" not in result.stdout


def test_apply_spectral_mask_preserves_tail_in_stdlib_fallback(monkeypatch):
    # The pure-Python DFT transforms at most 4096 samples per call; the
    # equaliser must process longer input in blocks rather than dropping
    # the tail.
    monkeypatch.setattr(spectral_utils, "HAS_NUMPY", False)
    src = [0.0] * 4096 + [1.0] * 904
    out = spectral_utils.apply_spectral_mask(src, 44100)
    assert len(out) == len(src)
    assert out[4500] != 0.0


def test_apply_spectral_mask_does_not_renormalize():
    # A uniform 0.5 gain must halve the signal -- the previous version
    # re-normalised every output to full scale, turning an attenuation
    # request into a boost.
    src = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(4000)]
    out = spectral_utils.apply_spectral_mask(
        src, 44100, low_gain=0.5, mid_gain=0.5, high_gain=0.5
    )
    assert max(abs(x) for x in out) < 0.3


def test_normalize_peak_rejects_non_finite_target():
    # 'target_peak <= 0' let NaN through (nan <= 0 is False), producing an
    # all-NaN "normalized" signal; +inf produced all-inf. Both are now
    # rejected -- the same isfinite hole fixed in core.normalize.
    src = [0.25, -0.25] * 16
    for bad in (float("nan"), float("inf")):
        try:
            spectral_utils.normalize_peak(src, bad)
        except ValueError:
            continue
        raise AssertionError(f"target_peak={bad} accepted")
    assert spectral_utils.normalize_peak(src, 0.5) == [
        0.5 if s > 0 else -0.5 for s in src]


def test_apply_spectral_mask_rejects_non_finite_gains():
    # 'gain < 0' let NaN through -- a NaN gain silently NaN'd the block.
    src = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(512)]
    for kw in ({"low_gain": float("nan")}, {"mid_gain": float("inf")},
               {"high_gain": float("nan")}):
        try:
            spectral_utils.apply_spectral_mask(src, 44100, **kw)
        except ValueError:
            continue
        raise AssertionError(f"{kw} accepted")
    assert spectral_utils.apply_spectral_mask(src, 44100) != []


def test_analyze_spectrum_rejects_non_finite_sample_rate():
    # 'sample_rate <= 0' let NaN/inf through; the report then carried
    # nan/inf in every frequency-derived field while rms stayed real.
    src = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(512)]
    for bad in (float("nan"), float("inf")):
        try:
            spectral_utils.analyze_spectrum(src, bad)
        except ValueError:
            continue
        raise AssertionError(f"sample_rate={bad} accepted")
    report = spectral_utils.analyze_spectrum(src, 44100)
    assert report.sample_rate == 44100


def test_apply_spectral_mask_rejects_bad_sample_rate():
    # bin_width derives every bin's band from sample_rate: nan -> all
    # high_gain, 0/negative -> all low_gain, inf -> all high_gain -- the
    # three-band equaliser silently became a flat uniform gain instead of
    # refusing, unlike analyze_spectrum which already rejects these.
    src = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(512)]
    for bad in (0, -8000, float("nan"), float("inf")):
        try:
            spectral_utils.apply_spectral_mask(src, bad)
        except ValueError:
            continue
        raise AssertionError(f"sample_rate={bad} accepted")
    # A valid rate still passes and applies per-band gains.
    out = spectral_utils.apply_spectral_mask(
        src, 44100, low_gain=0.0, mid_gain=1.0, high_gain=1.0)
    assert len(out) == len(src)


def test_spectral_helpers_reject_non_finite_samples():
    # float() accepts NaN/inf, so _to_float_sequence used to pass them
    # through: analyze_spectrum reported nan rms/dc, apply_spectral_mask
    # NaN'd the whole block, normalize_peak's max() silently zeroed the
    # signal on inf, linear_resample and sliding_window_rms spread nan.
    nan = float("nan")
    inf = float("inf")
    calls = [
        lambda bad: spectral_utils.analyze_spectrum([0.1, bad, 0.5], 44100),
        lambda bad: spectral_utils.normalize_peak([0.1, bad, 0.5]),
        lambda bad: spectral_utils.linear_resample(
            [0.1, bad, 0.5], 8000, 16000),
        lambda bad: spectral_utils.apply_spectral_mask(
            [0.1, bad, 0.3, 0.5], 44100),
        lambda bad: spectral_utils.sliding_window_rms([0.1, bad, 0.5], 2),
    ]
    for call in calls:
        for bad in (nan, inf, -inf):
            try:
                call(bad)
            except ValueError:
                continue
            raise AssertionError(f"non-finite sample {bad} accepted")

    src = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(512)]
    assert spectral_utils.normalize_peak(src) != []
    assert spectral_utils.analyze_spectrum(src, 44100).rms_level > 0
    assert spectral_utils.sliding_window_rms(src, 64) != []
    assert spectral_utils.linear_resample(src, 44100, 22050) != []
    assert spectral_utils.apply_spectral_mask(src, 44100) != []


def test_sliding_window_rms_empty_input_returns_empty():
    # Empty input clamped window_size to 0, then divided by it --
    # a ZeroDivisionError where every sibling entry point returns [].
    assert spectral_utils.sliding_window_rms([], 5) == []


def test_sliding_window_rms_values():
    assert spectral_utils.sliding_window_rms([2.0] * 8, 4) == [2.0] * 5
    # A window wider than the signal clamps to one full-length window.
    assert spectral_utils.sliding_window_rms([3.0, -3.0], 10) == [3.0]
