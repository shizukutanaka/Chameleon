# Changelog

## Unreleased

### Added

- True-peak (dBTP) metering: `mastering_chain.LoudnessMeter.measure_true_peak`
  implements ITU-R BS.1770-4 Annex 2's oversample-then-peak method (4×
  oversampling via scipy's polyphase resampler), catching inter-sample peaks
  the raw sample peak misses (up to ~3 dB on limited material). Exposed as
  `true_peak_db` in `MasteringChain.analyze()` and surfaced in `process
  --master` output. Honestly scoped as an accurate estimate (uses scipy's
  resampler, not the standard's example FIR coefficients); falls back to the
  sample peak without scipy.

### Fixed

- `ci/proposed-ci.yml`'s import smoke-check still referenced `audio_utils` and
  `config_manager` (deleted this cycle), which would have broken the workflow
  the moment a maintainer adopted it verbatim; corrected to the current
  stdlib-core module list.

## 1.1.0 - 2026-07-17

### Added

- `analyze --loudness`: integrated loudness (LUFS) via a new pure-Python,
  stdlib-only ITU-R BS.1770-4 K-weighting filter and gated-loudness meter
  (`bs1770_loudness.py`). Coefficients verified against the standard's
  published reference values. Sums per-channel energy correctly for
  mono/stereo (no surround weighting or true-peak) and is bounded to a
  prefix of the file — not a certified full-track measurement. See
  CHARTER.md §9.
- `core.get_samples_for_analysis(separate_channels=True)`: per-channel
  waveform extraction (no mono downmix) for analysis tooling.

### Changed (accuracy — see CHARTER.md §9 for research citations)

- Spectral analysis (`analyze --spectrum`) now applies a Hann window before
  the transform (was rectangular = spectral leakage) and refines detected
  peaks with parabolic interpolation for sub-bin frequency accuracy.
- MIDI pitch detection replaced global-max autocorrelation (frequent octave
  errors) with the YIN algorithm (difference function → cumulative
  mean-normalized difference → absolute threshold → parabolic
  interpolation), still pure standard library.
- `mastering_chain.LoudnessMeter` is now a real ITU-R BS.1770-4 meter when
  SciPy is available (reuses `bs1770_loudness`'s exact verified
  coefficients via single-pass `lfilter`; 400ms blocks with 75% overlap;
  absolute gate before relative gate; per-channel energy summed), instead
  of a 200–2000 Hz band-pass approximation mislabeled as K-weighting.
  `measure_range` now computes a real EBU-Tech-3342-style loudness range
  (3s windows, 100ms hop, P95−P10) instead of echoing integrated loudness.
- Loudness measured from stereo input no longer under-reads by ~3 dB
  (identical L/R) to ~6 dB (uncorrelated): channels are measured and their
  energies summed per BS.1770 instead of averaging samples to mono before
  filtering.

### Fixed

- Denoise used a noise-estimation window twice as long as documented
  (frame count computed against the wrong STFT hop size).
- `LoudnessMeter` diverged to inf/NaN for sample rates below the K-weighting
  filter's ~8kHz stability floor instead of falling back (the guard
  expected an exception its callees never raise), and crashed outright at
  `sample_rate=0`; a single NaN input sample silently corrupted loudness
  readings by silently gating away contaminated blocks (reproduced as a
  25 dB error) — now returns NaN explicitly; `auto_adjust` propagated an
  infinite gain adjustment (NaN output audio) for clips too short to form
  one gated loudness block; unknown dither types silently applied no dither
  at all (now falls back to TPDF with a logged warning).
- `personal_config.py` was missing from packaging (pyproject/setup.py
  py-modules and the Dockerfile), so built wheels and container images
  silently dropped the documented `personal_config.py setup` onboarding
  flow.

### Removed

- `core.py`'s `AIMusicAnalyzer` ("AI-powered music analysis" whose feature
  extractors returned hardcoded placeholder literals and never read the
  audio file), six zero-caller `*FeatureExtractor` classes, and the
  zero-caller `AudioFormatSupport` (depended on pydub, which was never a
  declared dependency) — user-confirmed deletions; `core.py` shrank from
  3,266 to 2,738 lines.

### Fixed (2026-07 quality pass — see CHARTER.md §9 for full rationale)

- WAV read/write assumed audio data starts at a fixed byte-44 offset; files
  with LIST/JUNK/fact chunks before `data` got silently wrong analysis and
  corrupted processed output. Replaced with a proper chunk-walking parser.
- `api_server.py`: four HTTP handlers caught `HTTPException` inside a bare
  `except Exception`, silently turning 429/404/503 into 200/500 (defeating
  rate limiting and leaking internal error detail).
- Path-containment check used `str.startswith`, wrongly treating
  `/data/safe-evil` as inside `/data/safe`; replaced with `os.path.commonpath`.
- Plugin sandbox: `__import__("os")` (no literal `import` statement) bypassed
  the AST-based import check entirely, running unrestricted code at plugin
  load time. Also bypassable via `importlib.import_module`. Closed the known
  bypasses; documented that AST-only checking remains a partial boundary, not
  a full runtime sandbox.
- `plugin_system.py` called `importlib.util.*` without ever importing
  `importlib.util` explicitly — worked by accident, failed on a fresh
  process. 3 of 5 shipped `demo_plugins/` failed the product's own
  `plugins audit` command due to unnecessary legacy import boilerplate.
- `BatchProcessor.process_directory` (sync, core.py) never returned its
  result list.
- CLI diagnostics printed to stdout instead of stderr (broke piping); no
  `--version` flag; import-time warnings on every invocation even on the
  supported stdlib-only install.

### Removed (2026-07)

- Three modules claiming "neural network" processing while running
  `random.choice` or importing torch unconditionally; four more orphaned
  modules duplicating already-working functionality; `codec_support.py`
  (unimported, broke the stdlib install, and was wrongly credited by this
  file's own earlier prose as the MP3/FLAC mechanism).
- `Dockerfile` referenced `chameleon_enhanced.py`/`enterprise_config.py` —
  files that never existed anywhere in this repository — so every container
  invocation failed at the health-check step regardless of command. Rewrote
  it to run the real `main.py`/`api_server.py` entry points, and removed
  "Enterprise Edition"/"National-level"/"military-grade security" marketing
  language along with a baked-in `production.yaml` that no code ever read.
- `api_requirements.txt` (pinned `pydantic==2.5.0`, breaking `api_server.py`'s
  v1-only syntax; also carried "Government-grade" wording) and
  `enhanced_requirements.txt` (torch/tensorflow/GPU packages for the
  already-deleted neural modules) — both contradicted `pyproject.toml`, the
  actual source of truth for dependencies.
- `pyproject.toml`'s `[ml]` extra (torch) — zero consumers in the codebase
  since the neural modules were removed.

### Fixed (2026-07 restoration pass)

- Restored the broken import chain: `main.py`, `core.py`, `plugin_system.py` and
  `batch_automation.py` previously crashed on import because they referenced
  local modules that did not exist. Added a single canonical, dependency-free
  `security_validator.py` and removed the dangling imports.
- Added the missing `main.py` entry point (`asyncio.run(main())` via a `cli()`
  wrapper); `python main.py` previously did nothing because the async `main()`
  was never awaited.
- Recovered the core module-level API (`analyze`/`normalize`/`trim_silence` and
  the processor singletons) that a stray placeholder token had erased.

### Removed (2026-07 restoration pass)

- ~3,700 lines of non-functional code from `core.py` (Quantum, Blockchain,
  Biometric, Edge, Cloud and ML-music classes), a duplicate
  `ParallelBatchProcessor`, and a duplicate `MemoryManager.get_file_data`.
- AI-generated marketing/analysis documents and doc pages that referenced
  commands and modules which do not exist.

### Changed (2026-07 restoration pass)

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
