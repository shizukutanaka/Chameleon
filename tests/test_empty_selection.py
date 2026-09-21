"""Empty selections must report failure, not success on a no-op.

A selection outside the clip (or with a degenerate range) produces an
empty mask. Every mutating op used to return True anyway -- writing
nothing, pushing an undo frame, and in `noise_reduce_selection`'s case
first tripping `np.median` on an empty array (RuntimeWarning + NaN).
Reporting success on work that did not happen is the same dishonesty the
interpolate no-op fix removed.
"""

import pytest

np = pytest.importorskip("numpy")

import spectral_editor

SAMPLE_RATE = 44100


def _editor():
    ed = spectral_editor.SpectralEditor()
    count = int(SAMPLE_RATE * 0.5)
    audio = 0.5 * np.sin(2 * np.pi * 440 * np.arange(count) / SAMPLE_RATE)
    ed.load_audio(audio, SAMPLE_RATE)
    return ed


def test_interpolate_rejects_full_spectrogram_selection():
    """Interpolation needs unselected bins as its source. With the whole
    spectrogram selected there is nothing to interpolate from: the op
    used to copy the magnitude back unchanged, report True, and push an
    undo frame for a no-op."""
    ed = _editor()
    everything = spectral_editor.SpectralSelection(
        time_start=float(ed.times[0]), time_end=float(ed.times[-1]) + 1.0,
        freq_start=0.0, freq_end=float(ed.freqs[-1]) + 1.0)

    undo_depth = len(ed.undo_stack)
    audio_before = ed.current_audio.copy()

    assert ed.interpolate_selection(everything) is False
    assert len(ed.undo_stack) == undo_depth
    assert np.array_equal(ed.current_audio, audio_before)


def test_mutations_reject_selection_outside_the_clip(recwarn):
    ed = _editor()
    # A 0.5 s clip; this region starts after the audio ends.
    outside = spectral_editor.SpectralSelection(
        time_start=9.0, time_end=9.5, freq_start=100.0, freq_end=1000.0)

    undo_depth = len(ed.undo_stack)
    audio_before = ed.current_audio.copy()

    assert ed.delete_selection(outside, fade_edges=False) is False
    assert ed.enhance_selection(outside) is False
    assert ed.harmonic_enhance_selection(outside) is False
    assert ed.interpolate_selection(outside) is False
    # noise_reduce is where the empty mask tripped np.median -> NaN.
    assert ed.noise_reduce_selection(outside) is False

    # A rejected selection must not have touched audio or the undo stack,
    # and must not have emitted the NaN-producing RuntimeWarning.
    assert np.array_equal(ed.current_audio, audio_before)
    assert len(ed.undo_stack) == undo_depth
    assert not [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]
