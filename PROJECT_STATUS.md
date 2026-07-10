# Chameleon Audio Processing System — Project Status

**Status**: Beta. Standard-library CLI core is stable and tested (147 automated
tests, all green). REST API server works end-to-end with `pip install -e .[api]`.
No web frontend ships (see §5).
**Last updated**: 2026-07-08
**Read first**: `CHARTER.md` — the project's scope charter and full decision
history (Socratic record, §9). This file is a status *snapshot*; `CHARTER.md`
is the source of truth for *why* each decision was made.

This file is written to be self-contained: a fresh Claude session (Opus or
Sonnet) with no prior context on this project should be able to read this file
alone and know what state the codebase is in, what was recently fixed, what is
known-broken-but-untouched, and what needs a human decision before further
action.

---

## 1. What this product actually is

- **Core**: `main.py` (CLI) + `core.py` (stdlib-only WAV processing engine).
  Runs with zero third-party dependencies for `analyze`/`normalize`/`batch`/
  `midi`. This zero-dependency property is the product's differentiator
  (CHARTER §1) — do not make it require numpy/scipy by default.
- **Optional extras** (`pip install -e .[audio]`): numpy/scipy/librosa/
  soundfile/pyaudio unlock `--master` (full mastering chain), noise
  reduction, format conversion, real-time streaming.
- **Optional REST API** (`pip install -e .[api]`): `api_server.py`, a FastAPI
  JSON REST adapter over the same stdlib core. Ships with 11 HTTP-level
  tests (`tests/test_api_routes.py`).
- **No web frontend ships.** `gui/` is an experimental, self-admittedly
  unwired React/TypeScript/Electron scaffold — not built by the Dockerfile,
  not referenced by any Python code. See §5 for its disposition status.
- **Security layer**: `security_validator.py` (trusted-root path containment,
  size limits) + `advanced_validation.py` (`DeepFileInspector` — WAV
  magic-number verification, wired into both the CLI batch path and
  `core.py`'s `BatchProcessor`) + `plugin_system.py` (AST-sandboxed plugins).

---

## 2. Recently fixed (this work cycle — see CHARTER §9 for full narrative)

| Category | Issue | Fix |
|---|---|---|
| Correctness (critical) | WAV read/write assumed data starts at byte 44; real-world WAVs with LIST/JUNK/fact chunks got silently wrong analysis and corrupted output | Canonical chunk-walking parser (`core.py:_read_wav_header`), `AudioInfo.data_offset`/`data_size` threaded through every reader/writer |
| Correctness | `BatchProcessor.process_directory` (sync) never returned its result list (fell off the end, returned `None`) | Added `return results` |
| Correctness | `BatchProcessor.process_directory` (sync) calls `self._execute_operation(...)`, a method that doesn't exist on the class | **NOT fixed** — zero callers found anywhere; recorded as an open question (§4 below), not silently patched |
| Security | Path-containment check used `str.startswith`, wrongly accepting `/data/safe-evil` as inside `/data/safe` | Replaced with `os.path.commonpath` |
| Security/honesty | `api_server.py`: 4 HTTP handlers caught `HTTPException` inside a bare `except Exception`, silently turning 429/404/503 into 200/500 | Re-raise `HTTPException` before the generic handler in all 4 |
| Honesty | `output_format` accepted `"flac"` but the stdlib core can only write WAV — produced a `.flac`-named WAV file | Restricted to WAV |
| Honesty | "Government-grade"/"classification: RESTRICTED" wording in `api_server.py` and fictional `chameleon-audio.com` contact emails in `pyproject.toml`/`openapi_spec.yaml` | Removed |
| Scope discipline | 3 modules claiming "neural network" processing while running `random.choice` or importing torch unconditionally | Deleted |
| Scope discipline | 4 more orphaned modules duplicating already-working, already-wired functionality (`realtime_effects.py`, `stability_enhancer.py`, `audio_utils.py`, `config_manager.py`) | Deleted (user-confirmed) |
| Deficiency | `mastering_chain.py`/`ux_improvements.py`/`spectral_utils.py` were real, working, non-duplicate code but never imported | Wired in (`process --master`, batch progress bars, `analyze --spectrum`) |
| Deficiency | `DeepFileInspector` ran in `main.py`'s batch filter but not in `core.py`'s `BatchProcessor` | Wired into both sync and async paths |
| CLI quality | Exit codes were 0/1 only; no `--version`; diagnostics printed to stdout (broke piping); import-time warning spam on the default install; Python 3.12+ deprecation warnings | `ExitCode` enum, `--version`, stderr routing, debug-level logging for missing optional deps, `datetime.now(timezone.utc)`/`asyncio.get_running_loop()` throughout |
| Docs | README/QUICKSTART hadn't caught up to `--spectrum`/`--master`/`--target-peak`/`batch effects`/exit codes; QUICKSTART still told users to run deleted `audio_utils.py` | Synced |

**Test count**: 22 → 147 passed. `python -m compileall -q .`, `python validation_test.py`,
and `python -m pytest -q` are the standing verification gate — all green as of
this snapshot.

---

## 3. Known-broken, deliberately left alone (recorded, not silently fixed)

- **`BatchProcessor.process_directory` (sync)**: calls a nonexistent method,
  `self._execute_operation`. Confirmed zero callers anywhere in the codebase
  — only the async `process_directory_async` (via `core.batch_process_async`)
  is actually used. Needs a decision: implement the sync method for parity,
  or delete the dead one. Not fixed because it's new work outside whatever
  task was in progress when it was found, not a one-line correction.
- **`advanced_validation.py`'s `IntegrityVerifier`/`SanitizationEngine`**:
  real code, only reachable via `personal_config.py`, not wired into the
  default batch/load path. Left alone deliberately — security-affecting
  wiring changes get extra scrutiny before being made by default.
- **`.github/workflows/ci-cd.yml`**: still the old broken 409-line pipeline
  (references a nonexistent `deployment_manager.py`, `tests/smoke/`,
  `tests/health/`). A working replacement exists at `ci/proposed-ci.yml`.
  **Cannot be applied by this automation account** — it lacks `workflows`
  permission to push `.github/workflows/` changes. Needs a human maintainer
  to run `cp ci/proposed-ci.yml .github/workflows/ci-cd.yml` and push.

---

## 4. Pending explicit user confirmation (deletion candidates, not yet actioned)

These three are orphaned/broken artifacts recommended for deletion, matching
the exact pattern already applied to `codec_support.py` and 6 other removed
modules — but destructive deletions in this project require explicit,
per-item user confirmation before acting (a standing safety practice, not a
technical limitation of any one file). As of this snapshot, confirmation has
been requested but not yet obtained.

1. **`gui/`** — experimental React/TypeScript/Electron scaffold, self-labeled
   "not yet wired up" in its own README, not built by the Dockerfile.
2. **`core.py`'s `RealtimeMusicProcessor`** (~L2769–3112) — a standalone
   `websockets`-based server with zero callers from `main.py` or
   `api_server.py`.
3. **`openapi_spec.yaml`** — referenced by no Python code (`api_server.py`
   generates its own OpenAPI schema live via FastAPI), fails to parse as
   valid YAML past line 28 (a second top-level document with no `---`
   separator), and repeats claims already removed from `api_server.py`
   ("Government-focused", a deleted SIMD-acceleration parameter).

If you are a future session picking this up: re-ask the user about these
three before deleting anything. Do not delete on the strength of this
document's "recommended" framing alone.

---

## 5. Deliberately kept as-is (real code, but a product-scope call, not a bug)

Three more orphaned-but-real modules were reviewed and intentionally left
unwired rather than deleted or integrated, because integrating them is a
product-scope decision, not a mechanical fix:

- **`spectral_editor.py`**: a full interactive spectral editor (selection
  regions, undo, visualization) — larger surface than this CLI's batch-WAV
  job-to-be-done.
- **`audio_restoration.py`**: real DSP (click/hum/clip repair) but imports
  numpy/scipy unconditionally (would need the same stdlib-install guard fix
  as other modules before it could ship) and needs a new CLI subcommand.
- **`batch_automation.py`**: a genuine DAG/scheduler engine, but wiring a
  generic task-orchestration framework into a "dependency-light auditable
  CLI" risks the exact "second product" scope creep CHARTER §4 forbids.

---

## 6. How to verify this snapshot is accurate

```bash
python -m compileall -q .          # syntax check, all files
python validation_test.py          # 6 functional checks, stdlib only
python -m pytest -q                # 147 passed, 1 skipped (pyaudio absent)
python main.py --version           # single source of truth: VERSION in main.py
```

## 7. Basic usage (current CLI surface)

```bash
chameleon analyze audio.wav --detailed --spectrum
chameleon process --normalize --target-peak 0.8 audio.wav
chameleon process --master streaming audio.wav      # requires [audio] extra
chameleon batch /dir/ normalize --target-peak 0.9 --output-dir /out/
chameleon batch /dir/ effects --effects chain.json
chameleon midi extract --input audio.wav --output notes.mid
chameleon server --port 8000                        # requires [api] extra
```

Exit codes: 0 success, 1 processing error, 2 usage error, 3 input validation,
4 security rejection, 130 interrupted. Diagnostics go to stderr; results and
`--json` output go to stdout.

## 8. Dependencies

**Core** (`pip install -e .`): Python 3.8+ standard library only.
**Optional extras**: `[audio]` (numpy/scipy/librosa/soundfile/pyaudio),
`[api]` (fastapi/uvicorn/pydantic<2), `[ml]` (torch), `[dev]` (test/lint
tooling, including `httpx<0.24` for API route tests).
