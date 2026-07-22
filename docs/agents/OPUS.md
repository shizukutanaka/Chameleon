# OPUS.md — guidance for deep-reasoning sessions

Read `CLAUDE.md` first; this file adds guidance specific to running as an
Opus-class model. Opus is the right tool for the hard, high-stakes, or
open-ended work on this codebase.

## Tasks this session is well-suited for
- **Architectural changes** — e.g. giving the plugin sandbox a real runtime
  boundary (restricted `__builtins__`/globals for `exec_module`), which
  `CHARTER.md` §9 flags as a project, not a patch.
- **DSP algorithm design** — new metering (surround-weighted loudness, higher-
  order true-peak), resampling, spectral work. Derive the math, then verify.
- **Resolving `CHARTER.md` §7 open strategic questions** and the
  `PRODUCT_ANALYSIS.md` §3 P4 items — the ones that need judgment, not just
  typing.
- **Leading adversarial review** of risky changes before they land.

## How to work here (the practices that have paid off)
- **Verify numeric claims against theory, always.** When this project added
  BS.1770 loudness, the stereo-summing fix was confirmed against the exact
  prediction `10·log10(2) = 3.01 dB`, and true-peak against the fs/4-at-45°
  worst case. Never ship a DSP number you haven't checked against a closed-form
  or an independent implementation.
- **Refuse to transcribe what you can't verify.** The reason
  `bs1770_loudness.measure_true_peak` *generates* its interpolation filter
  instead of copying the standard's example FIR table is that the table
  couldn't be verified here — an unverified "standard" coefficient set is
  exactly the unfalsifiable claim `CHARTER.md` §8 forbids. Hold this line.
- **Use independent verification for anything risky.** Spawning independent
  reviewer subagents to *refute* a change caught four real bugs in the
  `mastering_chain` K-weighting work (a dead low-sample-rate guard, NaN
  contamination, a tuple leak, a stale label) *before* they shipped. For
  correctness-critical or security-critical changes, run that adversarial pass
  and default reviewers to "refuted unless proven."
- **Fixing one bug often exposes the next.** Making the sync `BatchProcessor`
  path run surfaced two more latent crashes. Expect this; follow the thread and
  fix the chain, with a test per link.
- **Write the decision down.** Non-trivial choices go in `CHARTER.md` §9 with
  the reasoning, so the next session inherits the *why*.

## Guardrails
- The `CLAUDE.md` absolute rules bind you too — most importantly, **deletions
  need explicit user confirmation**, even when your deeper analysis makes the
  case for removal obvious. Make the case, then let the user decide.
- Don't force-push `main` or rewrite published history to "clean up" GitHub's
  merge-commit metadata — it's cosmetic and the cost is destructive.
- Scope large work into reviewable commits; a 500-line rewrite in one commit is
  hard to verify and hard to revert.
