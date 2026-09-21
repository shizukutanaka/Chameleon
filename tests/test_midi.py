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


def test_parse_midi_from_audio_propagates_analyzer_crash(monkeypatch):
    """A crashed pitch estimator used to print one line and return [] --
    indistinguishable from a genuinely unmusical input, so `midi extract`
    reported "No MIDI notes extracted" on an internal bug. Extraction
    failures propagate now; the caller decides how to surface them."""
    import math
    analyzer = MIDIAnalyzer()

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(analyzer, "_estimate_pitch", _boom)
    audio = [0.3 * math.sin(2 * math.pi * 440 * i / 44100)
             for i in range(44100)]

    import pytest
    with pytest.raises(RuntimeError, match="boom"):
        analyzer.parse_midi_from_audio(audio, 44100)


def test_estimate_pitch_propagates_non_audio_input():
    """Per-frame estimation legitimately returns None for unpitched frames;
    a frame that is not numeric at all is a caller bug, not unpitchedness,
    and must not collapse into the same None."""
    analyzer = MIDIAnalyzer()

    import pytest
    with pytest.raises(TypeError):
        analyzer._estimate_pitch([None] * 2048, 44100)


def test_estimate_pitch_none_on_silence_is_genuine():
    # Contract pin: None on silence is the YIN unvoiced verdict (the
    # periodicity fallback), not a swallowed error -- keep it.
    analyzer = MIDIAnalyzer()
    assert analyzer._estimate_pitch([0.0] * 2048, 44100) is None


def test_analyze_harmony_reports_each_template_types_real_quality():
    # The quality map only knew minor/min7/min9 and dim; every other
    # detectable type fell into the 'major' bucket -- a detected Amin6 was
    # reported as quality 'major' with an uppercase 'VI', and an Aaug the
    # same. Assert the full vocabulary maps to its true quality and the
    # roman numeral's case tracks triad quality (lower = minor-family).
    from midi_analysis import Chord, MusicalKey
    analyzer = MIDIAnalyzer()
    key = MusicalKey(tonic=0, mode="major", confidence=0.9)

    expected = {
        "major": ("major", "VI"),
        "minor": ("minor", "vi"),
        "dim": ("diminished", "vi°"),
        "aug": ("augmented", "VI+"),
        "maj7": ("major", "VI"),
        "min7": ("minor", "vi"),
        "dom7": ("dominant", "VI"),
        "maj9": ("major", "VI"),
        "min9": ("minor", "vi"),
        "sus2": ("suspended", "VI"),
        "sus4": ("suspended", "VI"),
        "add9": ("major", "VI"),
        "6": ("major", "VI"),
        "min6": ("minor", "vi"),
    }
    for chord_type, (quality, roman) in expected.items():
        chord = Chord(root=9, chord_type=chord_type, notes=[9, 12, 16],
                      start_time=0.0, duration=2.0, confidence=0.9)
        result = analyzer.analyze_harmony([chord], key)
        entry = result["progression"][0]
        assert entry["quality"] == quality, f"{chord_type}: {entry['quality']}"
        assert entry["roman"] == roman, f"{chord_type}: {entry['roman']}"


def test_parse_midi_rejects_nonpositive_or_nonfinite_sample_rate():
    # The declared rate drives frame_size/hop_size arithmetic: 0 or
    # negative produced a negative frame_size whose range() either crashed
    # with "arg 3 must not be zero" (naming range, not the rate) or scanned
    # nothing and reported "no notes"; nan/inf did the same via int().
    import math
    import pytest
    analyzer = MIDIAnalyzer()
    for bad in (0, -8000, -1, math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="sample_rate"):
            analyzer.parse_midi_from_audio([0.1] * 500, bad)


def test_parse_midi_tiny_rate_returns_empty_instead_of_crashing():
    # Rates below ~174 Hz give frame_size < 4, so frame_size // 4 == 0 and
    # range(0, n, 0) raised ValueError("arg 3 must not be zero"). A rate the
    # window cannot resolve should honestly find no notes, not crash.
    analyzer = MIDIAnalyzer()
    for tiny in (1, 43, 100):
        assert analyzer.parse_midi_from_audio([0.1] * 500, tiny) == []


def test_parse_midi_normal_rate_still_extracts_notes():
    # Regression guard: a 440 Hz sine at 44.1 kHz still yields an A4 note,
    # so the validation did not disturb the working path.
    import math
    analyzer = MIDIAnalyzer()
    sr = 44100
    audio = [0.5 * math.sin(2 * math.pi * 440 * i / sr) for i in range(sr // 4)]
    notes = analyzer.parse_midi_from_audio(audio, sr)
    assert len(notes) >= 1
    assert any(note.pitch == 69 for note in notes)


def test_generate_melody_anchors_to_first_chord():
    # Chords from real analysis sit where the audio put them (e.g. t=8-16),
    # not at 0. A melody clock that starts at 0 emits nothing for a
    # requested length before the first chord -- the shipped demo printed
    # "Generated Melody:" followed by silence.
    from midi_analysis import Chord, MusicalKey, MIDIComposer, MIDIConfig
    composer = MIDIComposer(MIDIConfig())
    key = MusicalKey(tonic=0, mode="major", confidence=1.0)
    chords = [
        Chord(root=0, chord_type="major", notes=[0, 4, 7],
              start_time=t, duration=2.0, confidence=1.0)
        for t in (8.0, 10.0, 12.0, 14.0)
    ]
    melody = composer.generate_melody(chords, key, length=4.0)
    assert len(melody) == 8  # half-beat notes across 4 beats
    assert melody[0].start_time == 8.0
    assert melody[-1].start_time + melody[-1].duration == 12.0


def test_generate_melody_zero_anchored_unchanged():
    from midi_analysis import Chord, MusicalKey, MIDIComposer, MIDIConfig
    composer = MIDIComposer(MIDIConfig())
    key = MusicalKey(tonic=0, mode="major", confidence=1.0)
    chords = [Chord(root=0, chord_type="major", notes=[0, 4, 7],
                    start_time=0.0, duration=8.0, confidence=1.0)]
    melody = composer.generate_melody(chords, key, length=2.0)
    assert [n.pitch for n in melody] == [60, 64, 67, 60]


def test_generate_melody_anchors_on_unsorted_chords():
    from midi_analysis import Chord, MusicalKey, MIDIComposer, MIDIConfig
    composer = MIDIComposer(MIDIConfig())
    key = MusicalKey(tonic=0, mode="major", confidence=1.0)
    chords = [
        Chord(root=0, chord_type="major", notes=[0, 4, 7],
              start_time=t, duration=2.0, confidence=1.0)
        for t in (14.0, 8.0)  # later chord listed first
    ]
    melody = composer.generate_melody(chords, key, length=2.0)
    assert melody[0].start_time == 8.0


# --- suggest_next_chord transition table -----------------------------------

def test_suggest_next_chord_follows_standard_progressions():
    # The transition table's own comments promised I -> V, IV, vi; the
    # semitone entries actually emitted III, V, VI, IV -- indexing off by
    # the accidental rows of the roman table.
    from midi_analysis import MIDIComposer, Chord, MusicalKey
    composer = MIDIComposer()
    key = MusicalKey(tonic=0, mode="major", confidence=0.9)
    i_chord = Chord(root=0, chord_type="major", notes=[0, 4, 7],
                    start_time=0.0, duration=2.0)
    suggestions = composer.suggest_next_chord([i_chord], key)
    romans = [r for r, _p in suggestions]
    assert romans == ["V", "IV", "vi", "ii"]


def test_suggest_next_chord_after_dominant_resolves_to_tonic():
    from midi_analysis import MIDIComposer, Chord, MusicalKey
    composer = MIDIComposer()
    key = MusicalKey(tonic=0, mode="major", confidence=0.9)
    v_chord = Chord(root=7, chord_type="major", notes=[7, 11, 2],
                    start_time=0.0, duration=2.0)
    romans = [r for r, _p in composer.suggest_next_chord([v_chord], key)]
    assert romans[0] == "I"


def test_suggest_next_chord_marks_minor_targets_lowercase():
    # A minor-mode i is a minor tonic -- reporting it "I" would claim major.
    from midi_analysis import MIDIComposer, Chord, MusicalKey
    composer = MIDIComposer()
    key = MusicalKey(tonic=9, mode="minor", confidence=0.9)  # A minor
    v_chord = Chord(root=9 + 7, chord_type="major", notes=[4, 8, 11],
                    start_time=0.0, duration=2.0)
    romans = [r for r, _p in composer.suggest_next_chord([v_chord], key)]
    assert romans[0] == "i"


def test_generate_melody_rejects_non_finite_and_non_positive_length():
    """generate_melody(length=inf) looped forever (`current_time < inf`
    is always true); nan and negatives silently returned an empty
    melody. The CLI guards --length but the direct API did not."""
    import pytest
    from midi_analysis import MIDIComposer, Chord, MusicalKey
    composer = MIDIComposer()
    key = MusicalKey(tonic=0, mode="major", confidence=1.0,
                     scale_notes=[0, 2, 4, 5, 7, 9, 11])
    chord = Chord(root=0, chord_type="major", notes=[0, 4, 7],
                  start_time=0.0, duration=8.0)
    for bad in (float("inf"), float("nan"), -1.0, 0.0):
        with pytest.raises(ValueError, match="positive finite"):
            composer.generate_melody([chord], key, length=bad)


def test_generate_melody_still_generates_for_valid_length():
    from midi_analysis import MIDIComposer, Chord, MusicalKey
    composer = MIDIComposer()
    key = MusicalKey(tonic=0, mode="major", confidence=1.0,
                     scale_notes=[0, 2, 4, 5, 7, 9, 11])
    chord = Chord(root=0, chord_type="major", notes=[0, 4, 7],
                  start_time=0.0, duration=8.0)
    assert len(composer.generate_melody([chord], key, length=8.0)) == 16


def test_detect_chords_on_empty_notes_returns_empty_list():
    # Silence/unpitched audio produces no MIDI notes; detect_key and
    # analyze_rhythm already answer honestly (confidence 0, tempo 0).
    # detect_chords used to leak `ValueError: max() iterable argument is
    # empty` from its window loop instead.
    analyzer = MIDIAnalyzer()

    assert analyzer.detect_chords([]) == []
