# SONNET.md — guidance for fast implementation sessions

Read `CLAUDE.md` first; this file adds guidance specific to running as a
Sonnet-class model. Sonnet is the right tool for well-specified, bounded work
executed quickly and correctly.

## Tasks this session is well-suited for
- **Clearly-specified fixes** — a named bug with a known cause, a
  `PRODUCT_ANALYSIS.md` §3 P1–P3 item, a doc-sync. **Read that table fresh
  every session rather than trusting a copy of it here** — a stale, hardcoded
  task list is exactly the defect class this project keeps finding in its own
  documentation (see `CHARTER.md` §9's running record: nine fantasy docs, a
  broken k8s manifest, an unparseable OpenAPI spec, a setup wizard
  recommending a command that didn't exist). This file listed three specific
  "honesty pass" targets and an import-guard task for months after all of
  them were fixed; don't reintroduce that by writing the next one in here.
- **Test coverage for the modules `PRODUCT_ANALYSIS.md`'s Coverage-gaps
  section currently names as untested.** Check the live list; it moves, and
  don't copy it into this file — the dated copy that used to sit here had
  already drifted when it was written (it named `spectral_editor.py` while
  `batch_automation.py` sat in the same section).
- **P4 items are Opus-shaped, not Sonnet-shaped** (per `OPUS.md`) — they
  need judgment about a design or a risk tradeoff, not just execution. Leave
  them for that session.

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
