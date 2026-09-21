import pytest


def test_repair_gaps_validates_bounds_and_repairs_edges():
    # Gaps touching frame 0 / the last frame used to be silently skipped
    # (returned "repaired" audio that was never touched), reversed gaps
    # crashed inside np.linspace, and out-of-range gaps were dropped.
    np = pytest.importorskip("numpy")
    pytest.importorskip("librosa")
    from audio_restoration import SpectralRepairer
    r = SpectralRepairer()
    sr = 44100
    audio = np.sin(2 * np.pi * 440 * np.arange(sr) / sr) * 0.5
    for gap in [(5000, 1000), (43000, 50000), (-5, 100), (100, 100)]:
        with pytest.raises(ValueError, match="Invalid gap"):
            r.repair_gaps(audio.copy(), [gap], sr)
    # Boundary gaps are now repaired with a one-sided hold, not skipped.
    out_start = r.repair_gaps(audio.copy(), [(0, 2048)], sr)
    assert np.abs(out_start - audio).max() > 1e-3
    out_end = r.repair_gaps(audio.copy(), [(sr - 2048, sr)], sr)
    assert np.abs(out_end - audio).max() > 1e-3
