"""IntegrityVerifier manifest handling: names must not escape the manifest
directory, and malformed manifests must fail verification instead of
crashing.

Reproduction basis (pre-fix):
* ``create_manifest(files, "../escape")`` wrote ``manifest_dir/../escape.json``
  -- outside the directory the verifier was configured for.
* ``verify_manifest`` on a JSON list crashed ``AttributeError``; on a
  non-dict entry it crashed ``TypeError: string indices``."""

import json
import os
import stat

import pytest

from advanced_validation import IntegrityVerifier


def _minimal_wav(path):
    """Smallest structurally valid WAV the inspector accepts."""
    path.write_bytes(
        b"RIFF" + (36).to_bytes(4, "little") + b"WAVE"
        + b"fmt " + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (0).to_bytes(4, "little")
    )


@pytest.fixture
def verifier(tmp_path):
    return IntegrityVerifier(manifest_dir=tmp_path / "manifests")


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "a.wav"
    _minimal_wav(path)
    return path


@pytest.mark.parametrize("bad_name", ["../escape", "..", "sub/dir", "a\\b", ""])
def test_manifest_name_cannot_escape_manifest_dir(verifier, wav, tmp_path, bad_name):
    with pytest.raises(ValueError):
        verifier.create_manifest([wav], bad_name)
    # Nothing may have been written outside manifest_dir.
    stray = [p for p in tmp_path.rglob("*.json")
             if "manifests" not in p.parts]
    assert stray == []


def test_legitimate_manifest_name_still_works(verifier, wav, tmp_path):
    path = verifier.create_manifest([wav], "backup_manifest")
    assert path.parent == tmp_path / "manifests"
    assert path.name == "backup_manifest.json"
    # Contract pin: manifest files stay owner-only.
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_verify_manifest_rejects_non_object_top_level(verifier, tmp_path):
    bad = tmp_path / "list.json"
    bad.write_text(json.dumps(["a.wav"]))
    ok, issues = verifier.verify_manifest(bad)
    assert ok is False
    assert issues and "Malformed" in issues[0]


def test_verify_manifest_rejects_non_dict_entry(verifier, wav, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({str(wav): "not-a-dict"}))
    ok, issues = verifier.verify_manifest(bad)
    assert ok is False
    assert any("Malformed entry" in issue for issue in issues)


def test_verify_manifest_round_trip_still_valid(verifier, wav):
    manifest_path = verifier.create_manifest([wav], "roundtrip")
    ok, issues = verifier.verify_manifest(manifest_path)
    assert ok is True
    assert issues == []
