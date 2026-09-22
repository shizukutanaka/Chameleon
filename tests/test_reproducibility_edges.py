"""Audit-50: dither determinism, empty spectral selections, odd-N bin width.

- Dither paths (int16 writer, mastering tpdf/rpdf/shaped) must be seeded so
  the same input produces the same bytes (CHARTER 1 reproducibility), the
  same convention apply_effects' reverb tail already follows.
- Spectral selection ops on an empty mask must refuse instead of reporting
  success on a no-op.
- Spectrum bin width is sample_rate/num_samples; the previous formula
  sr/(2*(bins-1)) is only equivalent for even transform lengths.
"""

import math
import sys

import pytest

np = pytest.importorskip("numpy", reason="these paths require numpy")

import mastering_chain
import spectral_editor
import spectral_utils
from main import AudioProcessor, ProcessingConfig


def _editor(tmp_path):
    editor = spectral_editor.SpectralEditor()
    t = np.arange(44100) / 44100
    editor.load_audio(0.5 * np.sin(2 * np.pi * 220 * t), 44100)
    return editor


def _empty_selection(editor):
    # A band entirely above Nyquist clamps to an empty mask.
    return editor.select_region(0.0, 0.5, 30000.0, 40000.0)


def test_mastering_dither_is_deterministic(tmp_path):
    chain = mastering_chain.MasteringChain(mastering_chain.MasteringConfig())
    audio = np.full(2000, 0.5)
    for dither_type in ("tpdf", "rpdf", "shaped"):
        first = chain._apply_dither(audio.copy(), dither_type)
        second = chain._apply_dither(audio.copy(), dither_type)
        assert np.array_equal(first, second), dither_type
        # Dither must actually modify the signal (guard against a stub).
        assert not np.array_equal(first, audio), dither_type


def test_int16_writer_dither_is_deterministic(tmp_path):
    config = ProcessingConfig(apply_dither=True)
    processor = AudioProcessor(config)
    audio = np.full(500, 0.5, dtype=np.float32)
    first = tmp_path / "a.wav"
    second = tmp_path / "b.wav"
    processor._save_wav_basic(audio.copy(), str(first), 44100)
    processor._save_wav_basic(audio.copy(), str(second), 44100)
    assert first.read_bytes() == second.read_bytes()


def test_delete_selection_refuses_empty_selection(tmp_path):
    editor = _editor(tmp_path)
    assert editor.delete_selection(_empty_selection(editor)) is False


def test_enhance_selection_refuses_empty_selection(tmp_path):
    editor = _editor(tmp_path)
    assert editor.enhance_selection(_empty_selection(editor)) is False


def test_harmonic_enhance_refuses_empty_selection(tmp_path):
    editor = _editor(tmp_path)
    assert editor.harmonic_enhance_selection(_empty_selection(editor)) is False


def test_interpolate_selection_refuses_empty_selection(tmp_path):
    editor = _editor(tmp_path)
    assert editor.interpolate_selection(_empty_selection(editor)) is False


def test_peak_frequency_uses_true_transform_length():
    # Odd transform length: the tone lands exactly on bin k. With the old
    # sr/(2*(K-1)) width the reported frequency comes out ~N/(N-1) high.
    sample_rate = 48000
    n = 1001  # odd
    k = 10
    true_freq = k * sample_rate / n
    samples = [math.sin(2 * math.pi * true_freq * i / sample_rate) for i in range(n)]
    report = spectral_utils.analyze_spectrum(samples, sample_rate, max_peaks=1)
    assert report.dominant_peaks
    assert abs(report.dominant_peaks[0].frequency_hz - true_freq) < 0.1


def test_band_gain_boundary_uses_true_transform_length():
    # N=481, k=20: k*sr/N = 1995.84 (< 2000 Hz mid band) while the old
    # sr/(N-1) width labels the same bin exactly 2000 Hz (high band).
    # With mid_gain=0 and high_gain=1 the fixed code silences the tone;
    # the old boundary leaves it untouched.
    sample_rate = 48000
    n = 481
    freq = 20 * sample_rate / n  # ~1995.8 Hz
    samples = [0.4 * math.sin(2 * math.pi * freq * i / sample_rate) for i in range(n)]
    processed = spectral_utils.apply_spectral_mask(
        samples, sample_rate, mid_gain=0.0, high_gain=1.0
    )
    energy = sum(v * v for v in processed)
    assert energy < 0.01 * sum(v * v for v in samples)
