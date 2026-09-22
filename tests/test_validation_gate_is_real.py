"""The verification gate's third step must exercise the product.

`python validation_test.py` is one of the three commands CLAUDE.md requires
before every commit. For most of its life that file hand-parsed WAVs and
greped paths against its own pattern list: it verified `tempfile`, `struct`
and `pathlib`, imported not a single product module, and still reported
"The core Chameleon system is ready for use." Rewritten 2026-09-22 to run
the real `core.analyze` / `SecurityValidator` paths. This guard fails if the
file drifts back to a shape where the product could be deleted entirely and
the gate would still print green.
"""

import re
from pathlib import Path

VALIDATION_TEST = Path(__file__).resolve().parent.parent / "validation_test.py"


def test_validation_gate_imports_product_modules():
    src = VALIDATION_TEST.read_text()
    for module in ("core", "security_validator"):
        assert re.search(rf"^\s*import {module}\b|^\s*from {module}\b|import {module}\b",
                         src, re.M), f"validation_test.py no longer touches {module!r}"


def test_validation_gate_calls_product_entry_points():
    src = VALIDATION_TEST.read_text()
    # The calls that make the file a gate: without them it verifies the
    # environment, not the product.
    for needle in ("core.analyze(", "validate_audio_content(", "validate_path("):
        assert needle in src, f"validation_test.py no longer calls {needle!r}"
