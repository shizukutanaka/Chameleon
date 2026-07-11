"""
🎼 Chameleon Audio Processing System v3.0
MIDI Analysis and Musical Intelligence Module

Advanced MIDI processing, music theory analysis, and musical feature extraction.
Professional-grade musical analysis with composition assistance.
"""

import math
import struct
import io
from typing import List, Dict, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time

@dataclass
class MIDIConfig:
    """Configuration for MIDI analysis and generation"""
    tempo: float = 120.0
    time_signature: Tuple[int, int] = (4, 4)
    key_signature: str = "C"
    scale_type: str = "major"
    quantization: int = 16  # 16th note quantization
    velocity_threshold: int = 64
    chord_detection_threshold: float = 0.3
    harmony_analysis_depth: int = 4
    enable_composition_ai: bool = True

class NoteClass(Enum):
    """Musical note classes"""
    C = 0
    C_SHARP = 1
    D = 2
    D_SHARP = 3
    E = 4
    F = 5
    F_SHARP = 6
    G = 7
    G_SHARP = 8
    A = 9
    A_SHARP = 10
    B = 11

@dataclass
class MIDINote:
    """MIDI note representation"""
    pitch: int
    velocity: int
    start_time: float
    duration: float
    channel: int = 0

    @property
    def note_name(self) -> str:
        """Get note name from MIDI pitch"""
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (self.pitch // 12) - 1
        note = note_names[self.pitch % 12]
        return f"{note}{octave}"

    @property
    def frequency(self) -> float:
        """Convert MIDI pitch to frequency"""
        return 440.0 * (2.0 ** ((self.pitch - 69) / 12.0))

@dataclass
class Chord:
    """Musical chord representation"""
    root: int
    chord_type: str
    notes: List[int]
    start_time: float
    duration: float
    confidence: float = 1.0

    @property
    def name(self) -> str:
        """Get chord name"""
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        root_name = note_names[self.root % 12]
        return f"{root_name}{self.chord_type}"

@dataclass
class MusicalKey:
    """Musical key representation"""
    tonic: int
    mode: str
    confidence: float
    scale_notes: List[int] = field(default_factory=list)

    def __post_init__(self):
        """Initialize scale notes"""
        if self.mode == "major":
            intervals = [0, 2, 4, 5, 7, 9, 11]
        elif self.mode == "minor":
            intervals = [0, 2, 3, 5, 7, 8, 10]
        elif self.mode == "dorian":
            intervals = [0, 2, 3, 5, 7, 9, 10]
        elif self.mode == "mixolydian":
            intervals = [0, 2, 4, 5, 7, 9, 10]
        else:
            intervals = [0, 2, 4, 5, 7, 9, 11]  # Default to major

        self.scale_notes = [(self.tonic + interval) % 12 for interval in intervals]

class MIDIAnalyzer:
    """Advanced MIDI analysis and musical intelligence"""

    def __init__(self, config: Optional[MIDIConfig] = None):
        self.config = config or MIDIConfig()
        self.chord_templates = self._initialize_chord_templates()
        self.key_profiles = self._initialize_key_profiles()

    def _initialize_chord_templates(self) -> Dict[str, List[int]]:
        """Initialize chord templates"""
        return {
            "major": [0, 4, 7],
            "minor": [0, 3, 7],
            "dim": [0, 3, 6],
            "aug": [0, 4, 8],
            "maj7": [0, 4, 7, 11],
            "min7": [0, 3, 7, 10],
            "dom7": [0, 4, 7, 10],
            "maj9": [0, 4, 7, 11, 14],
            "min9": [0, 3, 7, 10, 14],
            "sus2": [0, 2, 7],
            "sus4": [0, 5, 7],
            "add9": [0, 4, 7, 14],
            "6": [0, 4, 7, 9],
            "min6": [0, 3, 7, 9]
        }

    def _initialize_key_profiles(self) -> Dict[str, List[float]]:
        """Initialize key detection profiles (Krumhansl-Schmuckler)"""
        major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

        return {
            "major": major_profile,
            "minor": minor_profile
        }

    def parse_midi_from_audio(self, audio_data: List[float], sample_rate: int) -> List[MIDINote]:
        """Extract MIDI notes from audio using onset detection and pitch tracking"""
        try:
            # Basic onset detection using energy changes
            frame_size = int(sample_rate * 0.023)  # 23ms frames
            hop_size = frame_size // 4

            notes = []
            current_time = 0.0

            for i in range(0, len(audio_data) - frame_size, hop_size):
                frame = audio_data[i:i + frame_size]

                # Simple energy-based onset detection
                energy = sum(x * x for x in frame)

                if energy > 0.001:  # Threshold for note detection
                    # Estimate fundamental frequency using autocorrelation
                    pitch_hz = self._estimate_pitch(frame, sample_rate)

                    if pitch_hz is not None:
                        midi_pitch = self._hz_to_midi(pitch_hz)
                        velocity = min(127, int(energy * 1000))

                        notes.append(MIDINote(
                            pitch=midi_pitch,
                            velocity=velocity,
                            start_time=current_time,
                            duration=0.1,  # Default duration
                            channel=0
                        ))

                current_time += hop_size / sample_rate

            return self._merge_overlapping_notes(notes)

        except Exception as e:
            print(f"Error in MIDI extraction: {e}")
            return []

    def _estimate_pitch(self, frame: List[float], sample_rate: int) -> Optional[float]:
        """Estimate fundamental frequency using the YIN algorithm.

        YIN (de Cheveigné & Kawahara, 2002) is the signal-processing gold
        standard for monophonic pitch: a difference function plus cumulative
        mean normalisation and an absolute threshold avoid the octave errors
        that a plain global-maximum autocorrelation suffers from, and a final
        parabolic interpolation recovers sub-sample period resolution. Pure
        standard library — no NumPy required.
        """
        try:
            n = len(frame)
            if n < 8:
                return None

            f_min, f_max = 80.0, 2000.0
            window = n // 2  # integration window
            tau_min = max(1, int(sample_rate / f_max))
            tau_max = min(window, int(sample_rate / f_min))
            if tau_max <= tau_min or window < 2:
                return None

            # Step 1: difference function d(tau) over a fixed integration window.
            diff = [0.0] * (tau_max + 1)
            for tau in range(1, tau_max + 1):
                total = 0.0
                for i in range(window):
                    delta = frame[i] - frame[i + tau]
                    total += delta * delta
                diff[tau] = total

            # Step 2: cumulative mean normalised difference (CMND).
            cmnd = [1.0] * (tau_max + 1)
            running = 0.0
            for tau in range(1, tau_max + 1):
                running += diff[tau]
                cmnd[tau] = diff[tau] * tau / running if running > 0 else 1.0

            # Step 3: absolute threshold — first dip below threshold, descended
            # to its local minimum (this is what defeats octave errors).
            threshold = 0.1
            tau_est: Optional[int] = None
            tau = tau_min
            while tau <= tau_max:
                if cmnd[tau] < threshold:
                    while tau + 1 <= tau_max and cmnd[tau + 1] < cmnd[tau]:
                        tau += 1
                    tau_est = tau
                    break
                tau += 1

            # Fallback: global minimum in range, rejected if not periodic enough.
            if tau_est is None:
                best = tau_min
                for tau in range(tau_min, tau_max + 1):
                    if cmnd[tau] < cmnd[best]:
                        best = tau
                if cmnd[best] >= 0.5:
                    return None
                tau_est = best

            # Step 4: parabolic interpolation around the chosen period.
            if tau_min < tau_est < tau_max:
                x0, x1, x2 = cmnd[tau_est - 1], cmnd[tau_est], cmnd[tau_est + 1]
                denominator = x0 - 2.0 * x1 + x2
                if denominator != 0:
                    shift = 0.5 * (x0 - x2) / denominator
                    tau_refined = tau_est + shift if -1.0 < shift < 1.0 else float(tau_est)
                else:
                    tau_refined = float(tau_est)
            else:
                tau_refined = float(tau_est)

            if tau_refined <= 0:
                return None
            frequency = sample_rate / tau_refined

            if f_min <= frequency <= f_max:
                return frequency
            return None

        except Exception:
            return None

    def _hz_to_midi(self, frequency: float) -> int:
        """Convert frequency to MIDI note number"""
        return int(round(69 + 12 * math.log2(frequency / 440.0)))

    def _merge_overlapping_notes(self, notes: List[MIDINote]) -> List[MIDINote]:
        """Merge overlapping notes of the same pitch"""
        if not notes:
            return notes

        # Sort notes by start time and pitch
        notes.sort(key=lambda n: (n.start_time, n.pitch))

        merged = []
        current_note = notes[0]

        for note in notes[1:]:
            if (note.pitch == current_note.pitch and
                note.start_time <= current_note.start_time + current_note.duration):
                # Merge notes
                end_time = max(
                    current_note.start_time + current_note.duration,
                    note.start_time + note.duration
                )
                current_note.duration = end_time - current_note.start_time
                current_note.velocity = max(current_note.velocity, note.velocity)
            else:
                merged.append(current_note)
                current_note = note

        merged.append(current_note)
        return merged

    def detect_chords(self, notes: List[MIDINote], window_size: float = 1.0) -> List[Chord]:
        """Detect chords from MIDI notes"""
        chords = []
        current_time = 0.0

        while current_time < max(n.start_time + n.duration for n in notes):
            # Get notes active in current window
            active_notes = [
                n for n in notes
                if n.start_time <= current_time < n.start_time + n.duration
            ]

            if len(active_notes) >= 3:  # Minimum notes for chord
                chord = self._analyze_chord(active_notes, current_time, window_size)
                if chord:
                    chords.append(chord)

            current_time += window_size / 2  # 50% overlap

        return self._merge_similar_chords(chords)

    def _analyze_chord(self, notes: List[MIDINote], start_time: float, duration: float) -> Optional[Chord]:
        """Analyze a group of notes to identify chord type"""
        if len(notes) < 3:
            return None

        # Get unique pitch classes
        pitch_classes = list(set(note.pitch % 12 for note in notes))
        pitch_classes.sort()

        best_match = None
        best_score = 0

        # Try each note as potential root
        for root in pitch_classes:
            for chord_type, template in self.chord_templates.items():
                # Normalize template to root
                normalized_template = [(root + interval) % 12 for interval in template]

                # Calculate match score
                matches = sum(1 for pc in pitch_classes if pc in normalized_template)
                score = matches / len(normalized_template)

                if score > best_score and score >= self.config.chord_detection_threshold:
                    best_score = score
                    best_match = Chord(
                        root=root,
                        chord_type=chord_type,
                        notes=pitch_classes,
                        start_time=start_time,
                        duration=duration,
                        confidence=score
                    )

        return best_match

    def _merge_similar_chords(self, chords: List[Chord]) -> List[Chord]:
        """Merge consecutive similar chords"""
        if not chords:
            return chords

        merged = []
        current_chord = chords[0]

        for chord in chords[1:]:
            if (chord.root == current_chord.root and
                chord.chord_type == current_chord.chord_type and
                chord.start_time <= current_chord.start_time + current_chord.duration):
                # Extend current chord
                end_time = max(
                    current_chord.start_time + current_chord.duration,
                    chord.start_time + chord.duration
                )
                current_chord.duration = end_time - current_chord.start_time
                current_chord.confidence = max(current_chord.confidence, chord.confidence)
            else:
                merged.append(current_chord)
                current_chord = chord

        merged.append(current_chord)
        return merged

    def detect_key(self, notes: List[MIDINote]) -> MusicalKey:
        """Detect musical key using Krumhansl-Schmuckler algorithm"""
        # Count pitch class occurrences weighted by duration and velocity
        pitch_class_weights = [0.0] * 12

        for note in notes:
            pc = note.pitch % 12
            weight = note.duration * (note.velocity / 127.0)
            pitch_class_weights[pc] += weight

        # Normalize weights
        total_weight = sum(pitch_class_weights)
        if total_weight == 0:
            return MusicalKey(tonic=0, mode="major", confidence=0.0)

        pitch_class_weights = [w / total_weight for w in pitch_class_weights]

        best_key = None
        best_correlation = -1

        # Test each key
        for tonic in range(12):
            for mode, profile in self.key_profiles.items():
                # Rotate profile to match tonic
                rotated_profile = profile[tonic:] + profile[:tonic]

                # Calculate correlation
                correlation = self._pearson_correlation(pitch_class_weights, rotated_profile)

                if correlation > best_correlation:
                    best_correlation = correlation
                    best_key = MusicalKey(
                        tonic=tonic,
                        mode=mode,
                        confidence=correlation
                    )

        return best_key or MusicalKey(tonic=0, mode="major", confidence=0.0)

    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        n = len(x)
        if n != len(y) or n == 0:
            return 0.0

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        sum_y2 = sum(y[i] ** 2 for i in range(n))

        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def analyze_harmony(self, chords: List[Chord], key: MusicalKey) -> Dict[str, Any]:
        """Analyze harmonic progression"""
        if not chords:
            return {"progression": [], "analysis": "No chords found"}

        progression = []
        roman_numerals = ["I", "♭II", "II", "♭III", "III", "IV", "♭V", "V", "♭VI", "VI", "♭VII", "VII"]

        for chord in chords:
            # Calculate scale degree
            degree = (chord.root - key.tonic) % 12

            # Determine quality based on chord type and key
            if chord.chord_type in ["minor", "min7", "min9"]:
                quality = "minor"
                roman = roman_numerals[degree].lower()
            elif chord.chord_type in ["dim"]:
                quality = "diminished"
                roman = roman_numerals[degree].lower() + "°"
            else:
                quality = "major"
                roman = roman_numerals[degree]

            progression.append({
                "chord": chord.name,
                "roman": roman,
                "degree": degree + 1,
                "quality": quality,
                "duration": chord.duration,
                "confidence": chord.confidence
            })

        # Analyze common progressions
        analysis = self._analyze_common_progressions(progression)

        return {
            "progression": progression,
            "analysis": analysis,
            "key": f"{key.tonic} {key.mode}",
            "key_confidence": key.confidence
        }

    def _analyze_common_progressions(self, progression: List[Dict]) -> str:
        """Identify common chord progressions"""
        if len(progression) < 2:
            return "Progression too short for analysis"

        # Extract Roman numeral sequence
        romans = [chord["roman"] for chord in progression]

        # Common progressions
        patterns = {
            ("I", "V", "vi", "IV"): "I-V-vi-IV (Pop progression)",
            ("vi", "IV", "I", "V"): "vi-IV-I-V (Pop variation)",
            ("I", "vi", "IV", "V"): "I-vi-IV-V (50s progression)",
            ("ii", "V", "I"): "ii-V-I (Jazz progression)",
            ("I", "IV", "V", "I"): "I-IV-V-I (Authentic cadence)",
            ("I", "V", "I"): "I-V-I (Perfect cadence)"
        }

        # Check for patterns
        for i in range(len(romans) - 1):
            for length in [4, 3, 2]:
                if i + length <= len(romans):
                    sequence = tuple(romans[i:i+length])
                    if sequence in patterns:
                        return f"Contains {patterns[sequence]}"

        return "Original progression"

    def generate_midi_file(self, notes: List[MIDINote], filename: str) -> bool:
        """Generate a basic MIDI file from notes"""
        try:
            # Basic MIDI file structure
            midi_data = bytearray()

            # MIDI Header chunk
            midi_data.extend(b'MThd')  # Header chunk ID
            midi_data.extend(struct.pack('>I', 6))  # Header length
            midi_data.extend(struct.pack('>H', 1))  # Format type 1
            midi_data.extend(struct.pack('>H', 1))  # Number of tracks
            midi_data.extend(struct.pack('>H', 480))  # Ticks per quarter note

            # Track chunk
            track_data = bytearray()

            # Sort notes by start time
            sorted_notes = sorted(notes, key=lambda n: n.start_time)

            current_time = 0
            active_notes = {}

            # Convert to MIDI events
            events = []
            for note in sorted_notes:
                # Note on event
                delta_time = int((note.start_time - current_time) * 480)
                events.append((note.start_time, 'note_on', note.pitch, note.velocity, delta_time))

                # Note off event
                end_time = note.start_time + note.duration
                delta_time_off = int((end_time - note.start_time) * 480)
                events.append((end_time, 'note_off', note.pitch, 0, delta_time_off))

            # Sort all events by time
            events.sort(key=lambda e: e[0])

            # Write events to track
            last_time = 0
            for event_time, event_type, pitch, velocity, _ in events:
                delta_ticks = int((event_time - last_time) * 480)

                # Write variable-length delta time
                track_data.extend(self._write_variable_length(delta_ticks))

                if event_type == 'note_on':
                    track_data.extend([0x90, pitch, velocity])  # Note on, channel 0
                else:  # note_off
                    track_data.extend([0x80, pitch, velocity])  # Note off, channel 0

                last_time = event_time

            # End of track
            track_data.extend([0x00, 0xFF, 0x2F, 0x00])

            # Track header
            midi_data.extend(b'MTrk')
            midi_data.extend(struct.pack('>I', len(track_data)))
            midi_data.extend(track_data)

            # Write to file
            with open(filename, 'wb') as f:
                f.write(midi_data)

            return True

        except Exception as e:
            print(f"Error generating MIDI file: {e}")
            return False

    def _write_variable_length(self, value: int) -> bytes:
        """Write variable-length quantity for MIDI"""
        result = []
        while value > 0x7F:
            result.insert(0, (value & 0x7F) | 0x80)
            value >>= 7
        result.insert(0, value & 0x7F)
        return bytes(result) if result else bytes([0])

    def analyze_rhythm(self, notes: List[MIDINote]) -> Dict[str, Any]:
        """Analyze rhythmic patterns"""
        if not notes:
            return {"tempo": 0, "time_signature": (4, 4), "patterns": []}

        # Calculate inter-onset intervals
        onsets = sorted([note.start_time for note in notes])
        intervals = [onsets[i+1] - onsets[i] for i in range(len(onsets)-1)]

        if not intervals:
            return {"tempo": self.config.tempo, "time_signature": self.config.time_signature, "patterns": []}

        # Estimate tempo from most common interval
        interval_counts = {}
        for interval in intervals:
            quantized = round(interval * 16) / 16  # Quantize to 16th notes
            interval_counts[quantized] = interval_counts.get(quantized, 0) + 1

        most_common_interval = max(interval_counts.keys(), key=lambda k: interval_counts[k])
        if most_common_interval > 0:
            estimated_tempo = 60.0 / (most_common_interval * 4)  # Assume quarter note
        else:
            estimated_tempo = self.config.tempo  # Fallback to config tempo

        return {
            "tempo": estimated_tempo,
            "time_signature": self.config.time_signature,
            "common_intervals": sorted(interval_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "rhythmic_complexity": len(set(intervals)) / len(intervals) if intervals else 0
        }

class MIDIComposer:
    """AI-assisted music composition"""

    def __init__(self, config: Optional[MIDIConfig] = None):
        self.config = config or MIDIConfig()
        self.analyzer = MIDIAnalyzer(config)

    def suggest_next_chord(self, current_progression: List[Chord], key: MusicalKey) -> List[Tuple[str, float]]:
        """Suggest next chord based on current progression"""
        if not current_progression:
            # Start with tonic
            return [("I", 1.0)]

        last_chord = current_progression[-1]
        last_degree = (last_chord.root - key.tonic) % 12

        # Simple Markov chain based on common progressions
        transition_probabilities = {
            0: [(4, 0.4), (7, 0.3), (9, 0.2), (5, 0.1)],  # I -> V, IV, vi, etc.
            4: [(0, 0.5), (7, 0.3), (2, 0.2)],  # V -> I, ii, etc.
            7: [(0, 0.4), (4, 0.3), (9, 0.3)],  # V -> I, V, vi
            9: [(4, 0.4), (0, 0.3), (5, 0.3)]   # vi -> V, I, IV
        }

        suggestions = []
        if last_degree in transition_probabilities:
            for next_degree, prob in transition_probabilities[last_degree]:
                roman_numerals = ["I", "♭II", "II", "♭III", "III", "IV", "♭V", "V", "♭VI", "VI", "♭VII", "VII"]
                suggestions.append((roman_numerals[next_degree], prob))

        return suggestions or [("I", 1.0)]

    def generate_melody(self, chords: List[Chord], key: MusicalKey, length: float = 8.0) -> List[MIDINote]:
        """Generate a simple melody over chord progression"""
        melody = []
        current_time = 0.0
        note_duration = 0.5  # Half beat notes

        while current_time < length:
            # Find current chord
            current_chord = None
            for chord in chords:
                if chord.start_time <= current_time < chord.start_time + chord.duration:
                    current_chord = chord
                    break

            if current_chord:
                # Choose note from chord or scale
                if len(current_chord.notes) > 0:
                    # Prefer chord tones
                    pitch_class = current_chord.notes[int(current_time * 2) % len(current_chord.notes)]
                else:
                    # Use scale notes
                    pitch_class = key.scale_notes[int(current_time * 2) % len(key.scale_notes)]

                # Add octave
                pitch = pitch_class + 60  # Middle C octave

                melody.append(MIDINote(
                    pitch=pitch,
                    velocity=80,
                    start_time=current_time,
                    duration=note_duration
                ))

            current_time += note_duration

        return melody

def demo_midi_analysis():
    """Demonstrate MIDI analysis capabilities"""
    print("🎼 MIDI Analysis Demo")
    print("=" * 50)

    # Create analyzer
    config = MIDIConfig(tempo=120, key_signature="C", scale_type="major")
    analyzer = MIDIAnalyzer(config)

    # Create sample MIDI notes (C major scale)
    sample_notes = [
        MIDINote(60, 80, 0.0, 1.0),  # C
        MIDINote(62, 80, 1.0, 1.0),  # D
        MIDINote(64, 80, 2.0, 1.0),  # E
        MIDINote(65, 80, 3.0, 1.0),  # F
        MIDINote(67, 80, 4.0, 1.0),  # G
        MIDINote(69, 80, 5.0, 1.0),  # A
        MIDINote(71, 80, 6.0, 1.0),  # B
        MIDINote(72, 80, 7.0, 1.0),  # C
    ]

    # Add chord progression (I-vi-IV-V)
    chord_notes = [
        # C major (I)
        MIDINote(60, 70, 8.0, 2.0),   # C
        MIDINote(64, 70, 8.0, 2.0),   # E
        MIDINote(67, 70, 8.0, 2.0),   # G

        # A minor (vi)
        MIDINote(57, 70, 10.0, 2.0),  # A
        MIDINote(60, 70, 10.0, 2.0),  # C
        MIDINote(64, 70, 10.0, 2.0),  # E

        # F major (IV)
        MIDINote(53, 70, 12.0, 2.0),  # F
        MIDINote(57, 70, 12.0, 2.0),  # A
        MIDINote(60, 70, 12.0, 2.0),  # C

        # G major (V)
        MIDINote(55, 70, 14.0, 2.0),  # G
        MIDINote(59, 70, 14.0, 2.0),  # B
        MIDINote(62, 70, 14.0, 2.0),  # D
    ]

    all_notes = sample_notes + chord_notes

    print("📝 Sample MIDI Notes:")
    for i, note in enumerate(all_notes[:5]):  # Show first 5
        print(f"  {i+1}. {note.note_name} (vel: {note.velocity}, time: {note.start_time:.1f}s)")
    print(f"  ... and {len(all_notes)-5} more notes")

    # Detect key
    print("\n🎵 Key Detection:")
    detected_key = analyzer.detect_key(all_notes)
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    key_name = note_names[detected_key.tonic]
    print(f"  Detected Key: {key_name} {detected_key.mode}")
    print(f"  Confidence: {detected_key.confidence:.3f}")

    # Detect chords
    print("\n🎸 Chord Detection:")
    chords = analyzer.detect_chords(all_notes)
    for i, chord in enumerate(chords):
        print(f"  {i+1}. {chord.name} (time: {chord.start_time:.1f}s, conf: {chord.confidence:.3f})")

    # Analyze harmony
    print("\n🎼 Harmonic Analysis:")
    harmony = analyzer.analyze_harmony(chords, detected_key)
    for i, chord_info in enumerate(harmony["progression"]):
        print(f"  {i+1}. {chord_info['chord']} ({chord_info['roman']}) - {chord_info['quality']}")
    print(f"  Analysis: {harmony['analysis']}")

    # Rhythm analysis
    print("\n🥁 Rhythm Analysis:")
    rhythm = analyzer.analyze_rhythm(all_notes)
    print(f"  Estimated Tempo: {rhythm['tempo']:.1f} BPM")
    print(f"  Time Signature: {rhythm['time_signature'][0]}/{rhythm['time_signature'][1]}")
    print(f"  Rhythmic Complexity: {rhythm['rhythmic_complexity']:.3f}")

    # Composition suggestions
    print("\n🤖 AI Composition Suggestions:")
    composer = MIDIComposer(config)
    suggestions = composer.suggest_next_chord(chords, detected_key)
    print("  Next chord suggestions:")
    for chord, prob in suggestions[:3]:
        print(f"    {chord} (probability: {prob:.2f})")

    # Generate melody
    print("\n🎵 Generated Melody:")
    melody = composer.generate_melody(chords, detected_key, length=4.0)
    for i, note in enumerate(melody[:8]):  # Show first 8 notes
        print(f"  {i+1}. {note.note_name} (time: {note.start_time:.1f}s)")

    return True

if __name__ == "__main__":
    demo_midi_analysis()