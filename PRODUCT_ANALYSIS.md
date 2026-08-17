# Chameleon — Product Analysis (Strengths, Weaknesses, Improvement Backlog)

**Snapshot date:** 2026-08-08 (first-principles audit) · **Version:** 1.1.0 ·
**Tests:** 211 passing, 3 skipped in a minimal env (skips are fastapi/numpy-gated,
not failures; the count varies with which optional extras are installed)

This is a *state snapshot* — an honest inventory of what is strong, what is
weak, and what to do next, written for the next contributor (human or AI).
It complements the two other source-of-truth documents:

- `CHARTER.md` — *why* the project is scoped the way it is (the "laws"), and
  §9 the running decision record.
- `PROJECT_STATUS.md` — *what state* the codebase is in right now.

When you change the product, update the relevant entry here rather than
letting this drift. Every claim below is cited to `file:line` so it can be
re-verified, not trusted.

---

## 1. Strengths (differentiators — preserve these)

- **Zero-dependency core.** `analyze` / `normalize` / `batch` / `midi` /
  `analyze --loudness` (integrated LUFS **and** true-peak dBTP) all run on the
  Python standard library alone. This is the product's reason to exist
  (`CHARTER.md` §1) — do not make the default install require numpy/scipy.
- **Verifiable standards conformance, not claimed conformance.** The BS.1770-4
  K-weighting coefficients in `bs1770_loudness.py` are validated against the
  standard's published reference table (`tests/test_bs1770_loudness.py`), and
  where an authoritative coefficient table could not be verified (true-peak
  Annex 2), the code *generates* its filter from first principles and
  cross-checks it against scipy to <0.05 dB rather than transcribing numbers
  it cannot prove. Honesty about measurement accuracy is a feature.
- **Honest labeling as a discipline.** Estimates are labeled estimates
  (true-peak), approximations are labeled approximate (the RMS fallback in
  `mastering_chain.LoudnessMeter`), and `performance_optimizer.py:4` even
  corrects its own earlier "SIMD" overclaim to "SIMD-like … not real vector
  instructions." This is the culture to keep.
- **Mechanized scope discipline.** `tests/test_no_fantasy_features.py`
  greps the project's Python sources for the forbidden feature classes in
  `CHARTER.md` §4/§8.4 (quantum / neural / GPU / AI transcription / source
  separation), so the add-then-remove fantasy-feature cycle cannot silently
  return.
- **Real verification gate.** `python -m compileall -q . && python -m pytest -q
  && python validation_test.py` is green and covers the wired surface
  (215 tests, up from 22 at the start of the hardening effort).
- **Load-bearing, dependency-free security core.** `security_validator.py`
  (trusted-root path containment via `os.path.commonpath`, size limits) plus
  `advanced_validation.py`'s `DeepFileInspector` (WAV magic-number gating,
  wired into both the CLI and `core.BatchProcessor`) and `plugin_system.py`'s
  AST-checked plugin loader. All stdlib-only and test-covered
  (`tests/test_security.py`, `tests/test_plugins.py`,
  `tests/test_advanced_validation_integration.py`).

---

## 1b. First-principles audit (2026-08-08): what is excess, what is missing

Rather than asking "what does an audio tool usually have", this pass derived
the necessary-and-sufficient feature set from `CHARTER.md` §1 (*dependency-free,
auditable, deterministic WAV CLI*) and measured the codebase against it.

**Excess — roughly 1 line in 4 of shipped Python is unreachable from the CLI.**

| Bucket | Lines | Share |
|--------|------:|------:|
| Reachable from the CLI (the stated product) | 9,367 | 66.5% |
| Reachable only via `server` + `[api]` extra | 1,600 | 11.4% |
| **Orphaned (no entry point reaches it)** | **3,121** | **22.2%** |

Including `core.py`'s `RealtimeAudioProcessor` (needs an undeclared
`websockets` dependency, zero callers) pushes dead weight to ~25%.

Specific findings, each cited so it can be re-verified:

- **`performance_optimizer.py` is ~100% redundant.** `get_optimal_worker_count`
  duplicates `main.py`'s `ProcessingConfig.from_environment` (making it the
  *third* place worker count is resolved); `CacheManager` is a weaker
  `core.py` `MemoryManager` (which does byte-accounted LRU + mmap);
  `SIMDOperations`' operations all exist in `core.py`. This is the same
  argument that retired `config_manager.py`.
- **Spectral subtraction is implemented three times**: `main.py`'s
  `remove_noise`, `audio_restoration.py`'s `AdaptiveDenoiser`, and
  `spectral_editor.py`'s `noise_reduce_selection`.
- **`audio_restoration.py` is mostly genuine capability** — 7 of its 8 classes
  (click/crackle/hum removal, declipping, gap repair, vinyl) have no wired
  equivalent. It is blocked on a CLI surface, not redundant.
- **`batch_automation.py` is genuine capability pointed the wrong way** — a
  generic DAG/workflow engine, i.e. §4's "a second product". Its own demo
  builds tasks for MP3/FLAC/OGG transcoding this product cannot do.
- **`api_server.py:52-54` imports three modules that have never existed**
  (`government_auth`, `secure_core`, `high_performance_core`). They sit in a
  `try/except`, so `HAS_SECURE_MODULES` is permanently `False` and the
  `skipif` guards in `tests/test_api_fallback.py` are permanently no-ops. The
  "government" naming is also the kind of claim §4 forbids.

**Missing — the gaps were in honesty and in standards coverage, not features.**
All of these were fixed in this pass (see §2 "Resolved"), except where noted.

- The bilingual command reference documented ~18 commands that do not exist,
  and a configuration file / `config` sub-command that do not exist.
- `analyze --loudness` reported only Integrated loudness, so it was an
  incomplete EBU-Mode reading. Momentary/Short-term were added first, which
  still left the set short of Tech 3341's definition (M + S + I + **LRA**);
  the loudness range followed, so `analyze --loudness` now reports the full
  set. (The earlier version of this line called the job done at M/S — an
  overclaim, corrected here.)
- Still open (needs a decision, not code): the disposition of the orphaned
  modules above, and the `api_server.py` phantom imports. Deleting any of them
  requires explicit user confirmation — see §3.

## 2. Weaknesses (known — do not paper over)

### Correctness / install integrity
- ~~**Orphaned modules break the stdlib-only story on import.**~~
  **RESOLVED 2026-08-08.** `spectral_editor.py` and `audio_restoration.py`
  imported numpy/scipy unconditionally, so `import spectral_editor` raised
  `ModuleNotFoundError` on a stdlib-only interpreter (confirmed the hard way:
  this session's container was reset to a bare interpreter and both modules
  did fail to import). Both now use the guarded `HAS_*` pattern plus a
  `_require_numpy()` / `_require_restoration_deps()` check that raises a clear
  error naming `pip install -e .[audio]`. Proven by
  `tests/test_orphaned_import_safety.py`, which blocks numpy/scipy in a
  subprocess so the tests hold regardless of the test environment.
- **`api_server.py:27-34`** imports `fastapi`/`pydantic`/`uvicorn`
  unconditionally. Mitigated because `main.py`'s `server` subcommand launches
  it by string (`uvicorn.run("api_server:app", …)`) and guards the uvicorn
  import — so it is a latent fragility, not a live bug. Covered by
  `tests/test_api_routes.py` / `tests/test_api_fallback.py`.

### Honesty residue (docstring/metadata overclaims) — RESOLVED 2026-07-18
The three overclaims below were fixed in the same pass that produced this
document (kept here as a record, per the honesty culture):
- **`advanced_validation.py`** claimed "malware detection capabilities"; now
  describes what it does (magic-number/structure/integrity/tamper checks) and
  states plainly it is *not* a malware scanner.
- **`gui/package.json`** carried `"Government-Grade Audio Processing GUI"`,
  `"Chameleon Security Team"`, `"license": "RESTRICTED"`; now an honest
  "experimental … not yet wired" description, `"Chameleon contributors"`, and
  `"MIT"` (matching the repo license).
- **`batch_automation.py`** "Intelligent batch processing …"; now describes
  its safe-AST condition evaluator + optional scheduling and notes its
  standalone/orphaned status.

### Coverage gaps
- **Zero test coverage:** `performance_optimizer.py`, `personal_config.py`.
  (`audio_restoration.py` and `spectral_editor.py` now have import-safety
  coverage via `tests/test_orphaned_import_safety.py`, but still no coverage
  of their actual DSP.)

### Infrastructure / architecture (need a human or a big investment)
- **The active CI workflow is broken and cannot be fixed by the automation
  account.** `.github/workflows/ci-cd.yml` uses the deprecated
  `actions/upload-artifact@v3` and references a nonexistent
  `deployment_manager.py` / `tests/smoke/` / `tests/health/`. A corrected,
  turnkey replacement sits at `ci/proposed-ci.yml`; adopting it needs a
  maintainer with `workflows` permission (see `ci/README.md`). PRs merged in
  this line therefore show a red "Code Quality & Security" check that reflects
  the stale workflow, **not** product health.
- **Plugin sandbox is AST-only, not a runtime boundary** (`CHARTER.md` §9).
  `plugin_system.py` blocks dangerous patterns at parse time but
  `exec_module()` still runs with full builtins. Closing this fully is a real
  architectural project, not a patch.
- **Loudness scope, honestly bounded:** no surround-channel weighting (every
  channel weighted equally — correct for mono/stereo only); pure-Python
  true-peak costs ~0.4 s per 65k-sample bounded prefix.

### Orphaned assets awaiting a disposition decision (deletion needs user OK)
`batch_automation.py`, `spectral_editor.py`, `audio_restoration.py`,
`personal_config.py` (documented onboarding entry point — see `CHARTER.md` §9),
`performance_optimizer.py`, `gui/`, `core.py`'s `RealtimeAudioProcessor`,
`openapi_spec.yaml`. Per project practice, deletions require **explicit,
per-item user confirmation** — do not delete on the strength of this list.

---

## 3. Improvement backlog (prioritized)

Priority = value ÷ (effort × risk). Deletions are intentionally **not** ranked
here because they need a user decision first.

| # | Improvement | Value | Effort | Risk | Notes |
|---|-------------|-------|--------|------|-------|
| ~~P1~~ | ~~Fix 3 docstring/metadata overclaims~~ | Med | XS | Low | **DONE 2026-07-18** — see §2 "Honesty residue" |
| ~~P1~~ | ~~Guard the unconditional numpy/scipy imports~~ | Med | S | Low | **DONE 2026-08-08** — guarded + `tests/test_orphaned_import_safety.py` |
| ~~P1~~ | ~~Rewrite the bilingual command/config references~~ | High | M | Low | **DONE 2026-08-08** — they documented ~18 nonexistent commands and a nonexistent config file; every replacement example was executed before being written |
| ~~P2~~ | ~~EBU-Mode loudness (M, S **and LRA**)~~ | Med | M | Low | **DONE 2026-08-08** — `analyze --loudness` was integrated-only; M/S then LRA (Tech 3342) complete the set. LRA cross-checks to 0.000 LU against the independent numpy/scipy meter |
| ~~P1~~ | ~~Anti-alias the fallback resampler; round instead of truncate~~ | High | M | Low | **DONE 2026-08-08** — alias −5.69 → −62.70 dBFS (scipy: −62.63); quantisation bias −0.4999 → −0.0002 LSB |
| ~~P1~~ | ~~Fix both EQs (band-pass resonator used as a peaking EQ)~~ | High | M | Low | **DONE 2026-08-08** — RBJ biquads; "+6 dB @1 kHz" went from 0.00 dB boost / −26.7 dB at 200 Hz to +6.00 / +0.27 |
| ~~P1~~ | ~~Fix key detection (profile rotated backwards) and seventh-chord collapse~~ | High | S | Low | **DONE 2026-08-08** — 11/12 keys were wrong; all 24 now correct. Jaccard chord scoring + bass-note tie-break |
| ~~P1~~ | ~~Fix denoise estimating noise from the signal~~ | High | S | Low | **DONE 2026-08-08** — per-bin percentile + Rayleigh scaling; material without a silent lead-in went -19.4 dB → -0.1 dB |
| ~~P1~~ | ~~Fix compressor's non-monotonic soft knee~~ | High | S | Low | **DONE 2026-08-08** — centred quadratic knee (Giannoulis 2012); output no longer drops 2 dB at the knee |
| P2 | Add minimal tests for the remaining zero-coverage modules | Med | M | Low | `performance_optimizer`, `personal_config` still uncovered |
| P3 | `apply_effects` compression is an instantaneous waveshaper | Low | S | Low | No attack/release; the real compressor is in `mastering_chain`. Label or point users at `--master` |
| P4 | Noise-shaped ("shaped") dither in `mastering_chain` | Low | M | Low | Advertised in the config docstring, unimplemented; falls back to TPDF with a warning |
| P3 | Consider TPDF dither by default, or a `--dither` CLI flag | Low | S | Med | Currently opt-in via `ProcessingConfig.apply_dither` only, to keep output deterministic (CHARTER §9). No CLI surface yet |
| P2 | Give `audio_restoration`'s 7 unique repair classes a CLI surface, or record that they stay standalone | Med | M | Med | The only orphan that is capability rather than duplication |
| P2 | Adopt `ci/proposed-ci.yml` → `.github/workflows/ci-cd.yml` | High (green CI) | XS (one `cp`) | Low | **Human-only** — needs `workflows` permission |
| P3 | Decide disposition of each orphaned asset (wire / keep-labeled / delete) | Med | Varies | Med | Deletion needs explicit user confirmation |
| P3 | Pure-Python true-peak perf, or a documented cap note | Low | S | Low | Currently ~0.4 s/65k samples |
| P4 | Plugin sandbox runtime boundary (restricted builtins for `exec_module`) | High (security) | L | High | Architectural; leaky if done partially — design first |
| P4 | Surround-channel loudness weighting | Low | M | Low | Only if a real multichannel use case appears |

---

## 4. How to keep this current

Re-verify any claim before trusting it — line numbers drift. Fast checks:

```bash
python -m pytest -q                      # confirm the test count in the header
grep -n "malware detection" advanced_validation.py
grep -n "RESTRICTED\|Government-Grade" gui/package.json
grep -rn "^import numpy\|^from scipy" spectral_editor.py audio_restoration.py
```

When you resolve a backlog item, move it out of §3, note it in `CHARTER.md`
§9 (the decision record), and bump the snapshot date above.
