# Proposed CI workflow

`proposed-ci.yml` is a lean, **locally verified** replacement for the active
`.github/workflows/ci-cd.yml`.

The active workflow cannot pass: it references a `deployment_manager.py` and
`tests/smoke/` / `tests/health/` directories that do not exist, and runs
`pytest -m integration` / `-m benchmark` markers with no matching tests. A red
check on a pull request here reflects that file, not the change under review.

That is not the complete inventory — verified on 2026-09-22, the same file
also:

- installs only the comments-only `requirements.txt` in the `code-quality`
  job, so `black`, `flake8`, `mypy` and `bandit` are never installed and all
  four steps fail on a missing command;
- runs `pip install -e .[dev,full]` — there is no `full` extra (the real
  ones are `audio`, `api`, `dev`);
- passes `--timeout=300` to pytest with no `pytest-timeout` in the dev
  extra, and `--staging-url` / `--production-url` flags no conftest defines;
- invokes `kubectl create backup`, which is not a kubectl verb;
- uses `actions/create-release@v1`, an action GitHub archived years ago;
- and stamps release notes advertising "AI analysis", "real-time streaming
  and visualization" and "enterprise security" — claims the product does
  not make (`CHARTER.md` §4 forbids the first outright).

## What the replacement does

Two jobs, because this project makes two different promises.

**`stdlib-only`** (Python 3.9 and 3.12) installs `pytest` and nothing else,
then refuses to start if numpy, scipy, librosa or soundfile turn out to be
present — a bare-install job that quietly runs against numpy proves nothing.
It byte-compiles every module, imports the core ones, runs `validation_test.py`
and the suite, and drives `analyze`, `analyze --loudness`,
`process --normalize --mono --trim` and `batch trim` end to end. This is the
job that defends the project's actual differentiator.

**`audio-extra`** (Python 3.9–3.12) installs numpy **and scipy**, runs the full
suite, repeats it with `-W error::RuntimeWarning` so NaN/inf/overflow cannot
slip through the DSP paths, and exercises `process --declip --dehum` and
`process --master`.

Installing scipy in that second job matters more than it looks: with numpy
alone, roughly ninety tests skip rather than run, so a green tick would mean
much less than it appears to.

Every step above has been executed locally against a clean copy of the tree.

## Adopting it

```bash
cp ci/proposed-ci.yml .github/workflows/ci-cd.yml
git rm ci/proposed-ci.yml
```

**A human has to run that.** The automation account that produced this branch
cannot write under `.github/workflows/` — `git push` is rejected with
"refusing to allow a GitHub App to create or update workflow ... without
`workflows` permission", and the REST contents API returns 403. Both were
re-confirmed on 2026-08-25.
