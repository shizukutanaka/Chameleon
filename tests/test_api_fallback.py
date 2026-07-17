"""Tests for the api_server fallback adapters.

When the optional high-performance modules are absent, api_server wires
``analyze_audio_fast`` / ``normalize_audio_fast`` to the standard-library core.
These tests verify the ProcessingResult -> dict adaptation. They require
fastapi/pydantic (imported at api_server module load) and are skipped otherwise.
"""

import asyncio

import pytest

from tests._helpers import write_sine_wave

pytest.importorskip("fastapi")

import api_server  # noqa: E402


def test_fallback_mode_defines_adapters():
    # In an environment without the secure modules the adapters must exist.
    assert hasattr(api_server, "analyze_audio_fast")
    assert hasattr(api_server, "normalize_audio_fast")


@pytest.mark.skipif(api_server.HAS_SECURE_MODULES,
                    reason="secure modules present; fallback adapters not active")
def test_analyze_audio_fast_returns_metadata(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5)

    result = asyncio.run(api_server.analyze_audio_fast(str(wav)))

    assert result["success"] is True
    assert result["sample_rate"] == 44100
    assert result["duration"] > 0
    assert result["processing_method"] == "stdlib-core"
    assert result["file_size"] > 0


@pytest.mark.skipif(api_server.HAS_SECURE_MODULES,
                    reason="secure modules present; fallback adapters not active")
def test_normalize_audio_fast_writes_and_reports(tmp_path):
    src = write_sine_wave(tmp_path / "in.wav", duration=0.5, amplitude=4000)
    dst = tmp_path / "out.wav"

    result = asyncio.run(api_server.normalize_audio_fast(str(src), str(dst), 0.95))

    assert result["success"] is True
    assert result["target_peak"] == 0.95
    assert result["scale_factor"] is not None
    assert dst.exists()


@pytest.mark.skipif(api_server.HAS_SECURE_MODULES,
                    reason="secure modules present; fallback adapters not active")
def test_analyze_audio_fast_reports_error_for_missing_file(tmp_path):
    result = asyncio.run(api_server.analyze_audio_fast(str(tmp_path / "nope.wav")))

    assert result["success"] is False
    assert "error" in result
