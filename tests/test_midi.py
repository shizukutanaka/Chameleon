"""Tests for MIDI musical analysis (chord and key detection)."""

from midi_analysis import MIDIAnalyzer, MIDINote


def _c_major_progression():
    # C major triad held, then a stepwise C-major scale fragment.
    return [
        MIDINote(60, 100, 0.0, 2.0),
        MIDINote(64, 100, 0.0, 2.0),
        MIDINote(67, 100, 0.0, 2.0),
        MIDINote(60, 100, 2.0, 1.0),
        MIDINote(62, 100, 3.0, 1.0),
        MIDINote(64, 100, 4.0, 1.0),
        MIDINote(65, 100, 5.0, 1.0),
        MIDINote(67, 100, 6.0, 1.0),
    ]


def test_detect_chords_finds_c_major():
    analyzer = MIDIAnalyzer()

    chords = analyzer.detect_chords(_c_major_progression())

    assert chords, "expected at least one detected chord"
    assert any(chord.name == "Cmajor" for chord in chords), [c.name for c in chords]


def test_detect_key_identifies_c_major():
    analyzer = MIDIAnalyzer()

    key = analyzer.detect_key(_c_major_progression())

    assert key.tonic == 0          # C
    assert key.mode == "major"
    assert key.confidence > 0.5


def test_note_name_and_frequency():
    note = MIDINote(69, 100, 0.0, 1.0)  # A4

    assert note.note_name == "A4"
    assert abs(note.frequency - 440.0) < 1e-6
