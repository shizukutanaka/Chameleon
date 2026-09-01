"""What the CLI prints when it cannot do what was asked.

Two problems, found by running every command on the dependency-free install --
the one this project leads with -- and reading the output.

`AudioProcessor.load_audio` returns an ndarray from every one of its backends,
so it cannot succeed without numpy. But `np` was left bound to `None` and the
failure surfaced ninety lines later, inside `_load_wav_basic`, as

    AttributeError: 'NoneType' object has no attribute 'frombuffer'

Deleting the `ml` command removed the first place that was reachable from.
`midi extract` and `midi analyze` still reached it, which is the difference
between removing an instance and removing the cause. The check now lives in
`load_audio`, where the requirement actually is.

Second, `cli()` caught only `KeyboardInterrupt`, so errors this CLI raises
*deliberately* -- an unsupported file type, a missing file, a missing optional
dependency -- reached the terminal as tracebacks with the one useful line
buried in them. It now prints those. It still does not catch `Exception`:
turning a genuine bug into a tidy "Error:" line would make the tool wrong about
itself in a new way.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests._helpers import write_sine_wave

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
    directory = tmp_path_factory.mktemp("no_numpy")
    (directory / "sitecustomize.py").write_text(_BLOCKER)
    return directory


def _run_without_numpy(blocker_dir, *args):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(blocker_dir)},
    )


@pytest.fixture
def tone(tmp_path):
    return write_sine_wave(tmp_path / "tone.wav", duration=0.5)


# --- no raw tracebacks for a missing optional dependency ------------------

@pytest.mark.parametrize("operation", ["extract", "analyze"])
def test_midi_commands_report_the_missing_dependency(blocker_dir, tone, operation):
    result = _run_without_numpy(blocker_dir, "midi", operation, "--input", str(tone))
    combined = result.stdout + result.stderr

    assert "Traceback" not in combined, "a deliberate error reached the user as a crash"
    assert "numpy" in combined
    assert "[audio]" in combined
    assert result.returncode == 1


@pytest.mark.parametrize("operation", ["extract", "analyze"])
def test_the_nonetype_attributeerror_is_gone(blocker_dir, tone, operation):
    # The exact symptom: `np` bound to None, discovered 90 lines from the cause.
    result = _run_without_numpy(blocker_dir, "midi", operation, "--input", str(tone))

    assert "'NoneType' object has no attribute" not in result.stdout + result.stderr


def test_the_check_lives_where_the_requirement_is(blocker_dir, tone):
    # Guarding at the call sites would need a new guard for each new caller.
    # Guarding in load_audio means the next one is covered before it is written.
    result = subprocess.run(
        [sys.executable, "-c",
         "import main; p = main.AudioProcessor(main.ProcessingConfig()); "
         f"p.load_audio({str(tone)!r})"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(blocker_dir)},
    )

    assert "ValueError" in result.stderr
    assert "numpy" in result.stderr


# --- deliberate errors print, bugs still show their traceback -------------

def test_a_missing_file_prints_a_message_not_a_traceback(tmp_path):
    result = subprocess.run(
        [sys.executable, "main.py", "midi", "extract", "--input", str(tmp_path / "nope.wav")],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )

    assert "Traceback" not in result.stdout + result.stderr
    assert result.returncode == 1


def test_an_unsupported_file_type_prints_a_message(tmp_path):
    bogus = tmp_path / "song.mp4"
    bogus.write_bytes(b"\x00" * 64)

    result = subprocess.run(
        [sys.executable, "main.py", "midi", "extract", "--input", str(bogus)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )

    assert "Traceback" not in result.stdout + result.stderr
    assert result.returncode == 1


def test_unexpected_exceptions_are_not_swallowed():
    # The line this must not cross. `except Exception` here would hide real
    # bugs behind a friendly message -- the same "wrong about itself" failure
    # this file exists to fix, pointed the other way.
    import inspect
    import main

    # Comments are stripped first: the handler explains *why* it does not catch
    # Exception, and a naive substring search matches that explanation.
    code = "\n".join(line for line in inspect.getsource(main.cli).splitlines()
                     if not line.strip().startswith("#"))

    assert "except Exception" not in code
    assert "except (ValueError, FileNotFoundError)" in code
