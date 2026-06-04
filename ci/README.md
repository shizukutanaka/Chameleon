# Proposed CI workflow

`proposed-ci.yml` is a lean, working replacement for
`.github/workflows/ci-cd.yml`.

The existing workflow cannot pass: it runs `black`/`flake8`/`mypy`/`bandit`
that are not installed, runs `pytest tests/` with `integration`/`benchmark`
markers that do not exist, and has Docker/Trivy/Kubernetes deploy stages driven
by a `deployment_manager.py` that does not exist and secrets that are not set.

`proposed-ci.yml` instead:

- byte-compiles every module,
- import-checks the core modules on the standard library alone,
- runs `validation_test.py` and the `pytest` suite,
- exercises the `analyze` / `process --normalize` CLI end to end,
  across Python 3.9–3.12.

To adopt it, replace `.github/workflows/ci-cd.yml` with this file. It is kept
here rather than committed directly to `.github/workflows/` because the
automation account that produced this branch lacks the `workflows` permission
required to push workflow changes.
