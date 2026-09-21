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

import pytest

import core
import spectral_utils
from tests._helpers import write_sine_wave, write_wav_raw

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


def test_dominant_peaks_exclude_the_noise_floor(tmp_path):
    """'Dominant' must mean significant relative to the top component: a
    16-bit sine's quantization floor sits ~110 dB down and used to fill the
    dominant-frequencies list with Nyquist-adjacent noise bins."""
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5, frequency=440.0)

    result = core.get_samples_for_analysis(str(wav))
    report = spectral_utils.analyze_spectrum(
        result.data["samples"], result.data["sample_rate"]
    )

    assert report.dominant_peaks
    # Every surviving peak must hug the fundamental -- window sidelobes a few
    # bins off are fine, noise-floor bins at 6 kHz/21 kHz are not.
    assert all(abs(peak.frequency_hz - 440.0) < 10.0
               for peak in report.dominant_peaks), report.dominant_peaks


def test_dominant_peaks_keep_a_real_secondary_tone(tmp_path):
    """The significance gate must not eat real content: a -20 dB second tone
    is legitimately dominant-adjacent and must still be reported."""
    import struct as _struct
    import wave as _wave
    count = 22050
    frames = [
        int(12000 * math.sin(2 * math.pi * 440 * i / 44100)
            + 1200 * math.sin(2 * math.pi * 2000 * i / 44100))
        for i in range(count)
    ]
    wav = tmp_path / "two_tone.wav"
    with _wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(_struct.pack("<" + "h" * count, *frames))

    result = core.get_samples_for_analysis(str(wav))
    report = spectral_utils.analyze_spectrum(
        result.data["samples"], result.data["sample_rate"]
    )

    frequencies = [peak.frequency_hz for peak in report.dominant_peaks]
    assert any(abs(f - 440.0) < 10.0 for f in frequencies), frequencies
    assert any(abs(f - 2000.0) < 20.0 for f in frequencies), frequencies


def _extras_installed() -> bool:
    import main
    return bool(main.HAS_SOUNDFILE or main.HAS_LIBROSA)


@pytest.mark.skipif(not _extras_installed(),
                    reason="covers the installed-extra decode path")
def test_cli_spectrum_and_loudness_decode_float_wav_via_audio_extra(tmp_path):
    """On an install with the audio extra, a float WAV must not print
    'install the audio extra' -- it is installed. Decode through it."""
    frames = [0.5 * math.sin(2 * math.pi * 440 * i / 44100)
              for i in range(22050)]
    wav, _ = write_wav_raw(tmp_path / "float.wav", frames=frames,
                           format_tag=3)

    result = _run("analyze", str(wav), "--spectrum", "--loudness",
                  cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Dominant Frequencies:" in result.stdout
    assert "440." in result.stdout
    assert "Loudness:" in result.stdout
    assert "pip install" not in result.stdout
    assert "pip install" not in result.stderr


@pytest.mark.skipif(_extras_installed(),
                    reason="covers the dependency-free refusal")
def test_cli_spectrum_names_pcm_only_reader_on_bare_install(tmp_path):
    """On the dependency-free build the refusal is the right answer -- and it
    names the real limitation instead of pointing at an installed extra."""
    frames = [0.5 * math.sin(2 * math.pi * 440 * i / 44100)
              for i in range(22050)]
    wav, _ = write_wav_raw(tmp_path / "float.wav", frames=frames,
                           format_tag=3)

    result = _run("analyze", str(wav), "--spectrum", cwd=str(tmp_path))

    combined = result.stdout + result.stderr
    assert "PCM" in combined  # the reader's actual limitation


def test_cli_analyze_export_leaves_no_partial_or_temp_files(tmp_path):
    """--export goes through a sibling temp file + os.replace: after success
    the directory must hold exactly the export, not temp debris."""
    import json as _json
    wav = write_sine_wave(tmp_path / "tone.wav")
    export = tmp_path / "report.json"

    result = _run("analyze", str(wav), "--export", str(export),
                  cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert _json.loads(export.read_text())
    assert not list(tmp_path.glob(".chameleon-*.tmp"))
