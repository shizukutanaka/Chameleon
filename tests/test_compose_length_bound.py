"""`midi compose --length` is bounded by the chord progression's span.

generate_melody emits a note only when a chord covers current_time, so
every iteration past the last chord's end produced nothing -- and a
huge --length (e.g. 1e9) looped effectively forever. The loop now stops
at min(length, chord coverage end), and the CLI says so when the
requested length exceeds the built-in progression's span.
"""

import os
import subprocess
import sys

import pytest


def test_generate_melody_terminates_beyond_chord_span(tmp_path):
    """A 2-billion-beat request must return, not spin forever."""
    code = (
        "from midi_analysis import MIDIComposer, Chord, MusicalKey\n"
        "chords = [Chord(root=0, chord_type='major', notes=[0, 4, 7],"
        "                start_time=0.0, duration=2.0)]\n"
        "key = MusicalKey(tonic=0, mode='major', confidence=1.0)\n"
        "melody = MIDIComposer().generate_melody(chords, key, 2e9)\n"
        "assert len(melody) == 4, len(melody)\n"
        "print('OK')\n"
    )
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env=env, timeout=30,
    )
    assert proc.returncode == 0 and "OK" in proc.stdout, proc.stderr


def test_compose_warns_when_length_exceeds_progression(tmp_path):
    out = tmp_path / "c.mid"
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
    proc = subprocess.run(
        [sys.executable, "-m", "main", "midi", "compose",
         "--key", "C", "--length", "60", "--output", str(out)],
        capture_output=True, text=True, env=env, timeout=60,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert proc.returncode == 0, proc.stderr
    assert "exceeds the built-in" in proc.stderr
