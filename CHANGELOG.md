# Changelog

## Unreleased

### Added

- **The test suite now runs on the dependency-free install.** Twelve test
  modules did a bare `import numpy`, so on a bare install `pytest` failed at
  collection and ran nothing — verifying the stdlib core required installing
  the dependency it is defined by not needing. Three configurations now pass:
  stdlib only (259 passed), + numpy (300), + numpy + scipy (410).
- **18 tests for `personal_config.py`**, the last zero-coverage module and the
  one new users are pointed at first by `quick_install`. They found a config
  loader that refused to start on any file written by another version of
  Chameleon, an unhelpful crash on malformed JSON, and playlists stamped with
  the home directory's modification time.
- `ci/proposed-ci.yml` rewritten into two jobs — a `stdlib-only` job that
  refuses to run if an audio package leaked into the environment, and an
  `audio-extra` job across Python 3.9–3.12 with a `-W error::RuntimeWarning`
  DSP pass. As written before, it installed numpy but not scipy: adopting it
  would have shown green while ~90 tests silently skipped, and three would in
  fact have failed. Every step has now been executed locally. Adopting it still
  needs a maintainer — re-confirmed that this automation account cannot write
  `.github/workflows/` by either git or the REST API.
- **`process --declip` and `process --dehum`** — the first CLI surface for
  `audio_restoration.py`, 530 lines of restoration DSP that no entry point had
  ever reached. `--declip` reconstructs peaks flattened by clipping;
  `--dehum` removes 50/60 Hz mains hum and its harmonics *when they are
  actually present*. Both are no-ops on material without the defect: a clean
  file comes back within one LSB, and a musical 55 Hz bass note — which sits
  between the two power-line frequencies — is left alone.

  They always run declip-then-dehum regardless of flag order, because damage
  must be undone in reverse: dehumming first ripples the clipped plateaus
  enough that declipping then finds none of them, and lands 6.8 dB further
  from the undamaged signal.

  Click removal, crackle removal, gap interpolation and the librosa denoiser
  are deliberately **not** exposed. Click detection in particular has no
  trustworthy implementation here — the existing envelope/z-score detector
  reports 354 clicks in a second of white noise, and a second-difference
  alternative reports 1,764 in clipped audio, one per clipping corner.
- **`tests/test_no_orphan_modules.py`** — fails CI when a packaged module is
  not reachable by following imports from `main` or `api_server`. Chameleon
  has repeatedly accumulated files no entry point touches; three were deleted
  in this release. Four modules are allow-listed with written justifications
  (`audio_restoration`, `personal_config`, `batch_automation`,
  `spectral_editor`), and a companion test fails if one of those
  justifications goes stale. Also catches a `py-modules` entry with no file
  behind it, and drift between `setup.py` and `pyproject.toml`.

- **`process --mono` and `process --trim`, plus `batch mono` / `batch trim`.**
  `core.py` had always implemented mono downmix and silence trimming in pure
  standard library — both are in `ALLOWED_BATCH_OPERATIONS` and covered by
  core's tests — but the CLI exposed neither, leaving half the dependency-free
  core reachable only from the Python API. Both now run through the CLI with
  numpy absent, verified by a test suite that executes the real CLI with
  numpy/scipy/librosa/soundfile made unimportable.
- Cross-validation of the loudness meter against `pyloudnorm`, an independent
  BS.1770-4 implementation: integrated loudness agrees to 0.043 LU across
  sines, noise and gated programme material (Tech 3341 allows ±0.1 LU). The
  residual is a coefficient-precision difference in the stage-1 high shelf —
  our error against the published table is ~1e-12, the reference's ~1e-4 — and
  a test pins that so nobody "corrects" ours toward it later. `pyloudnorm` is
  test-only and in no install extra; the tests skip when it is absent.
- **Loudness range (LRA)**: `bs1770_loudness.measure_loudness_range` adds the
  last piece of EBU Mode (M + S + I + LRA) in pure standard library — EBU
  Tech 3342's P95 − P10 of the gated short-term loudness, with the -20 LU
  relative gate the range measurement uses (not the integrated meter's
  -10 LU). Reported by `analyze --loudness` (exported as `loudness_range_lu`),
  with an explicit note when the analysed excerpt is under the 60 s Tech 3342
  treats as settled. Returns NaN rather than 0.0 when unmeasurable, so that
  stays distinct from a genuine 0 LU. Validated by an invariant that follows
  from the definition (a two-level signal's LRA equals the levels' dB
  difference: 6.021 LU for 6.021 dB, 20.000 for 20.000) and by agreeing to
  0.000 LU with the independent numpy/scipy meter in `mastering_chain`.
- `process --master` now reports the loudness range of the mastered result.
  `MasteringChain.analyze()` had always computed it, but `main.py` never
  threaded it out of the operation result, so it could never be displayed —
  it shows how much the chain narrowed the dynamics (12.0 LU → 3.0 LU on the
  test file).
- **EBU Mode loudness**: `bs1770_loudness.measure_momentary_loudness` /
  `measure_short_term_loudness` and their `measure_max_*` counterparts add the
  two ungated sliding-window meters (400 ms and 3 s) that EBU Tech 3341's
  "EBU Mode" requires alongside the existing gated Integrated measurement.
  Surfaced in `analyze --loudness` as Max Momentary / Max Short-term and in
  `--export` as `max_momentary_lufs` / `max_short_term_lufs`. Pure standard
  library, no new coefficients — it reuses the validated K-weighting and a
  generalized block-energy helper. Scope is stated honestly: the primary
  Tech 3341 document could not be retrieved, so correctness is pinned by
  first-principles invariants (stationary signal ⇒ M == S == I, etc.) rather
  than claimed against the standard's text.

### Fixed

- **`process --effects` silently skipped effects it could not apply.** Each
  effect was gated on its dependency and did nothing when absent, so on an
  install without scipy the command wrote a file, reported success, and applied
  no EQ. It now raises, naming the effect and the extra that fixes it.
- **`process --mono` on an already-mono file printed "Error: Already mono",
  wrote no output, and exited 0.** An error message on a success exit, a
  satisfied request reported as a failure, and a promised output file that did
  not exist — so a batch over mixed material left a pipeline believing it had
  files it did not. `--mono` is now idempotent: the file is copied through and
  reported as already mono.
- `PersonalConfig.load` no longer dies with a bare `TypeError` on a config
  written by a different version of Chameleon; unrecognised keys are logged and
  ignored. Malformed JSON now raises an error naming the file, and leaves it
  alone rather than replacing the user's settings with defaults.
- `PersonalLibraryManager.create_playlist` recorded the home directory's
  modification time as every playlist's creation time.

### Removed

- **`performance_optimizer.py`** (324 lines, zero importers). Everything in it
  already existed in code that runs: worker count in `main.py`'s
  `ProcessingConfig.from_environment`, chunk size in `core.py`'s
  `_determine_chunk_size`, caching in `core.py`'s byte-accounted
  `MemoryManager`. It also carried a defect proving it had never been
  executed: `SIMDOperations.normalize_int16` truncated its scale factor to an
  integer, returning digital silence for any signal peaking above ~34% of full
  scale. Dropped from `setup.py`, `pyproject.toml`, the `Dockerfile` COPY list,
  `README.md` and `docs/agents/SONNET.md` at the same time.
- **`core.py`'s `RealtimeAudioProcessor`** (393 lines, the whole tail of the
  file) — a WebSocket streaming server with zero callers anywhere in the
  repository, which could not run in any install anyway: `websockets` is in no
  extra, so its constructor raised `ImportError` unconditionally. Real-time
  streaming is outside `CHARTER.md` §1's file-in/file-out scope, and none of
  the path-validation layer that backs the "secure" claim applies to a socket.
  The `try: import websockets ...` block went with it — a block that, because
  a `try` body stops at its first exception, silently skipped the five stdlib
  imports listed after `websockets` whenever it was absent. `core.py`
  2,780 → 2,367 lines.
- **`api_server.py`'s three phantom "secure module" imports and the six dead
  branches behind them.** `government_auth`, `secure_core` and
  `high_performance_core` have never existed in this repository, so the
  `try/except ImportError` around them pinned `HAS_SECURE_MODULES` to `False`
  permanently and every `if HAS_SECURE_MODULES:` branch was structurally
  unreachable — as were the three `skipif` guards in
  `tests/test_api_fallback.py`, which could not fire. The reachable code is now
  unconditional, and `require_permission` states plainly that it requires a
  session and does not enforce per-permission authorization (which is what it
  has always done). The "government" naming was also the kind of unverifiable
  institutional claim `CHARTER.md` §4 forbids.

### Changed

- `import uvicorn` moved from `api_server.py`'s module scope into its
  `__main__` block. It is needed to *run* the server, never to import `app`,
  so serving under gunicorn — or importing the module in a test — no longer
  requires it.


### Changed (honesty / documentation)

- Rewrote `docs/{en,ja}/commands.md`, `docs/{en,ja}/advanced_config.md` and the
  benchmark docs, which described a product that does not exist: ~18 commands
  with no `add_parser` anywhere (`normalize`, `convert`, `trim`, `menu`,
  `benchmark`, `diagnostics`, `health-check`, `audit-log`, …), a JSON
  configuration file, and a `config` sub-command. They now document only the 8
  real subcommands and the 7 environment variables the code actually reads;
  every example was executed before being written down.
- `README.md`: the Python API example no longer builds on the orphaned
  `performance_optimizer`; removed the listing for the deleted
  `stability_enhancer.py`; retired the "SIMD" wording the module itself
  retracts; added the loudness/DSP modules that were missing.
- `setup.py`: extras now mirror `pyproject.toml` (`audio`/`api`/`dev`, with
  `python-multipart`) instead of advertising undocumented `full`/`realtime`
  extras and a `midi` extra requiring `mido`, which nothing imports.
- `personal_config.py`: `podcast_workflow` / `music_workflow` printed step
  banners and a success line while performing no processing; they now raise
  `NotImplementedError` naming the CLI commands that do the work.

### Fixed

- **Tempo estimation was four times too slow.** `analyze_rhythm` divided by an
  extra factor of four, so notes half a second apart (120 BPM) were reported
  as 30 BPM. Its interval histogram also used 62.5 ms buckets described as
  "16th notes", making resolution tempo-dependent; intervals are now grouped
  on a log scale for equal precision at any tempo, and the result is folded
  into the 40-240 BPM range since onset spacing determines the beat period
  only up to a factor of two.
- **Key detection reported the wrong key for 11 of 12 keys.** `detect_key`
  rotated the Krumhansl-Schmuckler profile in the wrong direction, so only
  C major resolved correctly and the rest came out as their inverse (G major
  detected as F, D as A#). All 24 major and minor keys are now correct; the
  published profile values were already right and are unchanged.
- **Every seventh chord was reported as its bare triad.** Chord templates were
  scored by `matches / len(template)`, which ignores notes the template cannot
  explain, so C-E-G-B matched "major" as well as "maj7" and dict order decided.
  Scoring by Jaccard overlap fixes it. Chords that are genuinely the same
  pitch-class set (Am7 vs C6) are now resolved by the bass note.
- **Noise reduction estimated its noise profile from the signal.**
  `remove_noise` sampled the first half second of the file, assuming every
  recording opens with silence. On material starting straight into music the
  "noise" it measured was the music itself, gutting the audio by ~19 dB
  (a tone beginning at t=0 came out 20.0 dB down). The profile is now the
  10th percentile of each frequency bin over time, scaled to a level estimate
  by the Rayleigh quantile-to-median ratio (~2.56, derived rather than tuned).
  The broken case goes from -19.4 dB to -0.1 dB while the silent-lead-in case
  keeps its noise reduction (8.7 -> 8.3 dB).
- **Compressor soft-knee curve was non-monotonic.** The static gain computer
  combined a knee placed above the threshold with the above-knee formula for a
  knee centred on it, so the two pieces did not meet: a 1 dB rise in input
  could drop the output 2 dB at the knee boundary. Replaced with the standard
  centred quadratic soft knee (Giannoulis, Massberg & Reiss, JAES 2012); the
  curve is now monotonic with the above-knee slope equal to 1/ratio. The
  mono and stereo paths now share one gain-computer helper.
- **Both equalizers destroyed out-of-band content.** `main.apply_effects` and
  `mastering_chain.ParametricEQ` were built on `scipy.iirpeak`, a band-pass
  resonator rather than a peaking EQ, so requesting a boost deleted everything
  outside the band: "+3 dB at 1 kHz" measured −24.6 dB at 200 Hz, and the
  mastering path delivered 0.00 dB of boost at the centre while attenuating
  200 Hz by 26.7 dB. The streaming/cd/vinyl presets were affected — every
  requested boost came out as attenuation. Both now use RBJ *Audio EQ
  Cookbook* biquads (`design_peaking_eq` / `design_shelf_eq`), applied with a
  single pass so the requested gain is exact. Verified against the properties
  that define a peaking EQ (unity at DC/Nyquist, exact centre gain, boost and
  equal cut cancelling) to within 0.01 dB.
- The reverb effect's synthetic impulse response is now seeded, so the same
  input produces the same output.
- **Sample-rate conversion aliased on the fallback path.** `_resample_audio`
  uses librosa, then scipy, then a built-in fallback that was plain
  `np.interp` — linear interpolation with no anti-aliasing, so downsampling
  folded content above the new Nyquist back into the audible band. It is now a
  windowed-sinc resampler with the cutoff at `min(1, target/source)`. On a
  15 kHz tone at 48 kHz → 16 kHz the alias drops from −5.69 dBFS to
  −62.70 dBFS (scipy's reference result: −62.63 dBFS). The librosa and scipy
  branches were already correct and are unchanged.
- **16-bit quantisation truncated instead of rounding.** `_save_wav_basic`
  used `.astype(np.int16)`, biasing single-signed material by −0.4999 LSB and
  allowing a full-LSB worst-case error. Rounding gives −0.0002 LSB mean error
  and a 0.5 LSB worst case.
- `ProcessingConfig.apply_dither` was a flag nothing read. It now applies
  2 LSB peak-to-peak TPDF dither when set. It stays **off by default** so
  output remains byte-for-byte reproducible (a documented differentiator);
  enabling it trades that for a quantisation error independent of the signal.
- Documentation: `--convert` and `--denoise` were listed as core commands
  without noting that they require numpy (only `analyze` and `normalize` run
  on the dependency-free install). Both command references now carry per-flag
  dependency columns.
- `spectral_editor.py` and `audio_restoration.py` imported numpy/scipy
  unconditionally, so importing either raised `ModuleNotFoundError` on a
  stdlib-only interpreter (a real failure, not a theoretical one). Both now use
  the guarded `HAS_*` pattern and raise a clear, actionable error naming
  `pip install -e .[audio]` only when actually used.

- Agent-facing documentation: `CLAUDE.md` (the working agreement for AI
  contributors — read order, absolute rules, verification gate, known traps),
  `PRODUCT_ANALYSIS.md` (strengths / weaknesses / prioritized improvement
  backlog with `file:line` citations), and `docs/agents/OPUS.md` +
  `docs/agents/SONNET.md` (per-model guidance). No prior CLAUDE.md existed.

- True-peak (dBTP) metering, ITU-R BS.1770-4 Annex 2 oversample-then-peak
  method, in two places:
  - `mastering_chain.LoudnessMeter.measure_true_peak` (4× via scipy's
    polyphase resampler), exposed as `true_peak_db` in
    `MasteringChain.analyze()` and surfaced in `process --master` output.
  - `bs1770_loudness.measure_true_peak` /
    `measure_true_peak_multichannel` (4× via a self-generated windowed-sinc
    polyphase interpolation, pure standard library — no numpy), surfaced in
    `analyze --loudness` output and the `--export` metadata as
    `true_peak_dbtp`.
  Catches inter-sample peaks the raw sample peak misses (up to ~3 dB on
  limited material). Both are honestly scoped as accurate *estimates*: they
  generate/borrow a windowed-sinc interpolation filter rather than
  transcribing the standard's *example* FIR coefficients, and agree with
  each other to <0.05 dB. The mastering-chain path falls back to the sample
  peak without scipy.

### Fixed

- `core.BatchProcessor` synchronous batch path: `process_directory` called a
  `_execute_operation` method that never existed (only the async twin did),
  so the `AttributeError` was swallowed and *every* file in a synchronous
  batch was silently reported as failed. Implemented the sync method (sharing
  operation dispatch with the async path via a new `_build_operation_runner`).
  This surfaced and fixed two latent crashes: the post-loop code assumed
  `result.data` was always a dict (only true while every file failed), so a
  successful `analyze` raised "argument of type 'AudioInfo' is not iterable";
  and `_execute_operation_async` leaked `recovery.execute`'s
  `(result, attempts)` tuple, so `batch_process_async` returned tuples
  despite its `List[ProcessingResult]` annotation.
- `ci/proposed-ci.yml`'s import smoke-check still referenced `audio_utils` and
  `config_manager` (deleted this cycle), which would have broken the workflow
  the moment a maintainer adopted it verbatim; corrected to the current
  stdlib-core module list.

### Changed (honesty)

- Removed three docstring/metadata overclaims surfaced by `PRODUCT_ANALYSIS.md`:
  `advanced_validation.py` "malware detection" → structure/integrity/tamper
  (states plainly it is not a malware scanner); `gui/package.json`
  "Government-Grade"/"Chameleon Security Team"/`"RESTRICTED"` → honest
  experimental description, "Chameleon contributors", `MIT` (matching the repo
  license); `batch_automation.py` "Intelligent …" → plain description noting
  its orphaned status.

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
