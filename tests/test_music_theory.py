"""Key and chord detection.

Two bugs sat in this file, both of the kind that only shows up when you check
against known-answer musical input rather than eyeballing the code:

* `detect_key` rotated the Krumhansl-Schmuckler profile the wrong way,
  computing profile[(pc + tonic) % 12] instead of profile[(pc - tonic) % 12].
  The two agree only at tonic 0, so C major came out right and the other
  eleven keys were reported as their inverse -- G major detected as F, D as
  A#, A as D#.

* `_analyze_chord` scored a template by matches / len(template), which asks
  only how much of the template is present and never penalises notes the
  template fails to explain. C-E-G-B scored 1.0 against the three-note "major"
  template just as it did against "maj7", and dictionary order broke the tie,
  so every seventh chord was reported as its bare triad.

The profile numbers themselves match the published Krumhansl & Kessler (1982)
values and are left alone.
"""

import pytest

import midi_analysis


PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
NATURAL_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]


def _analyzer():
    return midi_analysis.MIDIAnalyzer()


def _scale_notes(tonic, intervals, octave=60):
    pitch_classes = [(tonic + step) % 12 for step in intervals]
    # Repeat the tonic so it dominates, as it would in real material.
    pitch_classes += [tonic, tonic]
    return [
        midi_analysis.MIDINote(pitch=octave + pc, velocity=100,
                               start_time=index * 0.5, duration=0.5)
        for index, pc in enumerate(pitch_classes)
    ]


def _chord(pitches):
    notes = [midi_analysis.MIDINote(pitch=p, velocity=100, start_time=0.0, duration=1.0)
             for p in pitches]
    return _analyzer()._analyze_chord(notes, 0.0, 1.0)


# --- key detection --------------------------------------------------------

@pytest.mark.parametrize("tonic", range(12))
def test_every_major_key_is_identified(tonic):
    key = _analyzer().detect_key(_scale_notes(tonic, MAJOR_SCALE))

    assert key.tonic == tonic, (
        f"{PITCH_NAMES[tonic]} major detected as {PITCH_NAMES[key.tonic]}")
    assert key.mode == "major"


@pytest.mark.parametrize("tonic", range(12))
def test_every_minor_key_is_identified(tonic):
    key = _analyzer().detect_key(_scale_notes(tonic, NATURAL_MINOR_SCALE))

    assert key.tonic == tonic
    assert key.mode == "minor"


def test_the_profile_values_are_the_published_ones():
    profiles = _analyzer().key_profiles
    assert profiles["major"] == [6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    assert profiles["minor"] == [6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def test_no_notes_gives_zero_confidence_rather_than_a_crash():
    key = _analyzer().detect_key([])
    assert key.confidence == 0.0


# --- chord detection ------------------------------------------------------

@pytest.mark.parametrize("pitches,expected_root,expected_type", [
    ([60, 64, 67], 0, "major"),        # C E G
    ([57, 60, 64], 9, "minor"),        # A C E
    ([62, 65, 69], 2, "minor"),        # D F A
    ([59, 62, 65], 11, "dim"),         # B D F
    ([60, 64, 68], 0, "aug"),          # C E G#
    ([60, 65, 67], 0, "sus4"),         # C F G
])
def test_triads_are_identified(pitches, expected_root, expected_type):
    chord = _chord(pitches)
    assert chord is not None
    assert chord.root == expected_root
    assert chord.chord_type == expected_type


@pytest.mark.parametrize("pitches,expected_root,expected_type", [
    ([55, 59, 62, 65], 7, "dom7"),     # G B D F
    ([60, 64, 67, 71], 0, "maj7"),     # C E G B
])
def test_sevenths_are_not_reduced_to_their_triad(pitches, expected_root, expected_type):
    chord = _chord(pitches)
    assert chord is not None
    assert (chord.root, chord.chord_type) == (expected_root, expected_type)


def test_identical_pitch_class_sets_are_resolved_by_the_bass():
    # A-C-E-G is Am7 or C6 depending only on what is underneath; pitch-class
    # content cannot decide, so the lowest note does.
    a_in_bass = _chord([57, 60, 64, 67])
    c_in_bass = _chord([60, 64, 67, 69])

    assert (a_in_bass.root, a_in_bass.chord_type) == (9, "min7")
    assert (c_in_bass.root, c_in_bass.chord_type) == (0, "6")


def test_fewer_than_three_notes_is_not_a_chord():
    assert _chord([60, 64]) is None


# --- tempo estimation -----------------------------------------------------
#
# `analyze_rhythm` reported every tempo four times too slow: notes half a
# second apart, which is 120 BPM, came out as 30. It also bucketed intervals
# with round(interval * 16) / 16 -- described as "quantize to 16th notes" but
# actually 62.5 ms buckets, so resolution depended on the tempo and fast
# material was badly quantised (100 ms onsets snapped to 125 ms).

def _evenly_spaced(gap_seconds, count=16):
    return [
        midi_analysis.MIDINote(pitch=60, velocity=100,
                               start_time=index * gap_seconds,
                               duration=gap_seconds * 0.9)
        for index in range(count)
    ]


def _is_octave_equivalent(reported, expected, tolerance=0.03):
    """Beat trackers may land on a related metrical level (half/double)."""
    return any(abs(reported / (expected * 2 ** k) - 1) < tolerance
               for k in range(-5, 6))


@pytest.mark.parametrize("gap,expected_bpm", [
    (0.5, 120.0),
    (0.25, 240.0),
    (1.0, 60.0),
    (0.6, 100.0),
    (0.4, 150.0),
    (0.35, 171.4),
])
def test_tempo_matches_the_note_spacing(gap, expected_bpm):
    tempo = _analyzer().analyze_rhythm(_evenly_spaced(gap))["tempo"]
    assert _is_octave_equivalent(tempo, expected_bpm), (
        f"{gap}s spacing is {expected_bpm} BPM, reported {tempo:.1f}")


def test_half_second_spacing_is_120_bpm_not_30():
    # The exact symptom of the factor-of-four bug.
    tempo = _analyzer().analyze_rhythm(_evenly_spaced(0.5))["tempo"]
    assert tempo == pytest.approx(120.0, abs=1.0)


@pytest.mark.parametrize("gap", [2.0, 0.1])
def test_extreme_spacings_fold_into_a_plausible_range(gap):
    tempo = _analyzer().analyze_rhythm(_evenly_spaced(gap))["tempo"]
    assert 40.0 <= tempo <= 240.0


def test_tempo_survives_small_timing_jitter():
    import random
    rng = random.Random(0)
    notes = [
        midi_analysis.MIDINote(pitch=60, velocity=100,
                               start_time=i * 0.5 + rng.uniform(-0.01, 0.01),
                               duration=0.4)
        for i in range(32)
    ]
    tempo = _analyzer().analyze_rhythm(notes)["tempo"]
    assert tempo == pytest.approx(120.0, abs=3.0)


def test_no_notes_reports_zero_tempo():
    assert _analyzer().analyze_rhythm([])["tempo"] == 0
