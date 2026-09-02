"""Non-goal guard — mechanizes CHARTER §8.4 (scope discipline).

CHARTER §4 lists features that were repeatedly added then removed and must not
be reintroduced: quantum / neural / GPU / AI transcription / source separation.
§8.4 says this discipline should be "watchable by a grep ... in CI."

This test IS that grep, run as part of the ordinary pytest suite (so it works
without the `workflows` permission needed to edit CI). It scans the project's
Python sources for active fantasy-feature claims and fails if any are found.

It also scans the **CLI surface** -- subcommand names and their help strings --
because for a long time it did not, and a top-level command literally called
`ml` passed the source grep cleanly. And it scans the **user-facing documents**
(README, QUICKSTART, docs/), because after `ml` was deleted README.md still
advertised "advanced spectral/ML processing" as an optional capability. Each
extension was prompted by a real miss, in order: sources, then the CLI, then
the docs. A claim does not become true by moving to a file the guard skips. Its one operation ran spectral subtraction
and peak normalization: deterministic DSP, no model, no learning. A §4 claim
does not become harmless by living on the first screen a user reads rather than
in a source file; it becomes more visible.

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


# --- the CLI surface --------------------------------------------------------
#
# Source greps miss what argparse prints. These run the real CLI, because that
# is the only way to see what a user sees; the parser is built inline inside
# main() and is not importable, and refactoring product code to suit a guard
# would be the wrong way round.

CLI_FORBIDDEN_NAMES = {"ml", "ai", "neural", "quantum", "gpu", "transcribe",
                       "separate", "generate-music", "compose-ai"}

CLI_FORBIDDEN_HELP = [
    re.compile(r"\bmachine[\s-]*learning\b", re.IGNORECASE),
    re.compile(r"\bdeep[\s-]*learning\b", re.IGNORECASE),
    re.compile(r"\bneural\b", re.IGNORECASE),
    re.compile(r"\bAI[\s-]", re.IGNORECASE),
    re.compile(r"\bGPU[\s-]*accelerat", re.IGNORECASE),
    re.compile(r"\bquantum\b", re.IGNORECASE),
    re.compile(r"source[\s-]*separation", re.IGNORECASE),
]


def _cli_help(*args):
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *args, "--help"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=120,
    )
    return result.stdout


def _subcommand_names():
    """The choices argparse prints for the top-level command."""
    match = re.search(r"\{([a-z0-9_,\-]+)\}", _cli_help())
    assert match, "could not read the subcommand list out of --help"
    return match.group(1).split(",")


def test_no_subcommand_is_named_after_a_non_goal():
    offenders = sorted(set(_subcommand_names()) & CLI_FORBIDDEN_NAMES)

    assert not offenders, (
        f"CLI subcommand(s) {offenders} are named after a CHARTER §4 non-goal. "
        "A command name is a claim: it is the first thing a user reads and the "
        "last thing they check against what the code does. Rename it after what "
        "it actually does, or remove it."
    )


def test_no_help_text_claims_a_non_goal():
    violations = []
    for name in [None, *_subcommand_names()]:
        text = _cli_help() if name is None else _cli_help(name)
        for line in text.splitlines():
            if _is_removal_record(line):
                continue
            for pattern in CLI_FORBIDDEN_HELP:
                if pattern.search(line):
                    where = "main --help" if name is None else f"{name} --help"
                    violations.append(f"{where}: {line.strip()}")
                    break

    assert not violations, (
        "CHARTER §4 claim(s) in user-facing help text:\n  " + "\n  ".join(violations))


# --- user-facing documents --------------------------------------------------

DOC_FORBIDDEN = [
    re.compile(r"\bmachine[\s-]*learning\b", re.IGNORECASE),
    re.compile(r"\bML[\s/-]*(processing|features?|models?|pipeline)\b"),
    re.compile(r"\bdeep[\s-]*learning\b", re.IGNORECASE),
    re.compile(r"neural[\s-]*network", re.IGNORECASE),
    re.compile(r"\bAI[\s-]*(powered|driven|based)\b", re.IGNORECASE),
    re.compile(r"\bGPU[\s-]*accelerat", re.IGNORECASE),
    re.compile(r"quantum\s+(computing|processing)", re.IGNORECASE),
    re.compile(r"source[\s-]*separation", re.IGNORECASE),
]


def _user_facing_docs():
    yield PROJECT_ROOT / "README.md"
    yield PROJECT_ROOT / "QUICKSTART.md"
    for path in (PROJECT_ROOT / "docs").rglob("*.md"):
        if "agents" not in path.parts:      # agent instructions discuss non-goals by name
            yield path


def test_no_user_facing_doc_advertises_a_non_goal():
    violations = []
    for path in _user_facing_docs():
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _is_removal_record(line):
                continue
            for pattern in DOC_FORBIDDEN:
                if pattern.search(line):
                    violations.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}")
                    break

    assert not violations, (
        "CHARTER §4 claim(s) in user-facing documentation. These are read before "
        "any source file, so an overclaim here is the first thing a user learns:\n  "
        + "\n  ".join(violations)
    )


def test_the_doc_guard_would_catch_the_line_it_was_written_for():
    assert any(p.search("(advanced spectral/ML processing, real-time streaming)")
               for p in DOC_FORBIDDEN)
    # ...and does not fire on a sentence that records a removal.
    assert _is_removal_record("the add-then-remove cycle of ML features was removed")
    # ...nor on ordinary words that happen to contain the letters.
    assert not any(p.search("HTML output and XML config") for p in DOC_FORBIDDEN)


def test_the_cli_guard_would_catch_the_command_it_was_written_for():
    # `ml` is the command that prompted this guard: it passed the source scan
    # for its whole life. A guard nobody has seen fail is a guard nobody knows
    # works.
    assert "ml" in CLI_FORBIDDEN_NAMES
    assert any(p.search("Audio enhancement using machine learning")
               for p in CLI_FORBIDDEN_HELP)
    assert not any(p.search("Remove noise") for p in CLI_FORBIDDEN_HELP)


def test_the_replacement_for_ml_enhance_still_exists():
    # Deleting a command is only honest if what it did is still reachable.
    process_help = _cli_help("process")
    assert "--denoise" in process_help
    assert "--normalize" in process_help


def test_guard_actually_detects_a_violation():
    """Sanity check: the guard's patterns match a known fantasy line."""
    sample = "        self.lstm = nn.LSTM(input_size, hidden_size)"
    assert any(p.search(sample) for p in FORBIDDEN_PATTERNS)
    # ...and that a removal record is correctly exempted.
    assert _is_removal_record("# Quantum computing features removed in 2024 refactor")
