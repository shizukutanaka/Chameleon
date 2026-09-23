"""`EnhancedSecurityValidator.validate_path_secure`'s ALLOWED_DIRECTORIES gate
was string-prefix matching: verified on 2026-09-22.

1. Prefix-sibling escape: ALLOWED_DIRECTORIES=/data/in admitted
   /data/incoming/evil.wav -- `"/data/incoming".startswith("/data/in")` is
   True even though the file sits outside the allowed tree. Containment is
   now computed on resolved paths via `root in path.parents`.
2. Symlinked configured dir over-rejected: `path` is resolved but each
   configured entry was not, so ALLOWED_DIRECTORIES=/tmp/x rejected every
   file inside /tmp/x on macOS (/tmp -> /private/tmp). Both sides are now
   resolved before comparing.
"""

import pytest

from core import EnhancedSecurityValidator


def test_prefix_sibling_directory_is_not_inside(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    sibling = tmp_path / "allowed_sibling"
    allowed.mkdir()
    sibling.mkdir()
    (allowed / "ok.wav").write_bytes(b"x")
    (sibling / "evil.wav").write_bytes(b"x")

    monkeypatch.setenv("ALLOWED_DIRECTORIES", str(allowed))

    assert EnhancedSecurityValidator.validate_path_secure(
        str(allowed / "ok.wav")) is True
    assert EnhancedSecurityValidator.validate_path_secure(
        str(sibling / "evil.wav")) is False


def test_configured_dir_through_symlink_still_admits(tmp_path, monkeypatch):
    """The configured dir may itself traverse a symlink (macOS /tmp ->
    /private/tmp): the gate must resolve both sides, not reject legit
    files inside it."""
    real = tmp_path / "real"
    real.mkdir()
    f = real / "ok.wav"
    f.write_bytes(b"x")
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    monkeypatch.setenv("ALLOWED_DIRECTORIES", str(link))

    assert EnhancedSecurityValidator.validate_path_secure(str(f)) is True


def test_outside_allowed_tree_rejected(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    other = tmp_path / "other"
    allowed.mkdir()
    other.mkdir()
    (other / "evil.wav").write_bytes(b"x")

    monkeypatch.setenv("ALLOWED_DIRECTORIES", str(allowed))

    assert EnhancedSecurityValidator.validate_path_secure(
        str(other / "evil.wav")) is False


def test_blank_entries_do_not_disable_or_enable_gate(tmp_path, monkeypatch):
    f = tmp_path / "ok.wav"
    f.write_bytes(b"x")

    # All-blank value = not configured: no gate.
    monkeypatch.setenv("ALLOWED_DIRECTORIES", " , ,")
    assert EnhancedSecurityValidator.validate_path_secure(str(f)) is True

    # Mixed blank + real entries: the real one still gates.
    monkeypatch.setenv("ALLOWED_DIRECTORIES", f" ,{tmp_path} ,")
    assert EnhancedSecurityValidator.validate_path_secure(str(f)) is True
