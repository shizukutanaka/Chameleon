"""Exercise the CLI's process exit codes (main.ExitCode) end-to-end.

These invoke ``main.py`` as a real subprocess so the assertions cover the
actual ``sys.exit(cli())`` wiring, not just the in-process return value of
``main()``.
"""

import os
import subprocess
import sys
import signal
import time
from pathlib import Path

import pytest

from tests._helpers import write_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _run(*args, cwd=None, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, MAIN_PY, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
        env=env,
    )


def test_no_command_is_usage_error(tmp_path):
    result = _run(cwd=str(tmp_path))
    assert result.returncode == 2  # ExitCode.USAGE


def test_analyze_success_is_ok(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("analyze", str(wav), cwd=str(tmp_path))
    assert result.returncode == 0  # ExitCode.OK
    assert "tone.wav" in result.stdout


def test_analyze_missing_file_is_input_error(tmp_path):
    """A supplied path that fails pre-flight is INPUT(3), not ERROR(1).

    Until the rejections carried their own exit code, this path instead
    crashed with ``KeyError: 'file'`` on the all-files-rejected sentinel
    dict and exited 1 -- the old assertion pinned the crash, not the
    documented contract.
    """
    missing = tmp_path / "does_not_exist.wav"
    result = _run("analyze", str(missing), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "Traceback" not in result.stderr
    assert "No valid audio files" in result.stderr


def test_process_missing_file_is_input_error(tmp_path):
    """The ``process`` command honors the same all-rejected contract."""
    missing = tmp_path / "does_not_exist.wav"
    result = _run("process", str(missing), "--normalize", cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "Traceback" not in result.stderr


def test_analyze_untrusted_path_is_security_error(tmp_path):
    """A file outside CHAMELEON_TRUSTED_ROOTS is SECURITY(4)."""
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    wav = write_sine_wave(outside / "tone.wav")
    result = _run(
        "analyze",
        str(wav),
        cwd=str(allowed),
        env_extra={"CHAMELEON_TRUSTED_ROOTS": str(allowed)},
    )
    assert result.returncode == 4  # ExitCode.SECURITY
    assert "Traceback" not in result.stderr


def test_wildcard_input_is_input_validation_error(tmp_path):
    result = _run("analyze", "a*.wav", cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT


def test_process_without_operation_is_usage_error(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), cwd=str(tmp_path))
    assert result.returncode == 2  # ExitCode.USAGE


def test_batch_missing_directory_is_input_error(tmp_path):
    missing_dir = tmp_path / "nope"
    result = _run("batch", str(missing_dir), "analyze", cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT


def _write_truncated_wav(path):
    """A WAV whose header survives but whose data chunk is absent -- the
    deep inspector's magic check passes, the parser then fails."""
    valid = tmp_wav = path.parent / "_src.wav"
    write_sine_wave(valid)
    path.write_bytes(valid.read_bytes()[:32])
    valid.unlink()


def test_analyze_unparseable_wav_is_input_error(tmp_path):
    """A file that fails WAV parsing mid-work is INPUT(3), not ERROR(1).

    Until per-file failures carried an error kind, any parse failure —
    the same class of problem as a missing file — returned the generic
    internal-error code.
    """
    bad = tmp_path / "bad.wav"
    _write_truncated_wav(bad)
    result = _run("analyze", str(bad), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "Traceback" not in result.stderr


def test_process_unparseable_wav_is_input_error(tmp_path):
    bad = tmp_path / "bad.wav"
    _write_truncated_wav(bad)
    result = _run("process", str(bad), "--normalize",
                  "--output-dir", str(tmp_path / "out"), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT


def test_analyze_mixed_good_and_bad_is_input_error(tmp_path):
    good = write_sine_wave(tmp_path / "good.wav")
    bad = tmp_path / "bad.wav"
    _write_truncated_wav(bad)
    result = _run("analyze", str(good), str(bad), cwd=str(tmp_path))
    # one success + one input failure -> INPUT, not the generic ERROR
    assert result.returncode == 3
    assert "good.wav" in result.stdout


def test_batch_partial_preflight_rejection_exits_input(tmp_path):
    """A batch where pre-flight rejects some files used to exit 0 with a
    'Processed 2/2' summary -- the rejected inputs vanished from both the
    denominator and the exit code, while `process` on the same file
    answers INPUT(3). Partial rejection must surface."""
    good = tmp_path / "good.wav"
    write_sine_wave(good)
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav" * 8)
    proc = _run("batch", str(tmp_path), "normalize",
                "--output-dir", str(tmp_path / "out"))
    assert proc.returncode == 3  # ExitCode.INPUT


def test_output_dir_that_is_a_file_exits_input(tmp_path):
    """--output-dir pointing at a regular file used to surface deep inside
    per-file processing as a raw OSError classified ERROR(1). The path is
    user input: it must answer INPUT(3) before any work starts."""
    wav = tmp_path / "a.wav"
    write_sine_wave(str(wav))
    proc = _run("process", str(wav), "--normalize",
                "--output-dir", str(wav))
    assert proc.returncode == 3  # ExitCode.INPUT
    assert "not a directory" in proc.stderr


def test_sigint_during_processing_exits_interrupted(tmp_path):
    """asyncio.Runner converts SIGINT into a main-task cancellation that can
    only be delivered at await points -- the whole process pipeline is
    synchronous, so Ctrl-C used to be queued and dropped: exit 0, all files
    processed. The CLI restores the default handler so the interrupt is a
    real KeyboardInterrupt.

    The signal is sent when the first output file appears -- guaranteed
    mid-run for a serial 8-file job, independent of machine speed."""
    pytest.importorskip("scipy")  # --denoise requires the audio extra
    files = []
    for i in range(8):
        f = tmp_path / f"f{i}.wav"
        write_sine_wave(str(f), duration=2.0)
        files.append(str(f))
    out_dir = tmp_path / "out"
    main_py = MAIN_PY
    proc = subprocess.Popen(
        [sys.executable, main_py, "--no-parallel", "process", *files,
         "--denoise", "--output-dir", str(out_dir)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
    sent = False
    deadline = time.time() + 60
    while proc.poll() is None and time.time() < deadline:
        if not sent and out_dir.exists() and any(out_dir.iterdir()):
            proc.send_signal(signal.SIGINT)
            sent = True
        time.sleep(0.05)
    rc = proc.wait(timeout=60)
    assert sent, "no output appeared within the polling window"
    assert rc == 130
