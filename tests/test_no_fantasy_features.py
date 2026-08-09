"""Non-goal guard — mechanizes CHARTER §8.4 (scope discipline).

CHARTER §4 lists features that were repeatedly added then removed and must not
be reintroduced: quantum / neural / GPU / AI transcription / source separation.
§8.4 says this discipline should be "watchable by a grep ... in CI."

This test IS that grep, run as part of the ordinary pytest suite (so it works
without the `workflows` permission needed to edit CI). It scans the project's
Python sources for active fantasy-feature claims and fails if any are found.

Lines that *document the removal* of such a feature (e.g. "Quantum computing
features removed in 2024 refactor", "HAS_QUANTUM = False", "avoid speculative
quantum") are explicitly allowed — recording history is the point, not a
regression.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Active-claim patterns that indicate a reintroduced §4 non-goal.
FORBIDDEN_PATTERNS = [
    re.compile(r"\bimport\s+torch\b"),
    re.compile(r"\bimport\s+tensorflow\b"),
    re.compile(r"\bfrom\s+torch\b"),
    re.compile(r"\bnn\.Module\b"),
    re.compile(r"\bnn\.LSTM\b"),
    re.compile(r"neural[\s-]*network", re.IGNORECASE),
    re.compile(r"\bspleeter\b", re.IGNORECASE),
    re.compile(r"quantum\s+(computing|processing)", re.IGNORECASE),
]

# Substrings that mark a line as a sanctioned removal / avoidance record.
REMOVAL_MARKERS = ("removed", "avoid", "no longer", "= false", "deprecated",
                   "do not reintroduce", "non-goal")


# Build artifacts that must never be scanned as project sources.
_EXCLUDE_DIRS = {"tests", "__pycache__", ".venv", "venv", ".git", ".tox", "build", "dist"}


def _python_sources():
    """Yield project .py files, excluding tests and caches.

    Also skips interpreter / virtualenv / build artifacts (e.g. `.venv/lib/...`
    from an installed test dependency) so a transient dependency string like
    "NeuralNetwork" inside site-packages can never fail the scope guard.
    """
    for path in PROJECT_ROOT.rglob("*.py"):
        parts = set(path.parts)
        if parts & _EXCLUDE_DIRS:
            continue
        if path.name == "setup.py":
            # setup.py is packaging metadata; module names live here, not code.
            continue
        yield path


def _is_removal_record(line: str) -> bool:
    low = line.lower()
    return any(marker in low for marker in REMOVAL_MARKERS)


def test_no_reintroduced_fantasy_features():
    violations = []
    for path in _python_sources():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _is_removal_record(line):
                continue
            for pat in FORBIDDEN_PATTERNS:
                if pat.search(line):
                    rel = path.relative_to(PROJECT_ROOT)
                    violations.append(f"{rel}:{lineno}: {line.strip()}")
                    break

    assert not violations, (
        "Reintroduced CHARTER §4 non-goal(s) detected. Remove these or, if they "
        "document a removal, add a removal marker to the line:\n  "
        + "\n  ".join(violations)
    )


def test_guard_actually_detects_a_violation():
    """Sanity check: the guard's patterns match a known fantasy line."""
    sample = "        self.lstm = nn.LSTM(input_size, hidden_size)"
    assert any(p.search(sample) for p in FORBIDDEN_PATTERNS)
    # ...and that a removal record is correctly exempted.
    assert _is_removal_record("# Quantum computing features removed in 2024 refactor")
