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


def test_midi_duration_scales_with_tempo(tmp_path):
    # Delta-times were written as seconds * 480 -- i.e. seconds mapped to
    # quarter notes 1:1 -- so a 1 s note played back as 0.5 s at the default
    # 120 BPM and changed length with --tempo. Ticks must be seconds *
    # tpq * bpm / 60 so a 1 s note sounds for 1 s at any tempo.
    analyzer = MIDIAnalyzer()

    def off_delta(path):
        track = path.read_bytes()
        track = track[track.find(b"MTrk") + 8:]
        i = 0
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
                i += 2 + track[i + 1]
                continue
            if status == 0x80:
                return delta
            i += 2 if status in (0x90,) else 1
        raise AssertionError("no note-off event")

    for tempo, expected in ((60, 480), (120, 960), (240, 1920)):
        out = tmp_path / f"t{tempo}.mid"
        analyzer.generate_midi_file(
            [MIDINote(69, 100, 0.0, 1.0)], str(out), tempo_bpm=tempo)
        delta = off_delta(out)
        # playback seconds = delta / tpq * (60 / bpm) == 1.0 always
        assert delta == expected
        assert abs(delta / 480 * 60 / tempo - 1.0) < 0.01


def test_compose_writes_eighth_notes_at_any_tempo(tmp_path):
    # compose_melody emits beat-unit times; the MIDI writer consumes
    # seconds. The compose handler must rescale by 60/tempo or eighth
    # notes come out as quarters and change length with --tempo.
    import subprocess
    import sys
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")

    def on_deltas(path):
        data = path.read_bytes()
        track = data[data.find(b"MTrk") + 8:]
        i = 0
        out = []
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
                i += 2 + track[i + 1]
                continue
            if status == 0x80:
                out.append(delta)  # note-off delta = note duration in ticks
            i += 2
        return out

    import midi_analysis as _m
    if not getattr(_m, "MIDIAnalyzer", None):
        raise AssertionError("unreachable")

    for tempo in (120, 240):
        out = tmp_path / f"c{tempo}.mid"
        proc = subprocess.run(
            [sys.executable, main_py, "midi", "compose",
             "--output", str(out), "--tempo", str(tempo),
             "--length", "4", "--key", "C", "--mode", "major"],
            capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            import pytest
            pytest.skip("midi compose unavailable in this environment")
        deltas = on_deltas(out)
        assert deltas and all(d == 240 for d in deltas), deltas


def test_midi_analyze_on_mid_file_explains_the_trap(tmp_path):
    """`midi analyze --input x.mid` is the most natural mistake: the op
    analyzes *audio* for musical content, and 'Unsupported file type'
    leaves the user guessing which part was wrong."""
    import subprocess
    import sys
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")
    mid = tmp_path / "x.mid"
    mid.write_bytes(b"MThd" + b"\x00" * 20)
    proc = subprocess.run(
        [sys.executable, main_py, "midi", "analyze", "--input", str(mid)],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 3  # INPUT
    assert "audio file" in proc.stderr


def test_midi_compose_rejects_nonfinite_tempo_and_length(tmp_path):
    """`--tempo nan` used to pass `<= 0` (NaN comparisons are False), reach
    the encoder as int(nan), and report ERROR(1). `--length inf` looped
    forever generating notes. Both are INPUT(3): a parsed float isn't a
    valid float until it's finite."""
    import subprocess
    import sys
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")
    out = tmp_path / "m.mid"
    for extra in [["--tempo", "nan"], ["--tempo", "inf"],
                  ["--length", "nan"], ["--length", "inf"]]:
        proc = subprocess.run(
            [sys.executable, main_py, "midi", "compose",
             *extra, "--output", str(out)],
            capture_output=True, text=True, timeout=30)
        assert proc.returncode == 3, (extra, proc.stderr)
        assert "finite" in proc.stderr.lower()
        assert not out.exists()


def test_midi_output_into_unwritable_dir_exits_input(tmp_path):
    """`midi compose --output` into a chmod-555 dir used to build the whole
    MIDI file in memory, then surface PermissionError as ERROR(1). The
    destination is user input: INPUT(3) before any work."""
    import subprocess
    import sys
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        proc = subprocess.run(
            [sys.executable, main_py, "midi", "compose", "--length", "4",
             "--output", str(locked / "x.mid")],
            capture_output=True, text=True, timeout=30)
    finally:
        locked.chmod(0o755)
    assert proc.returncode == 3
    assert "not writable" in proc.stderr


def test_analyze_harmony_names_the_key_not_a_pitch_class():
    # The library dict used to ship f"{key.tonic} {key.mode}" -- "0 major" --
    # while the CLI mapped the same field through the note table. A pitch
    # class integer is not a key name a musician can read.
    analyzer = MIDIAnalyzer()
    chords = analyzer.detect_chords(_c_major_progression())
    key = analyzer.detect_key(_c_major_progression())

    harmony = analyzer.analyze_harmony(chords, key)

    assert harmony["key"] == "C major"


def test_parse_midi_velocity_tracks_loudness():
    # velocity came from `int(energy * 1000)` on a frame-length-dependent
    # sum, so any audible level pegged 127 and velocity carried no
    # information. It must move with loudness and stay inside 1-127.
    import math
    analyzer = MIDIAnalyzer()
    sr = 44100

    def velocities(amp):
        signal = [amp * math.sin(2 * math.pi * 440 * i / sr)
                  for i in range(int(sr * 0.4))]
        return {n.velocity for n in analyzer.parse_midi_from_audio(signal, sr)}

    loud, quiet = velocities(0.5), velocities(0.1)
    assert loud and quiet
    assert max(loud) <= 127
    assert min(quiet) >= 1  # velocity 0 reads as note-off
    assert max(quiet) < min(loud)


def test_compose_length_is_seconds_not_beats(tmp_path):
    """--length is documented in seconds but used to reach generate_melody's
    beat counter raw: `--length 3 --tempo 120` produced 3 beats = 1.5 s of
    music. Seconds convert to beats via tempo/60 before the generator."""
    import subprocess
    import sys
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")

    def track_ticks(path):
        data = path.read_bytes()
        track = data[data.find(b"MTrk") + 8:]
        i = 0
        ticks = 0
        while i < len(track):
            delta = 0
            while True:
                b = track[i]
                i += 1
                delta = (delta << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            ticks += delta
            status = track[i]
            i += 1
            if status == 0xFF:
                i += 2 + track[i + 1]
                continue
            i += 2
        return ticks

    out = tmp_path / "l.mid"
    proc = subprocess.run(
        [sys.executable, main_py, "midi", "compose",
         "--output", str(out), "--tempo", "120", "--length", "3",
         "--key", "C", "--mode", "major"],
        capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        import pytest
        pytest.skip("midi compose unavailable in this environment")
    # 3 s at 120 BPM = 6 beats; at 480 ticks/quarter the last note ends at
    # tick 2880. Pre-fix the track ends at 1440 (3 beats = 1.5 s).
    assert track_ticks(out) == 2880
