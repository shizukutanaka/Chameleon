"""Build and agent-doc files must not carry claims that drift from the code.

Found on the packaging/doc audit: the Makefile's docker target tagged the
release image ``chameleon-audio:1.0.0`` and the Dockerfile's ``ARG VERSION``
defaulted to ``1.0.0`` while the package reported ``1.1.0`` -- a released
image and a bare ``docker build`` both stamped a version nothing reports.
And SONNET.md had frozen a dated copy of PRODUCT_ANALYSIS's coverage list
that was incomplete the day it was written.
"""

import re
from pathlib import Path

from main import VERSION

ROOT = Path(__file__).resolve().parent.parent


def test_makefile_carries_no_hardcoded_image_tag():
    text = (ROOT / "Makefile").read_text()
    tags = re.findall(r"chameleon-audio:(\d+\.\d+\.\d+)", text)
    assert tags == [], (
        f"hardcoded image tag(s) {tags} in Makefile -- derive the tag from "
        "main.VERSION so a version bump can't leave a stale release tag")


def test_dockerfile_version_arg_default_matches_the_package():
    text = (ROOT / "Dockerfile").read_text()
    m = re.search(r"^ARG VERSION=(\d+\.\d+\.\d+)", text, re.M)
    assert m, "Dockerfile must declare a VERSION build-arg default"
    assert m.group(1) == VERSION, (
        f"Dockerfile ARG VERSION={m.group(1)} but main.VERSION={VERSION} -- "
        "a bare `docker build` would label the image with a version the "
        "package doesn't report")


def test_sonnet_doc_does_not_freeze_a_dated_coverage_list():
    text = (ROOT / "docs" / "agents" / "SONNET.md").read_text()
    assert not re.search(r"[Aa]s of \d{4}-\d{2}-\d{2}", text), (
        "SONNET.md froze a dated copy of the coverage-gap list -- it was "
        "incomplete the day it was written; point at the live "
        "PRODUCT_ANALYSIS section instead")
