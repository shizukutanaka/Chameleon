---
name: testing-chameleon
description: How to e2e-test the Chameleon CLI on this machine — venv interpreter paths, isolated-HOME onboarding, alias-sourcing in fresh shells, and exit-code expectations.
---

# Testing the Chameleon CLI

## Interpreter paths (CRITICAL)
This machine has **no `python` on PATH** — only Xcode's `python3` (3.9, unusable).
Always invoke the repo venv explicitly:
- Full deps: `/Users/devin/repos/Chameleon/.venv/bin/python` (3.12 + numpy/scipy/librosa/soundfile/fastapi)
- Stdlib-only: `/tmp/ch-bare-venv/bin/python` (pytest only — no third-party
  packages, so no blocker needed; `/tmp` can be wiped on restart — recreate
  with `python3 -m venv /tmp/ch-bare-venv && /tmp/ch-bare-venv/bin/pip install pytest`)
- numpy-only (blocks scipy/librosa/soundfile):
  `PYTHONPATH=$HOME/chameleon-blockers/numpy_only .venv/bin/python -m pytest -q`
  (stdlib blocker for the main venv lives alongside at `$HOME/chameleon-blockers/stdlib`;
  the `$HOME` copies persist — a `/tmp/chameleon-blockers` copy does NOT survive reboots)
CLAUDE.md's `python -m pytest` gate must be run via these absolute paths, in all
three configurations.

## Onboarding flow e2e
`personal_config.py setup` is interactive: 3 prompts (library path, perf mode,
auto-backup) — pipe `printf '\n\n\n'`. Run it with `HOME=/tmp/isolated` and
cwd=repo root; aliases.sh embeds `Path.cwd()` and `sys.executable`, so cwd and
interpreter at setup time are what the aliases will call.

## Sourcing generated aliases in a fresh shell
Aliases do NOT expand in non-interactive bash by default. Two working patterns:
- script file: `shopt -s expand_aliases` on its own line BEFORE `source ~/.chameleon/aliases.sh`, run via `env -i HOME=... PATH=/usr/bin:/bin bash --noprofile --norc script.sh`
- interactive-faithful: pipe commands into `bash -i` (expand_aliases is on)
`env -i` + `PATH=/usr/bin:/bin` guarantees no venv and no stray interpreters.

## Exit codes (README table, verified)
0 success · 2 usage/argparse/no-command · 3 input validation (missing dir,
wildcard/control-char args, empty batch dir, unreadable effects JSON) · 1
processing failure (e.g. corrupt-but-valid-magic WAV) · 4 security
· 130 interrupt. When every input is rejected at pre-flight, the command exits
with the classified reason (3 input / 4 security) — no traceback.

## Denoiser behavior (audio_restoration.py)
`AdaptiveDenoiser.denoise` needs librosa (full venv only) and raises
RuntimeError("no quiet sections...") on stationary input (quietest RMS decile
within ~6dB of loudest). To exercise the real denoise path, synthesize audio
with a genuine quiet lead-in: e.g. 0.5s of low-level noise before a loud noisy
sine, so the decile gate (loud > 2× quiet) passes. `AudioRestorer.restore`
records it under `skipped_processes` (auto mode) / `steps_skipped` (vinyl mode).

## Test WAVs
`tests/_helpers.write_sine_wave` (stdlib) or the `wave` module; plant copies
under `<isolated-HOME>/Music/Chameleon` for `audio-batch` to find them.
