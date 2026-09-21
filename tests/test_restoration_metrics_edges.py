"""_calculate_metrics must not warn or crash on silent / empty input.

At HEAD, `restore()` on silent audio reached `np.log10(0/…)` for
`dynamic_range_*` and `signal_to_change_db`, emitting
`RuntimeWarning: divide by zero encountered in log10` -- which the DSP
gate (`-W error::RuntimeWarning`) turns into an error. Empty audio
crashed outright. Silence's dynamic range is honestly -inf, but it must
be *set* to -inf, not computed through a warned log.
"""
import warnings

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

import numpy as np

from audio_restoration import AudioRestorer


def test_silent_input_reports_neg_inf_without_warning():
    restorer = AudioRestorer()
    silent = np.zeros(44100)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        _, info = restorer.restore(silent, 44100)
    metrics = info["quality_metrics"]
    assert metrics["dynamic_range_original"] == float("-inf")
    assert metrics["dynamic_range_restored"] == float("-inf")


def test_empty_input_returns_empty_metrics():
    restorer = AudioRestorer()
    out, info = restorer.restore(np.array([]), 44100)
    assert out.size == 0
    assert info["quality_metrics"] == {}


def test_normal_input_metrics_finite():
    restorer = AudioRestorer()
    t = np.linspace(0, 0.5, 22050)
    audio = np.sin(2 * np.pi * 440 * t) * 0.5
    _, info = restorer.restore(audio, 44100)
    metrics = info["quality_metrics"]
    assert np.isfinite(metrics["dynamic_range_original"])
    assert np.isfinite(metrics["dynamic_range_restored"])
