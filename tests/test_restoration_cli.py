"""The restoration repairs, through the CLI.

`audio_restoration.py` shipped for its whole life with no entry point
reaching it -- 530 lines of real DSP that no user could invoke. Wiring it up
is not a matter of adding flags, though: an orphan module is unexamined, and
this one turned out to contain a declipper that damaged clean audio and a hum
detector that answered yes to a signal with no hum in it.

So only what has been measured ships. `--declip` and `--dehum` are exposed;
click removal, crackle removal, gap interpolation and the librosa denoiser are
not. Click removal in particular has no trustworthy detector -- the shipped
envelope/z-score one finds 354 clicks in a second of white noise, and a
second-difference/MAD alternative finds 1,764 in hard-clipped audio, one per
clipping corner.

The properties worth defending, in order:
  1. clean audio comes back unchanged;
  2. damaged audio comes back measurably closer to the truth;
  3. the repairs run in the order that actually helps, not the order the flags
     were typed.
"""

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_RATE = 44100


def _write_wav(path, samples):
    pcm = np.clip(np.round(samples * 32767), -32768, 32767).astype(np.int16)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())


def _read_wav(path):
    with wave.open(str(path)) as handle:
        raw = handle.readframes(handle.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768


def _tone(freq, amplitude=0.5, seconds=1.0):
    count = int(SAMPLE_RATE * seconds)
    return amplitude * np.sin(2 * np.pi * freq * np.arange(count) / SAMPLE_RATE)


def _rms_db(signal):
    return 20.0 * np.log10(np.sqrt(np.mean(signal ** 2)) + 1e-20)


def _level_db(signal, freq):
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freqs = np.fft.rfftfreq(len(signal), 1 / SAMPLE_RATE)
    return 20.0 * np.log10(spectrum[np.argmin(np.abs(freqs - freq))] / len(signal) + 1e-20)


def _run_cli(*args):
    return subprocess.run([sys.executable, "main.py", *args],
                          capture_output=True, text=True, cwd=str(REPO_ROOT))


@pytest.fixture
def damaged(tmp_path):
    """A tone recorded with mains hum in the chain, then hard-clipped.

    Damage order matters: the hum is present *before* the clipping, which is
    what makes the plateaus flat and the file repairable at all.
    """
    seconds = 2.0
    raw = _tone(220, 0.85, seconds) + _tone(60, 0.15, seconds)
    path = tmp_path / "damaged.wav"
    _write_wav(path, np.clip(raw, -0.75, 0.75))
    return path, _tone(220, 0.85, seconds)


# --- clean audio must survive ---------------------------------------------

def test_clean_audio_is_returned_within_a_single_lsb(tmp_path):
    source = tmp_path / "clean.wav"
    _write_wav(source, _tone(440))

    result = _run_cli("process", str(source), "--declip", "--dehum",
                      "--output-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr

    before = _read_wav(source)
    after = _read_wav(tmp_path / "clean_restored.wav")
    # The only permitted difference is the float32 round trip in the writer.
    assert np.abs(after - before).max() <= 2 / 32768


@pytest.mark.parametrize("freq", [55, 100, 440])
def test_a_musical_bass_note_is_not_mistaken_for_mains_hum(tmp_path, freq):
    # 55 Hz sits between the two power-line frequencies the dehummer looks for.
    source = tmp_path / f"bass{freq}.wav"
    _write_wav(source, _tone(freq, 0.5))

    result = _run_cli("process", str(source), "--dehum", "--output-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr

    before, after = _read_wav(source), _read_wav(tmp_path / f"bass{freq}_restored.wav")
    assert _level_db(after, freq) == pytest.approx(_level_db(before, freq), abs=0.5)


# --- damaged audio must improve -------------------------------------------

def test_repairs_move_damaged_audio_closer_to_the_truth(tmp_path, damaged):
    source, truth = damaged

    result = _run_cli("process", str(source), "--declip", "--dehum",
                      "--output-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr

    before = _rms_db(_read_wav(source) - truth)
    after = _rms_db(_read_wav(tmp_path / "damaged_restored.wav") - truth)
    assert after < before - 5.0, f"only improved {before - after:.1f} dB"


def test_hum_is_removed_and_the_music_is_kept(tmp_path, damaged):
    source, _ = damaged

    _run_cli("process", str(source), "--dehum", "--output-dir", str(tmp_path))

    before, after = _read_wav(source), _read_wav(tmp_path / "damaged_restored.wav")
    assert _level_db(before, 60) - _level_db(after, 60) > 20.0
    assert abs(_level_db(after, 220) - _level_db(before, 220)) < 1.0


def test_declipping_raises_the_peak_back_above_the_clip_level(tmp_path, damaged):
    source, _ = damaged

    _run_cli("process", str(source), "--declip", "--output-dir", str(tmp_path))

    before, after = _read_wav(source), _read_wav(tmp_path / "damaged_restored.wav")
    assert np.abs(after).max() > np.abs(before).max() + 0.05


# --- ordering -------------------------------------------------------------

def test_flag_order_does_not_change_the_result(tmp_path, damaged):
    # Clipping is undone before hum, whichever way round the flags are typed:
    # dehumming first ripples the plateaus enough that declipping then finds
    # none of them.
    source, _ = damaged
    one, two = tmp_path / "a", tmp_path / "b"
    one.mkdir()
    two.mkdir()

    _run_cli("process", str(source), "--declip", "--dehum", "--output-dir", str(one))
    _run_cli("process", str(source), "--dehum", "--declip", "--output-dir", str(two))

    assert np.array_equal(_read_wav(one / "damaged_restored.wav"),
                          _read_wav(two / "damaged_restored.wav"))


def test_the_canonical_order_is_the_one_that_measures_better(tmp_path, damaged):
    import audio_restoration
    import main

    source, truth = damaged
    audio = _read_wav(source)

    declipper = audio_restoration.DeclippingProcessor()
    dehummer = audio_restoration.HumRemover()

    declip_first = dehummer.remove_hum(
        declipper.restore_clipped(audio.copy(), SAMPLE_RATE), SAMPLE_RATE)
    dehum_first = declipper.restore_clipped(
        dehummer.remove_hum(audio.copy(), SAMPLE_RATE), SAMPLE_RATE)

    assert _rms_db(declip_first - truth) < _rms_db(dehum_first - truth) - 3.0
    assert main.AudioProcessor.RESTORATION_REPAIRS == ("declip", "dehum")


# --- scope ----------------------------------------------------------------

def test_only_the_verified_repairs_are_exposed():
    help_text = _run_cli("process", "--help").stdout

    assert "--declip" in help_text
    assert "--dehum" in help_text
    # Not shipped: no trustworthy detector. See the module docstring.
    assert "--declick" not in help_text
    assert "--decrackle" not in help_text


def test_an_unknown_repair_is_rejected():
    import main
    processor = main.AudioProcessor(main.ProcessingConfig())

    with pytest.raises(ValueError, match="Unknown repair"):
        processor.repair_audio(_tone(440), SAMPLE_RATE, ["destroy"])


def test_stereo_files_are_repaired_channel_by_channel(tmp_path):
    import main
    processor = main.AudioProcessor(main.ProcessingConfig())
    stereo = np.stack([_tone(440), _tone(660, 0.3)])

    repaired = processor.repair_audio(stereo, SAMPLE_RATE, ["declip", "dehum"])

    assert repaired.shape == stereo.shape
    assert np.abs(repaired - stereo).max() < 1e-9   # nothing wrong with it
