# Chameleon — Functional Specification

Status: living document. Describes the **intended** behaviour (contract) of the
Chameleon CLI, the Python API, and the optional REST API, and tracks where the
implementation does not yet meet it ("Conformance gaps").

Version: 1.0.0 · Entry point: `python main.py …` / `chameleon …` (console script).

---

## 1. Scope & principles
- Core audio operations work on the **Python standard library alone** (WAV PCM).
- Optional features degrade gracefully when their dependency is absent and must
  not crash on import; the CLI reports unavailability via exit codes.
- All file access is mediated by `security_validator` (path validation, size
  limits, trusted roots).

## 2. Global CLI
```
chameleon [--version] [--max-workers N] [--no-parallel] <command> [...]
```
- `--version` → prints `chameleon <VERSION>` and exits 0.
- `--max-workers N` → cap worker threads for batch/parallel work.
- `--no-parallel` → force sequential execution.
- No command → print help, exit 1.

### 2.1 Exit-code taxonomy (normative)
| Code | Meaning |
|------|---------|
| 0 | success |
| 1 | runtime or usage error (bad input, validation failure, I/O error) |
| 2 | requested feature **not implemented** or its optional dependency is unavailable |

Scripts may rely on `2` to distinguish "this build can't do that" from a hard
failure. argparse usage errors exit 2 as well (standard), which is consistent
with "the request can't be served as given".

## 3. Commands

### 3.1 `analyze <files…> [--detailed] [--export FILE] [--json]`
Print duration, sample rate, channels, peak/RMS (and, with `--detailed`, dynamic
range / frequency range / tempo / spectral centroid when available). `--export`
writes a JSON report to a file; `--json` emits the analysis as JSON to stdout
(human-readable lines are suppressed in that mode). Per-file errors are reported;
overall exit is 1 if any file failed, else 0.

### 3.2 `process <files…> [--normalize] [--denoise] [--effects JSON] [--convert …] [--output-dir DIR] [--parallel] [--dry-run] [--json]`
Apply the selected operations and write outputs (default: alongside input, or to
`--output-dir`). `--dry-run` previews without writing. `--json` emits a machine
-readable summary. Conversion: `--convert-format` (wav), `--convert-sample-rate`,
`--convert-bit-depth {16,24,32}`.

### 3.3 `batch <directory> <operation> [--recursive] [--output-dir DIR] [--format F] [--quality {low,medium,high,lossless}] [--sample-rate N] [--bit-depth {16,24,32}] [--dry-run]`
`operation ∈ {analyze, normalize, denoise, convert}`. Discovers supported audio
files (recursively with `--recursive`) and processes them in parallel when
enabled. `--dry-run` previews the planned operations without writing any files.
Empty/missing directory → exit 1.

### 3.4 `stream [--input-device D] [--output-device D] [--effects JSON] [--monitor]`
Real-time pass-through with effects. Requires PyAudio; absent → exit 2.

### 3.5 `midi <operation> [--input F] [--output F] [--key K] [--mode {major,minor}] [--tempo BPM] [--length S] [--dry-run]`
`operation ∈ {extract, analyze, compose, generate}`. `extract`/`analyze` require
`--input`; `generate`/`compose` require `--output`. `--dry-run` previews without
writing the MIDI file. MIDI write requires `mido`.

### 3.6 `ml <operation> --input F [--model M] [--output F]`
`operation ∈ {classify, separate, transcribe, enhance}`. `enhance` =
denoise + normalize + save (implemented). `classify`/`separate`/`transcribe` are
**not implemented** in this build → exit 2 with a pointer to the relevant
optional model (see `docs/IMPROVEMENT_RESEARCH.md`).

### 3.7 `plugins <list|audit> [--plugin-dir DIR] [--json]` (`audit [--fail-fast]`)
List discovered plugins / audit them for sandbox (AST allowlist) compliance.
Audit failure → exit 1.

### 3.8 `server [--host H] [--port P] [--workers N]`
Launch the REST API (uvicorn + `api_server:app`). uvicorn absent → exit 2.

## 4. Python API (`core`)
`analyze`, `normalize`, `to_mono`, `trim_silence` → `ProcessingResult(success,
message, data, duration_ms)`; `open_secure`; `SecurityValidator`. WAV parsing is
bounded/hardened (see §6).

## 5. Configuration (environment)
`CHAMELEON_TRUSTED_ROOTS`, `CHAMELEON_MAX_FILE_SIZE`, `CHAMELEON_MAX_WORKERS`,
`CHAMELEON_CHUNK_SIZE`, `CHAMELEON_PERFORMANCE_MODE` (fast|balanced|safe),
`CHAMELEON_TIMEOUT`, `CHAMELEON_API_KEY_FILE`, `CHAMELEON_ALLOWED_ORIGINS`.

## 6. Security model
- Absolute-path enforcement, suspicious-character/traversal rejection, size
  limits, optional trusted-root confinement.
- WAV/RIFF parser validates declared chunk sizes against the real file size,
  honours word alignment, bounds the chunk walk, and guards arithmetic
  (hardened — see `tests/test_wav_robustness.py`).
- Plugin sandbox is an **AST allowlist + resource limits**; this is hardening,
  **not** a security boundary (see Conformance gaps).

## 7. Conformance gaps (implementation ≠ spec)

Resolved:
- ✅ `--version` flag (was missing) and accurate program description (was the
  stale "v3.0").
- ✅ `ml classify/separate/transcribe` now exit `2` (were printing a message and
  exiting `0`, i.e. reporting success for an unimplemented operation).
- ✅ `server` without uvicorn now exits `2` (was `1`).
- ✅ `analyze --json` stdout output (parity with `process --json`).
- ✅ `--dry-run` on `process`, `batch`, and `midi` (preview without writing).

Known remaining gaps (tracked for future work):
- `ml separate/transcribe/classify` need optional models to actually function
  (Demucs / basic-pitch / Essentia) — currently honestly report "not implemented".
- `midi compose/generate` produce only simple demo output; `compose` ignores most
  musical parameters.
- Multi-format input: the core `analyze`/`process` path is WAV-only even though
  `codec_support` can read FLAC/MP3/OGG. [cat 1]
- LUFS/EBU R128 loudness normalization is not wired into `normalize` (peak only).
  [cat 2]
- Plugin isolation is AST-only (no process/seccomp/WASM sandbox). [E7]
- REST API lacks magic-byte upload validation, `/health` readiness split, and an
  async job queue. [E2]

These map to entries in `docs/IMPROVEMENT_RESEARCH.md` and
`docs/CATEGORY_RESEARCH*.md`.
