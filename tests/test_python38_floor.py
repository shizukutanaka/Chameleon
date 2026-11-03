"""Floor guard — the declared minimum is Python 3.8, but local dev runs 3.12,
so APIs added in 3.9+ compile and pass locally, then crash the CLI only on the
CI 3.8 job. That is exactly what happened with ``Path.is_relative_to()``
(main.py, batch command: 7 failures, CI job 126075311866).

This test is a grep for the small set of stdlib calls that exist on >=3.9 but
not 3.8 — the same style as tests/test_no_fantasy_features.py, run in the
ordinary suite because the repo's automation account cannot edit CI. Comment
lines are skipped: documenting the incompatibility is allowed.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_CALLS = [
    re.compile(r"\.is_relative_to\("),   # pathlib, added 3.9
    re.compile(r"\.removeprefix\("),     # str/bytes, added 3.9
    re.compile(r"\.removesuffix\("),     # str/bytes, added 3.9
    re.compile(r"\bfunctools\.cache\b"), # functools.cache, added 3.9 (lru_cache exists)
    re.compile(r"\brandom\.randbytes\("),
]


def _product_sources():
    # The stdlib-core CLI and its imports: the top-level modules, not tests or
    # tooling (tests may use newer APIs guarded by skips).
    return sorted(PROJECT_ROOT.glob("*.py"))


def test_no_python39_only_apis_in_product_code():
    offenders = []
    for path in _product_sources():
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for pattern in FORBIDDEN_CALLS:
                if pattern.search(line):
                    offenders.append(
                        f"{path.name}:{lineno}: {pattern.pattern!r} -> {line.strip()}"
                    )
    assert not offenders, (
        "Python >=3.9-only API used in product code (floor is 3.8):\n"
        + "\n".join(offenders)
    )
