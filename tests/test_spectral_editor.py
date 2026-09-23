"""What spectral_editor claims versus what it does.

The module is an allowed orphan (packaged, not wired into the CLI) — but
its library API is still shipped surface, and four independent defects
meant none of its edit operations could ever have worked on the default
install:

* `_compute_stft_manual` built the frequency axis with `np.fft.fftfreq`
  (two-sided: the Nyquist bin lands as -fs/2) for a one-sided rfft
  spectrum. The axis was no longer sorted, `searchsorted` returned
  nonsense indices, and every selection collapsed to an empty mask.
* `_smooth_mask_edges` returned the float convolution result; indexing
  `stft[float_mask]` raises TypeError, so every default
  `delete_selection`/`enhance_selection` (fade_edges=True) caught it and
  returned False.
* `_compute_stft_manual` counted only whole frames, so ISTFT never
  covered the file's tail and every edit silently truncated output.
* `_compute_istft_manual` normalized the overlap-add by the bare window
  although the window is applied twice (analysis + synthesis), returning
  `audio * window` — a round-trip off by up to 100% of the amplitude.
* `paste_selection` read `copied_stft[target_mask]` — positions that
  copy_selection had zeroed — so it pasted silence and returned True.

The librosa path never saved any of this on a stock [audio] install:
`import librosa.display` pulls in matplotlib, which the extra does not
install, so HAS_LIBROSA is False and the manual path is what runs.
"""

import pytest

np = pytest.importorskip("numpy")

import spectral_editor


SAMPLE_RATE = 44100


def _sine(freq, amplitude=0.5, seconds=1.0):
    count = int(SAMPLE_RATE * seconds)
    return amplitude * np.sin(2 * np.pi * freq * np.arange(count) / SAMPLE_RATE)


def test_frequency_axis_is_one_sided_and_sorted():
    proc = spectral_editor.SpectrogramProcessor()
    _, _, freqs = proc.compute_stft(_sine(440), SAMPLE_RATE)

    assert freqs[-1] == pytest.approx(SAMPLE_RATE / 2)
    assert np.all(np.diff(freqs) > 0)


def test_stft_istft_round_trip_is_identity():
    audio = _sine(440)
    proc = spectral_editor.SpectrogramProcessor()
    stft, _, _ = proc.compute_stft(audio, SAMPLE_RATE)
    restored = proc.compute_istft(stft, SAMPLE_RATE, len(audio))

    assert len(restored) == len(audio)
    assert np.abs(restored - audio).max() < 1e-6


def test_delete_selection_actually_deletes():
    ed = spectral_editor.SpectralEditor()
    audio = _sine(440)
    ed.load_audio(audio, SAMPLE_RATE)

    assert ed.delete_selection(ed.select_region(0.4, 0.6, 0, 22050))
    interior = ed.current_audio[int(0.46 * SAMPLE_RATE):int(0.54 * SAMPLE_RATE)]
    assert np.abs(interior).max() < 0.02
    assert np.abs(ed.current_audio[: int(0.3 * SAMPLE_RATE)]).max() == \
        pytest.approx(0.5, abs=0.05)


def test_paste_selection_actually_pastes():
    ed = spectral_editor.SpectralEditor()
    audio = np.zeros(SAMPLE_RATE)
    audio[int(0.1 * SAMPLE_RATE):int(0.3 * SAMPLE_RATE)] = \
        _sine(440)[: int(0.2 * SAMPLE_RATE)]
    ed.load_audio(audio, SAMPLE_RATE)

    copied = ed.copy_selection(ed.select_region(0.1, 0.3, 0, 22050))
    assert ed.paste_selection(copied, ed.select_region(0.7, 0.9, 0, 22050))
    pasted = ed.current_audio[int(0.72 * SAMPLE_RATE):int(0.86 * SAMPLE_RATE)]
    assert np.abs(pasted).max() > 0.2


def test_paste_of_empty_copy_refuses():
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)

    assert not ed.paste_selection(
        np.zeros_like(ed.stft), ed.select_region(0.5, 0.6, 0, 22050))


def test_harmonic_enhance_stays_inside_selection():
    # Boosting harmonics must write only the selected time columns --
    # the previous version multiplied whole frequency rows, changing
    # audio far outside the user's selection.
    ed = spectral_editor.SpectralEditor()
    audio = np.sin(2 * np.pi * 220 * np.arange(SAMPLE_RATE) / SAMPLE_RATE) * 0.3
    ed.load_audio(audio, SAMPLE_RATE)
    before = np.abs(ed.stft).copy()

    sel = ed.select_region(0.4, 0.5, 0, 100)
    assert ed.harmonic_enhance_selection(sel, harmonic_strength=0.5)

    after = np.abs(ed.stft)
    changed = np.argwhere(after - before > 1e-9)
    assert changed.size > 0
    times = ed.times
    assert all(0.4 <= times[c[1]] <= 0.5 for c in changed)


def test_noise_reduce_on_empty_selection_refuses_instead_of_writing_nan():
    # An empty mask means np.median([]) == NaN, and NaN propagates through
    # the whole spectrogram: the operation returned True with an all-NaN
    # file. A selection that covers no cells must refuse instead.
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)
    # 30-31 kHz clamps to the top of the band and selects nothing.
    empty = ed.select_region(0.1, 0.2, 30000.0, 31000.0)
    assert not ed.get_selection_mask(empty).any()

    assert ed.noise_reduce_selection(empty) is False
    assert not np.isnan(ed.export_current_audio()).any()


def test_manual_round_trip_recovers_signal_at_the_edges(monkeypatch):
    # The manual STFT anchored frames at signal index 0 rather than
    # center-padding like librosa: samples under the window's zero ends
    # (index 0 for hann) were multiplied away and could not come back.
    # A sine hides it (sine[0] == 0), so use noise with nonzero edges --
    # measured old-code error at sample 0: ~0.8.
    monkeypatch.setattr(spectral_editor, "HAS_LIBROSA", False)
    rng = np.random.RandomState(7)
    audio = rng.randn(8192) * 0.1
    proc = spectral_editor.SpectrogramProcessor()
    stft, _, _ = proc.compute_stft(audio, SAMPLE_RATE)
    restored = proc.compute_istft(stft, SAMPLE_RATE, len(audio))

    assert len(restored) == len(audio)
    assert np.abs(restored[:2048] - audio[:2048]).max() < 1e-6
    assert np.abs(restored[-2048:] - audio[-2048:]).max() < 1e-6


def test_manual_round_trip_honours_the_hamming_window(monkeypatch):
    # Analysis applied 'hamming' but synthesis treated anything non-hann
    # as rectangular: window**2 normalisation divided by ones**2 and the
    # reconstruction came back scaled and tapered (max error ~1.4).
    monkeypatch.setattr(spectral_editor, "HAS_LIBROSA", False)
    audio = _sine(440, seconds=0.2)
    cfg = spectral_editor.SpectrogramConfig(window="hamming")
    proc = spectral_editor.SpectrogramProcessor(cfg)
    stft, _, _ = proc.compute_stft(audio, SAMPLE_RATE)
    restored = proc.compute_istft(stft, SAMPLE_RATE, len(audio))

    assert np.abs(restored - audio).max() < 1e-3


def test_manual_stft_uses_the_same_frame_grid_as_librosa(monkeypatch):
    # Center-padded convention: 1 + len//hop frames, frame i centered on
    # sample i*hop -- identical to librosa.stft(center=True), so a
    # spectrogram does not shift shape with the installed extras.
    monkeypatch.setattr(spectral_editor, "HAS_LIBROSA", False)
    audio = _sine(440, seconds=0.2)
    proc = spectral_editor.SpectrogramProcessor()
    stft, times, _ = proc.compute_stft(audio, SAMPLE_RATE)

    expected_frames = 1 + len(audio) // 512
    assert stft.shape[1] == expected_frames
    assert times[0] == pytest.approx(0.0)
