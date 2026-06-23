# Chameleon Quick Start Guide

## Installation

### Basic Setup (5 minutes)

```bash
# Clone or download the project
cd Chameleon

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

Chameleon ships in two honest tiers — pick one:

**1. Default — WAV only, zero third-party dependencies.** The core analyze/normalize/
batch/MIDI CLI runs on the Python standard library alone. Nothing to install.

```bash
# Optional: install the recommended (still small) runtime deps
pip install -r requirements.txt
```

**2. `[audio]` extra — adds MP3 / FLAC / OGG input.** Installs numpy/scipy/librosa/
soundfile so the loader can decode compressed formats:

```bash
pip install -e .[audio]
```

> Without the `[audio]` extra, Chameleon is genuinely WAV-only and will report
> `Unsupported file type` for an `.mp3` — it does not pretend otherwise.

## First Steps

### 1. Validate Installation

```bash
# Test basic functionality
python validation_test.py
```

### 2. Analyze a WAV File

```bash
# Quick file info
python audio_utils.py /path/to/file.wav

# Detailed analysis
python main.py analyze /path/to/file.wav
```

### 3. Basic Processing

```bash
# Normalize audio
python main.py process --normalize /path/to/input.wav

# Batch processing
python main.py batch /path/to/directory/ normalize --output-dir /path/to/output/
```

### 4. Working with MP3 / FLAC (optional)

Requires the `[audio]` extra (`pip install -e .[audio]`). Once installed, the same
commands accept compressed input:

```bash
# Analyze an MP3 or FLAC directly
python main.py analyze /path/to/song.mp3
python main.py analyze /path/to/track.flac
```

**Input vs. output — what is guaranteed:**

| Direction | Default install | With `[audio]` |
|-----------|-----------------|----------------|
| Read / `analyze` | WAV | WAV, MP3, FLAC, OGG, AIFF, M4A |
| Write / `process` output | WAV | WAV, FLAC |

Processing (`--normalize`, etc.) writes **WAV by default and FLAC when `[audio]` is
installed**. MP3 *output* is intentionally not promised — it depends on your local
libsndfile version, so the tool falls back to WAV rather than failing silently.

## Common Tasks

### File Analysis

```bash
# Basic info
python audio_utils.py test.wav

# Detailed analysis with export
python main.py analyze test.wav --detailed --export results.json
```

### Audio Processing

```bash
# Normalize
python main.py process --normalize input.wav

# Remove noise
python main.py process --denoise input.wav

# Convert format/sample rate
python main.py process --convert --convert-sample-rate 48000 input.wav

# Multiple operations
python main.py process --normalize --denoise input.wav --output-dir processed/
```

### Batch Operations

```bash
# Process all WAV files in directory
python main.py batch /audio/directory/ normalize

# Recursive processing
python main.py batch /audio/directory/ normalize --recursive

# Preview changes (dry run)
python main.py batch /audio/directory/ normalize --dry-run
```

### MIDI Features

```bash
# Extract MIDI from audio
python main.py midi extract --input audio.wav --output notes.mid

# Analyze musical content
python main.py midi analyze --input audio.wav

# Generate composition
python main.py midi compose --output song.mid --tempo 120
```

## Configuration

### Environment Variables

```bash
# Set log directory
export CHAMELEON_LOG_DIR=/custom/log/path

# Set trusted directories
export CHAMELEON_TRUSTED_ROOTS=/trusted/dir1:/trusted/dir2

# Adjust chunk size for performance
export CHAMELEON_CHUNK_SIZE=131072

# Set max worker threads
export CHAMELEON_MAX_WORKERS=8
```

### Performance Tuning

```bash
# Disable parallel processing
python main.py --no-parallel process --normalize input.wav

# Limit workers
python main.py --max-workers 4 batch /directory/ normalize
```

## Testing

### Run Tests

```bash
# Basic validation
python validation_test.py

# Core functionality tests
python test_core.py
```

### Create Test Files

```bash
# Generate test WAV file
python -c "
from validation_test import create_test_wav
create_test_wav('test.wav', frequency=440.0, duration=2.0)
"
```

## Plugin System

### List Plugins

```bash
# Show available plugins
python main.py plugins list

# Audit plugin security
python main.py plugins audit
```

### Custom Plugin Directory

```bash
python main.py plugins list --directory /path/to/plugins/
```

## API Server

### Start Server

```bash
# Basic server
python main.py server

# Custom host and port
python main.py server --host 0.0.0.0 --port 8080

# Multiple workers
python main.py server --workers 8
```

## Troubleshooting

### Common Issues

**Import errors:**
```bash
# Install optional dependencies
pip install numpy scipy soundfile librosa
```

**Permission errors:**
```bash
# Use absolute paths
python main.py analyze /absolute/path/to/file.wav

# Check trusted directories
echo $CHAMELEON_TRUSTED_ROOTS
```

**File size errors:**
```bash
# Check file size (max 500MB)
ls -lh file.wav

# Split large files before processing
```

### Getting Help

```bash
# General help
python main.py --help

# Command-specific help
python main.py analyze --help
python main.py process --help
python main.py batch --help
```

## Best Practices

### File Paths
- Always use absolute paths
- Avoid spaces and special characters in filenames
- Check file permissions before processing

### Performance
- Use batch processing for multiple files
- Enable parallel processing (default)
- Adjust worker count based on CPU cores
- Use dry-run to preview operations

### Security
- Only process files from trusted directories
- Verify file integrity before processing
- Review plugin code before installation
- Check audit logs regularly

## Next Steps

1. Read [README.md](README.md) for detailed features
2. Check [MIDI_USAGE.md](MIDI_USAGE.md) for MIDI features
3. Review [CHANGELOG.md](CHANGELOG.md) for version history
4. Explore example workflows in documentation

## Examples

### Complete Workflow

```bash
# 1. Validate file
python audio_utils.py input.wav

# 2. Analyze content
python main.py analyze input.wav --detailed

# 3. Process with multiple operations
python main.py process --normalize --denoise input.wav --output-dir processed/

# 4. Batch process similar files
python main.py batch /audio/directory/ normalize --output-dir /output/

# 5. Generate report
python main.py analyze processed/*.wav --export report.json
```

### MIDI Workflow

```bash
# 1. Extract MIDI from audio
python main.py midi extract --input song.wav --output notes.mid

# 2. Analyze musical content
python main.py midi analyze --input song.wav

# 3. Generate new composition
python main.py midi compose --output new_song.mid --tempo 120 --length 16
```

## Support

- GitHub Issues: Report bugs and request features
- Documentation: Check docs/ directory
- Community: Join discussions for help

## Resources

- Main documentation: [README.md](README.md)
- MIDI guide: [MIDI_USAGE.md](MIDI_USAGE.md)
- Change log: [CHANGELOG.md](CHANGELOG.md)
- License: [LICENSE](LICENSE)
