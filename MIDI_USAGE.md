# Chameleon MIDI Features Usage Guide

## Overview

Chameleon includes MIDI analysis and musical intelligence capabilities. The system can extract MIDI from audio, analyze musical content, and generate compositions.

## Quick Start

### Generate a Simple Scale
```bash
python main.py midi generate --output scale.mid
```

### Analyze Audio for Musical Content
```bash
python main.py midi analyze --input audio.wav
```

### Create a Composition
```bash
python main.py midi compose --output song.mid --tempo 120 --length 8
```

## Features

### Audio-to-MIDI Conversion
Extract MIDI notes from audio files using pitch detection:

```python
from midi_analysis import MIDIAnalyzer, MIDIConfig

config = MIDIConfig(tempo=120.0)
analyzer = MIDIAnalyzer(config)

# Convert audio to list format
audio_list = audio_data.tolist()
notes = analyzer.parse_midi_from_audio(audio_list, sample_rate)
```

### Musical Analysis

#### Key Detection
Uses the Krumhansl-Schmuckler algorithm for key identification:
```python
detected_key = analyzer.detect_key(notes)
print(f"Key: {detected_key.tonic} {detected_key.mode}")
print(f"Confidence: {detected_key.confidence:.3f}")
```

#### Chord Analysis
Chord detection with confidence scoring:
```python
chords = analyzer.detect_chords(notes, window_size=1.0)
for chord in chords:
    print(f"{chord.name} (confidence: {chord.confidence:.3f})")
```

#### Harmonic Analysis
Roman numeral analysis and progression identification:
```python
harmony = analyzer.analyze_harmony(chords, key)
print(f"Progression: {harmony['analysis']}")
for chord_info in harmony['progression']:
    print(f"{chord_info['chord']} ({chord_info['roman']})")
```

### Composition Tools

#### Chord Progression Suggestions
```python
from midi_analysis import MIDIComposer

composer = MIDIComposer(config)
suggestions = composer.suggest_next_chord(current_chords, key)
for chord, probability in suggestions:
    print(f"{chord}: {probability:.2f}")
```

#### Melody Generation
```python
melody = composer.generate_melody(chords, key, length=8.0)
print(f"Generated {len(melody)} melody notes")
```

### MIDI File Export
```python
success = analyzer.generate_midi_file(notes, "output.mid")
if success:
    print("MIDI file created successfully")
```

## CLI Commands

### Extract MIDI from Audio
```bash
python main.py midi extract --input audio.wav --output notes.mid
```

### Analyze Musical Content
```bash
python main.py midi analyze --input audio.wav
```

Shows:
- Detected musical key
- Chord progressions
- Harmonic analysis
- Tempo estimation
- Composition suggestions

### Generate Compositions
```bash
python main.py midi compose --output composition.mid --tempo 120 --length 16
```

### Create MIDI Demos
```bash
python main.py midi generate --output demo.mid
```

## Supported Chord Types

The system recognizes:
- **Major**: major, maj7, maj9, 6, add9
- **Minor**: minor, min7, min9, min6
- **Dominant**: dom7
- **Diminished**: dim
- **Augmented**: aug
- **Suspended**: sus2, sus4

## Musical Keys

Supports all 24 major and minor keys with confidence scoring:
- **Major keys**: C, G, D, A, E, B, F#, C#, F, Bb, Eb, Ab
- **Minor keys**: Am, Em, Bm, F#m, C#m, G#m, D#m, A#m, Dm, Gm, Cm, Fm

## Configuration Options

### MIDIConfig Parameters
```python
config = MIDIConfig(
    tempo=120.0,                    # BPM
    time_signature=(4, 4),          # Time signature
    key_signature="C",              # Default key
    scale_type="major",             # major/minor
    quantization=16,                # Note quantization
    velocity_threshold=64,          # Note velocity threshold
    chord_detection_threshold=0.3,  # Chord confidence threshold
    harmony_analysis_depth=4,       # Analysis depth
    enable_composition_ai=True      # Enable AI features
)
```

## Output Formats

### MIDI Notes
Each note includes:
- **Pitch**: MIDI note number (0-127)
- **Velocity**: Note velocity (0-127)
- **Start Time**: Note onset in seconds
- **Duration**: Note length in seconds
- **Channel**: MIDI channel (0-15)

### Analysis Results
JSON format including:
- Note count and timing
- Key detection results
- Chord progressions
- Harmonic analysis
- Rhythm analysis
- Composition suggestions

## Example Workflow

```python
# 1. Load and analyze audio
audio, sr = load_audio("song.wav")
analyzer = MIDIAnalyzer()

# 2. Extract MIDI
notes = analyzer.parse_midi_from_audio(audio, sr)

# 3. Analyze musical content
key = analyzer.detect_key(notes)
chords = analyzer.detect_chords(notes)
harmony = analyzer.analyze_harmony(chords, key)

# 4. Generate suggestions
composer = MIDIComposer()
next_chords = composer.suggest_next_chord(chords, key)

# 5. Export results
analyzer.generate_midi_file(notes, "extracted.mid")
```

## Technical Notes

### Audio Processing
- Autocorrelation-based pitch detection
- Energy-based onset detection
- Configurable analysis windows
- Robust to noise and harmonics

### Music Theory
- Krumhansl-Schmuckler key profiles
- Circle of fifths relationships
- Common progression patterns
- Modal interchange support

### Composition
- Markov chain-based chord suggestions
- Scale-aware melody generation
- Rhythm pattern analysis
- Style-based parameter adjustment

## Performance Tips

1. **Quality Audio**: Higher quality input produces better MIDI extraction
2. **Monophonic Sources**: Single instrument tracks work best for pitch detection
3. **Clean Recordings**: Minimal background noise improves accuracy
4. **Moderate Tempo**: 80-140 BPM analyzes most accurately

## Requirements

- Python 3.8+
- NumPy (for audio analysis)
- Mido (for MIDI file generation)

Install with:
```bash
pip install numpy mido
```

## Integration

The MIDI system integrates with Chameleon's other features:
- Batch processing for multiple files
- JSON output for automation
- Plugin system for custom analysis
- API server for remote operations
