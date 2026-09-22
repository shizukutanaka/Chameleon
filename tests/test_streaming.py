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


# _process_stream_buffer factors the callback's DSP path out of PyAudio, so
# the claims above about "cannot be unit-tested" no longer apply to it.


def test_process_stream_buffer_deinterleaves_before_effects():
    """A stereo callback buffer must be processed per channel, not as mono.

    PyAudio delivers interleaved samples. Filtering that flat array makes
    each biquad tap the other channel's samples as its own history: a silent
    right channel previously came back at 0.28 amplitude from a 12 dB EQ
    band on the left channel's tone.
    """
    np = pytest.importorskip("numpy")
    if not main.HAS_SCIPY:
        pytest.skip("EQ effect requires scipy")

    processor = main.AudioProcessor(
        main.ProcessingConfig(channels=2, normalize=False)
    )
    sr, n = 44100, 2048
    t = np.arange(n) / sr
    left = 0.5 * np.sin(2.0 * np.pi * 1000.0 * t).astype(np.float32)
    interleaved = np.empty(2 * n, dtype=np.float32)
    interleaved[0::2] = left
    interleaved[1::2] = 0.0

    out = np.frombuffer(
        processor._process_stream_buffer(
            interleaved.tobytes(),
            {"eq": [{"frequency": 1000.0, "gain": 12.0, "q": 1.0}]},
        ),
        dtype=np.float32,
    )

    assert out.shape == interleaved.shape
    assert float(np.abs(out[1::2]).max()) < 1e-3  # silent channel stays silent
    assert float(np.abs(out[0::2]).max()) > 0.5   # the tone channel was EQ'd


def test_process_stream_buffer_mono_is_byte_identical_when_noop():
    """Mono config + no effects + no normalize returns the input bytes."""
    np = pytest.importorskip("numpy")
    processor = main.AudioProcessor(
        main.ProcessingConfig(channels=1, normalize=False)
    )
    audio = np.linspace(-0.5, 0.5, 512, dtype=np.float32)

    out = processor._process_stream_buffer(audio.tobytes(), None)

    assert out == audio.tobytes()
