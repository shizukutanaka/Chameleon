"""`analyze --detailed` must not print dataclass defaults as measurements.

Two fields on `AudioMetadata` were reported whether or not anything had
measured them.

`frequency_range` defaults to `(0.0, 0.0)` and is only ever populated inside
the `if HAS_LIBROSA:` branch. librosa is in no extra of this project, so on
essentially every install `analyze --detailed` printed

    Frequency Range: 0.0-0.0Hz

for a 440 Hz sine. Not an approximation, not a limitation -- a default, dressed
as a result. `analyze --spectrum` measures the same quantity for real, in pure
Python, on every install, and reports 419.9-452.2 Hz for that file.

`dynamic_range` was worse, because the fix was already sitting there. It is the
crest factor, `20*log10(peak/rms)`, and the standard-library core reports both
peak and RMS -- but only the numpy path did the division, so the dependency-free
install, the one this project leads with, printed `Dynamic Range: 0.0dB` for a
sine whose crest factor is 3.01 dB.
"""

import math
import subprocess
import sys
from pathlib import Path

import pytest

from tests._helpers import write_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")

# 20*log10(sqrt(2)) -- a sine's peak is sqrt(2) times its RMS, whatever its
# amplitude or frequency.
SINE_CREST_FACTOR_DB = 20 * math.log10(math.sqrt(2))


def _run(*args):
    return subprocess.run([sys.executable, MAIN_PY, *args],
                          capture_output=True, text=True)


def _field(output, label):
    for line in output.splitlines():
        if line.strip().startswith(label):
            return line.split(":", 1)[1].strip()
    return None


@pytest.fixture
def tone(tmp_path):
    return write_sine_wave(tmp_path / "tone.wav", duration=1.0)


def test_dynamic_range_is_the_real_crest_factor(tone):
    result = _run("analyze", str(tone), "--detailed")
    assert result.returncode == 0, result.stderr

    reported = float(_field(result.stdout, "Dynamic Range").rstrip("dB"))
    assert reported == pytest.approx(SINE_CREST_FACTOR_DB, abs=0.2), (
        f"a sine's crest factor is {SINE_CREST_FACTOR_DB:.2f} dB, reported {reported}")


def test_dynamic_range_is_never_reported_as_zero_for_a_tone(tone):
    # The exact symptom: the dataclass default surviving to the output.
    result = _run("analyze", str(tone), "--detailed")

    assert _field(result.stdout, "Dynamic Range") != "0.0dB"


def test_an_unmeasured_frequency_range_says_so(tone):
    result = _run("analyze", str(tone), "--detailed")
    assert result.returncode == 0, result.stderr

    reported = _field(result.stdout, "Frequency Range")
    assert reported is not None
    assert reported != "0.0-0.0Hz", "a default was printed as a measurement"
    if "not measured" not in reported:
        # librosa is installed and really measured it; then it must be a real
        # band containing the tone.
        low, high = (float(v) for v in reported.rstrip("Hz").split("-"))
        assert low < 440.0 < high


def test_spectrum_measures_what_detailed_could_not(tone):
    result = _run("analyze", str(tone), "--spectrum")
    assert result.returncode == 0, result.stderr

    low, high = (float(v) for v in
                 _field(result.stdout, "Spectrum Bandwidth").rstrip("Hz").split("-"))
    assert low < 440.0 < high


def test_detailed_does_not_advertise_spectrum_when_spectrum_is_already_running(tone):
    # Suggesting a flag the user just used would be noise.
    result = _run("analyze", str(tone), "--detailed", "--spectrum")

    assert "use --spectrum" not in result.stdout
    assert "Spectrum Bandwidth" in result.stdout


def test_silence_does_not_produce_a_nonsense_crest_factor(tmp_path):
    import struct
    import wave

    silent = tmp_path / "silence.wav"
    with wave.open(str(silent), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(struct.pack("<h", 0) * 44100)

    result = _run("analyze", str(silent), "--detailed")

    assert result.returncode == 0, result.stderr
    # log(0/0) has no answer; 0.0 dB is the honest placeholder for "no signal",
    # and it must not be an inf, a nan, or a crash.
    assert _field(result.stdout, "Dynamic Range") == "0.0dB"
