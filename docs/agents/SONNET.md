# SONNET.md — guidance for fast implementation sessions

Read `CLAUDE.md` first; this file adds guidance specific to running as a
Sonnet-class model. Sonnet is the right tool for well-specified, bounded work
executed quickly and correctly.

## Tasks this session is well-suited for
- **Clearly-specified fixes** — a named bug with a known cause, a
  `PRODUCT_ANALYSIS.md` §3 P1–P3 item, a doc-sync.
- **Test coverage** — adding tests for the zero-coverage modules listed in
  `PRODUCT_ANALYSIS.md` §2 (`audio_restoration`, `spectral_editor`,
  `personal_config`): import + a happy path each.
- **Honesty passes** — the P1 docstring/metadata overclaim fixes
  (`advanced_validation.py:4`, `gui/package.json`, `batch_automation.py:4`).
  Text-only, low-risk, high-value.
- **Import-guard hygiene** — wrapping the unconditional numpy/scipy imports in
  `spectral_editor.py` / `audio_restoration.py` to match the guarded pattern
  used elsewhere.

## How to work here
- **One concern per commit.** Keep each change small enough to verify and
  revert on its own. Match the surrounding code's style, comment density, and
  naming.
- **Run the gate every time** (from `CLAUDE.md`): `compileall`, `pytest -q`,
  `validation_test.py`. For anything touching DSP/numbers, add
  `-W error::RuntimeWarning`.
- **Reuse, don't reinvent.** Before writing a helper, grep for an existing one
  (e.g. loudness helpers live in `bs1770_loudness.py`; batch dispatch in
  `core.BatchProcessor._build_operation_runner`).
- **Stay honest.** If a change would make the code claim more than it does
  (accuracy, "standard-conformant", "malware detection"), stop — that's a
  defect here, not a polish.

## When to stop and escalate (don't push through)
- **A deletion looks warranted** → do NOT delete. Record it as a
  `CHARTER.md` §9 open question (or confirm it's already listed) and ask the
  user with a specific, named proposal.
- **The fix turns architectural** (touches the sandbox boundary, the security
  core `security_validator.py`, or needs a design decision) → hand it to an
  Opus session or the user rather than improvising a big change.
- **A "standard" coefficient/algorithm can't be verified** → follow
  `CLAUDE.md`'s rule: generate-and-cross-check, or label it an estimate; never
  transcribe unverified numbers.
- **Ambiguity about intent** → ask one focused question rather than guessing on
  a change that's hard to undo.

## Reminders
- Committer identity `Claude <noreply@anthropic.com>`; explain *why* in commit
  bodies; a merged PR is finished (branch from fresh `main` for follow-ups).
- A red CI check on your PR is almost certainly the known-broken
  `.github/workflows/ci-cd.yml`, not your change — verify locally with the gate
  and note it (see `ci/README.md`).
