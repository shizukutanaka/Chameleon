# Chameleon Audio Processing System

A WAV-focused audio processing CLI with a path-validation security layer.

## Overview

Chameleon is a WAV audio processing toolkit. Its core (analysis, normalization,
batch processing, MIDI analysis) runs on the Python standard library alone, with
a consistent path-validation security layer. Heavier capabilities (advanced
spectral/ML processing, real-time streaming, the REST API) are opt-in and depend
on optional packages — see [Configuration](#configuration).

**Status:** Beta — the standard-library CLI is stable; the REST API and
real-time streaming require optional dependencies.
**License:** MIT
**Platform Support:** Linux, macOS, Windows

## Features

### Core Capabilities
- Audio analysis (duration, sample rate, bit depth, peak/RMS levels)
- Audio processing (normalization, noise reduction, format conversion)
- Batch operations with parallel processing
- MIDI extraction and analysis
- Real-time audio streaming
- Plugin system for extensibility

### Security
- Path validation and sanitization (trusted-root enforcement)
- File size limits (500MB default)
- Audit logging for API operations
- Rate limiting for API endpoints
- Sandboxed plugin execution with AST import whitelisting

### Performance
- Parallel batch processing across multiple worker threads
- Memory-efficient chunked/streaming processing for large files
- In-memory caching with LRU eviction
- Configurable worker threads

### Reliability
- Graceful degradation when optional dependencies are unavailable
- Comprehensive error handling
- Health-check endpoint for orchestration
- Health checks and metrics

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/shizukutanaka/Chameleon.git
cd Chameleon

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Core CLI needs no third-party packages (standard library only)
python validation_test.py
```

### Dependency tiers

The core CLI runs on the standard library alone. Optional capabilities are
grouped as installable extras (single source of truth in `pyproject.toml`):

```bash
pip install -e .          # core CLI only
pip install -e .[audio]   # numpy/scipy/librosa/soundfile/pyaudio — full pipeline
pip install -e .[api]     # fastapi/uvicorn/pydantic — REST API server
pip install -e .[ml]      # torch — optional ML-backed features
pip install -e .[dev]     # test/lint/build tooling
```

The legacy `enhanced_requirements.txt` and `api_requirements.txt` files are kept
for reference only; prefer the extras above.

### Basic Usage

```bash
# Analyze audio file
python main.py analyze audio.wav --detailed

# Normalize volume
python main.py process --normalize audio.wav

# Batch process directory
python main.py batch /path/to/audio/ normalize --output-dir /output/

# Preview changes (dry-run)
python main.py batch /path/to/audio/ normalize --dry-run
```

### Docker Deployment

```bash
# Build image
docker build -t chameleon:latest .

# Run container
docker run -v /audio:/data chameleon:latest analyze /data/file.wav
```

## Configuration

### Environment Variables

```bash
# Security
export CHAMELEON_TRUSTED_ROOTS="/trusted/audio:/workspace"
export CHAMELEON_MAX_FILE_SIZE=524288000  # 500MB

# Performance
export CHAMELEON_MAX_WORKERS=8
export CHAMELEON_CHUNK_SIZE=131072  # 128KB
export CHAMELEON_PERFORMANCE_MODE=fast  # fast, balanced, safe

# API Server
export CHAMELEON_API_KEY_FILE=/etc/chameleon/api_keys.json
export CHAMELEON_ALLOWED_ORIGINS=https://your-domain.example.com
```

## Usage Examples

### Command Line

```bash
# Detailed analysis with JSON export
python main.py analyze audio.wav --detailed --export report.json

# Multiple processing operations
python main.py process --normalize --denoise audio.wav --output-dir processed/

# Batch with custom workers
python main.py --max-workers 16 batch /audio/ normalize --recursive

# MIDI extraction
python main.py midi extract --input song.wav --output notes.mid

# Start API server
python main.py server --host 0.0.0.0 --port 8080
```

### Python API

```python
from main import AudioProcessor, ProcessingConfig
from performance_optimizer import ParallelProcessor

# Setup processor
config = ProcessingConfig.from_environment()
processor = AudioProcessor(config)

# Process single file
audio, sr = processor.load_audio("/path/to/file.wav")
metadata = processor.analyze_audio(audio, sr)
normalized = processor.normalize_audio(audio, target_peak=0.95)
processor.save_audio(normalized, "/output/normalized.wav", sr)

# Parallel batch processing
parallel = ParallelProcessor(max_workers=8)
results = parallel.process_files_parallel(
    files=file_list,
    process_func=process_single_file,
    use_processes=True
)
```

## Architecture

### Core Modules
- **core.py** - WAV processing, file I/O, safe operations
- **main.py** - CLI entry point with all commands
- **security_validator.py** - Path/file validation, secure file operations
- **api_server.py** - Optional REST API (requires fastapi/uvicorn)
- **plugin_system.py** - Sandboxed plugin execution with AST validation

### Security Modules
- **security_validator.py** - Path validation, trusted-root enforcement, size limits
- **advanced_validation.py** - Deeper file inspection and integrity checks

### Performance Modules
- **performance_optimizer.py** - Parallel processing, SIMD, caching
- **stability_enhancer.py** - Circuit breakers, retry, resources
- **ux_improvements.py** - Progress bars, colors, formatting

## System Requirements

### Minimum
- Python 3.8+
- 512 MB RAM
- 2 CPU cores
- 100 MB disk space

### Recommended
- Python 3.10+
- 4 GB RAM
- 8 CPU cores
- SSD storage

### Supported Formats
- Audio: WAV (PCM, 8/16/24/32-bit)
- Sample Rates: 8kHz to 96kHz
- Maximum File Size: 500MB (configurable)

### Optional Dependencies

```bash
# Advanced audio processing
pip install numpy scipy librosa soundfile

# Real-time processing
pip install pyaudio

# MIDI support
pip install mido

# API server
pip install fastapi uvicorn

# Resource monitoring
pip install psutil
```

## Documentation

- **QUICKSTART.md** - Quick reference guide
- **DEPLOYMENT_GUIDE.md** - Production deployment instructions
- **docs/api_documentation.md** - API reference
- **CHANGELOG.md** - Version history

## Testing

```bash
# Basic validation (standard library only)
python validation_test.py

# Unit tests (core + security primitives)
python test_core.py

# Full test suite
pytest
```

## Monitoring

### Health Checks

```bash
# Check system health
curl http://localhost:8080/health
# {"status": "healthy", "version": "1.0.0", "uptime": 3600}
```

### Audit Logs

Located in `~/.chameleon/audit/`:
- `security.log` - Security events
- `compliance.jsonl` - Compliance audit trail

## Contributing

Contributions welcome! Please:
1. Follow existing code style
2. Add type annotations
3. Include tests
4. Update documentation
5. Follow security best practices

## License

MIT License - See LICENSE for details

## Support

- **Issues**: https://github.com/shizukutanaka/Chameleon/issues
- **Documentation**: See `docs/` directory
- **Security Issues**: Report via GitHub Security Advisories

---

**Chameleon Audio Processing System** - Professional audio processing with security and performance for production environments.
