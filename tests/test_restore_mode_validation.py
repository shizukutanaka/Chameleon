"""AudioRestorer.restore mode validation (audit 71).

``mode`` accepted any string and the docstring advertised five modes, but
only two pipelines exist: "vinyl" runs VinylRestorer and everything else
fell through to the RestorationConfig-driven path -- so ``mode="voice"``
reported ``"mode": "voice"`` over the same processing ``"auto"`` runs,
and ``mode="garbage"`` was silently accepted and echoed back.
"""

import pytest

np = pytest.importorskip("numpy")
# AudioRestorer's entry point refuses without SciPy too (same gate the
# rest of this module's tests use).
pytest.importorskip("scipy")

from audio_restoration import AudioRestorer

SAMPLE_RATE = 22050


def _sine(freq=440.0, seconds=0.5):
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return np.sin(2 * np.pi * freq * t) * 0.3


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="auto.*vinyl"):
        AudioRestorer().restore(_sine(), SAMPLE_RATE, mode="garbage")


@pytest.mark.parametrize("phantom", ["digital", "voice", "music"])
def test_phantom_docstring_modes_are_rejected(phantom):
    # These names were listed in the docstring but never had distinct
    # pipelines -- each ran the same generic path while reporting its
    # own name. Accepting them again would revive a fantasy knob.
    with pytest.raises(ValueError, match="auto.*vinyl"):
        AudioRestorer().restore(_sine(), SAMPLE_RATE, mode=phantom)


def test_auto_mode_runs_config_driven_pipeline():
    _, info = AudioRestorer().restore(_sine(), SAMPLE_RATE, mode="auto")
    assert info["mode"] == "auto"


def test_vinyl_mode_still_routes_to_vinyl_pipeline():
    _, info = AudioRestorer().restore(_sine(), SAMPLE_RATE, mode="vinyl")
    assert info["mode"] == "vinyl"
    # VinylRestorer reports under the shared schema keys.
    assert "applied_processes" in info
    assert "skipped_processes" in info


def test_default_mode_is_auto():
    restorer = AudioRestorer()
    _, default_info = restorer.restore(_sine(), SAMPLE_RATE)
    assert default_info["mode"] == "auto"
