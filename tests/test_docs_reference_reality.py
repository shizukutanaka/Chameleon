"""Documentation must not teach an API or a script that does not exist.

On 2026-08-25 nine documentation files were deleted for describing a different,
nonexistent product. Seven told the reader to `import chameleon_audio`; one used
`audio_tool`; three invoked `python enterprise_cli.py`, `python chameleon_cli.py`
or `python security_tools.py`. **None of those modules or scripts has ever
existed in this repository, in any commit.** Several pages were branded
"Enterprise Edition" and "Commercial Release" -- the vocabulary README says the
charter exists to stop.

This is the same defect that `api_server.py` carried until PR #23: imports of
three modules that never existed. There it was dead code behind a permanently
false flag. Here it was worse, because documentation is not dead -- someone
copies it into a terminal and it fails, and the failure looks like their
mistake rather than ours.

`tests/test_no_fantasy_features.py` guards the *vocabulary* of CHARTER §4.
This file guards something narrower and more mechanical: every module a doc
tells you to import, and every script a doc tells you to run, must be a thing
that is actually here.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Third-party and standard-library names a doc may legitimately mention without
# this repository providing them.
EXTERNAL = {
    "os", "sys", "json", "time", "math", "wave", "struct", "pathlib", "re",
    "subprocess", "logging", "asyncio", "typing", "dataclasses", "tempfile",
    "shutil", "argparse", "threading", "hashlib", "datetime", "collections",
    "numpy", "scipy", "pytest", "psutil", "requests", "fastapi", "uvicorn",
    "librosa", "soundfile", "mido", "pydantic", "httpx", "pyaudio", "pyloudnorm",
}


def _documentation_files():
    """Docs written for users. `docs/agents/` is excluded deliberately: those
    files instruct AI contributors and must name the non-goals to forbid them."""
    for path in (PROJECT_ROOT / "docs").rglob("*.md"):
        if "agents" not in path.parts:
            yield path
    for name in ("README.md", "QUICKSTART.md", "MIDI_USAGE.md", "DEPLOYMENT_GUIDE.md"):
        candidate = PROJECT_ROOT / name
        if candidate.is_file():
            yield candidate


def _relative(path):
    return path.relative_to(PROJECT_ROOT)


def test_no_doc_imports_a_module_that_does_not_exist():
    violations = []
    pattern = re.compile(
        r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", re.M)

    for path in _documentation_files():
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            module = (match.group(1) or match.group(2)).split(".")[0]
            if module in EXTERNAL or (PROJECT_ROOT / f"{module}.py").is_file():
                continue
            if (PROJECT_ROOT / module).is_dir():
                continue
            line = text[:match.start()].count("\n") + 1
            violations.append(f"{_relative(path)}:{line}: imports `{module}`")

    assert not violations, (
        "Documentation imports module(s) this repository does not provide. A "
        "reader copies this into a terminal and it fails, and the failure looks "
        "like their mistake:\n  " + "\n  ".join(violations))


def test_no_doc_tells_you_to_run_a_script_that_does_not_exist():
    violations = []
    pattern = re.compile(r"python3?\s+([A-Za-z_][\w/]*\.py)")

    for path in _documentation_files():
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            script = match.group(1)
            if (PROJECT_ROOT / script).is_file():
                continue
            line = text[:match.start()].count("\n") + 1
            violations.append(f"{_relative(path)}:{line}: `python {script}`")

    assert not violations, (
        "Documentation invokes script(s) that do not exist:\n  "
        + "\n  ".join(violations))


@pytest.mark.parametrize("ghost", ["chameleon_audio", "audio_tool", "enterprise_cli",
                                   "chameleon_cli", "security_tools"])
def test_the_named_ghosts_really_are_absent(ghost):
    # Pinned by name because each was documented for months. If one is ever
    # genuinely added, delete its entry here rather than leaving a test that
    # asserts the absence of a file that now exists.
    assert not (PROJECT_ROOT / f"{ghost}.py").is_file()


def test_the_guard_would_catch_a_reintroduced_ghost(tmp_path):
    # The guard is only worth its line if it fails on the thing it was written
    # for. This is the exact shape of the deleted docs' first code block.
    sample = "```python\nfrom chameleon_audio import AudioProcessor\n```"
    pattern = re.compile(
        r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", re.M)
    match = pattern.search(sample)

    assert match is not None
    module = (match.group(1) or match.group(2)).split(".")[0]
    assert module == "chameleon_audio"
    assert not (PROJECT_ROOT / f"{module}.py").is_file()


def test_real_imports_are_not_flagged():
    # The mirror: the guard must accept what the project genuinely provides,
    # or it will be disabled the first time it cries wolf.
    for module in ("core", "main", "bs1770_loudness", "security_validator"):
        assert (PROJECT_ROOT / f"{module}.py").is_file()
    assert "numpy" in EXTERNAL and "pytest" in EXTERNAL


# Parser variable name -> the subcommand users type. `plugins` registers
# shared flags on the parent and on each list/audit subparser, so a doc
# line like `plugins audit --fail-fast` may draw from all three.
_SUBPARSERS = {
    "analyze": "analyze",
    "process": "process",
    "stream": "stream",
    "batch": "batch",
    "midi": "midi",
    "server": "server",
    "plugins_cmd": "plugins",
    "list_parser": "plugins",
    "audit": "plugins",
}


def _cli_flags_by_command():
    main_src = (PROJECT_ROOT / "main.py").read_text()
    global_flags = set(re.findall(
        r"(?<![\w.])parser\.add_argument\(\s*['\"](--[\w-]+)", main_src))
    by_command = {}
    for var, command in _SUBPARSERS.items():
        flags = set(re.findall(
            rf"(?<![\w.]){var}\.add_argument\(\s*['\"](--[\w-]+)", main_src))
        by_command.setdefault(command, set()).update(flags)
    for command in by_command:
        by_command[command] |= global_flags
        # argparse's built-in -h/--help is real on every parser.
        by_command[command] |= {"-h", "--help"}
    return by_command


def test_no_doc_teaches_a_cli_flag_argparse_rejects():
    # batch_processing.md described a `batch` that never existed -- a
    # sequential analyze-only run with `--skip-errors`, `--max-files` and
    # `--output` (all exit-2 in argparse). error_recovery.md suggested
    # `--workers 2`. Scan every doc line invoking the CLI and check each
    # flag against the invoked subcommand's registered arguments.
    flags_by_command = _cli_flags_by_command()
    assert all(flags_by_command.values()), (
        "a subcommand has no registered flags -- is this guard stale?")

    invoke = re.compile(
        r"(?:python3?\s+main\.py|chameleon)\s+"
        r"(analyze|process|stream|batch|midi|plugins|server)\b")
    # DEPLOYMENT_GUIDE.md's TLS block still teaches `--cert`/`--key` on
    # main -- a sibling remediation already rewrites that section, so this
    # file's flag coverage resumes when that lands.
    skip = {"DEPLOYMENT_GUIDE.md"}
    violations = []
    for path in _documentation_files():
        if path.name in skip:
            continue
        # Flags may sit on `\`-continuations of the CLI line; join first.
        text = re.sub(r"\\\n\s*", " ", path.read_text())
        for line_no, line in enumerate(text.splitlines(), 1):
            match = invoke.search(line)
            if not match:
                continue
            allowed = flags_by_command[match.group(1)]
            for flag in re.findall(r"--[\w-]+", line):
                if flag not in allowed:
                    violations.append(
                        f"{_relative(path)}:{line_no}: `{flag}`")
    assert not violations, (
        "Documentation passes flag(s) the invoked subcommand does not accept:\n  "
        + "\n  ".join(violations))


def test_docs_call_only_security_validator_methods_that_exist():
    # error_recovery.md's playbook called `validator.audit_log(...)` and
    # described `validate_url()` -- neither method exists, so the example
    # raised AttributeError on the first call. Every SecurityValidator
    # method a doc invokes must be a real def in security_validator.py.
    source = (PROJECT_ROOT / "security_validator.py").read_text()
    methods = set(re.findall(r"def (\w+)\(", source))
    methods |= {"secure_open"}  # SecureFileOperations context manager

    violations = []
    call_pattern = re.compile(
        r"(?:\bvalidator|\bSecurityValidator|\bSecureFileOperations|\bops)\.(\w+)\s*\(")
    for path in _documentation_files():
        text = path.read_text()
        for match in call_pattern.finditer(text):
            method = match.group(1)
            if method.startswith("_") or method in methods:
                continue
            line = text[:match.start()].count("\n") + 1
            violations.append(f"{_relative(path)}:{line}: `.{method}()`")
    assert not violations, (
        "Documentation calls SecurityValidator method(s) that do not exist:\n  "
        + "\n  ".join(violations))
