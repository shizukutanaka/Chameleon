"""Covers bs1770_loudness.py's wiring into main.py's `analyze --loudness` flag.

Mirrors tests/test_spectral_wiring.py's approach: bs1770_loudness.py is a
real, deterministic, stdlib-only module (see CHARTER §9 "C1"), wired in
through the existing core.get_samples_for_analysis helper.
"""

import json
import subprocess
import sys
from pathlib import Path

from tests._helpers import write_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, MAIN_PY, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


def test_cli_analyze_loudness_flag_reports_lufs(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=1.0, frequency=1000.0,
                           amplitude=32000)

    result = _run("analyze", str(wav), "--loudness", cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Loudness:" in result.stdout
    assert "LUFS" in result.stdout
    assert "BS.1770" in result.stdout


def test_cli_analyze_without_loudness_flag_omits_loudness_output(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")

    result = _run("analyze", str(wav), cwd=str(tmp_path))

    assert result.returncode == 0
    assert "Loudness" not in result.stdout


def test_cli_analyze_loudness_reports_gate_message_for_silence(tmp_path):
    wav = write_sine_wave(tmp_path / "silent.wav", duration=0.1, amplitude=0)

    result = _run("analyze", str(wav), "--loudness", cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "below measurement gate" in result.stdout


def test_cli_analyze_loudness_reports_unsupported_for_unstable_sample_rate(tmp_path):
    # Below bs1770_loudness's stability floor (8000 Hz), K-weighting is
    # numerically unstable; the CLI must report this honestly instead of
    # printing "inf LUFS".
    wav = write_sine_wave(tmp_path / "lowrate.wav", duration=1.0, frequency=200.0,
                           sample_rate=4000)

    result = _run("analyze", str(wav), "--loudness", cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "unsupported" in result.stdout
    assert "inf" not in result.stdout.lower().split("loudness:")[-1].split("\n")[0]


def test_cli_analyze_loudness_flows_into_export_json(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", duration=1.0, frequency=1000.0,
                           amplitude=32000)
    export_path = tmp_path / "out.json"

    result = _run("analyze", str(wav), "--loudness", "--export", str(export_path),
                   cwd=str(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    exported = json.loads(export_path.read_text())
    metadata_blob = exported[0]["metadata"]
    # main.py's --export uses json.dump(..., default=str), which stringifies
    # the AudioMetadata dataclass (a pre-existing behavior, out of scope
    # here) -- so assert the field made it into that string representation
    # rather than assuming structured JSON.
    assert "loudness_lufs=" in metadata_blob
    assert "loudness_lufs=None" not in metadata_blob
