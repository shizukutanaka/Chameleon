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


def test_midi_varint_encodes_deltas_over_127_ticks(tmp_path):
    # _write_variable_length used to emit groups LSB-first with the
    # continuation bit on the wrong byte -- any delta >= 128 ticks (a note
    # longer than ~0.27 s) produced unparseable MIDI. A whole file written
    # that way is "generated" only in name.
    analyzer = MIDIAnalyzer()
    out = tmp_path / "n.mid"
    note = MIDINote(pitch=69, velocity=100, start_time=0.0, duration=1.0,
                    channel=0)
    assert analyzer.generate_midi_file([note], str(out)) is True

    data = out.read_bytes()
    track = data[data.find(b"MTrk") + 8:]
    # strict sequential parse: delta varint, then event
    i = 0
    deltas = []
    events = []
    while i < len(track):
        delta = 0
        while True:
            b = track[i]
            i += 1
            delta = (delta << 7) | (b & 0x7F)
            if not b & 0x80:
                break
        status = track[i]
        i += 1
        if status == 0xFF:
            # meta event: FF <type> <len> <len bytes of data>
            i += 2 + track[i + 1]
            continue
        if status == 0x90:
            i += 2
            events.append("on")
        elif status == 0x80:
            i += 2
            events.append("off")
        deltas.append(delta)

    assert "on" in events and "off" in events
    # 1.0 s at 120 BPM / 480 tpq is 960 ticks -> the off delta must be >=128
    assert any(d >= 128 for d in deltas)
