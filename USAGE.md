# Chameleon Audio System - Usage Guide

A practical, lightweight audio processing system with no external dependencies.

## Quick Start

### Basic Usage

```bash
# Show file information
python chameleon_cli.py info audio.wav

# Convert and normalize audio
python chameleon_cli.py convert audio.wav --normalize --output clean.wav

# Mix multiple files
python chameleon_cli.py mix "intro.wav,content.wav,outro.wav" --output podcast.wav

# Visualize audio levels
python chameleon_cli.py visualize audio.wav --type levels

# Record audio (or generate test tone)
python chameleon_cli.py record --test-tone --frequency 440 --duration 5 --output tone.wav

# Batch process directory
python chameleon_cli.py batch /audio/folder --operation normalize --output /processed/
```

## Features

### Audio Processing
- **Noise Reduction**: Spectral gating for noise removal
- **Normalization**: Peak and RMS level adjustment
- **Compression**: Dynamic range compression
- **Voice Activity Detection**: Automatic speech segment detection
- **Format Detection**: Auto-detect WAV, MP3, FLAC, OGG, AIFF, AU

### Real-time Processing
- **Stream Processing**: Real-time audio pipeline with 11x+ performance
- **Effect Chains**: Configurable processing pipelines
- **Presets**: Voice enhancement, music enhancement, podcast processing

### Audio Mixing
- **Multi-track Mixing**: Combine multiple audio files
- **Timing Control**: Precise start times and overlaps
- **Auto-leveling**: Automatic volume adjustment
- **Fades**: Configurable fade-in/out

### Visualization
- **Text-based Graphs**: Waveform, spectrum, level meters
- **Analysis Reports**: Comprehensive audio analysis
- **Voice Activity**: Visual representation of speech segments

### Batch Processing
- **Directory Processing**: Process entire folders
- **Smart Detection**: Automatic format recognition
- **Parallel Processing**: Multi-threaded for speed
- **Progress Tracking**: Real-time status updates

## Core Modules

### chameleon.py
Main audio processor with optimized operations:
```python
from chameleon import AudioProcessor

processor = AudioProcessor()
samples, info = processor.load_wav("audio.wav")
normalized = processor.normalize(samples)
denoised = processor.reduce_noise(samples, noise_floor_db=-40)
```

### audio_mixer.py
Simple audio mixing:
```python
from audio_mixer import SimpleAudioMixer

mixer = SimpleAudioMixer()
mixer.add_track("intro.wav", volume=1.0, start_time=0.0)
mixer.add_track("content.wav", volume=0.8, start_time=2.0)
mixer.export_mix("output.wav")
```

### realtime_processor.py
Real-time audio processing:
```python
from realtime_processor import StreamProcessor, RealtimeEffects

processor = StreamProcessor()
processor.pipeline = RealtimeEffects.create_voice_enhancer()
processor.start()
```

### batch_processor.py
Batch operations:
```python
from batch_processor import BatchOperations

# Normalize all files in directory
BatchOperations.normalize_directory("/audio/folder", "/output/folder")
```

## Performance

- **Cache Optimization**: 90%+ cache hit rate for repeated operations
- **Memory Efficient**: Chunk-based processing for large files
- **Parallel Processing**: Multi-threaded batch operations
- **Real-time Capable**: 11x+ real-time performance factor

## Requirements

- Python 3.6+
- No external dependencies for core functionality
- Optional: NumPy for enhanced performance

## Architecture

```
chameleon_cli.py     # Unified command-line interface
├── chameleon.py     # Core audio processor
├── audio_mixer.py   # Multi-track mixing
├── audio_visualizer.py # Text-based visualization
├── audio_recorder.py   # Recording and tone generation
├── batch_processor.py  # Batch operations
├── realtime_processor.py # Stream processing
├── audio_analyzer.py   # Analysis functions
├── audio_converter.py  # Format conversion
└── audio_effects.py    # Audio effects
```

## Examples

### Voice Enhancement Pipeline
```bash
# Real-time voice processing
python chameleon_cli.py realtime --preset voice

# Batch voice enhancement
python chameleon_cli.py batch /recordings --operation denoise
```

### Podcast Production
```python
from audio_mixer import AutoMixer

mixer = AutoMixer()
mixer.create_podcast_mix(
    intro_file="intro.wav",
    content_files=["episode1.wav", "episode2.wav"],
    outro_file="outro.wav",
    output_path="podcast.wav"
)
```

### Audio Analysis
```bash
# Generate comprehensive report
python chameleon_cli.py visualize audio.wav --report --output analysis.txt

# Quick level check
python chameleon_cli.py visualize audio.wav --type levels
```

## Tips

1. **Use batch processing** for multiple files to leverage parallel processing
2. **Enable caching** by processing similar files together
3. **Use presets** for real-time processing to get optimized effect chains
4. **Check file info** before processing to understand audio characteristics
5. **Use normalization** as final step to ensure consistent levels

## Troubleshooting

- **Import errors**: Ensure all module files are in the same directory
- **Performance issues**: Use NumPy if available for faster processing
- **Memory issues**: Process large files in chunks using batch mode
- **Recording fails**: System recording tools may not be available, use test tone generation instead