"""k8s-deployment.yaml must only declare env vars the code actually reads.

The manifest previously mounted a ~40-key `production.yaml` ConfigMap that
no code path opens (`enable_intrusion_detection`, `enable_simd`, a `backup:`
section) and injected a Secret whose keys (`api-token`, `master-key`,
`encryption-key`) the app never consults -- it reads only CHAMELEON_* env
vars. `api-token` in particular made the operator believe the API-key layer
was configured while CHAMELEON_API_KEY was unset and that layer silently
disabled. Fixed 2026-09-22 (audit 58): the ConfigMap now carries real
CHAMELEON_* variables consumed via `envFrom: configMapRef`, and the Secret
lists the real key names. This test fails if fiction returns.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules whose environment reads constitute the product's real env surface.
ENV_SOURCES = ("main.py", "core.py", "api_server.py", "security_validator.py")


def _env_vars_the_code_reads():
    found = set()
    for name in ENV_SOURCES:
        src = (ROOT / name).read_text()
        found.update(re.findall(r"""os\.environ\.get\(\s*['"]([A-Z][A-Z0-9_]*)""", src))
        found.update(re.findall(r"""os\.environ\[['"]([A-Z][A-Z0-9_]*)""", src))
        found.update(re.findall(r"""os\.getenv\(\s*['"]([A-Z][A-Z0-9_]*)""", src))
    return found


def _k8s_doc(kind):
    for doc in (ROOT / "k8s-deployment.yaml").read_text().split("\n---\n"):
        if f"kind: {kind}" in doc.split("metadata:")[0]:
            return doc
    raise AssertionError(f"no {kind} document in k8s-deployment.yaml")


def _scalar_keys(doc, section):
    """CAPS key names under a `data:`/`stringData:` block (2-space indent)."""
    keys = set()
    in_block = False
    for line in doc.splitlines():
        if re.match(rf"^{section}:\s*$", line):
            in_block = True
            continue
        if in_block:
            if re.match(r"^\S", line) or re.match(r"^---", line):
                break
            m = re.match(r"^\s+([A-Z][A-Z0-9_]+):", line)
            if m:
                keys.add(m.group(1))
    return keys


def test_k8s_configmap_declares_only_env_vars_the_code_reads():
    declared = _scalar_keys(_k8s_doc("ConfigMap"), "data")
    assert declared, "ConfigMap declares no env vars (the envFrom would inject nothing)"
    fictional = declared - _env_vars_the_code_reads()
    assert not fictional, f"ConfigMap declares env vars nothing reads: {sorted(fictional)}"


def test_k8s_secret_uses_only_env_names_the_code_reads():
    doc = _k8s_doc("Secret")
    declared = _scalar_keys(doc, "stringData") | _scalar_keys(doc, "data")
    assert declared, "Secret declares no keys"
    fictional = declared - _env_vars_the_code_reads()
    assert not fictional, f"Secret declares env vars nothing reads: {sorted(fictional)}"


def test_k8s_secret_commits_no_real_looking_credential():
    doc = _k8s_doc("Secret")
    # Base64 blobs under data: are committed credentials -- decode-at-will
    # secrets in git. Only `stringData` placeholders are acceptable.
    assert not re.search(r"^\s+data:\s*$", doc, re.M), \
        "Secret carries a data: section (base64-committed credentials)"
    assert "Q0hhbWVsZW9u" not in doc, "the committed Chameleon*2025 placeholders are back"
