import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FUNDING_URL = "https://github.com/shizukutanaka/Chameleon/issues/new?template=commercial_support.yml"


def _custom_funding_urls():
    funding = (ROOT / ".github" / "FUNDING.yml").read_text()
    custom = re.search(r"(?m)^custom:\s*\[(.*?)\]\s*$", funding)
    assert custom is not None
    return re.findall(r"""https?://[^,\s"']+""", custom.group(1))


def test_custom_funding_issue_templates_exist():
    urls = _custom_funding_urls()
    assert urls
    for url in urls:
        template = re.search(r"[?&]template=([^&]+)", url)
        if template:
            assert (ROOT / ".github" / "ISSUE_TEMPLATE" / template.group(1)).is_file()


def test_funding_url_matches_package_metadata():
    urls = _custom_funding_urls()
    funding_url = next(url for url in urls if "template=" in url)
    pyproject = (ROOT / "pyproject.toml").read_text()
    setup = (ROOT / "setup.py").read_text()
    assert funding_url == FUNDING_URL
    assert re.search(r'(?m)^Funding\s*=\s*"([^"]+)"', pyproject).group(1) == funding_url
    assert re.search(r'(?m)^\s*"Funding":\s*"([^"]+)"', setup).group(1) == funding_url


def test_readme_contains_funding_url():
    assert FUNDING_URL in (ROOT / "README.md").read_text()
