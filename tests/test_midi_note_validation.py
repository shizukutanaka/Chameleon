"""generate_midi_file must reject unrepresentable notes instead of
writing them.

Every note field lands in a byte-sized event slot. Before the check:
- pitch/velocity outside 0..127 crashed `bytearray.extend` mid-write
  (cryptic ValueError, whole output lost),
- a negative duration put note_off before note_on and the delta-time
  clamp then encoded that order -- a file that parses but plays
  corrupted,
- tempo <= 0 / NaN divided or overflowed in the meta event.

The writer now validates and returns False; extraction additionally
skips pitches MIDI cannot encode (>127) instead of dying at write time.
"""

import pytest

import midi_analysis
from midi_analysis import MIDINote, MIDIAnalyzer


def _good_note():
    return MIDINote(pitch=69, velocity=80, start_time=0.0, duration=0.5)


def test_rejects_out_of_range_pitch_and_velocity(tmp_path):
    out = tmp_path / "x.mid"
    assert MIDIAnalyzer().generate_midi_file([MIDINote(200, 80, 0.0, 0.5)], str(out)) is False
    assert MIDIAnalyzer().generate_midi_file([MIDINote(69, 128, 0.0, 0.5)], str(out)) is False
    assert MIDIAnalyzer().generate_midi_file([MIDINote(-1, 80, 0.0, 0.5)], str(out)) is False
    assert not out.exists()


def test_rejects_negative_duration_and_start(tmp_path):
    out = tmp_path / "x.mid"
    assert MIDIAnalyzer().generate_midi_file([MIDINote(69, 80, 0.0, -0.1)], str(out)) is False
    assert MIDIAnalyzer().generate_midi_file([MIDINote(69, 80, -1.0, 0.5)], str(out)) is False
    assert MIDIAnalyzer().generate_midi_file([MIDINote(69, 80, 0.0, 0.0)], str(out)) is False
    assert not out.exists()


def test_rejects_bad_tempo(tmp_path):
    out = tmp_path / "x.mid"
    assert MIDIAnalyzer().generate_midi_file([_good_note()], str(out), tempo_bpm=0.0) is False
    assert MIDIAnalyzer().generate_midi_file([_good_note()], str(out), tempo_bpm=float("nan")) is False
    assert not out.exists()


def test_extract_skips_unrepresentable_pitch(monkeypatch):
    # 8 kHz is a real pitch estimate but past MIDI 127 (G9 = 12544 Hz
    # lands at pitch 127*); force the estimator to return it.
    analyzer = MIDIAnalyzer()
    monkeypatch.setattr(analyzer, "_estimate_pitch", lambda *a, **k: 20000.0)
    audio = [0.5] * 48000  # one second of constant energy above threshold
    notes = analyzer.parse_midi_from_audio(audio, 44100)
    assert notes == []


def test_valid_notes_still_write(tmp_path):
    out = tmp_path / "ok.mid"
    assert MIDIAnalyzer().generate_midi_file([_good_note()], str(out)) is True
    assert out.read_bytes().startswith(b"MThd")
