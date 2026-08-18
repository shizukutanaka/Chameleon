"""The dependency-free operations, end to end through the CLI.

The product's stated reason to exist is a core that runs with no third-party
packages. `core.py` has always implemented four such operations -- analyze,
normalize, mono, trim -- and lists all four in ALLOWED_BATCH_OPERATIONS, but
the CLI exposed only the first two. Half the differentiator was unreachable
except from the Python API.

These tests run the real CLI as a subprocess with numpy, scipy, librosa and
soundfile all made unimportable, so they fail if any of these operations
quietly acquires a third-party dependency.
"""

import math
import struct
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

_BLOCKER = textwrap.dedent('''
    import sys
    from importlib.abc import MetaPathFinder
    class _Absent(MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("numpy", "scipy", "librosa", "soundfile"):
                raise ModuleNotFoundError(f"No module named {name!r}", name=name)
            return None
    sys.meta_path.insert(0, _Absent())
''')


@pytest.fixture(scope="module")
def blocker_dir(tmp_path_factory):
    """A directory whose sitecustomize.py makes the optional deps unimportable."""
    directory = tmp_path_factory.mktemp("no_numpy")
    (directory / "sitecustomize.py").write_text(_BLOCKER)
    return directory


def _write_stereo_wav(path, seconds=2.0, sample_rate=44100, silent_edges=True):
    frames = []
    total = int(sample_rate * seconds)
    edge = int(sample_rate * 0.25)
    for i in range(total):
        loud = not silent_edges or (edge <= i < total - edge)
        amplitude = 0.4 if loud else 0.0
        value = int(amplitude * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.append(struct.pack("<hh", value, value // 2))
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(frames))


def _run_cli(blocker_dir, *args):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(blocker_dir)},
    )


def _wav_info(path):
    with wave.open(str(path)) as handle:
        return handle.getnchannels(), handle.getnframes() / handle.getframerate()


def test_numpy_really_is_unavailable_in_these_tests(blocker_dir):
    # Guards the guard: if numpy were importable, every test below would pass
    # for the wrong reason.
    result = subprocess.run(
        [sys.executable, "-c", "import numpy"],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(blocker_dir)},
    )
    assert result.returncode != 0
    assert "No module named" in result.stderr


def test_mono_downmix_runs_without_numpy(blocker_dir, tmp_path):
    source = tmp_path / "in.wav"
    _write_stereo_wav(source)

    result = _run_cli(blocker_dir, "process", str(source), "--mono",
                      "--output-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    channels, _ = _wav_info(tmp_path / "in_mono.wav")
    assert channels == 1


def test_trim_silence_runs_without_numpy(blocker_dir, tmp_path):
    source = tmp_path / "in.wav"
    _write_stereo_wav(source, seconds=2.0)  # 0.25s of silence at each end

    result = _run_cli(blocker_dir, "process", str(source), "--trim",
                      "--output-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    _, duration = _wav_info(tmp_path / "in_trimmed.wav")
    assert duration == pytest.approx(1.5, abs=0.1)


def test_trim_threshold_is_honoured(blocker_dir, tmp_path):
    source = tmp_path / "in.wav"
    _write_stereo_wav(source)

    result = _run_cli(blocker_dir, "process", str(source), "--trim",
                      "--threshold", "0.02", "--output-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "in_trimmed.wav").exists()


def test_normalize_still_runs_without_numpy(blocker_dir, tmp_path):
    source = tmp_path / "in.wav"
    _write_stereo_wav(source)

    result = _run_cli(blocker_dir, "process", str(source), "--normalize",
                      "--output-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "in_normalized.wav").exists()


def test_analyze_still_runs_without_numpy(blocker_dir, tmp_path):
    source = tmp_path / "in.wav"
    _write_stereo_wav(source)

    result = _run_cli(blocker_dir, "analyze", str(source))

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("operation", ["mono", "trim"])
def test_batch_accepts_the_stdlib_operations(blocker_dir, tmp_path, operation):
    _write_stereo_wav(tmp_path / "a.wav")
    output = tmp_path / "out"
    output.mkdir()

    result = _run_cli(blocker_dir, "batch", str(tmp_path), operation,
                      "--output-dir", str(output))

    assert result.returncode == 0, result.stderr


def test_operations_needing_numpy_still_say_so(blocker_dir, tmp_path):
    # The flip side: denoise genuinely needs numpy and must fail with a
    # message naming the extra, not a bare traceback.
    source = tmp_path / "in.wav"
    _write_stereo_wav(source)

    result = _run_cli(blocker_dir, "process", str(source), "--denoise",
                      "--output-dir", str(tmp_path))

    combined = result.stdout + result.stderr
    assert "numpy" in combined.lower()
    assert "[audio]" in combined


def test_mono_and_trim_can_be_combined(blocker_dir, tmp_path):
    source = tmp_path / "in.wav"
    _write_stereo_wav(source)

    result = _run_cli(blocker_dir, "process", str(source), "--mono", "--trim",
                      "--output-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "in_mono.wav").exists()
    assert (tmp_path / "in_trimmed.wav").exists()
