"""The declared Python floor must be installable.

pyproject.toml declares ``requires-python = ">=3.8"`` and CI runs a 3.8 job,
but the ``dev`` extra pinned ``sphinx>=7.3`` (which needs 3.9) -- and the
theme/myst-parser pull sphinx transitively -- so ``pip install -e .[dev]``
could not resolve on 3.8 at all. Every PR's 3.8 job failed during
dependency resolution on exactly this (pip's own error message).

The fix gates the sphinx family behind ``python_version>='3.9'`` markers.
This test evaluates the markers the same way pip does -- for a simulated
3.8 interpreter and a 3.9 one -- so the floor claim stays enforceable.
"""

import re
from pathlib import Path

import pytest

tomllib = pytest.importorskip(
    "tomllib", reason="tomllib needs Python 3.11+; the guard runs wherever "
    "it exists and the 3.8 floor is enforced in pyproject itself")

try:
    from packaging.requirements import Requirement
except ImportError:  # bare stdlib venv still has pip's vendored copy
    from pip._vendor.packaging.requirements import Requirement

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"

# Packages whose required Python floor exceeds the project's declared
# >=3.8 floor (sphinx>=7.3 needs 3.9; the other two pull sphinx>=5/7).
SPHINX_FAMILY = {"sphinx", "sphinx-rtd-theme", "myst-parser"}


def _dev_requirements():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return [Requirement(r) for r in data["project"]["optional-dependencies"]["dev"]]


def test_sphinx_family_is_gated_off_python_38():
    installs_on_38 = [
        req.name for req in _dev_requirements()
        if req.name in SPHINX_FAMILY
        and (req.marker is None or req.marker.evaluate({"python_version": "3.8"}))
    ]
    assert not installs_on_38, (
        f"{installs_on_38} resolve on Python 3.8 but need >=3.9 -- the dev "
        "extra fails resolution on the project's own floor again")


def test_sphinx_family_still_installs_on_39_plus():
    missing = [
        req.name for req in _dev_requirements()
        if req.name in SPHINX_FAMILY
        and req.marker is not None
        and not req.marker.evaluate({"python_version": "3.9"})
    ]
    assert not missing, (
        f"{missing} are gated too tightly -- 3.9+ dev installs lose them")


def test_no_other_dev_requirement_is_marked_off_the_floor():
    # If a future pin gets a python_version marker, the floor needs a look.
    floor_breakers = [
        req.name for req in _dev_requirements()
        if req.name not in SPHINX_FAMILY
        and req.marker is not None
        and not req.marker.evaluate({"python_version": "3.8"})
    ]
    assert not floor_breakers, (
        f"{floor_breakers} exclude Python 3.8 without a sphinx-style "
        "reason -- check whether requires-python should move instead")


def test_requires_python_floor_is_declared():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    floor = data["project"]["requires-python"]
    assert re.search(r">=\s*3\.8\b", floor), (
        f"requires-python is {floor!r} -- the sphinx gating above assumes "
        "the 3.8 floor is still the project's claim")
