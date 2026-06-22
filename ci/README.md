# Proposed CI workflow

`proposed-ci.yml` is a lean, working replacement for the active
`.github/workflows/ci-cd.yml`.

The active workflow cannot pass: it references a `deployment_manager.py` and
`tests/smoke/` / `tests/health/` directories that do not exist, and runs
`pytest -m integration` / `-m benchmark` markers with no matching tests.

`proposed-ci.yml` instead, across Python 3.9–3.12:

- byte-compiles every module,
- import-checks the core modules on the standard library alone,
- runs `validation_test.py` and the `pytest` suite,
- exercises the `analyze` / `process --normalize` CLI end to end.

## Adopting it

Replace `.github/workflows/ci-cd.yml` with this file:

```bash
cp ci/proposed-ci.yml .github/workflows/ci-cd.yml
git rm ci/proposed-ci.yml
```

It is kept here rather than committed directly under `.github/workflows/`
because the automation account that produced this branch lacks the `workflows`
permission required to push workflow changes. A maintainer with that permission
needs to perform the copy above.
