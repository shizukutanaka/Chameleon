"""`save_audio`'s stdlib fallback must not mislabel its output.

soundfile picks the container from the destination suffix. When sf.write
fails on a non-WAV suffix (`output_path="out.mp3"`, `out.flac` on a
partial build, ...) the code used to fall back to `_save_wav_basic` and
write RIFF/WAV bytes under the foreign name -- a file that is not what
it claims to be. The fallback is now restricted to WAV destinations.
"""

import wave

import pytest

import main
from tests._helpers import write_sine_wave


def test_save_audio_refuses_foreign_suffix(tmp_path):
    np = pytest.importorskip("numpy")
    audio = np.zeros(8000, dtype=np.float32)
    dest = tmp_path / "out.mp3"

    with pytest.raises(ValueError, match="Cannot write WAV data"):
        main.AudioProcessor().save_audio(audio, str(dest), 8000)

    assert not dest.exists()


def test_explicit_output_path_with_foreign_suffix_fails(tmp_path):
    """The programmatic entry (`output_path=` kwarg) must not produce a
    WAV-under-.mp3 either."""
    np = pytest.importorskip("numpy")
    src = write_sine_wave(tmp_path / "in.wav", duration=0.05)
    dest = tmp_path / "out.mp3"

    with pytest.raises(ValueError, match="Cannot write WAV data"):
        main.AudioProcessor()._process_single_file(
            str(src), "normalize", output_path=str(dest))

    assert not dest.exists()


def test_save_audio_extensionless_destination_writes_wav(tmp_path):
    """An extensionless output is an honest WAV (magic bytes say what it
    is); only a wrong extension is a lie."""
    np = pytest.importorskip("numpy")
    audio = np.zeros(8000, dtype=np.float32)
    dest = tmp_path / "out"

    main.AudioProcessor().save_audio(audio, str(dest), 8000)

    with wave.open(str(dest), "rb") as w:
        assert w.getframerate() == 8000
