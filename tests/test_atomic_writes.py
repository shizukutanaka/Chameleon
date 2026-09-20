"""Atomic output writes.

Every user-facing producer (WAV transforms, the mono-copy fast path, MIDI
generation, ``analyze --export``, state snapshots, WAV sanitization) writes
through a sibling ``.part-<pid>`` temp file renamed onto the destination
only on success -- a reader sees the old file or the new one, never a
truncated file that still parses. A mid-write failure must also remove the
temp file rather than leaving strays in the output directory.
"""

import json
import os
import struct
import threading
from pathlib import Path

import pytest

import core
import main
import midi_analysis
from tests._helpers import write_sine_wave, write_stereo_sine_wave


def _partials(directory: Path):
    return [p.name for p in Path(directory).iterdir() if ".part-" in p.name]


def _fail_replace(*args, **kwargs):
    raise OSError("rename failed")


# -- the helpers -----------------------------------------------------------

def test_atomic_output_failure_preserves_existing_destination(tmp_path):
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"ORIGINAL")

    with pytest.raises(RuntimeError):
        with core.atomic_output(dest) as handle:
            handle.write(b"partial")
            raise RuntimeError("disk full")

    assert dest.read_bytes() == b"ORIGINAL"
    assert _partials(tmp_path) == []


def test_atomic_output_success_replaces_destination(tmp_path):
    dest = tmp_path / "out.bin"
    with core.atomic_output(dest) as handle:
        handle.write(b"new")
    assert dest.read_bytes() == b"new"
    assert _partials(tmp_path) == []
    if os.name != "nt":
        assert dest.stat().st_mode & 0o777 == 0o600


def test_staged_output_path_keeps_suffix_and_is_atomic(tmp_path):
    dest = tmp_path / "out.wav"
    dest.write_bytes(b"ORIGINAL")

    with pytest.raises(RuntimeError):
        with core.staged_output_path(dest) as tmp:
            # soundfile infers the container from the extension
            assert tmp.suffix == ".wav"
            tmp.write_bytes(b"partial")
            raise RuntimeError("disk full")

    assert dest.read_bytes() == b"ORIGINAL"
    assert _partials(tmp_path) == []


# -- producers -------------------------------------------------------------

def test_normalize_mid_write_failure_preserves_existing_output(tmp_path, monkeypatch):
    src = write_stereo_sine_wave(tmp_path / "in.wav", duration=0.1)
    dest = tmp_path / "out.wav"
    dest.write_bytes(b"ORIGINAL")

    def fail_mid_write(self, src_f, dst_f, info, new_data_size, *, channels=None):
        dst_f.write(b"TRUNCATED-JUNK")
        raise RuntimeError("disk full")

    monkeypatch.setattr(core.WAVProcessor, "_copy_patched_header", fail_mid_write)

    result = core.WAVProcessor().normalize(str(src), str(dest))

    assert not result.success
    assert dest.read_bytes() == b"ORIGINAL"
    assert _partials(tmp_path) == []


def test_convert_to_mono_copy_failure_preserves_output(tmp_path, monkeypatch):
    src = write_sine_wave(tmp_path / "in.wav", duration=0.1)  # mono: copyfile path
    dest = tmp_path / "out.wav"
    dest.write_bytes(b"ORIGINAL")

    def partial_copy(src_f, dst_f, *args, **kwargs):
        Path(dst_f).write_bytes(b"TRUNCATED-JUNK")
        raise RuntimeError("disk full")

    monkeypatch.setattr(core.shutil, "copyfile", partial_copy)

    result = core.WAVProcessor().convert_to_mono(str(src), str(dest))

    assert not result.success
    assert dest.read_bytes() == b"ORIGINAL"
    assert _partials(tmp_path) == []


def test_record_state_failure_writes_nothing(tmp_path, monkeypatch):
    mgr = core.StateRecoveryManager(state_dir=tmp_path / "state")

    monkeypatch.setattr(os, "replace", _fail_replace)
    assert mgr.record_state({"files_processed": 1}) is None

    state_dir = tmp_path / "state"
    assert not list(state_dir.glob("batch_state_*.json"))
    assert _partials(state_dir) == []


def test_record_state_roundtrip_leaves_no_partials(tmp_path):
    mgr = core.StateRecoveryManager(state_dir=tmp_path / "state")
    path = mgr.record_state({"files_processed": 3})

    assert path is not None and path.exists()
    assert json.loads(path.read_text())["summary"]["files_processed"] == 3
    assert _partials(tmp_path / "state") == []


def test_generate_midi_file_failure_leaves_nothing(tmp_path, monkeypatch):
    dest = tmp_path / "out.mid"
    monkeypatch.setattr(os, "replace", _fail_replace)

    ok = midi_analysis.MIDIAnalyzer().generate_midi_file(
        [midi_analysis.MIDINote(60, 100, 0.0, 0.5)], str(dest))

    assert ok is False
    assert not dest.exists()
    assert _partials(tmp_path) == []


def test_save_wav_basic_mid_write_failure_preserves_output(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    audio = np.zeros(4000, dtype=np.float32)
    dest = tmp_path / "out.wav"
    dest.write_bytes(b"ORIGINAL")

    real_pack = struct.pack
    calls = {"n": 0}

    def fail_after_header_start(fmt, *args):
        calls["n"] += 1
        if calls["n"] > 2:
            raise RuntimeError("disk full")
        return real_pack(fmt, *args)

    monkeypatch.setattr(struct, "pack", fail_after_header_start)

    with pytest.raises(RuntimeError):
        main.AudioProcessor()._save_wav_basic(audio, str(dest), 8000)

    assert dest.read_bytes() == b"ORIGINAL"
    assert _partials(tmp_path) == []


def test_save_audio_soundfile_failure_falls_back_without_partials(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    if not main.HAS_SOUNDFILE:
        pytest.skip("soundfile not installed")
    audio = np.zeros(4000, dtype=np.float32)
    dest = tmp_path / "out.wav"
    seen = {}

    def partial_write(path, *args, **kwargs):
        seen["path"] = str(path)
        Path(path).write_bytes(b"TRUNCATED-JUNK")
        raise RuntimeError("sf failure")

    monkeypatch.setattr(main.sf, "write", partial_write)

    written = main.AudioProcessor().save_audio(audio, str(dest), 8000)

    assert written == 16                      # clean fallback to basic writer
    assert ".part-" in seen["path"]           # soundfile never saw the real name
    assert dest.read_bytes()[:4] == b"RIFF"   # fallback produced a valid file
    assert _partials(tmp_path) == []


def test_concurrent_writers_same_destination_get_unique_temps(tmp_path):
    """Batch may run the same-named output twice in parallel: each writer must
    get its own temp file -- one writer's os.replace must not remove the
    other's still-open temp (an ENOENT crash on the losing writer)."""
    dest = tmp_path / "out.bin"
    errors = []

    def write_once():
        try:
            for _ in range(50):
                with core.atomic_output(dest) as handle:
                    handle.write(b"A" * 4096)
        except Exception as exc:  # noqa: BLE001 - collect, assert below
            errors.append(exc)

    threads = [threading.Thread(target=write_once) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert dest.read_bytes() == b"A" * 4096
    assert _partials(tmp_path) == []


def test_sanitize_wav_metadata_failure_preserves_destination(tmp_path, monkeypatch):
    from advanced_validation import SanitizationEngine
    src = write_sine_wave(tmp_path / "in.wav", duration=0.1)
    dest = tmp_path / "clean.wav"
    dest.write_bytes(b"ORIGINAL")

    monkeypatch.setattr(os, "replace", _fail_replace)
    with pytest.raises(OSError):
        SanitizationEngine.sanitize_wav_metadata(src, dest)

    assert dest.read_bytes() == b"ORIGINAL"
    assert _partials(tmp_path) == []
