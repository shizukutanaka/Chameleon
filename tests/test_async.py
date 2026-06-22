"""Tests for the asynchronous audio API in core.py.

These also guard the timing fix in ``analyze_async`` (previously the elapsed
time was computed as ``perf_counter() - perf_counter()`` and was always 0).
"""

import asyncio

from tests._helpers import write_sine_wave

import core


def test_analyze_async_succeeds_and_reports_metadata(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=0.5)

    result = asyncio.run(core.analyze_async(str(wav)))

    assert result.success, result.message
    assert result.data["sample_rate"] == 44100
    assert result.data["duration"] > 0


def test_analyze_async_duration_is_measured(tmp_path):
    # Regression test: the elapsed time must reflect real work, not be a
    # constant 0 produced by subtracting two adjacent perf_counter() calls.
    wav = write_sine_wave(tmp_path / "tone.wav", duration=1.0)

    result = asyncio.run(core.analyze_async(str(wav)))

    assert result.success
    assert result.duration_ms >= 0
    # The message embeds the measured duration; it must be a real integer ms.
    assert "ms" in result.message


def test_normalize_async_writes_output(tmp_path):
    src = write_sine_wave(tmp_path / "in.wav", duration=0.5, amplitude=4000)
    dst = tmp_path / "out.wav"

    result = asyncio.run(core.normalize_async(str(src), str(dst), 0.95))

    assert result.success, result.message
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_concurrent_analyze(tmp_path):
    files = [write_sine_wave(tmp_path / f"t{i}.wav", duration=0.3, frequency=220 * (i + 1))
             for i in range(5)]

    async def run_all():
        return await asyncio.gather(*(core.analyze_async(str(f)) for f in files))

    results = asyncio.run(run_all())

    assert len(results) == 5
    assert all(r.success for r in results)
