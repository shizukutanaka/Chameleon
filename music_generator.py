#!/usr/bin/env python3
"""
AI Music Generation System
Neural network-based music composition and generation
"""

import warnings
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    warnings.warn("PyTorch not installed. Music generation limited.")

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

class MusicStyle(Enum):
    """Music generation styles"""
    CLASSICAL = "classical"
    JAZZ = "jazz"
    ROCK = "rock"
    ELECTRONIC = "electronic"
    AMBIENT = "ambient"
    POP = "pop"
    HIPHOP = "hiphop"
    FOLK = "folk"

@dataclass
class GenerationConfig:
    """Configuration for music generation"""
    style: MusicStyle = MusicStyle.CLASSICAL
    tempo: int = 120
    key: str = "C"
    time_signature: str = "4/4"
    duration: float = 30.0  # seconds
    complexity: float = 0.5  # 0-1
    variation: float = 0.7
    instruments: List[str] = None
    seed: Optional[int] = None

class MusicTheory:
    """Music theory utilities"""

    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    SCALES = {
        'major': [0, 2, 4, 5, 7, 9, 11],
        'minor': [0, 2, 3, 5, 7, 8, 10],
        'dorian': [0, 2, 3, 5, 7, 9, 10],
        'phrygian': [0, 1, 3, 5, 7, 8, 10],
        'lydian': [0, 2, 4, 6, 7, 9, 11],
        'mixolydian': [0, 2, 4, 5, 7, 9, 10],
        'aeolian': [0, 2, 3, 5, 7, 8, 10],
        'locrian': [0, 1, 3, 5, 6, 8, 10],
        'pentatonic': [0, 2, 4, 7, 9],
        'blues': [0, 3, 5, 6, 7, 10]
    }

    CHORD_PROGRESSIONS = {
        'pop': ['I', 'V', 'vi', 'IV'],
        'jazz': ['IIM7', 'V7', 'IM7'],
        'blues': ['I7', 'I7', 'I7', 'I7', 'IV7', 'IV7', 'I7', 'I7', 'V7', 'IV7', 'I7', 'V7'],
        'classical': ['I', 'IV', 'V', 'I'],
        'rock': ['I', 'bVII', 'IV', 'I']
    }

    @staticmethod
    def note_to_freq(note: str, octave: int = 4) -> float:
        """Convert note to frequency"""
        note_idx = MusicTheory.NOTES.index(note)
        midi_number = (octave + 1) * 12 + note_idx
        return 440 * (2 ** ((midi_number - 69) / 12))

    @staticmethod
    def get_scale_notes(root: str, scale_type: str = 'major') -> List[str]:
        """Get notes in a scale"""
        root_idx = MusicTheory.NOTES.index(root)
        scale_intervals = MusicTheory.SCALES.get(scale_type, MusicTheory.SCALES['major'])

        scale_notes = []
        for interval in scale_intervals:
            note_idx = (root_idx + interval) % 12
            scale_notes.append(MusicTheory.NOTES[note_idx])

        return scale_notes

    @staticmethod
    def get_chord(root: str, chord_type: str = 'major') -> List[str]:
        """Get notes in a chord"""
        root_idx = MusicTheory.NOTES.index(root)

        if chord_type == 'major':
            intervals = [0, 4, 7]
        elif chord_type == 'minor':
            intervals = [0, 3, 7]
        elif chord_type == '7':
            intervals = [0, 4, 7, 10]
        elif chord_type == 'maj7':
            intervals = [0, 4, 7, 11]
        elif chord_type == 'min7':
            intervals = [0, 3, 7, 10]
        elif chord_type == 'dim':
            intervals = [0, 3, 6]
        else:
            intervals = [0, 4, 7]

        chord_notes = []
        for interval in intervals:
            note_idx = (root_idx + interval) % 12
            chord_notes.append(MusicTheory.NOTES[note_idx])

        return chord_notes

class MelodyGenerator:
    """Generate melodies using AI"""

    def __init__(self):
        self.model = None
        if HAS_TORCH:
            self.model = self._build_model()

    def _build_model(self) -> nn.Module:
        """Build LSTM model for melody generation"""
        class MelodyLSTM(nn.Module):
            def __init__(self, input_size: int = 128, hidden_size: int = 256, num_layers: int = 2):
                super().__init__()
                self.hidden_size = hidden_size
                self.num_layers = num_layers

                self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
                self.fc = nn.Linear(hidden_size, 128)  # 128 possible notes
                self.dropout = nn.Dropout(0.2)

            def forward(self, x, hidden=None):
                out, hidden = self.lstm(x, hidden)
                out = self.dropout(out)
                out = self.fc(out)
                return out, hidden

        return MelodyLSTM()

    def generate(self, config: GenerationConfig, scale_notes: List[str]) -> np.ndarray:
        """Generate melody"""
        sample_rate = 44100
        duration = config.duration
        tempo = config.tempo

        # Calculate timing
        beat_duration = 60 / tempo
        notes_per_beat = 2 if config.complexity > 0.5 else 1
        note_duration = beat_duration / notes_per_beat
        total_notes = int(duration / note_duration)

        # Generate note sequence
        if self.model and HAS_TORCH:
            melody_sequence = self._generate_with_ai(total_notes, scale_notes, config.variation)
        else:
            melody_sequence = self._generate_algorithmic(total_notes, scale_notes, config.variation)

        # Convert to audio
        audio = self._sequence_to_audio(melody_sequence, note_duration, sample_rate)

        return audio

    def _generate_with_ai(self, num_notes: int, scale_notes: List[str], variation: float) -> List[Tuple[str, int]]:
        """Generate melody using neural network"""
        sequence = []

        # Initialize with random note from scale
        current_note = np.random.choice(scale_notes)
        current_octave = 4

        # Generate sequence
        temperature = variation * 2  # Higher variation = higher temperature

        for _ in range(num_notes):
            # Simple markov-like generation (placeholder for trained model)
            if np.random.random() < 0.8:  # Stay in scale
                note = np.random.choice(scale_notes)
            else:  # Chromatic passing note
                note = np.random.choice(MusicTheory.NOTES)

            # Octave movement
            if np.random.random() < 0.1:
                current_octave = np.clip(current_octave + np.random.choice([-1, 1]), 3, 6)

            sequence.append((note, current_octave))

        return sequence

    def _generate_algorithmic(self, num_notes: int, scale_notes: List[str], variation: float) -> List[Tuple[str, int]]:
        """Generate melody using algorithmic approach"""
        sequence = []
        current_idx = len(scale_notes) // 2
        current_octave = 4

        for i in range(num_notes):
            # Get current note
            note = scale_notes[current_idx % len(scale_notes)]
            sequence.append((note, current_octave))

            # Determine next movement
            if np.random.random() < variation:
                # Random jump
                step = np.random.choice([-3, -2, -1, 1, 2, 3])
            else:
                # Stepwise motion
                step = np.random.choice([-1, 1])

            current_idx += step

            # Handle octave changes
            if current_idx < 0:
                current_idx += len(scale_notes)
                current_octave = max(3, current_octave - 1)
            elif current_idx >= len(scale_notes):
                current_idx -= len(scale_notes)
                current_octave = min(6, current_octave + 1)

        return sequence

    def _sequence_to_audio(self, sequence: List[Tuple[str, int]], note_duration: float, sample_rate: int) -> np.ndarray:
        """Convert note sequence to audio"""
        samples_per_note = int(note_duration * sample_rate)
        total_samples = len(sequence) * samples_per_note
        audio = np.zeros(total_samples)

        for i, (note, octave) in enumerate(sequence):
            if note != 'rest':
                freq = MusicTheory.note_to_freq(note, octave)
                t = np.linspace(0, note_duration, samples_per_note)

                # Generate note with harmonics
                note_audio = np.sin(2 * np.pi * freq * t)
                note_audio += 0.3 * np.sin(4 * np.pi * freq * t)  # 2nd harmonic
                note_audio += 0.1 * np.sin(6 * np.pi * freq * t)  # 3rd harmonic

                # Apply envelope
                envelope = self._create_envelope(samples_per_note)
                note_audio *= envelope

                # Add to audio
                start_idx = i * samples_per_note
                end_idx = start_idx + samples_per_note
                audio[start_idx:end_idx] = note_audio

        return audio

    def _create_envelope(self, length: int) -> np.ndarray:
        """Create ADSR envelope"""
        attack = int(length * 0.1)
        decay = int(length * 0.1)
        sustain_level = 0.7
        release = int(length * 0.2)

        envelope = np.ones(length) * sustain_level

        # Attack
        envelope[:attack] = np.linspace(0, 1, attack)

        # Decay
        envelope[attack:attack+decay] = np.linspace(1, sustain_level, decay)

        # Release
        envelope[-release:] = np.linspace(sustain_level, 0, release)

        return envelope

class ChordProgressionGenerator:
    """Generate chord progressions"""

    def __init__(self):
        self.theory = MusicTheory()

    def generate(self, config: GenerationConfig) -> List[List[str]]:
        """Generate chord progression"""
        style_progressions = {
            MusicStyle.POP: ['I', 'V', 'vi', 'IV'],
            MusicStyle.JAZZ: ['IIM7', 'V7', 'IM7', 'VIM7'],
            MusicStyle.ROCK: ['I', 'bVII', 'IV', 'I'],
            MusicStyle.CLASSICAL: ['I', 'ii', 'V', 'I'],
            MusicStyle.FOLK: ['I', 'IV', 'I', 'V']
        }

        progression = style_progressions.get(config.style, ['I', 'IV', 'V', 'I'])

        # Convert to actual chords
        key = config.key
        scale_notes = self.theory.get_scale_notes(key)
        chords = []

        for chord_symbol in progression:
            # Parse chord symbol
            root_degree = self._parse_degree(chord_symbol)
            chord_type = self._parse_chord_type(chord_symbol)

            # Get root note
            root_idx = root_degree - 1
            if root_idx < len(scale_notes):
                root_note = scale_notes[root_idx]
            else:
                root_note = key

            # Get chord notes
            chord_notes = self.theory.get_chord(root_note, chord_type)
            chords.append(chord_notes)

        return chords

    def _parse_degree(self, symbol: str) -> int:
        """Parse scale degree from chord symbol"""
        degree_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7}

        for degree_str, degree_num in degree_map.items():
            if symbol.upper().startswith(degree_str):
                return degree_num

        return 1

    def _parse_chord_type(self, symbol: str) -> str:
        """Parse chord type from symbol"""
        if 'M7' in symbol or 'maj7' in symbol:
            return 'maj7'
        elif 'm7' in symbol or 'min7' in symbol:
            return 'min7'
        elif '7' in symbol:
            return '7'
        elif 'm' in symbol.lower() or 'min' in symbol.lower():
            return 'minor'
        elif 'dim' in symbol.lower():
            return 'dim'
        else:
            return 'major'

    def to_audio(self, chords: List[List[str]], duration: float, sample_rate: int = 44100) -> np.ndarray:
        """Convert chord progression to audio"""
        chord_duration = duration / len(chords)
        samples_per_chord = int(chord_duration * sample_rate)
        total_samples = len(chords) * samples_per_chord
        audio = np.zeros(total_samples)

        for i, chord in enumerate(chords):
            t = np.linspace(0, chord_duration, samples_per_chord)
            chord_audio = np.zeros(samples_per_chord)

            # Add each note in the chord
            for note in chord:
                freq = MusicTheory.note_to_freq(note, 3)  # Lower octave for chords
                chord_audio += np.sin(2 * np.pi * freq * t) * 0.3

            # Apply envelope
            envelope = np.ones(samples_per_chord)
            fade = int(samples_per_chord * 0.05)
            envelope[:fade] = np.linspace(0, 1, fade)
            envelope[-fade:] = np.linspace(1, 0, fade)
            chord_audio *= envelope

            # Add to audio
            start_idx = i * samples_per_chord
            end_idx = start_idx + samples_per_chord
            audio[start_idx:end_idx] = chord_audio

        return audio

class RhythmGenerator:
    """Generate drum patterns and rhythms"""

    def __init__(self):
        self.patterns = {
            'rock': {
                'kick': [1, 0, 0, 0, 1, 0, 0, 0],
                'snare': [0, 0, 1, 0, 0, 0, 1, 0],
                'hihat': [1, 1, 1, 1, 1, 1, 1, 1]
            },
            'jazz': {
                'kick': [1, 0, 0, 1, 0, 0, 1, 0],
                'snare': [0, 0, 0, 1, 0, 0, 1, 0],
                'ride': [1, 0, 1, 1, 0, 1, 1, 0]
            },
            'electronic': {
                'kick': [1, 0, 0, 0, 1, 0, 0, 0],
                'snare': [0, 0, 1, 0, 0, 0, 1, 0],
                'hihat': [0, 1, 0, 1, 0, 1, 0, 1]
            }
        }

    def generate(self, config: GenerationConfig) -> np.ndarray:
        """Generate rhythm pattern"""
        sample_rate = 44100
        tempo = config.tempo
        duration = config.duration

        # Get pattern for style
        style_name = config.style.value
        if style_name in ['rock', 'jazz', 'electronic']:
            pattern = self.patterns[style_name]
        else:
            pattern = self.patterns['rock']

        # Calculate timing
        beat_duration = 60 / tempo
        subdivision = len(pattern['kick'])
        step_duration = beat_duration / (subdivision / 4)
        samples_per_step = int(step_duration * sample_rate)

        # Generate audio
        total_beats = int(duration / beat_duration)
        total_steps = total_beats * subdivision // 4
        audio = np.zeros(total_steps * samples_per_step)

        for step in range(total_steps):
            pattern_idx = step % subdivision

            # Kick drum
            if pattern['kick'][pattern_idx]:
                kick = self._generate_kick(samples_per_step)
                start_idx = step * samples_per_step
                end_idx = start_idx + len(kick)
                audio[start_idx:end_idx] += kick

            # Snare drum
            if 'snare' in pattern and pattern['snare'][pattern_idx]:
                snare = self._generate_snare(samples_per_step)
                start_idx = step * samples_per_step
                end_idx = start_idx + len(snare)
                audio[start_idx:end_idx] += snare * 0.8

            # Hi-hat
            if 'hihat' in pattern and pattern['hihat'][pattern_idx]:
                hihat = self._generate_hihat(samples_per_step)
                start_idx = step * samples_per_step
                end_idx = start_idx + len(hihat)
                audio[start_idx:end_idx] += hihat * 0.3

        return audio

    def _generate_kick(self, length: int) -> np.ndarray:
        """Generate kick drum sound"""
        t = np.linspace(0, length / 44100, length)

        # Sine wave with pitch envelope
        pitch_env = np.exp(-35 * t)
        kick = np.sin(2 * np.pi * (60 * pitch_env + 40) * t)

        # Add click
        click = np.random.randn(length) * np.exp(-100 * t)
        kick += click * 0.5

        # Envelope
        envelope = np.exp(-10 * t)
        kick *= envelope

        return kick

    def _generate_snare(self, length: int) -> np.ndarray:
        """Generate snare drum sound"""
        t = np.linspace(0, length / 44100, length)

        # Tone component
        tone = np.sin(2 * np.pi * 200 * t) + np.sin(2 * np.pi * 300 * t)

        # Noise component
        noise = np.random.randn(length)

        # Mix and envelope
        snare = (tone * 0.5 + noise) * np.exp(-30 * t)

        return snare

    def _generate_hihat(self, length: int) -> np.ndarray:
        """Generate hi-hat sound"""
        t = np.linspace(0, length / 44100, length)

        # High-frequency noise
        hihat = np.random.randn(length)

        # High-pass filter simulation
        hihat = np.diff(np.concatenate(([0], hihat)))

        # Short envelope
        envelope = np.exp(-200 * t)
        hihat *= envelope

        return hihat

class BasslineGenerator:
    """Generate basslines"""

    def __init__(self):
        self.theory = MusicTheory()

    def generate(self, chords: List[List[str]], config: GenerationConfig) -> np.ndarray:
        """Generate bassline from chord progression"""
        sample_rate = 44100
        tempo = config.tempo
        duration = config.duration

        # Calculate timing
        beat_duration = 60 / tempo
        notes_per_beat = 2  # Eighth notes
        note_duration = beat_duration / notes_per_beat

        # Generate bass pattern
        chord_duration = duration / len(chords)
        notes_per_chord = int(chord_duration / note_duration)

        audio = np.zeros(int(duration * sample_rate))
        current_sample = 0

        for chord in chords:
            root_note = chord[0]  # Use root note

            for i in range(notes_per_chord):
                # Create bass pattern
                if i % 4 == 0:  # Strong beat
                    note = root_note
                    octave = 2
                    velocity = 1.0
                elif i % 2 == 0:  # Weak beat
                    note = chord[2] if len(chord) > 2 else root_note  # Fifth
                    octave = 2
                    velocity = 0.7
                else:  # Off beat
                    note = root_note
                    octave = 3
                    velocity = 0.5

                # Generate note
                freq = MusicTheory.note_to_freq(note, octave)
                samples = int(note_duration * sample_rate)
                t = np.linspace(0, note_duration, samples)

                # Bass tone with harmonics
                bass_note = np.sin(2 * np.pi * freq * t)
                bass_note += 0.3 * np.sin(2 * np.pi * freq * 2 * t)

                # Envelope
                envelope = np.ones(samples)
                attack = int(samples * 0.01)
                release = int(samples * 0.1)
                envelope[:attack] = np.linspace(0, 1, attack)
                envelope[-release:] = np.linspace(1, 0, release)

                bass_note *= envelope * velocity

                # Add to audio
                end_sample = min(current_sample + samples, len(audio))
                audio[current_sample:end_sample] = bass_note[:end_sample-current_sample]
                current_sample = end_sample

        return audio

class MusicGenerator:
    """Main music generation system"""

    def __init__(self):
        self.melody_gen = MelodyGenerator()
        self.chord_gen = ChordProgressionGenerator()
        self.rhythm_gen = RhythmGenerator()
        self.bass_gen = BasslineGenerator()
        self.theory = MusicTheory()

    def generate(self, config: GenerationConfig) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Generate complete music piece"""
        info = {
            "style": config.style.value,
            "tempo": config.tempo,
            "key": config.key,
            "duration": config.duration,
            "components": []
        }

        # Initialize random seed if provided
        if config.seed:
            np.random.seed(config.seed)

        # Get scale for the key
        scale_notes = self.theory.get_scale_notes(config.key)

        # Generate components
        components = []

        # Generate chord progression
        chords = self.chord_gen.generate(config)
        chord_audio = self.chord_gen.to_audio(chords, config.duration)
        components.append(("chords", chord_audio * 0.3))
        info["components"].append("chords")

        # Generate melody
        melody_audio = self.melody_gen.generate(config, scale_notes)
        components.append(("melody", melody_audio * 0.5))
        info["components"].append("melody")

        # Generate bassline
        bass_audio = self.bass_gen.generate(chords, config)
        components.append(("bass", bass_audio * 0.4))
        info["components"].append("bass")

        # Generate rhythm (if not classical/ambient)
        if config.style not in [MusicStyle.CLASSICAL, MusicStyle.AMBIENT]:
            rhythm_audio = self.rhythm_gen.generate(config)
            components.append(("drums", rhythm_audio * 0.3))
            info["components"].append("drums")

        # Mix components
        max_length = max(len(audio) for _, audio in components)
        mixed = np.zeros(max_length)

        for name, audio in components:
            mixed[:len(audio)] += audio

        # Normalize
        max_val = np.max(np.abs(mixed))
        if max_val > 0:
            mixed = mixed / max_val * 0.9

        # Add reverb for ambience
        if config.style == MusicStyle.AMBIENT:
            mixed = self._add_reverb(mixed)

        info["final_length_samples"] = len(mixed)
        info["final_duration_seconds"] = len(mixed) / 44100

        return mixed, info

    def _add_reverb(self, audio: np.ndarray) -> np.ndarray:
        """Add simple reverb effect"""
        reverb = np.zeros_like(audio)
        delays = [1323, 1531, 1743, 1951]  # Prime numbers for delay

        for delay in delays:
            if delay < len(audio):
                delayed = np.zeros_like(audio)
                delayed[delay:] = audio[:-delay] * 0.5
                reverb += delayed

        return audio + reverb * 0.3

    def generate_variation(self, original: np.ndarray, variation_amount: float = 0.3) -> np.ndarray:
        """Generate variation of existing music"""
        # Apply random modifications
        variation = original.copy()

        # Pitch shift some sections
        if HAS_LIBROSA:
            sections = 4
            section_length = len(variation) // sections

            for i in range(sections):
                if np.random.random() < variation_amount:
                    start = i * section_length
                    end = min((i + 1) * section_length, len(variation))

                    # Random pitch shift
                    semitones = np.random.choice([-2, -1, 1, 2])
                    variation[start:end] = librosa.effects.pitch_shift(
                        variation[start:end], sr=44100, n_steps=semitones
                    )

        return variation

# Example usage
if __name__ == "__main__":
    print("AI Music Generation System")

    # Create generator
    generator = MusicGenerator()

    # Configure generation
    config = GenerationConfig(
        style=MusicStyle.JAZZ,
        tempo=120,
        key="G",
        duration=10.0,
        complexity=0.6,
        variation=0.7
    )

    # Generate music
    music, info = generator.generate(config)

    print(f"Generated {info['final_duration_seconds']:.1f} seconds of {config.style.value} music")
    print(f"Components: {', '.join(info['components'])}")
    print(f"Sample rate: 44100 Hz")
    print(f"Total samples: {len(music)}")