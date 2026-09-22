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


def test_selection_to_reported_end_covers_last_frame_and_top_bin():
    # load_audio reports time_range/frequency_range ending at the last
    # frame and the top bin, and select_region clamps to those same
    # values -- but get_selection_mask sliced end-exclusive, so a
    # selection to the module's own advertised end silently dropped the
    # final frame and the Nyquist bin.
    ed = spectral_editor.SpectralEditor()
    info = ed.load_audio(_sine(440), SAMPLE_RATE)

    sel = ed.select_region(0.0, info["time_range"][1],
                           0.0, info["frequency_range"][1])
    mask = ed.get_selection_mask(sel)

    assert mask.shape == ed.stft.shape
    assert mask[:, -1].all(), "last time frame not covered by full-range selection"
    assert mask[-1, :].all(), "top (Nyquist) bin not covered by full-range selection"
    assert mask.all()


def test_selection_end_boundary_is_inclusive():
    # A selection ending exactly on an interior frame must include that
    # frame (same inclusive-end contract as the range-end fix above).
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)

    boundary = float(ed.times[3])
    sel = ed.select_region(0.0, boundary, 0.0, 0.0)
    mask = ed.get_selection_mask(sel)
    covered = mask.any(axis=0)

    assert covered[3], "frame at the end boundary was excluded"
    assert not covered[4], "selection included a frame past its end"
