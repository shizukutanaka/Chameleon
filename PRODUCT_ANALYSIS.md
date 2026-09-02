# Chameleon — Product Analysis (Strengths, Weaknesses, Improvement Backlog)

**Snapshot date:** 2026-08-25 (claims re-verified against the code) ·
**Version:** 1.1.0 · **Tests:** the suite runs in three dependency
configurations and is green in all of them —
**324 passed** on the standard library alone, **365** with numpy,
**454** with numpy + scipy (2 skipped; the skips are fastapi-gated).

> Every claim in this file was re-checked against the code on the snapshot
> date. Eight were false — including four "fast checks" in §4 that could no
> longer fire, and a headline strength that overstated which commands run
> without numpy. A checklist whose items always pass is not verification; it
> is the appearance of it. Re-run, do not re-read.

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

- **Zero-dependency core.** `analyze` (including `--loudness`, `--detailed`
  and `--spectrum`), `normalize`, `mono`, `trim`, `batch` and
  `midi compose` / `midi generate` all run on the Python standard library
  alone. This is the product's reason to exist (`CHARTER.md` §1) — do not make
  the default install require numpy/scipy.
  *Checked 2026-08-25, and the previous version of this line was wrong:* it
  listed `midi` without qualification, but `midi extract` and `midi analyze`
  load audio into arrays and exit 1 without numpy. Only the two generative
  MIDI operations are dependency-free. Verified by running each subcommand
  with numpy blocked and reading the exit code.
- **Verifiable standards conformance, not claimed conformance.** The BS.1770-4
  K-weighting coefficients in `bs1770_loudness.py` are validated against the
  standard's published reference table (`tests/test_bs1770_loudness.py`), and
  where an authoritative coefficient table could not be verified (true-peak
  Annex 2), the code *generates* its filter from first principles and
  cross-checks it against scipy to <0.05 dB rather than transcribing numbers
  it cannot prove. Honesty about measurement accuracy is a feature.
- **Honest labeling as a discipline.** Estimates are labeled estimates
  (true-peak), approximations are labeled approximate (the RMS fallback in
  `mastering_chain.LoudnessMeter`). The now-deleted `performance_optimizer.py`
  even corrected its own earlier "SIMD" overclaim to "SIMD-like … not real
  vector instructions." This is the culture to keep.
- **Mechanized scope discipline, including the surface users read.**
  `tests/test_no_fantasy_features.py` scans the project's Python sources for
  the forbidden feature classes in `CHARTER.md` §4/§8.4 (quantum / neural /
  GPU / AI transcription / source separation) — *and*, since 2026-08-25, the
  CLI surface itself: every subcommand name and every `help=` string, read by
  running the real CLI. That extension was not theoretical. A top-level
  command literally named `ml` passed the source-only grep for its entire
  life, because argparse strings are not source. The guard is negative-tested:
  reintroducing that command makes it fail.
- **Real verification gate, run against three dependency configurations.**
  `compileall` + `pytest` + `validation_test.py` is green with no third-party
  packages (324 tests), with numpy (365) and with numpy + scipy (454) — up
  from 22 tests at the start of the hardening effort. The three-way run is
  itself a differentiator and is newer than it looks: until 2026-08-25 twelve
  test modules imported numpy unguarded, so on a bare install `pytest` failed
  at *collection* and ran nothing. Verifying the dependency-free core required
  installing the dependency it is defined by not needing.
- **The suite is mutation-checked, not just green.** "445 tests pass" says
  nothing on its own about whether they would fail if the code broke. On
  2026-08-25 six of this branch's fixes were deliberately reverted in the
  source, one at a time, and the suite was re-run: the declipper's unbalanced
  crossfade, the resampler's anti-aliasing cutoff, the key-profile rotation,
  `--mono`'s idempotency, the quantiser's rounding, and a K-weighting
  coefficient nudged by 0.1%. **All six were caught**, each by the test written
  for it. A static audit of the suite in the same pass found no vacuous
  tests — no `assert True`, no `x == x`, nothing swallowing exceptions, and the
  only three assertion-free tests are "must not raise" checks where the call
  itself is the assertion.
- **DSP claims are checked against ground truth, not eyeballed.** The
  regression suite asserts measured quantities — a clean sine survives
  restoration bit-exactly, a clipped signal comes back 14.5 dB closer to the
  unclipped truth, the loudness meter agrees with `pyloudnorm` to 0.043 LU.
  Several defects in this codebase were invisible to code review and obvious
  to a measurement.
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

**Excess — re-measured 2026-08-25, after the deletions and the wiring.**

| Bucket | 2026-08-08 | 2026-08-25 |
|--------|------:|------:|
| Reachable from the CLI (the stated product) | 9,367 (66.5%) | **10,432 (73.0%)** |
| Reachable only via `server` + `[api]` extra | 1,600 (11.4%) | 1,572 (11.0%) |
| **Orphaned (no entry point reaches it)** | **3,121 (22.2%)** | **2,296 (16.1%)** |

Orphaned code fell from roughly one line in four to one in six. Two causes,
and they pull in opposite directions: ~800 lines were **deleted**
(`performance_optimizer.py`, `core.py`'s `RealtimeAudioProcessor`,
`api_server.py`'s phantom imports) and `audio_restoration.py` was **wired in**
rather than removed, moving 530 lines from orphaned to reachable. Deleting is
not the only way to stop something being dead.

The three modules still in the orphan column are `batch_automation.py`,
`spectral_editor.py` and `personal_config.py`. Each is allow-listed with a
written reason in `tests/test_no_orphan_modules.py`, which fails if a fourth
appears. Re-measure with the reachability walk in that test rather than
trusting these numbers.

Specific findings, each cited so it can be re-verified:

- ~~**`performance_optimizer.py` is ~100% redundant.**~~ — **deleted
  2026-08-25** with per-item confirmation. `get_optimal_worker_count`
  duplicated `main.py`'s `ProcessingConfig.from_environment` (the *third*
  place worker count was resolved); `CacheManager` was a weaker `core.py`
  `MemoryManager` (which does byte-accounted LRU + mmap); `SIMDOperations`'
  operations all exist in `core.py`. Same argument that retired
  `config_manager.py`. Its `normalize_int16` also silenced any signal peaking
  above ~34% FS — see `CHARTER.md` §9.
- **Spectral subtraction is implemented three times**: `main.py`'s
  `remove_noise`, `audio_restoration.py`'s `AdaptiveDenoiser`, and
  `spectral_editor.py`'s `noise_reduce_selection`.
- ~~**`audio_restoration.py` is blocked on a CLI surface**~~ — **wired
  2026-08-25** as `process --declip` / `--dehum`, after an audit that had to
  come first: the declipper reported 880 clipped regions in one second of a
  *clean* sine and damaged every one, and the hum detector answered yes to
  audio containing no hum. Click, crackle, gap-repair and the librosa denoiser
  are deliberately **not** exposed — see §2 for why click detection in
  particular has no trustworthy implementation here.
- **`batch_automation.py` is genuine capability pointed the wrong way** — a
  generic DAG/workflow engine, i.e. §4's "a second product". Its own demo
  builds tasks for MP3/FLAC/OGG transcoding this product cannot do.
- ~~**`api_server.py` imports three modules that have never existed**
  (`government_auth`, `secure_core`, `high_performance_core`)~~ — **deleted
  2026-08-25** with per-item user confirmation, along with the six unreachable
  `if HAS_SECURE_MODULES:` branches and the three inert `skipif`s in
  `tests/test_api_fallback.py`. See `CHARTER.md` §9.

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

### Unsolved DSP problems (stated, not hidden)
These are the honest residue of the 2026-08-25 restoration audit. They are not
bugs to fix but problems without a known-good answer in this codebase.

- **Click detection has no trustworthy implementation.** Two candidates were
  measured and both have a regime where they destroy audio rather than repair
  it: the shipped envelope/z-score detector reports 354 clicks in one second
  of white noise (pulling its peak from 0.473 to 0.325), and a
  second-difference/MAD detector reports 1,764 in hard-clipped material — one
  per clipping corner, since a corner is a derivative discontinuity that looks
  exactly like an impulse. Separating the two needs a model of what the signal
  should do next, i.e. the autoregressive prediction the old code's comment
  falsely claimed. `--declick` is therefore **not** shipped. Shipping a third
  mediocre detector would be the error `CHARTER.md` §9 keeps warning about.
- **Declipping cannot see clipping that was attenuated afterwards**, and a
  *pure* tone at or below 33 Hz at full scale reads as a plateau at the
  detector's one-LSB flatness tolerance (0 false regions at 35 Hz, 24 at
  32 Hz, 60 at 30 Hz). Real bass carries harmonics that curve the peak — 40 Hz
  with two harmonics gives zero — and a test pins the boundary so the
  docstring cannot drift from the behaviour.
- **Spectral subtraction is still implemented three times**: `main.py`'s
  `remove_noise` (fixed 2026-08-08), `audio_restoration.py`'s
  `AdaptiveDenoiser` (librosa-only) and `spectral_editor.py`'s
  `noise_reduce_selection` (orphaned). Only the first is wired and tested.
  Consolidating them is a real refactor, not a tidy-up.

### Coverage gaps
- ~~**Zero test coverage:** `personal_config.py`.~~ — covered 2026-08-25 by
  `tests/test_personal_config.py`, which found three defects in the two
  functions a new user hits first.
- **The orphaned modules' DSP is still untested.** `spectral_editor.py` and
  `batch_automation.py` have import-safety coverage
  (`tests/test_orphaned_import_safety.py`, `tests/test_smoke.py`) but nothing
  exercises what they compute. The `audio_restoration` audit is the reason to
  care: every defect it turned up was in code that imported cleanly.

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
Measured 2026-08-25: `batch_automation.py`, `spectral_editor.py` (both kept by
explicit user decision over a recommendation to delete) and `personal_config.py`
(a documented onboarding entry point — reachable by a *user* via
`quick_install`, just not by an import). Outside the Python module list:
`gui/`, `openapi_spec.yaml`.

Per project practice, deletions require **explicit, per-item user
confirmation** — do not delete on the strength of this list.
`tests/test_no_orphan_modules.py` holds the same three in an allow-list with
written justifications and fails if a fourth appears, so this section and that
test must agree.

Resolved from this list on 2026-08-25: `core.py`'s `RealtimeAudioProcessor`
and `performance_optimizer.py` (deleted, with confirmation) and
`audio_restoration.py` (wired into the CLI instead).

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
| ~~P1~~ | ~~Fix tempo estimation (4x too slow, tempo-dependent resolution)~~ | High | S | Low | **DONE 2026-08-08** — 120 BPM was reported as 30; log-scale interval bucketing + 40-240 BPM folding |
| ~~P1~~ | ~~Fix key detection (profile rotated backwards) and seventh-chord collapse~~ | High | S | Low | **DONE 2026-08-08** — 11/12 keys were wrong; all 24 now correct. Jaccard chord scoring + bass-note tie-break |
| ~~P1~~ | ~~Fix denoise estimating noise from the signal~~ | High | S | Low | **DONE 2026-08-08** — per-bin percentile + Rayleigh scaling; material without a silent lead-in went -19.4 dB → -0.1 dB |
| ~~P1~~ | ~~Fix compressor's non-monotonic soft knee~~ | High | S | Low | **DONE 2026-08-08** — centred quadratic knee (Giannoulis 2012); output no longer drops 2 dB at the knee |
| ~~P2~~ | ~~Add minimal tests for the remaining zero-coverage modules~~ | Med | S | Low | **DONE 2026-08-25** — 18 tests for `personal_config`, which found a config loader that died on any file written by another version, an unhelpful crash on malformed JSON, and playlists stamped with the home directory's mtime. (`performance_optimizer` was deleted instead — the honest resolution for code with no callers) |
| P3 | `apply_effects` compression is an instantaneous waveshaper | Low | S | Low | No attack/release; the real compressor is in `mastering_chain`. Label or point users at `--master` |
| P4 | Noise-shaped ("shaped") dither in `mastering_chain` | Low | M | Low | Advertised in the config docstring, unimplemented; falls back to TPDF with a warning |
| P3 | Consider TPDF dither by default, or a `--dither` CLI flag | Low | S | Med | Currently opt-in via `ProcessingConfig.apply_dither` only, to keep output deterministic (CHARTER §9). No CLI surface yet |
| ~~P2~~ | ~~Give `audio_restoration` a CLI surface~~ | Med | M | Med | **DONE 2026-08-25** — `process --declip` / `--dehum` ship after an audit that found the declipper damaging clean audio and the hum detector firing on silence. Click/crackle/gap/denoise deliberately not exposed: no trustworthy detector. See `CHARTER.md` §9 |
| P2 | Adopt `ci/proposed-ci.yml` → `.github/workflows/ci-cd.yml` | High (green CI) | XS (one `cp`) | Low | **Human-only** — needs `workflows` permission |
| ~~P3~~ | ~~Decide disposition of each orphaned asset~~ | Med | Varies | Med | **DONE 2026-08-25** — every module now has a decision: deleted (2), wired (1), or allow-listed with a written reason (3). `tests/test_no_orphan_modules.py` fails if a new one appears |
| P3 | Consolidate the three spectral-subtraction implementations | Low | M | Med | `main.py` (wired, fixed), `audio_restoration` (librosa-only), `spectral_editor` (orphaned). A real refactor, not a tidy-up |
| P4 | A trustworthy click detector, or a documented decision not to have one | Med | L | High | Both measured candidates destroy audio in some regime — see §2. Needs AR prediction or equivalent; do not ship a third guess |
| P3 | Pure-Python true-peak perf, or a documented cap note | Low | S | Low | Currently ~0.4 s/65k samples |
| P4 | Plugin sandbox runtime boundary (restricted builtins for `exec_module`) | High (security) | L | High | Architectural; leaky if done partially — design first |
| P4 | Surround-channel loudness weighting | Low | M | Low | Only if a real multichannel use case appears |

---

## 4. How to keep this current

Re-verify any claim before trusting it — line numbers drift and prose rots.

The checks that used to live here were four greps for `malware detection`,
`Government-Grade` in `gui/package.json`, and unguarded numpy/scipy imports.
On 2026-08-25 **all four returned zero hits**: every problem they looked for
had been fixed, some of them months earlier. A check that cannot fail teaches
you nothing and costs you the feeling of having checked. They are replaced
with commands that produce a *number to compare*, not a hit to hope for.

```bash
# 1. The three dependency configurations. Header says 324 / 365 / 454.
python -m pytest -q                       # numpy + scipy present
#   ...and with numpy/scipy made unimportable, and with only scipy blocked:
#   see tests/test_stdlib_operations.py for the sitecustomize blocker pattern.

# 2. Reachability, for the §1b table. Reuses the walk the guard test performs.
python -m pytest -q tests/test_no_orphan_modules.py

# 3. Scope discipline, sources *and* the CLI surface.
python -m pytest -q tests/test_no_fantasy_features.py

# 4. Which commands actually survive without numpy — the §1 claim that was
#    wrong for months. Run each one with numpy blocked and read the exit code.
python main.py --help
```

**The deep check, worth running before any claim that the suite is sound:**
break the code on purpose and confirm the suite notices. Revert one fix in the
source, run only its test file, restore. Six known-good pairs, all verified to
fail-then-pass on 2026-08-25:

| Revert | Should fail |
|---|---|
| `(1.0 - window)` → `(1.0 - window) * 0.5` in `audio_restoration.py` | `tests/test_declipping.py` |
| `cutoff = min(1.0, ratio)` → `cutoff = 1.0` in `main.py` | `tests/test_resample_quality.py` |
| `(pc - tonic)` → `(pc + tonic)` in `midi_analysis.py` | `tests/test_music_theory.py` |
| drop the `shutil.copyfile` in `core.py`'s already-mono branch | `tests/test_stdlib_operations.py` |
| `np.round(scaled)` → `scaled` in `main.py` | `tests/test_quantization.py` |
| any K-weighting coefficient × 1.001 in `bs1770_loudness.py` | `tests/test_bs1770_loudness.py` |

A green suite that survives none of these is measuring nothing. Restore the
file after each one — `git status` must come back empty.

Two habits worth more than any of the above:

- **Read the CLI's own output.** Three false statements were fixed on
  2026-08-25 that had been printing on nearly every command for months — a
  security warning that fired on ordinary audio, a frequency range of
  `0.0-0.0Hz`, and a dynamic range of `0.0dB`. No test caught them because no
  test was looking at what the user reads.
- **Ask what a claim would look like if it were false**, then run that. "The
  suite is green" was true and also hid that on a bare install it collected
  nothing at all.

When you resolve a backlog item, move it out of §3, note it in `CHARTER.md`
§9 (the decision record), bump the snapshot date above, and re-run the numbers
rather than editing them by hand.
