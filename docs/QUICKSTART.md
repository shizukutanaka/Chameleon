# Chameleon Audio System - Quick Start Guide

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/chameleon.git
cd chameleon

# No installation required for basic usage!
# The core system uses only Python standard library

# Optional: Install additional dependencies for monitoring
pip install -r requirements.txt
```

## Basic Usage in 30 Seconds

### 1. Process a Single File

```bash
# Normalize audio volume
python3 chameleon.py process input.wav -o output.wav --operation normalize

# Add echo effect
python3 chameleon.py process input.wav -o output.wav --operation echo

# Convert sample rate
python3 chameleon.py convert input.wav -o output_22k.wav --sample-rate 22050
```

### 2. Batch Processing

```bash
# Process all WAV files in a directory
python3 chameleon.py batch ./audio_files -o ./processed --operation normalize
```

## Common Audio Operations

### Volume & Dynamics

```bash
# Normalize to 95% peak
python3 chameleon.py process input.wav -o normalized.wav --operation normalize --peak 0.95

# Amplify by 6dB
python3 chameleon.py process input.wav -o louder.wav --operation amplify --gain 6

# Compress dynamic range
python3 chameleon.py process input.wav -o compressed.wav --operation compress
```

### Effects

```bash
# Add echo/delay
python3 chameleon.py process input.wav -o echo.wav --operation echo --delay 300 --decay 0.5

# Add chorus
python3 chameleon.py process input.wav -o chorus.wav --operation chorus --depth 0.3

# Pitch shift
python3 chameleon.py process input.wav -o pitched.wav --operation pitch --factor 1.2
```

### Editing

```bash
# Trim silence
python3 chameleon.py process input.wav -o trimmed.wav --operation trim --threshold -40

# Add fade in/out
python3 chameleon.py process input.wav -o faded.wav --operation fade --fade-in 500 --fade-out 1000

# Reverse audio
python3 chameleon.py process input.wav -o reversed.wav --operation reverse
```

## Python API Usage

### Basic Example

```python
from chameleon import AudioProcessor

# Initialize processor
processor = AudioProcessor()

# Load audio
samples, info = processor.load_wav('input.wav')

# Apply processing
normalized = processor.normalize(samples, target_peak=0.95)

# Save result
processor.save_wav('output.wav', normalized, info['sample_rate'])
```

### Adding Effects

```python
from audio_effects import AudioEffects

effects = AudioEffects()

# Load audio
samples, info = processor.load_wav('input.wav')

# Apply effects chain
result = effects.echo(samples, info['sample_rate'], delay_ms=300, decay=0.5)
result = effects.chorus(result, info['sample_rate'], depth=0.3)
result = effects.compressor(result, threshold=0.7, ratio=0.5)

# Save
processor.save_wav('with_effects.wav', result, info['sample_rate'])
```

### Real-time Analysis

```python
from audio_analyzer import AudioAnalyzer

analyzer = AudioAnalyzer()

# Load audio
samples, info = processor.load_wav('input.wav')

# Get audio properties
rms = analyzer.get_rms(samples)
peak = analyzer.get_peak_amplitude(samples)
dominant_freq = analyzer.find_dominant_frequency(samples, info['sample_rate'])

print(f"RMS Level: {rms}")
print(f"Peak: {peak}")
print(f"Dominant Frequency: {dominant_freq} Hz")
```

## Batch Processing with Configuration

Create a `batch_config.json`:

```json
{
  "input_dir": "./raw_audio",
  "output_dir": "./processed",
  "operations": [
    {"type": "normalize", "params": {"peak": 0.9}},
    {"type": "echo", "params": {"delay_ms": 200, "decay": 0.4}},
    {"type": "compress", "params": {"threshold": 0.7}}
  ],
  "parallel": true,
  "num_workers": 4
}
```

Run batch processing:

```bash
python3 chameleon.py batch ./raw_audio -o ./processed --parallel
```

## GUI Interface

Launch the graphical interface:

```bash
python3 audio_gui.py
```

Features:
- Drag & drop file loading
- Real-time waveform visualization
- Interactive parameter controls
- Live preview of effects
- Batch processing queue

## Performance Tips

1. **Use optimized module for large files:**
   ```python
   from audio_optimized import OptimizedProcessor
   processor = OptimizedProcessor()
   ```

2. **Enable parallel processing for batch operations:**
   ```python
   from batch_processor_optimized import OptimizedBatchProcessor
   batch = OptimizedBatchProcessor(num_workers=4)
   ```

3. **Stream processing for real-time applications:**
   ```python
   from audio_stream import AudioStream
   stream = AudioStream(buffer_size=1024)
   ```

## Common Use Cases

### Podcast Processing
```bash
# Clean up voice recording
python3 chameleon.py process podcast.wav -o clean.wav \
  --operation chain \
  --trim-silence -40 \
  --normalize 0.95 \
  --compress 0.7 \
  --noise-gate 0.02
```

### Music Mastering
```python
# Master a track
samples = processor.normalize(samples, 0.9)
samples = effects.compressor(samples, threshold=0.8, ratio=0.3)
samples = effects.high_pass_filter(samples, sr, cutoff=80)
samples = processor.fade(samples, sr, fade_in=100, fade_out=500)
```

### Sound Design
```python
# Create complex sound effect
base = processor.generate_tone(440, duration=2.0)
base = effects.distortion(base, amount=0.3)
base = effects.echo(base, sr, delay_ms=150, decay=0.6)
base = effects.tremolo(base, sr, rate=8, depth=0.5)
```

## Troubleshooting

### No audio output
- Check input file format (WAV required)
- Verify sample rate compatibility
- Ensure output directory exists

### Poor quality
- Use higher sample rates (44100 Hz recommended)
- Avoid excessive gain/amplification
- Apply effects in proper order (EQ → Compression → Effects)

### Performance issues
- Install numpy for optimized operations: `pip install numpy`
- Use batch processing for multiple files
- Enable parallel processing when available

## Next Steps

- Run examples: `python3 examples/basic_usage.py`
- Run benchmarks: `python3 scripts/benchmark.py`
- Read full documentation: `docs/README.md`
- Explore advanced features in `examples/advanced_demo.py`

## Support

For issues or questions:
- GitHub Issues: [github.com/yourusername/chameleon/issues]
- Documentation: [docs/]
- Examples: [examples/]