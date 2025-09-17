# Chameleon Audio System

Lightweight, practical audio processing toolkit for WAV files.

## Features

### Core Audio Processing
- **Normalize** - Adjust audio to optimal levels
- **Amplify** - Apply gain with clipping protection
- **Fade** - Add fade in/out effects
- **Trim** - Remove silence from start/end
- **Reverse** - Reverse audio playback
- **Speed** - Change playback speed
- **Mix** - Combine two audio signals

### Audio Effects
- **Echo** - Add echo/delay
- **Chorus** - Create richer sound
- **Distortion** - Soft clipping distortion
- **Filters** - Low-pass and high-pass filtering
- **Compressor** - Dynamic range compression
- **Tremolo** - Amplitude modulation
- **Pitch Shift** - Change pitch without speed
- **Noise Gate** - Remove background noise
- **Auto Gain** - Automatic level adjustment

### Format Conversion
- **Resample** - Change sample rate
- **Channel conversion** - Mono/stereo conversion
- **Bit depth** - Convert between bit depths
- **WAV/RAW** - Convert between formats
- **Concatenate** - Join multiple files

### Batch Processing
- Process entire directories
- Parallel processing support
- JSON configuration files
- Processing chains
- Detailed reports

## Installation

```bash
# Core functionality (no dependencies)
python3 chameleon.py --help

# Optional dependencies for enhanced features
pip install -r requirements.txt
```

## Usage

### Command Line

```bash
# Get file information
python3 chameleon.py info input.wav

# Process single file
python3 chameleon.py process input.wav --operation normalize
python3 chameleon.py process input.wav --operation amplify --gain 6
python3 chameleon.py process input.wav --operation fade --fade-in 1000 --fade-out 2000

# Batch processing
python3 chameleon.py batch /audio/folder --operation normalize --output /output/folder

# Apply effects
python3 chameleon.py process input.wav --operation echo --mix-with drums.wav
```

### Python API

```python
from chameleon import AudioProcessor
from audio_effects import AudioEffects
from audio_converter import AudioConverter

# Basic processing
processor = AudioProcessor()
samples, info = processor.load_wav('input.wav')
normalized = processor.normalize(samples)
processor.save_wav('output.wav', normalized)

# Apply effects
effects = AudioEffects()
echoed = effects.echo(samples, delay_ms=500, decay=0.5)
filtered = effects.low_pass_filter(samples, cutoff_hz=1000)

# Convert formats
converter = AudioConverter()
resampled = converter.resample(samples, 44100, 22050)
```

## File Structure

- `chameleon.py` - Main audio processor with core functions
- `audio_effects.py` - DSP effects collection
- `audio_converter.py` - Format conversion utilities
- `chameleon.py` - Main processor with batch processing support
- `test_audio.py` - Test suite

## Testing

```bash
python3 test_audio.py
```

## Performance

- Optimized for speed with array operations
- Parallel batch processing support
- Memory-efficient streaming for large files
- Typical processing: ~100x realtime on modern CPUs

## Supported Formats

- WAV files (8/16/24/32-bit)
- Raw PCM data
- Mono and stereo
- Sample rates: 8kHz - 192kHz

## License

MIT