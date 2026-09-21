"""`CHAMELEON_TRUSTED_ROOTS` must apply on every path check, not just the
call sites that happened to use the env-aware hybrid.

core.py built its module-level `security_validator` with a bare
`SecurityConfig()` -- empty trusted_roots, default max size -- while
class-level `SecurityValidator.validate_path(...)` calls resolved through
`_default()`, an env-aware instance. The same named policy was on or off
depending on which spelling a call site used: `batch` over a directory
outside the roots sailed through, and `analyze --export`/`midi --output`
weren't containment-checked at all.
"""

import os
import subprocess
import sys
import wave
from pathlib import Path

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x01\x00" * 400)


def _env_with_roots(roots: Path) -> dict:
    env = dict(os.environ, CHAMELEON_TRUSTED_ROOTS=str(roots))
    env.pop("ALLOWED_DIRECTORIES", None)
    return env


def test_batch_rejects_directory_outside_trusted_roots(tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    _write_wav(outside / "in.wav")
    inside.mkdir()

    proc = subprocess.run(
        [sys.executable, MAIN_PY, "batch", str(outside), "analyze"],
        capture_output=True, text=True, timeout=60,
        env=_env_with_roots(inside))

    # At HEAD the directory arg was only shape-sanitized: batch happily
    # walked a directory the declared boundary says is untrusted.
    assert proc.returncode == 4, proc.stderr
    assert "trusted roots" in proc.stderr


def test_core_op_honors_trusted_roots(tmp_path):
    """The library surface must enforce the same boundary -- the fix is
    that core's singleton reads the env config like the default instance
    already did."""
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    _write_wav(outside / "in.wav")

    proc = subprocess.run(
        [sys.executable, "-c",
         "import core; r = core.BatchProcessor().processor.normalize("
         f"'{outside}/in.wav', '{inside}/out.wav');"
         "import sys; sys.exit(0 if not r.success else 1)"],
        capture_output=True, text=True, timeout=60,
        cwd=str(Path(MAIN_PY).parent),
        env=_env_with_roots(inside))

    assert proc.returncode == 0, proc.stderr
    assert not (inside / "out.wav").exists()


def test_export_respects_trusted_roots(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    _write_wav(inside / "in.wav")

    proc = subprocess.run(
        [sys.executable, MAIN_PY, "analyze", str(inside / "in.wav"),
         "--export", str(tmp_path / "report.json")],
        capture_output=True, text=True, timeout=60,
        env=_env_with_roots(inside))

    # Export destination outside the root -> INPUT error, no file.
    assert proc.returncode == 3, proc.stderr
    assert not (tmp_path / "report.json").exists()


def test_export_inside_trusted_root_still_works(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    _write_wav(inside / "in.wav")

    proc = subprocess.run(
        [sys.executable, MAIN_PY, "analyze", str(inside / "in.wav"),
         "--export", str(inside / "report.json")],
        capture_output=True, text=True, timeout=60,
        env=_env_with_roots(inside))

    assert proc.returncode == 0, proc.stderr
    assert (inside / "report.json").exists()


def test_midi_generate_output_outside_roots_rejected(tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()

    proc = subprocess.run(
        [sys.executable, MAIN_PY, "midi", "generate",
         "--output", str(outside / "out.mid")],
        capture_output=True, text=True, timeout=60,
        env=_env_with_roots(inside))

    assert proc.returncode == 3, proc.stderr
    assert not (outside / "out.mid").exists()
