# Chameleon — Product Analysis (Strengths, Weaknesses, Improvement Backlog)

**Snapshot date:** 2026-07-18 · **Version:** 1.1.0 · **Tests:** 215 passing, 1 skipped

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

## 2. Weaknesses (known — do not paper over)

### Correctness / install integrity
- **Orphaned modules break the stdlib-only story on import.**
  `spectral_editor.py:9` (`import numpy as np`) and `audio_restoration.py:10-12`
  (`import numpy` + `from scipy import …`) import third-party packages
  *unconditionally* at module top. They are not wired into `main.py`/`api_server.py`
  (only referenced by `setup.py` packaging), so they don't break the default
  install today — but `import spectral_editor` from anywhere would. Contrast
  the correct pattern in `mastering_chain.py` / `spectral_utils.py` (guarded).
- **`api_server.py:27-34`** imports `fastapi`/`pydantic`/`uvicorn`
  unconditionally. Mitigated because `main.py`'s `server` subcommand launches
  it by string (`uvicorn.run("api_server:app", …)`) and guards the uvicorn
  import — so it is a latent fragility, not a live bug. Covered by
  `tests/test_api_routes.py` / `tests/test_api_fallback.py`.

### Honesty residue (docstring/metadata overclaims)
- **`advanced_validation.py:4`** claims "malware detection capabilities"; the
  code does file-structure integrity + tamper detection (its own line 309 says
  so honestly). Overclaim — exactly what `CHARTER.md` §8 warns against.
- **`gui/package.json`** still carries `"description": "Government-Grade Audio
  Processing GUI"` (:4), `"author": "Chameleon Security Team"` (:8), and
  `"license": "RESTRICTED"` (:9) — inconsistent with the repo's MIT license
  and with `gui/README.md`'s own honest "experimental / not wired up" framing.
- **`batch_automation.py:4`** "Intelligent batch processing with workflow
  automation and scheduling" overclaims relative to its orphaned status.

### Coverage gaps
- **Zero test coverage:** `audio_restoration.py`, `spectral_editor.py`,
  `performance_optimizer.py`, `personal_config.py`.

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
| P1 | Fix 3 docstring/metadata overclaims (`advanced_validation.py:4`, `gui/package.json`, `batch_automation.py:4`) | Med (honesty = the brand) | XS | Low | Same shape as prior approved honesty passes; text-only |
| P1 | Guard the unconditional numpy/scipy imports in `spectral_editor.py` / `audio_restoration.py` (or record why not) | Med | S | Low | Makes `import`-safety uniform with the rest of the tree |
| P2 | Add minimal tests for the 4 zero-coverage modules | Med | M | Low | Even import + one-happy-path each raises the floor |
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
