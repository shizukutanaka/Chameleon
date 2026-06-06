# Changelog

## Unreleased

### Security

- Hardened the hand-rolled WAV/RIFF parsers in `audio_utils.py` and `core.py`
  (`WAVProcessor._read_wav_header` / `_read_wav_header_optimized`): declared
  chunk sizes are now validated against the actual file size (never trusted for
  reads/seeks), RIFF word-alignment padding is honoured, the chunk walk is
  bounded (no hang on zero-size/looping chunks), the duration calc is guarded
  against zero sample-rate/channels/bit-depth, and implausible format fields are
  rejected. Added `tests/test_wav_robustness.py` (valid parsing + truncated,
  oversized, odd-sized, zero-rate, and fuzzed inputs). Addresses the audio-parser
  CVE class (cf. libsndfile CVE-2021-3246 / CVE-2014-9496 / CVE-2017-8363).

### Added

- `docs/SPECIFICATION.md`: a functional specification of the CLI / API contract,
  including a normative exit-code taxonomy and a tracked list of conformance gaps.
- `--version` flag on the CLI (prints `chameleon <VERSION>`); the program
  description now reports the real version instead of a stale "v3.0".
- `analyze --json` (machine-readable analysis on stdout, parity with
  `process --json`); `batch --dry-run` and `midi --dry-run` (preview without
  writing files).
- `tests/test_cli_contract.py`: subprocess-level CLI contract tests.

### Fixed

- Not-implemented `ml` operations (`classify`, `separate`, `transcribe`) now exit
  with code 2 ("unavailable") and a clear message instead of printing a note and
  exiting 0 (which falsely reported success). `server` without uvicorn likewise
  exits 2. See the exit-code taxonomy in `docs/SPECIFICATION.md`.
- Restored the broken import chain: `main.py`, `core.py`, `plugin_system.py` and
  `batch_automation.py` previously crashed on import because they referenced
  local modules that did not exist. Added a single canonical, dependency-free
  `security_validator.py` and removed the dangling imports.
- Added the missing `main.py` entry point (`asyncio.run(main())` via a `cli()`
  wrapper); `python main.py` previously did nothing because the async `main()`
  was never awaited.
- Recovered the core module-level API (`analyze`/`normalize`/`trim_silence` and
  the processor singletons) that a stray placeholder token had erased.

### Removed

- ~3,700 lines of non-functional code from `core.py` (Quantum, Blockchain,
  Biometric, Edge, Cloud and ML-music classes), a duplicate
  `ParallelBatchProcessor`, and a duplicate `MemoryManager.get_file_data`.
- AI-generated marketing/analysis documents and doc pages that referenced
  commands and modules which do not exist.

### Changed

- Reconciled packaging metadata (version 1.0.0, `chameleon = main:cli`) across
  `setup.py` and `pyproject.toml`, and replaced the non-functional CI workflow
  with one that compiles, import-checks, and runs the test suite and CLI.
- Corrected documentation: project name (Chameleon, not "Otedama"), repository
  URLs, module references, and removed unsubstantiated performance claims.

## 1.0.0 - 2025-09-25

Initial public release of the Chameleon Audio Tool.

### Added

- Core processing commands for analyze, normalize, mono, and trim operations
- Batch automation with directory traversal and error handling
- Collection utilities including duplicate detection and duration-based organization
- Security validation to enforce safe paths, size limits, and WAV format checks
- Plugin system with AST whitelisting and resource constraints
- MIDI analysis and composition features
- Real-time audio processing capabilities
- Spectral analysis and editing tools
- API server for remote operations

### Features

- Absolute path enforcement for all file operations
- Resource tuning via environment variables (CHAMELEON_CHUNK_SIZE, CHAMELEON_PERFORMANCE_MODE)
- Audit logging with rotation and secure storage
- Graceful degradation when optional dependencies are unavailable
- Multi-language support (English and Japanese)
- Dry-run mode for safe operation preview
- JSON output for structured reporting

### Known Limitations

- Only uncompressed PCM WAV files are supported
- Maximum file size: 500 MB
- Real-time streaming requires PyAudio
- Advanced ML features require optional dependencies

### Support

- Community support via GitHub Issues
- Documentation in English and Japanese
- Example workflows and sample files included

---

## 0.9.0 - 2024-12-01 - Pre-Release

### Initial Development

- Basic audio processing functionality
- Core command-line interface
- Essential documentation
- Initial testing framework
- Basic security features
- Performance optimization foundation
