"""Guard against re-accumulating modules nothing imports.

Chameleon has repeatedly grown files that no entry point reaches. Three were
deleted in one pass on 2026-08-25 (`performance_optimizer.py`, `core.py`'s
`RealtimeAudioProcessor`, and `api_server.py`'s imports of three modules that
never existed); several more were deleted in earlier passes. Each time, the
module had been sitting there long enough that nobody remembered whether it
worked -- and at least one of them did not: `performance_optimizer`'s
`normalize_int16` returned digital silence for any signal peaking above ~34%
of full scale, a defect that survived because the code had never once run.

The cost of an orphan is not the disk it takes. It is that it *looks
available*: it ships in the wheel, it imports, its docstring promises
something, and the first person to wire it up inherits however many years of
unexercised bugs.

So this test asserts that every module we package is reachable by following
imports from an entry point -- with an explicit, reasoned allow-list for the
ones we knowingly ship unwired. The allow-list is the honest part: an
exception you have to write down and justify is very different from one you
never noticed.

Adding a module to ALLOWED_ORPHANS is a real decision. Make it deliberately,
and say why in the dict below.
"""

import ast
import tomllib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

# Everything a user can invoke: the console script from pyproject.toml, and the
# ASGI app served by `chameleon server`.
ENTRY_POINTS = ("main", "api_server")

# Packaged modules that deliberately have no importer, and why. Each entry is a
# standing decision recorded in CHARTER.md §9 -- not a to-do list.
ALLOWED_ORPHANS = {
    "personal_config":
        "quick_install.sh / quick_install.ps1 document `python "
        "personal_config.py setup` as the personal-use onboarding flow, and it "
        "is the one documented entry point for advanced_validation's "
        "IntegrityVerifier / SanitizationEngine. Reachable by a user, just not "
        "by an import -- deleting it would mean redesigning that flow.",
    "batch_automation":
        "A generic DAG/workflow engine. CHARTER.md §4 would call this a second "
        "product, and its own demo builds tasks for transcoding this tool "
        "cannot do -- but it is genuine, working capability, and the user "
        "chose to keep it when asked directly on 2026-08-25.",
    "spectral_editor":
        "Interactive spectral editing, which points away from CHARTER.md §2's "
        "user. Kept by explicit user decision on 2026-08-25; its STFT "
        "machinery overlaps spectral_utils, but the editing surface is its own.",
}


def _packaged_modules():
    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        config = tomllib.load(handle)
    return set(config["tool"]["setuptools"]["py-modules"])


def _first_party_imports(module, packaged):
    """Every packaged module imported by `module`, at any nesting depth.

    Walks the whole AST rather than just the top level: main.py imports
    mastering_chain, bs1770_loudness and midi_analysis inside functions so the
    stdlib-only core stays importable without numpy.
    """
    tree = ast.parse((REPO_ROOT / f"{module}.py").read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found & packaged


def _reachable_from_entry_points(packaged):
    reached = set(ENTRY_POINTS)
    pending = list(ENTRY_POINTS)
    while pending:
        for dependency in _first_party_imports(pending.pop(), packaged):
            if dependency not in reached:
                reached.add(dependency)
                pending.append(dependency)
    return reached


def test_every_packaged_module_is_reachable_or_explicitly_allowed():
    packaged = _packaged_modules()
    orphans = packaged - _reachable_from_entry_points(packaged)

    unexplained = sorted(orphans - set(ALLOWED_ORPHANS))
    assert not unexplained, (
        f"{unexplained} are packaged but no entry point imports them.\n"
        "Wire the module into the CLI, drop it from pyproject.toml's "
        "py-modules, delete it (with the per-item confirmation CLAUDE.md "
        "requires) -- or, if shipping it unwired is genuinely intended, add it "
        "to ALLOWED_ORPHANS in this file with the reason."
    )


def test_the_allow_list_has_no_stale_entries():
    # The mirror image: once an allowed orphan gets wired up or deleted, its
    # justification stops being true and must go, or the list decays into
    # folklore.
    packaged = _packaged_modules()
    orphans = packaged - _reachable_from_entry_points(packaged)

    stale = sorted(set(ALLOWED_ORPHANS) - orphans)
    assert not stale, (
        f"{stale} are in ALLOWED_ORPHANS but are no longer orphaned "
        "(or no longer packaged). Remove the entries."
    )


@pytest.mark.parametrize("module", sorted(ALLOWED_ORPHANS))
def test_each_allowed_orphan_gives_a_substantive_reason(module):
    reason = ALLOWED_ORPHANS[module]
    assert len(reason) > 80, f"{module}'s justification is too thin to audit"


def test_every_packaged_module_actually_exists():
    # Catches the other half of a deletion: removing the file but leaving the
    # name in py-modules, which builds a wheel that fails on import.
    missing = sorted(m for m in _packaged_modules()
                     if not (REPO_ROOT / f"{m}.py").is_file())
    assert not missing, f"pyproject.toml packages nonexistent modules: {missing}"


def test_setup_py_and_pyproject_agree_on_the_module_list():
    # Two hand-maintained copies of the same list; they drifted before.
    source = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    listed = None
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "py_modules":
            listed = {elt.value for elt in node.value.elts}
    assert listed is not None, "setup.py no longer passes py_modules"
    assert listed == _packaged_modules(), (
        "setup.py and pyproject.toml disagree: "
        f"only in setup.py {sorted(listed - _packaged_modules())}, "
        f"only in pyproject.toml {sorted(_packaged_modules() - listed)}"
    )
