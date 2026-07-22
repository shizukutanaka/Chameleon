# CLAUDE.md — working agreement for AI agents on Chameleon

You are working on **Chameleon**, a WAV-focused audio-processing **CLI** whose
differentiator is a **zero-dependency standard-library core** with a
path-validation security layer and **auditable, honestly-scoped** behavior.
This file is the common baseline. Read it fully before editing.

## Read these first (source of truth, in order)
1. **`CHARTER.md`** — the project's laws (scope, non-goals, threat model) and
   §9, the running decision record for *why* each change was made.
2. **`PROJECT_STATUS.md`** — current state snapshot (what's wired, what's broken).
3. **`PRODUCT_ANALYSIS.md`** — strengths, weaknesses, and the prioritized backlog.

## Absolute rules (violating these is a defect)
- **No fantasy features.** `CHARTER.md` §4 forbids quantum / neural / GPU /
  "AI" transcription / source-separation and similar. `tests/test_no_fantasy_features.py`
  greps for them in CI — adding one turns the suite red. Removed placeholder
  "AI/ML" code is not to be reintroduced.
- **Deletions need explicit, per-item user confirmation.** Orphaned modules
  (see `PRODUCT_ANALYSIS.md` §2) may look deletable, but removing files/classes
  is destructive — get a specific go-ahead naming the target. Never delete on
  the strength of a "clean this up" or a doc's "candidate for deletion" list.
- **No unverifiable standards claims.** If you cannot verify a coefficient
  table / algorithm against an authoritative source, do not label the result
  "standard-conformant." Generate from first principles and cross-check
  (as `bs1770_loudness.measure_true_peak` does vs scipy), or label it an
  estimate. Honest labeling is a hard requirement, not a nicety.
- **Keep the core dependency-free.** `analyze`/`normalize`/`batch`/`midi`/
  `analyze --loudness` must run with no third-party packages. Optional features
  guard their imports (`try: import numpy … except ImportError`) and degrade or
  raise a clear message — never make the default install need numpy/scipy.

## Verification gate (run before every commit)
```bash
python -m compileall -q .
python -m pytest -q                 # 215 passing, 1 skipped as of 2026-07-18
python validation_test.py
```
For DSP/numeric changes also run `python -m pytest -q -W error::RuntimeWarning`
(NaN/inf/overflow must not sneak through). Note: use `python`, not `python3` —
in this environment `python3` may resolve to an interpreter without numpy/scipy.

## Git conventions
- Develop on the feature branch you were assigned; never push to a different
  branch without explicit permission.
- Commit messages explain **why** in the body, not just what. End with the
  `Co-Authored-By: …` and `Claude-Session: …` trailers this repo already uses.
- Record every non-trivial decision in `CHARTER.md` §9; move resolved items out
  of `PRODUCT_ANALYSIS.md` §3.
- **A merged PR is finished** — start follow-up work from the latest `main`,
  don't reuse the merged branch history.
- Committer identity must be `Claude <noreply@anthropic.com>`
  (`git config user.email noreply@anthropic.com && git config user.name Claude`).

## Known traps (learned the hard way — see `CHARTER.md` §9)
- `core.BatchProcessor` result `.data` is a dict only on the error path; a
  successful op returns its own type (e.g. `AudioInfo`). Guard with `isinstance`.
- `mastering_chain` behaves differently with vs without scipy — test both paths
  (tests skip the scipy path under a minimal install rather than fake it).
- The active CI (`.github/workflows/ci-cd.yml`) is broken and **cannot be fixed
  by this automation account** (no `workflows` permission). A red CI check on a
  PR here reflects that stale workflow, not your change. See `ci/README.md`.

## Model-specific guidance
Pick the file matching the model you are running as:
- **`docs/agents/OPUS.md`** — deep-reasoning / large or architectural tasks.
- **`docs/agents/SONNET.md`** — fast, well-specified implementation tasks.
