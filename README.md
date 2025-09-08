# Chameleon Audio Processing Framework

Modern, efficient audio processing framework with comprehensive format support and professional-grade features.

## Features

### Core Audio Processing
- High-quality sine wave generation with LUT optimization
- Professional audio normalization and silence trimming
- Advanced mixing and volume adjustment
- Real-time audio processing capabilities
- Performance-optimized algorithms

### Format Support
- **Input/Output**: WAV, MP3, FLAC, OGG, AAC, M4A
- **Multiple backends**: FFmpeg, SoX, soundfile, pydub
- **Automatic fallback**: Uses best available backend
- **Quality control**: Low, medium, high conversion settings

### Batch Processing
- **Parallel processing**: Multi-threaded batch operations
- **Progress tracking**: Real-time progress indicators with ETA
- **Bulk conversion**: Convert multiple files simultaneously
- **Pattern matching**: Wildcard file selection support
- **Error resilience**: Continues processing on individual failures

### Configuration Profiles
- **Built-in presets**: Podcast, Music, Game Audio, Quick, Archive
- **Custom profiles**: Create and save your own configurations
- **Profile management**: Import, export, and share profiles
- **Context switching**: Switch between different use cases instantly

### Advanced Features
- **Structured logging**: JSON-formatted logs with session tracking
- **Performance monitoring**: Detailed timing and resource usage
- **System diagnostics**: Health checks and optimization recommendations
- **Memory optimization**: Intelligent caching and resource management
- **GUI interface**: User-friendly desktop application

## Installation

### Basic Installation
```bash
pip install -r requirements.txt
```

### Full Installation (Recommended)
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install ffmpeg sox

# Install system dependencies (macOS)
brew install ffmpeg sox
```

### Development Installation
```bash
pip install -e .
```

## Quick Start

### Command Line Interface

#### Basic Operations
```bash
# System status and capabilities
chameleon status

# Generate test tone
chameleon tone -f 440 -d 2.0 -o test_tone.wav

# Analyze audio file
chameleon analyze input.wav

# Convert audio format
chameleon convert input.wav -f mp3 -q high
```

#### Batch Processing
```bash
# Generate multiple tones
chameleon advanced-batch tones -f "220,440,880,1320" -d 1.5 -o ./tones

# Batch convert files
chameleon batch-convert *.wav -f mp3 -o ./converted -q high

# Analyze multiple files
chameleon advanced-batch analyze *.wav *.mp3 *.flac
```

#### Profile Management
```bash
# List available profiles
chameleon profile list

# Set active profile
chameleon profile set music

# Create custom profile
chameleon profile create my-podcast -d "My podcast setup" -t podcast

# Show profile details
chameleon profile show music
```

#### Audio Processing
```bash
# Normalize audio
chameleon process input.wav --normalize --amplitude 0.8

# Trim silence and normalize
chameleon process input.wav --trim --normalize -o clean.wav

# Apply multiple effects
chameleon process input.wav --volume 1.2 --normalize --trim -o processed.wav
```

### GUI Interface
```bash
# Launch desktop application
chameleon-gui
```

### Python API
```python
import chameleon

# Generate audio
audio_data = chameleon.generate_sine_wave(440, 1.0, 44100)
chameleon.write_wav_file('tone.wav', audio_data)

# Convert formats
from chameleon.audio_formats import convert_audio_file
convert_audio_file('input.wav', 'output.mp3', quality='high')

# Batch processing
from chameleon.batch_processor import batch_generate_tones
result = batch_generate_tones([220, 440, 880], 1.0, 44100, './output')

# Profile management
from chameleon.profiles import get_profile_manager
manager = get_profile_manager()
manager.set_active_profile('music')
```

## Architecture

### Core Modules
- **core.py** - Essential audio processing functions (982 lines)
- **logger.py** - Structured logging system
- **audio_formats.py** - Multi-format conversion support
- **batch_processor.py** - Parallel processing with progress tracking
- **profiles.py** - Configuration management system
- **cli.py** - Command-line interface
- **app.py** - GUI desktop application
- **perf.py** - Performance optimization and monitoring

### Design Principles
- **Functional programming** - Pure functions for audio processing
- **Modular design** - Independent, composable components  
- **Performance first** - Optimized algorithms and memory usage
- **Error resilience** - Robust error handling throughout
- **Extensible** - Plugin-ready architecture

## Configuration Profiles

### Built-in Profiles

#### Podcast
- **Sample rate**: 44.1 kHz, Mono, MP3 output
- **Optimization**: Voice recording, moderate compression
- **Use case**: Podcast production and voice content

#### Music
- **Sample rate**: 48 kHz, Stereo, FLAC output  
- **Optimization**: High quality, maximum fidelity
- **Use case**: Music production and mastering

#### Game Audio
- **Sample rate**: 44.1 kHz, Mono, OGG output
- **Optimization**: Small file sizes, fast processing
- **Use case**: Game sound effects and interactive audio

#### Quick
- **Sample rate**: 22 kHz, Mono, WAV output
- **Optimization**: Maximum speed, minimal resources
- **Use case**: Testing and rapid prototyping

#### Archive
- **Sample rate**: 96 kHz, Stereo, FLAC output
- **Optimization**: Preservation quality, no compression
- **Use case**: Digital archiving and restoration

### Custom Profiles
Create profiles optimized for your specific workflow:
```bash
chameleon profile create broadcast -d "Radio broadcast" -t podcast
# Then customize settings as needed
```

## Performance

### Benchmarks
- **Sine generation**: 10x faster with LUT optimization
- **Batch processing**: Linear scalability with CPU cores
- **Format conversion**: Automatic backend selection for optimal speed
- **Memory usage**: Intelligent caching and resource management

### Optimization Features
- **Lookup table generation** - Pre-computed sine waves
- **Parallel processing** - Multi-threaded batch operations
- **Memory pooling** - Reduced allocation overhead
- **Adaptive caching** - Frequency-based cache optimization

## Testing

```bash
# Run comprehensive test suite
python test_chameleon.py

# Run system diagnostics
chameleon diagnostics health
chameleon diagnostics performance
chameleon diagnostics comprehensive
```

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Make changes and test: `python test_chameleon.py`
4. Commit changes: `git commit -m "Add feature"`
5. Push branch: `git push origin feature-name`
6. Create pull request

### Development Guidelines
- Follow functional programming principles
- Add comprehensive tests for new features
- Update documentation for API changes
- Maintain performance benchmarks

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: Full API reference in source code
- **Issues**: Report bugs via GitHub issues
- **Performance**: Use built-in diagnostics for optimization

*Chameleon - Clean, Simple, Powerful Audio Processing*