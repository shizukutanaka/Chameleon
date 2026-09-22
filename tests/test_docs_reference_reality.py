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


# --- Audit-63: README-level claims, checked against the code they name -------
#
# The checks above guard imports and scripts. README.md also makes factual
# claims about the product -- CLI verbs, env-var values, auth mechanics,
# installable packages -- and each of the ones below was wrong for months.
# Every test pins the corrected claim, and every one was verified to fail on
# the pre-fix README before it was written.

def _readme():
    return (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")


def _readme_docker_run_verbs():
    """Each `docker run` command's first positional after the image name."""
    verbs = []
    for match in re.finditer(r"docker run[^\n]*?chameleon:latest\s+([^\s]+)", _readme()):
        verbs.append(match.group(1))
    return verbs


def test_readme_docker_run_uses_the_cli_verb():
    # The entrypoint routes `cli` -> `python3 main.py ...` and a bare verb to
    # `exec "$@"` (exec: analyze: not found). Only `cli`, `server` and `shell`
    # reach the product.
    verbs = _readme_docker_run_verbs()
    assert verbs, "README shows no `docker run ... chameleon:latest <verb>`"
    assert all(v == "cli" for v in verbs), (
        f"README runs the container with bare verb(s) {verbs}; the "
        "entrypoint exec's those as system binaries, so the command fails")


def test_readme_batch_operations_match_argparse():
    readme_ops = set()
    match = re.search(r"\(operations:\s*([\w/]+)\)", _readme())
    assert match, "README no longer lists batch operations"
    readme_ops = set(match.group(1).split("/"))

    source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    batch = re.search(r'add_parser\("batch".*?choices=\[([^\]]+)\]', source, re.S)
    assert batch, "batch subparser choices not found in main.py"
    argparse_ops = set(re.findall(r'"(\w+)"', batch.group(1)))

    assert readme_ops == argparse_ops, (
        f"README lists {sorted(readme_ops)} but argparse offers "
        f"{sorted(argparse_ops)} -- a user cannot discover the difference")


def test_readme_performance_mode_values_are_real():
    # `fast`, `safe`, `auto` are the only modes _determine_chunk_size honours;
    # anything else warns and falls back to auto. README claimed `balanced`.
    line = next(
        (l for l in _readme().splitlines() if "CHAMELEON_PERFORMANCE_MODE" in l),
        "",
    )
    assert line, "README no longer documents CHAMELEON_PERFORMANCE_MODE"
    comment = line.split("#", 1)[1] if "#" in line else ""
    listed = set(re.findall(r"[a-z]+", comment.lower()))
    assert listed <= {"fast", "safe", "auto", "default", "or", "only",
                      "chunk", "size", "for", "larger", "smaller"}, (
        f"README lists performance mode(s) the code never accepts: "
        f"{sorted(listed)}")


def test_readme_audit_log_example_shows_a_bearer_token():
    # get_current_user requires an HTTPBearer session token; X-API-Key alone
    # 401s before the key check is even reached -- it is a layered check on
    # top, not a credential. The old README showed only the key.
    text = _readme()
    audit_idx = text.find("/audit/log")
    assert audit_idx != -1, "README no longer shows the audit log"
    section = text[max(0, audit_idx - 1500):audit_idx]
    assert "Bearer" in section or "auth/login" in section, (
        "README's /audit/log example still presents X-API-Key as the only "
        "credential; a session Bearer token is required first")


def test_readme_pip_installs_only_what_code_imports():
    # Every `pip install <pkg>` the README teaches must be a package some
    # product module actually imports -- `mido` was listed for months while
    # nothing imported it (the .mid writer is stdlib `struct`).
    imported = set()
    for py in PROJECT_ROOT.glob("*.py"):
        for match in re.finditer(
                r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", py.read_text(
                    encoding="utf-8", errors="replace"), re.M):
            imported.add(match.group(1).lower())

    taught = set()
    for match in re.finditer(r"pip install\s+([^\n`]+)", _readme()):
        for token in match.group(1).split("#", 1)[0].split():
            name = token.strip()
            if name.startswith(("-", ".", "'", '"')) or "[" in name:
                continue
            name = name.split("[")[0].split("=")[0].split("<")[0].split(">")[0]
            if re.fullmatch(r"[A-Za-z_][\w-]*", name):
                taught.add(name.lower().replace("-", "_"))

    not_imported = taught - imported
    assert not not_imported, (
        f"README tells the reader to install {sorted(not_imported)} but no "
        "module imports them -- installing changes nothing")


def test_benchmark_doc_scopes_the_psutil_claim():
    # psutil is imported exactly once, in api_server.py for /system/status.
    # The doc claimed installing it enriched CLI "command summaries".
    text = (PROJECT_ROOT / "docs/en/performance_benchmarks.md").read_text(
        encoding="utf-8")
    assert "command summaries" not in text, (
        "performance_benchmarks.md still claims psutil feeds CLI command "
        "summaries; it only enriches the API's /system/status")
