import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPONSORS_URL = "https://github.com/sponsors/shizukutanaka"


def _funding_text():
    return (ROOT / ".github" / "FUNDING.yml").read_text(encoding="utf-8")


def test_funding_uses_github_sponsors_only():
    # Project policy (2026-11-10): the software is free; support is accepted
    # only through GitHub Sponsors. No custom links to other channels.
    funding = _funding_text()
    assert re.search(r'(?m)^github:\s*\[?"?shizukutanaka"?\]?\s*$', funding)
    assert not re.search(r"(?m)^custom\s*:", funding)


def test_funding_url_matches_package_metadata():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    setup = (ROOT / "setup.py").read_text(encoding="utf-8")
    assert re.search(r'(?m)^Funding\s*=\s*"([^"]+)"', pyproject).group(1) == SPONSORS_URL
    assert re.search(r'(?m)^\s*"Funding":\s*"([^"]+)"', setup).group(1) == SPONSORS_URL


def test_readme_contains_funding_url():
    assert SPONSORS_URL in (ROOT / "README.md").read_text(encoding="utf-8")
