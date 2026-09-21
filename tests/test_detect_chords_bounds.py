"""detect_chords edge inputs: empty notes and non-positive window_size.

analyze_rhythm/detect_key/analyze_harmony all handle an empty note list;
detect_chords crashed in max() on the same input. And window_size<=0 made
the sliding-window loop never advance -- the same non-progressing-loop
class as `compose --length`.
"""
import subprocess
import sys

import pytest

from midi_analysis import MIDIAnalyzer, MIDINote


def test_detect_chords_empty_notes_returns_empty():
    assert MIDIAnalyzer().detect_chords([]) == []


def test_detect_chords_rejects_nonpositive_window():
    """window_size=0 must raise immediately, not loop forever. At HEAD the
    call hangs, so run it in a subprocess with a timeout: the fix turns the
    hang into a fast ValueError exit."""
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from midi_analysis import MIDIAnalyzer, MIDINote;"
        "a = MIDIAnalyzer();"
        "n = MIDINote(pitch=60, velocity=80, start_time=0.0, duration=1.0, channel=0);"
        "a.detect_chords([n], window_size=0.0)"
    )
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode != 0
    assert "ValueError" in proc.stderr


def test_detect_chords_normal_case_still_works():
    a = MIDIAnalyzer()
    notes = [
        MIDINote(pitch=60, velocity=80, start_time=0.0, duration=1.0, channel=0),
        MIDINote(pitch=64, velocity=80, start_time=0.0, duration=1.0, channel=0),
        MIDINote(pitch=67, velocity=80, start_time=0.0, duration=1.0, channel=0),
    ]
    chords = a.detect_chords(notes)
    assert isinstance(chords, list)
