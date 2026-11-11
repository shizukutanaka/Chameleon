# CI workflow

The active CI workflow is [`.github/workflows/ci-cd.yml`](../.github/workflows/ci-cd.yml).
It was adopted from the former `ci/proposed-ci.yml` draft (retired on adoption),
plus two changes made at adoption time: `timeout-minutes: 15` on both jobs, and
the Python matrix narrowed to 3.11 / 3.12 to match `requires-python >=3.11`.

Two jobs, because this project makes two different promises.

**`stdlib-only`** installs `pytest` and nothing else, then refuses to start if
numpy, scipy, librosa or soundfile turn out to be present — a bare-install job
that quietly runs against numpy proves nothing. It byte-compiles every module,
imports the core ones, runs `validation_test.py` and the suite, and drives
`analyze`, `analyze --loudness`, `process --normalize --mono --trim` and
`batch trim` end to end. This is the job that defends the project's actual
differentiator.

**`audio-extra`** installs numpy **and scipy**, runs the full suite, repeats it
with `-W error::RuntimeWarning` so NaN/inf/overflow cannot slip through the DSP
paths, and exercises `process --declip --dehum` and `process --master`.

Installing scipy in that second job matters more than it looks: with numpy
alone, roughly ninety tests skip rather than run, so a green tick would mean
much less than it appears to.

The workflow this replaced had no `timeout-minutes` anywhere and a
coverage-enabled `test` job slow enough that the gate effectively answered
"red, or silent for six hours". Coverage is intentionally not part of the gate;
if it returns, it should be a separate non-gating job.
