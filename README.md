# Otedama Audio Processing System

Production-grade audio processing system for professional and enterprise use.

## Overview

Otedama is a secure, high-performance audio processing system designed for professional audio workflows. Built with security, reliability, and performance as core principles.

**Status:** Production Ready
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
- Path validation and sanitization
- File size limits (500MB default)
- Audit logging with rotation
- Encryption at rest (optional)
- Rate limiting for API endpoints
- RBAC for enterprise deployment

### Performance
- Parallel batch processing (4-8x faster)
- Memory-efficient streaming for large files
- SIMD-optimized operations
- Intelligent caching
- Configurable worker threads

### Reliability
- Graceful degradation when dependencies unavailable
- Circuit breakers for fault tolerance
- Automatic retry with exponential backoff
- Comprehensive error handling
- Health checks and metrics

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourorg/otedama.git
cd otedama

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python validation_test.py
```

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
docker build -t otedama:latest .

# Run container
docker run -v /audio:/data otedama:latest analyze /data/file.wav
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
export CHAMELEON_API_KEY_FILE=/etc/otedama/api_keys.json
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
- **core.py** - Security validation, file I/O, safe operations
- **main.py** - CLI entry point with all commands
- **api_server.py** - REST API with authentication
- **plugin_system.py** - Sandboxed plugin execution

### Security Modules
- **security_hardening.py** - Rate limiting, encryption, secrets
- **enhanced_security.py** - RBAC, API keys, compliance
- **advanced_validation.py** - Deep file inspection, integrity

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
# Basic validation
python validation_test.py

# Core functionality
python test_core.py

# Security modules
python -m security_hardening
python -m enhanced_security
python -m advanced_validation
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

- **Issues**: https://github.com/yourorg/otedama/issues
- **Documentation**: See `docs/` directory
- **Security Issues**: Report via GitHub Security Advisories

---

**Otedama Audio Processing System** - Professional audio processing with security and performance for production environments.
