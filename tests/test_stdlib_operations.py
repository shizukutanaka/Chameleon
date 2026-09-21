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


def _write_mono_wav(path, seconds=1.0, sample_rate=44100):
    frames = []
    for i in range(int(sample_rate * seconds)):
        value = int(0.4 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(frames))


def test_mono_is_idempotent_on_a_file_that_is_already_mono(blocker_dir, tmp_path):
    # `--mono` on a mono file used to print "Error: Already mono", write no
    # output, and exit 0 -- so a pipeline saw success and then could not find
    # the file it had been promised. Asking a mono file to be mono is a
    # satisfied request.
    source = tmp_path / "in.wav"
    _write_mono_wav(source)

    result = _run_cli(blocker_dir, "process", str(source), "--mono",
                      "--output-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "Error" not in result.stdout
    output = tmp_path / "in_mono.wav"
    assert output.exists(), "no output written for an already-mono file"
    assert _wav_info(output)[0] == 1


def test_an_already_mono_file_is_copied_unchanged(blocker_dir, tmp_path):
    source = tmp_path / "in.wav"
    _write_mono_wav(source)

    _run_cli(blocker_dir, "process", str(source), "--mono", "--output-dir", str(tmp_path))

    assert (tmp_path / "in_mono.wav").read_bytes() == source.read_bytes()


def test_a_batch_of_mixed_channel_counts_all_succeeds(blocker_dir, tmp_path):
    # The case that surfaced it: one mono and one stereo file in one batch.
    _write_mono_wav(tmp_path / "already_mono.wav")
    _write_stereo_wav(tmp_path / "stereo.wav")
    output = tmp_path / "out"
    output.mkdir()

    result = _run_cli(blocker_dir, "batch", str(tmp_path), "mono",
                      "--output-dir", str(output))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2/2" in result.stdout


def test_trim_drops_position_anchored_metadata_chunks(tmp_path):
    # A `cue ` (or smpl/plst/bext) chunk before `data` anchors to absolute
    # sample positions; copying it verbatim through trim ships stale cue
    # points that refer to deleted audio. The processed file is a new
    # artifact, so trim drops them -- while descriptive chunks like
    # LIST-INFO still carry over.
    import wave
    sr = 44100
    loud = b"\x00\x20" * sr
    silent = b"\x00\x00" * sr
    cue_body = struct.pack("<I", 1) + struct.pack("<II4sIII", 1, sr, b"data", 0, 0, sr)
    list_body = b"INFO" + b"INAM" + struct.pack("<I", 5) + b"title\x00\x00\x00"
    fmt_body = struct.pack("<HHIIHH", 1, 1, sr, sr * 2, 2, 16)
    body = b"fmt " + struct.pack("<I", 16) + fmt_body
    body += b"cue " + struct.pack("<I", len(cue_body)) + cue_body
    body += b"LIST" + struct.pack("<I", len(list_body)) + list_body
    if len(list_body) % 2:
        body += b"\x00"
    samples = silent + loud
    body += b"data" + struct.pack("<I", len(samples)) + samples
    source = tmp_path / "cued.wav"
    source.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body)

    from core import WAVProcessor
    out = tmp_path / "trimmed.wav"
    result = WAVProcessor().trim_silence(str(source), str(out), threshold=0.01)
    assert result.success, result.message

    written = out.read_bytes()
    assert b"cue " not in written, "stale cue points survived the trim"
    assert b"LIST" in written, "descriptive metadata was dropped too"
    with wave.open(str(out)) as handle:
        assert abs(handle.getnframes() / handle.getframerate() - 1.0) < 0.05


def test_normalize_keeps_position_metadata(tmp_path):
    # Positions don't shift under gain, so verbatim preservation is right.
    import wave
    sr = 44100
    cue_body = struct.pack("<I", 1) + struct.pack("<II4sIII", 1, sr // 2, b"data", 0, 0, sr // 2)
    fmt_body = struct.pack("<HHIIHH", 1, 1, sr, sr * 2, 2, 16)
    body = b"fmt " + struct.pack("<I", 16) + fmt_body
    body += b"cue " + struct.pack("<I", len(cue_body)) + cue_body
    samples = b"\x00\x20" * sr
    body += b"data" + struct.pack("<I", len(samples)) + samples
    source = tmp_path / "cued.wav"
    source.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body)

    from core import WAVProcessor
    out = tmp_path / "norm.wav"
    result = WAVProcessor().normalize(str(source), str(out))
    assert result.success, result.message
    assert b"cue " in out.read_bytes()
