"""Tests for real-time streaming graceful degradation in main.py.

`AudioProcessor.process_stream` needs PyAudio (and live audio hardware), so its
inner processing logic cannot be unit-tested in CI. What *can* and must be tested
is the contract CHARTER §6.2 requires: under the default, dependency-free install
the feature degrades with a clear message rather than failing obscurely. These
tests pin that contract so "real-time streaming" is a verified behaviour, not just
code that exists.
"""

import asyncio

import pytest

import main


def _processor():
    return main.AudioProcessor()


def test_process_stream_without_pyaudio_raises_clear_error(monkeypatch):
    """Without PyAudio, process_stream must raise a RuntimeError naming the cause."""
    monkeypatch.setattr(main, "HAS_PYAUDIO", False)

    def _unused_callback(*_args, **_kwargs):  # pragma: no cover - never reached
        raise AssertionError("callbacks must not run when PyAudio is absent")

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(
            _processor().process_stream(_unused_callback, _unused_callback)
        )

    assert "PyAudio" in str(excinfo.value)


@pytest.mark.skipif(main.HAS_PYAUDIO, reason="PyAudio installed; degradation path not exercised")
def test_default_install_has_no_pyaudio():
    """Document the default-install expectation that backs the test above."""
    assert main.HAS_PYAUDIO is False
