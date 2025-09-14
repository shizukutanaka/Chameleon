#!/usr/bin/env python3
"""
MIDI Integration - Musical Intelligence and MIDI Processing
Advanced music theory analysis, MIDI generation, and audio-MIDI sync
"""

import math
import struct
import time
from typing import List, Dict, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json

# Note definitions
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
SCALE_PATTERNS = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
    'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11],
    'phrygian': [0, 1, 3, 5, 7, 8, 10],
    'locrian': [0, 1, 3, 5, 6, 8, 10],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
    'pentatonic_major': [0, 2, 4, 7, 9],
    'pentatonic_minor': [0, 3, 5, 7, 10],
    'blues': [0, 3, 5, 6, 7, 10],
    'chromatic': list(range(12))
}

CHORD_PATTERNS = {
    'major': [0, 4, 7],
    'minor': [0, 3, 7],
    'diminished': [0, 3, 6],
    'augmented': [0, 4, 8],
    'major7': [0, 4, 7, 11],
    'minor7': [0, 3, 7, 10],
    'dominant7': [0, 4, 7, 10],
    'diminished7': [0, 3, 6, 9],
    'major9': [0, 4, 7, 11, 14],
    'minor9': [0, 3, 7, 10, 14],
    'suspended2': [0, 2, 7],
    'suspended4': [0, 5, 7],
    'add9': [0, 4, 7, 14],
    'major6': [0, 4, 7, 9],
    'minor6': [0, 3, 7, 9]
}

class MIDIEventType(Enum):
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    POLY_AFTERTOUCH = 0xA0
    CONTROL_CHANGE = 0xB0
    PROGRAM_CHANGE = 0xC0
    CHANNEL_AFTERTOUCH = 0xD0
    PITCH_BEND = 0xE0
    SYSTEM_EXCLUSIVE = 0xF0

@dataclass
class MIDINote:
    """MIDI Note representation"""
    note: int  # 0-127 MIDI note number
    velocity: int  # 0-127 velocity
    start_time: float  # Start time in seconds
    duration: float  # Duration in seconds
    channel: int = 0  # MIDI channel 0-15
    
    @property
    def frequency(self) -> float:
        """Get frequency in Hz"""
        return 440.0 * (2.0 ** ((self.note - 69) / 12.0))
    
    @property
    def note_name(self) -> str:
        """Get note name (e.g., 'C4')"""
        octave = (self.note // 12) - 1
        note_name = NOTE_NAMES[self.note % 12]
        return f"{note_name}{octave}"

@dataclass
class MIDIEvent:
    """MIDI Event representation"""
    type: MIDIEventType
    channel: int
    data1: int
    data2: int
    timestamp: float

@dataclass
class ChordDetection:
    """Detected chord information"""
    root: str
    type: str
    notes: List[str]
    confidence: float
    start_time: float
    duration: float

@dataclass
class ScaleDetection:
    """Detected scale information"""
    root: str
    type: str
    notes: List[str]
    confidence: float

class MusicTheoryAnalyzer:
    """Advanced music theory analysis"""
    
    def __init__(self):
        self.reference_pitch = 440.0  # A4
        self.tuning_tolerance = 0.02  # 2 cents tolerance
        
    def frequency_to_midi_note(self, frequency: float) -> int:
        """Convert frequency to MIDI note number"""
        if frequency <= 0:
            return 0
        return int(round(69 + 12 * math.log2(frequency / self.reference_pitch)))
    
    def midi_note_to_frequency(self, midi_note: int) -> float:
        """Convert MIDI note number to frequency"""
        return self.reference_pitch * (2.0 ** ((midi_note - 69) / 12.0))
    
    def detect_key_signature(self, notes: List[int]) -> Tuple[str, str, float]:
        """Detect key signature from note list"""
        if not notes:
            return 'C', 'major', 0.0
        
        # Count note occurrences (normalized to chromatic scale)
        note_counts = [0] * 12
        for note in notes:
            note_counts[note % 12] += 1
        
        # Normalize counts
        total = sum(note_counts)
        if total == 0:
            return 'C', 'major', 0.0
        
        note_weights = [count / total for count in note_counts]
        
        # Test against all scales
        best_match = ('C', 'major', 0.0)
        
        for root in range(12):
            for scale_name, pattern in SCALE_PATTERNS.items():
                if scale_name == 'chromatic':  # Skip chromatic
                    continue
                    
                # Calculate match score
                score = 0.0
                scale_notes = [(root + interval) % 12 for interval in pattern]
                
                for note_idx in range(12):
                    if note_idx in scale_notes:
                        score += note_weights[note_idx]
                    else:
                        score -= note_weights[note_idx] * 0.5
                
                if score > best_match[2]:
                    root_name = NOTE_NAMES[root]
                    best_match = (root_name, scale_name, score)
        
        return best_match
    
    def detect_chord_progression(self, notes_over_time: List[Tuple[float, List[int]]]) -> List[ChordDetection]:
        """Detect chord progression from notes over time"""
        chords = []
        
        for timestamp, chord_notes in notes_over_time:
            if len(chord_notes) < 3:
                continue
                
            # Normalize to root position
            normalized_notes = sorted(set(note % 12 for note in chord_notes))
            
            best_chord = self._identify_chord(normalized_notes)
            if best_chord:
                chord = ChordDetection(
                    root=best_chord[0],
                    type=best_chord[1],
                    notes=[NOTE_NAMES[note] for note in normalized_notes],
                    confidence=best_chord[2],
                    start_time=timestamp,
                    duration=1.0  # Will need to calculate actual duration
                )
                chords.append(chord)
        
        return chords
    
    def _identify_chord(self, notes: List[int]) -> Optional[Tuple[str, str, float]]:
        """Identify chord from normalized note list"""
        if len(notes) < 3:
            return None
        
        best_match = None
        
        # Try all possible roots
        for root in range(12):
            for chord_type, pattern in CHORD_PATTERNS.items():
                chord_notes = [(root + interval) % 12 for interval in pattern]
                
                # Calculate match score
                matches = sum(1 for note in notes if note in chord_notes)
                extras = len(notes) - matches
                missing = len(chord_notes) - matches
                
                # Score: reward matches, penalize extras and missing notes
                score = matches / len(chord_notes) - extras * 0.1 - missing * 0.2
                
                if score > 0.6 and (not best_match or score > best_match[2]):
                    best_match = (NOTE_NAMES[root], chord_type, score)
        
        return best_match
    
    def generate_harmonies(self, melody_notes: List[MIDINote], 
                          key: str, scale: str) -> List[List[MIDINote]]:
        """Generate harmonies for a melody"""
        if not melody_notes:
            return []
        
        # Get scale pattern
        if scale not in SCALE_PATTERNS:
            scale = 'major'
        
        root_note = NOTE_NAMES.index(key.upper())
        scale_pattern = SCALE_PATTERNS[scale]
        scale_notes = [(root_note + interval) % 12 for interval in scale_pattern]
        
        harmony_parts = [[] for _ in range(3)]  # 3 harmony parts
        
        for melody_note in melody_notes:
            melody_pitch_class = melody_note.note % 12
            
            # Find position in scale
            if melody_pitch_class in scale_notes:
                scale_degree = scale_notes.index(melody_pitch_class)
                
                # Generate third and fifth harmonies
                third_degree = (scale_degree + 2) % len(scale_notes)
                fifth_degree = (scale_degree + 4) % len(scale_notes)
                
                # Calculate actual MIDI notes (in appropriate octave)
                base_octave = melody_note.note // 12
                
                third_note = MIDINote(
                    note=base_octave * 12 + scale_notes[third_degree],
                    velocity=max(20, melody_note.velocity - 20),
                    start_time=melody_note.start_time,
                    duration=melody_note.duration,
                    channel=1
                )
                
                fifth_note = MIDINote(
                    note=base_octave * 12 + scale_notes[fifth_degree],
                    velocity=max(15, melody_note.velocity - 30),
                    start_time=melody_note.start_time,
                    duration=melody_note.duration,
                    channel=2
                )
                
                # Lower harmony (below melody)
                lower_note = MIDINote(
                    note=max(24, melody_note.note - 12 + scale_notes[(scale_degree - 2) % len(scale_notes)]),
                    velocity=max(25, melody_note.velocity - 25),
                    start_time=melody_note.start_time,
                    duration=melody_note.duration,
                    channel=3
                )
                
                harmony_parts[0].append(third_note)
                harmony_parts[1].append(fifth_note)
                harmony_parts[2].append(lower_note)
        
        return harmony_parts

class MIDIProcessor:
    """MIDI file processing and generation"""
    
    def __init__(self):
        self.ticks_per_quarter = 480
        self.tempo = 500000  # Microseconds per quarter note (120 BPM)
        
    def create_simple_midi(self, notes: List[MIDINote], filename: str) -> bool:
        """Create a simple MIDI file from note list"""
        try:
            # Simple MIDI file structure (Format 0)
            midi_data = bytearray()
            
            # Header chunk
            midi_data.extend(b'MThd')
            midi_data.extend(struct.pack('>I', 6))  # Header length
            midi_data.extend(struct.pack('>H', 0))  # Format 0
            midi_data.extend(struct.pack('>H', 1))  # One track
            midi_data.extend(struct.pack('>H', self.ticks_per_quarter))
            
            # Track chunk
            track_events = self._create_track_events(notes)
            
            midi_data.extend(b'MTrk')
            midi_data.extend(struct.pack('>I', len(track_events)))
            midi_data.extend(track_events)
            
            # Write to file
            with open(filename, 'wb') as f:
                f.write(midi_data)
            
            return True
            
        except Exception as e:
            print(f"MIDI creation error: {e}")
            return False
    
    def _create_track_events(self, notes: List[MIDINote]) -> bytearray:
        """Create MIDI track events from notes"""
        events = []
        
        # Set tempo
        events.append((0, 0xFF, 0x51, 0x03, 
                      (self.tempo >> 16) & 0xFF,
                      (self.tempo >> 8) & 0xFF,
                      self.tempo & 0xFF))
        
        # Convert notes to MIDI events
        for note in notes:
            # Note on event
            on_ticks = int(note.start_time * self.ticks_per_quarter * 2)  # Assuming 120 BPM
            events.append((on_ticks, 0x90 | note.channel, note.note, note.velocity))
            
            # Note off event
            off_ticks = int((note.start_time + note.duration) * self.ticks_per_quarter * 2)
            events.append((off_ticks, 0x80 | note.channel, note.note, 0))
        
        # Sort events by time
        events.sort(key=lambda x: x[0])
        
        # Convert to MIDI track format
        track_data = bytearray()
        last_tick = 0
        
        for event in events:
            tick = event[0]
            delta_time = tick - last_tick
            last_tick = tick
            
            # Write variable length delta time
            track_data.extend(self._write_variable_length(delta_time))
            
            # Write event
            if len(event) == 4:  # Standard MIDI event
                track_data.extend([event[1], event[2], event[3]])
            else:  # Meta event
                track_data.extend(event[1:])
        
        # End of track
        track_data.extend([0x00, 0xFF, 0x2F, 0x00])
        
        return track_data
    
    def _write_variable_length(self, value: int) -> bytearray:
        """Write variable length quantity"""
        result = bytearray()
        
        while value >= 0x80:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        
        result.append(value & 0x7F)
        return result[::-1]  # Reverse byte order
    
    def audio_to_midi(self, audio_data: bytes, sample_rate: int = 44100) -> List[MIDINote]:
        """Convert audio to MIDI notes using pitch detection"""
        # Simple pitch detection using autocorrelation
        samples = self._bytes_to_samples(audio_data)
        
        # Process in windows
        window_size = int(sample_rate * 0.05)  # 50ms windows
        hop_size = window_size // 2
        
        notes = []
        current_note = None
        
        for i in range(0, len(samples) - window_size, hop_size):
            window = samples[i:i + window_size]
            
            # Detect pitch
            frequency = self._detect_pitch_autocorr(window, sample_rate)
            
            if frequency > 80:  # Valid musical frequency
                midi_note = self._frequency_to_midi_note(frequency)
                timestamp = i / sample_rate
                
                if current_note and current_note.note == midi_note:
                    # Extend current note
                    current_note.duration = timestamp - current_note.start_time + (hop_size / sample_rate)
                else:
                    # New note
                    if current_note:
                        notes.append(current_note)
                    
                    # Calculate velocity from amplitude
                    amplitude = sum(abs(s) for s in window) / len(window)
                    velocity = min(127, max(1, int(amplitude * 127 * 4)))
                    
                    current_note = MIDINote(
                        note=midi_note,
                        velocity=velocity,
                        start_time=timestamp,
                        duration=hop_size / sample_rate
                    )
            else:
                # No pitch detected, end current note
                if current_note:
                    notes.append(current_note)
                    current_note = None
        
        # Add final note
        if current_note:
            notes.append(current_note)
        
        return notes
    
    def _detect_pitch_autocorr(self, samples: List[float], sample_rate: int) -> float:
        """Detect pitch using autocorrelation"""
        if len(samples) < 100:
            return 0.0
        
        # Autocorrelation
        correlations = []
        min_period = int(sample_rate / 1000)  # 1000 Hz max
        max_period = int(sample_rate / 80)    # 80 Hz min
        
        for lag in range(min_period, min(max_period, len(samples) // 2)):
            correlation = 0.0
            for i in range(len(samples) - lag):
                correlation += samples[i] * samples[i + lag]
            correlations.append((lag, correlation))
        
        if not correlations:
            return 0.0
        
        # Find maximum correlation
        best_lag = max(correlations, key=lambda x: x[1])
        
        if best_lag[1] > 0:
            frequency = sample_rate / best_lag[0]
            return frequency
        
        return 0.0
    
    def _frequency_to_midi_note(self, frequency: float) -> int:
        """Convert frequency to MIDI note number"""
        if frequency <= 0:
            return 60  # Middle C default
        return int(round(69 + 12 * math.log2(frequency / 440.0)))
    
    def _bytes_to_samples(self, audio_data: bytes) -> List[float]:
        """Convert audio bytes to normalized samples"""
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        return samples

class AudioMIDISync:
    """Synchronize audio and MIDI"""
    
    def __init__(self):
        self.tempo = 120  # BPM
        self.time_signature = (4, 4)
        
    def sync_audio_to_midi_tempo(self, audio_data: bytes, target_tempo: float,
                                 sample_rate: int = 44100) -> bytes:
        """Time-stretch audio to match MIDI tempo"""
        # Detect current tempo
        current_tempo = self._detect_tempo(audio_data, sample_rate)
        
        if current_tempo <= 0:
            return audio_data
        
        # Calculate stretch ratio
        stretch_ratio = target_tempo / current_tempo
        
        # Apply time stretching (simplified)
        return self._time_stretch_audio(audio_data, stretch_ratio)
    
    def _detect_tempo(self, audio_data: bytes, sample_rate: int) -> float:
        """Simple tempo detection using onset detection"""
        samples = self._bytes_to_samples(audio_data)
        
        # Calculate energy in overlapping windows
        window_size = int(sample_rate * 0.1)  # 100ms
        hop_size = window_size // 4
        
        energies = []
        for i in range(0, len(samples) - window_size, hop_size):
            window = samples[i:i + window_size]
            energy = sum(s ** 2 for s in window)
            energies.append(energy)
        
        if len(energies) < 10:
            return 0.0
        
        # Detect peaks (onsets)
        peaks = []
        threshold = sum(energies) / len(energies) * 1.5
        
        for i in range(1, len(energies) - 1):
            if (energies[i] > threshold and 
                energies[i] > energies[i-1] and 
                energies[i] > energies[i+1]):
                peaks.append(i * hop_size / sample_rate)
        
        if len(peaks) < 4:
            return 0.0
        
        # Calculate intervals and estimate tempo
        intervals = [peaks[i] - peaks[i-1] for i in range(1, len(peaks))]
        avg_interval = sum(intervals) / len(intervals)
        
        if avg_interval > 0:
            tempo = 60.0 / avg_interval
            return tempo
        
        return 0.0
    
    def _time_stretch_audio(self, audio_data: bytes, ratio: float) -> bytes:
        """Simple time stretching using sample rate manipulation"""
        samples = self._bytes_to_samples(audio_data)
        
        # Simple linear interpolation time stretching
        stretched = []
        for i in range(int(len(samples) * ratio)):
            src_index = i / ratio
            src_index_int = int(src_index)
            fraction = src_index - src_index_int
            
            if src_index_int + 1 < len(samples):
                sample = (samples[src_index_int] * (1 - fraction) + 
                         samples[src_index_int + 1] * fraction)
            else:
                sample = samples[src_index_int] if src_index_int < len(samples) else 0
            
            stretched.append(sample)
        
        # Convert back to bytes
        result = b''
        for sample in stretched:
            sample = max(-1.0, min(1.0, sample))
            sample_int = int(sample * 32767)
            result += struct.pack('<h', sample_int)
        
        return result
    
    def _bytes_to_samples(self, audio_data: bytes) -> List[float]:
        """Convert audio bytes to samples"""
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        return samples

def analyze_music_theory(audio_file: str) -> Dict[str, Any]:
    """Analyze audio file for music theory elements"""
    try:
        import wave
        
        # Load audio
        with wave.open(audio_file, 'rb') as wav:
            audio_data = wav.readframes(wav.getnframes())
            sample_rate = wav.getframerate()
        
        # Create processors
        midi_processor = MIDIProcessor()
        theory_analyzer = MusicTheoryAnalyzer()
        
        # Convert audio to MIDI notes
        print("Converting audio to MIDI notes...")
        midi_notes = midi_processor.audio_to_midi(audio_data, sample_rate)
        
        if not midi_notes:
            return {'error': 'No musical content detected'}
        
        # Analyze music theory
        print("Analyzing music theory...")
        note_numbers = [note.note for note in midi_notes]
        key_root, key_scale, key_confidence = theory_analyzer.detect_key_signature(note_numbers)
        
        # Group notes by time for chord detection
        chord_times = []
        current_time = 0
        time_window = 1.0  # 1 second windows
        
        while current_time < max(note.start_time + note.duration for note in midi_notes):
            chord_notes = [note.note for note in midi_notes 
                          if current_time <= note.start_time < current_time + time_window]
            if len(chord_notes) >= 3:
                chord_times.append((current_time, chord_notes))
            current_time += time_window
        
        chords = theory_analyzer.detect_chord_progression(chord_times)
        
        # Generate statistics
        unique_notes = set(note.note % 12 for note in midi_notes)
        note_names = [NOTE_NAMES[note] for note in sorted(unique_notes)]
        
        return {
            'detected_key': f"{key_root} {key_scale}",
            'key_confidence': key_confidence,
            'notes_used': note_names,
            'total_notes': len(midi_notes),
            'duration': max(note.start_time + note.duration for note in midi_notes),
            'chord_progression': [
                {
                    'time': chord.start_time,
                    'chord': f"{chord.root} {chord.type}",
                    'notes': chord.notes,
                    'confidence': chord.confidence
                }
                for chord in chords[:10]  # First 10 chords
            ],
            'midi_notes_detected': len(midi_notes)
        }
        
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python midi_integration.py analyze <audio.wav>")
        print("  python midi_integration.py convert <audio.wav> <output.mid>")
        print("  python midi_integration.py harmonize <audio.wav> <output.mid> [key] [scale]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "analyze":
        if len(sys.argv) != 3:
            print("Usage: python midi_integration.py analyze <audio.wav>")
            sys.exit(1)
        
        audio_file = sys.argv[2]
        result = analyze_music_theory(audio_file)
        
        if 'error' in result:
            print(f"Error: {result['error']}")
        else:
            print("Music Theory Analysis:")
            print("=" * 40)
            print(f"Detected Key: {result['detected_key']}")
            print(f"Key Confidence: {result['key_confidence']:.2f}")
            print(f"Notes Used: {', '.join(result['notes_used'])}")
            print(f"Total MIDI Notes: {result['total_notes']}")
            print(f"Duration: {result['duration']:.1f} seconds")
            
            if result['chord_progression']:
                print("\nChord Progression:")
                for chord in result['chord_progression']:
                    print(f"  {chord['time']:.1f}s: {chord['chord']} (confidence: {chord['confidence']:.2f})")
    
    elif command == "convert":
        if len(sys.argv) != 4:
            print("Usage: python midi_integration.py convert <audio.wav> <output.mid>")
            sys.exit(1)
        
        audio_file = sys.argv[2]
        midi_file = sys.argv[3]
        
        try:
            import wave
            
            # Load audio
            with wave.open(audio_file, 'rb') as wav:
                audio_data = wav.readframes(wav.getnframes())
                sample_rate = wav.getframerate()
            
            # Convert to MIDI
            processor = MIDIProcessor()
            midi_notes = processor.audio_to_midi(audio_data, sample_rate)
            
            if midi_notes:
                success = processor.create_simple_midi(midi_notes, midi_file)
                
                if success:
                    print(f"Converted {len(midi_notes)} notes to MIDI file: {midi_file}")
                else:
                    print("Failed to create MIDI file")
            else:
                print("No musical content detected in audio")
        
        except Exception as e:
            print(f"Conversion error: {e}")
    
    elif command == "harmonize":
        if len(sys.argv) < 4:
            print("Usage: python midi_integration.py harmonize <audio.wav> <output.mid> [key] [scale]")
            sys.exit(1)
        
        audio_file = sys.argv[2]
        midi_file = sys.argv[3]
        key = sys.argv[4] if len(sys.argv) > 4 else 'C'
        scale = sys.argv[5] if len(sys.argv) > 5 else 'major'
        
        try:
            import wave
            
            # Load and convert audio
            with wave.open(audio_file, 'rb') as wav:
                audio_data = wav.readframes(wav.getnframes())
                sample_rate = wav.getframerate()
            
            # Convert to MIDI and generate harmonies
            processor = MIDIProcessor()
            theory = MusicTheoryAnalyzer()
            
            melody_notes = processor.audio_to_midi(audio_data, sample_rate)
            
            if melody_notes:
                # Generate harmonies
                harmonies = theory.generate_harmonies(melody_notes, key, scale)
                
                # Combine melody and harmonies
                all_notes = melody_notes[:]
                for harmony_part in harmonies:
                    all_notes.extend(harmony_part)
                
                # Create MIDI file
                success = processor.create_simple_midi(all_notes, midi_file)
                
                if success:
                    total_notes = len(melody_notes) + sum(len(h) for h in harmonies)
                    print(f"Created harmonized MIDI with {total_notes} notes: {midi_file}")
                    print(f"Key: {key} {scale}")
                    print(f"Melody notes: {len(melody_notes)}")
                    print(f"Harmony parts: {len(harmonies)} parts")
                else:
                    print("Failed to create harmonized MIDI file")
            else:
                print("No musical content detected in audio")
        
        except Exception as e:
            print(f"Harmonization error: {e}")
    
    else:
        print(f"Unknown command: {command}")