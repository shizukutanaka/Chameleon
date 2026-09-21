"""Bounds for DeepFileInspector's chunk walk and IntegrityVerifier's
constructor side effects.

_core's header walker stops at _MAX_WAV_CHUNKS; the inspector's
_validate_wav_structure had no such bound, so a crafted file of
zero-size chunks made chunks_found grow unboundedly -- memory and a
full-file scan inside the component meant to be the security gate.
"""
import struct
from pathlib import Path

import pytest

from advanced_validation import DeepFileInspector, IntegrityVerifier


def _wav_with_junk_chunks(path: Path, n_chunks: int) -> Path:
    """Minimal RIFF: fmt + data, then n_chunks zero-size 'JUNK' chunks."""
    fmt = struct.pack('<HHIIHH', 1, 1, 8000, 8000, 1, 8)
    data = b'\x00' * 8
    body = (
        b'fmt ' + struct.pack('<I', len(fmt)) + fmt
        + b'data' + struct.pack('<I', len(data)) + data
        + b'JUNK' + struct.pack('<I', 0) * 0  # placeholder, see loop
    )
    body = body[:len(body) - len(b'JUNK') - 0]  # strip placeholder
    for _ in range(n_chunks):
        body += b'JUNK' + struct.pack('<I', 0)
    riff = b'RIFF' + struct.pack('<I', 4 + len(body)) + b'WAVE' + body
    path.write_bytes(riff)
    return path


def test_chunk_walk_is_bounded(tmp_path):
    wav = _wav_with_junk_chunks(tmp_path / "many.wav", 400)
    meta = DeepFileInspector()._validate_wav_structure(wav)
    assert meta.get("error", "").startswith("Too many chunks")
    assert meta["chunks_truncated"] is True
    assert len(meta["chunks"]) <= DeepFileInspector._MAX_SCAN_CHUNKS


def test_normal_wav_not_flagged(tmp_path):
    wav = _wav_with_junk_chunks(tmp_path / "few.wav", 3)
    meta = DeepFileInspector()._validate_wav_structure(wav)
    assert meta["chunks_truncated"] is False
    assert meta.get("error") is None


def test_verifier_init_does_not_mkdir(tmp_path, monkeypatch):
    """IntegrityVerifier() must not create ~/.chameleon/manifests at
    construction -- the same lazy-side-effect rule as ~/.chameleon_state
    and PluginManager's directory creation."""
    monkeypatch.setenv("HOME", str(tmp_path))
    IntegrityVerifier()  # read-only construction
    assert not (tmp_path / ".chameleon" / "manifests").exists()


def test_manifest_creation_makes_dir(tmp_path):
    """The directory appears when it is actually needed."""
    monkeypatch_dir = tmp_path / "m"
    v = IntegrityVerifier(manifest_dir=monkeypatch_dir)
    wav = _wav_with_junk_chunks(tmp_path / "a.wav", 0)
    path = v.create_manifest([wav], "m1")
    assert path.exists()
