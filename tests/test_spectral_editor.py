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


def test_select_region_rejects_non_finite_bounds():
    # max/min clamping silently absorbs NaN: every comparison is False, so a
    # NaN bound returns the file's own limit -- select_region(nan, nan, ...)
    # used to produce a FULL-FILE selection that delete_selection would then
    # act on. Non-finite bounds must be rejected, not widened.
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)

    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            ed.select_region(bad, 0.5, 0, 22050)
        with pytest.raises(ValueError):
            ed.select_region(0.1, bad, 0, 22050)
        with pytest.raises(ValueError):
            ed.select_region(0.1, 0.5, bad, 22050)
        with pytest.raises(ValueError):
            ed.select_region(0.1, 0.5, 0, bad)


def test_select_region_rejects_non_numeric_bounds():
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)

    with pytest.raises(ValueError):
        ed.select_region("middle", 0.5, 0, 22050)


def test_select_region_clamps_finite_out_of_range_bounds():
    # Clamping itself is the contract -- only non-finite values are refused.
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)

    sel = ed.select_region(-5.0, 99.0, -1.0, 10 ** 9)
    assert sel.time_start == 0
    assert sel.time_end == ed.times[-1]
    assert sel.freq_start == ed.freqs[0]
    assert sel.freq_end == ed.freqs[-1]


def test_interpolate_refuses_empty_selection():
    # A reversed/out-of-range selection produces an all-False mask. The op
    # used to return True, push an undo state, and rewrite every sample via
    # the istft round-trip anyway -- a reported repair that changed audio
    # it never selected.
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)
    empty = ed.select_region(0.9, 0.1, 0, 22050)  # end < start
    assert not ed.get_selection_mask(empty).any()

    before_audio = ed.current_audio.copy()
    undo_depth = len(ed.undo_stack)
    assert not ed.interpolate_selection(empty)
    assert len(ed.undo_stack) == undo_depth
    assert np.array_equal(ed.current_audio, before_audio)


def test_harmonic_enhance_refuses_empty_selection():
    # Same contract as interpolate/delete/enhance/noise_reduce: an empty
    # mask must fail, not return True after consuming undo state and
    # round-tripping the whole file through istft.
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)
    empty = ed.select_region(0.9, 0.1, 0, 22050)
    assert not ed.get_selection_mask(empty).any()

    before_audio = ed.current_audio.copy()
    undo_depth = len(ed.undo_stack)
    assert not ed.harmonic_enhance_selection(empty)
    assert len(ed.undo_stack) == undo_depth
    assert np.array_equal(ed.current_audio, before_audio)


def test_noise_reduce_stays_inside_selection():
    # Spectral subtraction must write only the selected cells; the previous
    # version rebuilt the entire spectrogram from reduced_magnitude,
    # attenuating audio the user never selected.
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)
    before = np.abs(ed.stft).copy()

    sel = ed.select_region(0.4, 0.5, 100, 1000)
    mask = ed.get_selection_mask(sel)
    assert ed.noise_reduce_selection(sel, strength=0.8)

    after = np.abs(ed.stft)
    assert np.allclose(after[~mask], before[~mask])
    assert np.any(after[mask] < before[mask] - 1e-9)


def test_interpolate_selection_numpy_path_fills_masked_cells(monkeypatch):
    # With scipy absent the fallback was `smoothed = magnitude`, i.e.
    # `magnitude[mask] = magnitude[mask]` -- a no-op that still returned
    # True. The pure-numpy 4-neighbour mean must actually fill the cells.
    monkeypatch.setattr(spectral_editor, "HAS_SCIPY", False)
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)

    sel = ed.select_region(0.4, 0.5, 300, 600)
    mask = ed.get_selection_mask(sel)
    ed.stft[mask] = 0  # the "missing" content interpolate exists to fill

    assert ed.interpolate_selection(sel)
    assert np.abs(ed.stft)[mask].max() > 0


@pytest.mark.skipif(not spectral_editor.HAS_SCIPY, reason="needs scipy")
def test_interpolate_selection_scipy_path_fills_masked_cells():
    ed = spectral_editor.SpectralEditor()
    ed.load_audio(_sine(440), SAMPLE_RATE)

    sel = ed.select_region(0.4, 0.45, 300, 600)
    mask = ed.get_selection_mask(sel)
    ed.stft[mask] = 0

    assert ed.interpolate_selection(sel)
    assert np.nanmax(np.abs(ed.stft)[mask]) > 0
