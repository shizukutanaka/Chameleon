"""Integration tests for wiring DeepFileInspector into the default batch path.

CHARTER §5/§9: the deep file inspector must actually run on the default
batch/load path, not just exist. These tests pin three behaviours:

1. A real WAV passes inspection and survives `_filter_safe_files`.
2. A file with a .wav extension whose bytes are an executable/script is
   rejected (magic-number mismatch).
3. A *real* WAV whose PCM payload coincidentally contains a "suspicious" byte
   sequence still passes — the scan only warns, it never rejects. This is the
   false-positive guard that keeps the gate safe for legitimate audio.
"""

import struct
import wave
from pathlib import Path

from tests._helpers import write_sine_wave

from advanced_validation import DeepFileInspector


def _write_wav_with_payload(path: Path, payload: bytes) -> Path:
    """Write a valid mono 16-bit WAV whose sample data embeds ``payload``."""
    path = Path(path)
    # Pad the payload to an even length so it forms whole 16-bit samples.
    if len(payload) % 2:
        payload += b"\x00"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        # A little silence, the payload bytes, then a little more silence.
        handle.writeframes(b"\x00\x00" * 100 + payload + b"\x00\x00" * 100)
    return path


# --- 1. real WAV passes -----------------------------------------------------

def test_real_wav_is_valid(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = DeepFileInspector().validate_for_processing(wav)
    assert result.is_valid, result.errors
    assert result.file_type == "WAV"


def test_real_wav_survives_filter(tmp_path):
    from main import AudioProcessor

    wav = write_sine_wave(tmp_path / "tone.wav")
    processor = AudioProcessor()
    safe, rejections = processor._filter_safe_files([str(wav)])
    assert safe == [str(wav)]
    assert rejections == []


# --- 2. disguised non-WAV is rejected ---------------------------------------

def test_disguised_executable_is_rejected(tmp_path):
    for name, magic in (
        ("dos.wav", b"MZ\x90\x00" + b"\x00" * 64),
        ("elf.wav", b"\x7fELF" + b"\x00" * 64),
        ("script.wav", b"#!/bin/sh\nrm -rf /\n"),
    ):
        fake = tmp_path / name
        fake.write_bytes(magic)
        result = DeepFileInspector().validate_for_processing(fake)
        assert not result.is_valid, f"{name} should be rejected"
        assert result.errors


def test_disguised_executable_is_filtered_out(tmp_path):
    from main import AudioProcessor

    good = write_sine_wave(tmp_path / "good.wav")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"MZ\x90\x00" + b"\x00" * 128)

    processor = AudioProcessor()
    safe, rejections = processor._filter_safe_files([str(good), str(bad)])
    assert str(good) in safe
    assert str(bad) not in safe
    # Inspection failure is an input rejection, not a security-policy one.
    assert rejections == [(str(bad), "input")]


# --- 3. false-positive guard ------------------------------------------------

def test_real_wav_with_suspicious_payload_still_passes(tmp_path):
    """Bytes that look like code inside the audio payload are audio.

    The `data` chunk holds arbitrary sample values, so `MZ` or `import ` in it
    carries no information: it is the sound. This used to warn -- and to warn
    on nearly every real recording, since `MZ` and `#!` are two bytes each and
    16-bit audio produces any given pair roughly once per 65,536 samples. See
    tests/test_suspicious_content_scan.py for the measurement.
    """
    wav = _write_wav_with_payload(
        tmp_path / "noisy.wav", b"MZ here is import os; eval( something )"
    )
    result = DeepFileInspector().validate_for_processing(wav)
    assert result.is_valid, result.errors
    assert not any("Suspicious pattern" in w for w in result.warnings), (
        "sample data was reported as injected code")


def test_suspicious_payload_wav_survives_filter(tmp_path):
    from main import AudioProcessor

    wav = _write_wav_with_payload(tmp_path / "noisy.wav", b"MZ import os eval(")
    processor = AudioProcessor()
    safe, rejections = processor._filter_safe_files([str(wav)])
    assert safe == [str(wav)]
    assert rejections == []


# --- method contract --------------------------------------------------------

def test_validate_for_processing_skips_checksum(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = DeepFileInspector().validate_for_processing(wav)
    assert result.checksum_sha256 == ""


def test_sanitize_preserves_data_after_odd_sized_metadata(tmp_path):
    # Skipping an odd-sized metadata chunk must also consume its RIFF pad
    # byte -- otherwise the next chunk header desyncs and the audio data
    # chunk is stripped along with the metadata.
    import struct as _st
    from advanced_validation import SanitizationEngine

    fmt = _st.pack("<HHIIHH", 1, 1, 44100, 88200, 2, 16)
    payload = _st.pack("<4h", 100, 200, 300, 400)
    odd_list = b"LIST" + _st.pack("<I", 5) + b"INFAx" + b"\x00"
    body = (b"fmt " + _st.pack("<I", 16) + fmt + odd_list
            + b"data" + _st.pack("<I", len(payload)) + payload)
    src = tmp_path / "meta.wav"
    src.write_bytes(b"RIFF" + _st.pack("<I", 4 + len(body)) + b"WAVE" + body)

    dst = tmp_path / "clean.wav"
    SanitizationEngine.sanitize_wav_metadata(src, dst)

    with wave.open(str(dst)) as w:
        assert w.readframes(4) == payload


def test_main_block_self_test_writes_no_state_into_the_real_home(tmp_path):
    """`python advanced_validation.py` used to leave a test_manifest.json
    inside ~/.chameleon/manifests permanently -- the self-test deleted its
    WAV fixtures but not the manifest it created in the user's state dir."""
    import os
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parent.parent
    home = tmp_path / "home"
    home.mkdir()

    result = subprocess.run(
        [sys.executable, "advanced_validation.py"],
        capture_output=True, text=True, cwd=str(repo_root),
        env={**os.environ, "HOME": str(home)},
    )

    assert result.returncode == 0, result.stderr
    assert "Verification: True" in result.stdout
    assert not (home / ".chameleon").exists()


def test_verify_manifest_reports_unreadable_manifest_instead_of_crashing(tmp_path):
    # json.load was unguarded: a truncated or missing manifest crashed the
    # verifier instead of reporting (False, issue) through its own contract.
    from advanced_validation import IntegrityVerifier

    verifier = IntegrityVerifier(manifest_dir=tmp_path)

    truncated = tmp_path / "truncated.json"
    truncated.write_text('{"x": {"checksum": "ab", "size": 5, "file_')
    valid, issues = verifier.verify_manifest(truncated)
    assert valid is False and "unreadable" in issues[0].lower()

    valid, issues = verifier.verify_manifest(tmp_path / "missing.json")
    assert valid is False and "unreadable" in issues[0].lower()
