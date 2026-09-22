"""Install docs/scripts must do what their own banners claim.

Two verified defects:

- ``quick_install.sh``/``.ps1`` printed "Python 3.8+ is required but not
  found" but only checked that *a* python binary exists — a 3.7
  interpreter sailed through to "Installation complete" on a project
  that declares ``requires-python = ">=3.8"``.
- ``pip install -r requirements.txt`` appeared in both scripts and in
  QUICKSTART.md as the dependency-install step, while requirements.txt is
  intentionally comments-only (the core is stdlib-only): the step ran
  successfully and installed nothing.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_python(bin_dir: Path, version: str) -> Path:
    script = bin_dir / "python3"
    script.write_text(
        '#!/bin/bash\n'
        f'if [ "$1" = "-c" ]; then echo "{version}"; exit 0; fi\n'
        'if [ "$2" = "venv" ]; then mkdir -p .venv/bin; '
        'touch .venv/bin/activate; exit 0; fi\n'
        'exit 0\n')
    script.chmod(0o755)
    return script


def _run_quick_install(tmp_path: Path, version: str) -> subprocess.CompletedProcess:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _fake_python(bin_dir, version)
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    return subprocess.run(
        ["bash", str(REPO_ROOT / "quick_install.sh")],
        capture_output=True, text=True, cwd=str(work_dir),
        env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
    )


def test_quick_install_rejects_a_python_below_the_declared_minimum(tmp_path):
    result = _run_quick_install(tmp_path, "3.7")
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "3.8" in combined
    assert "Installation complete" not in combined


def test_quick_install_accepts_a_python_at_the_minimum(tmp_path):
    result = _run_quick_install(tmp_path, "3.12")

    # Past the version gate: the venv step is reached. (pip is absent in
    # the stub PATH, so the run may warn later -- the gate is the point.)
    assert "Creating virtual environment" in result.stdout + result.stderr


def _requirements_declares_nothing() -> bool:
    reqs = (REPO_ROOT / "requirements.txt").read_text()
    return not [line for line in reqs.splitlines()
                if line.strip() and not line.lstrip().startswith("#")]


@pytest.mark.parametrize("doc", [
    "quick_install.sh", "quick_install.ps1", "QUICKSTART.md",
])
def test_install_instructions_do_not_invoke_the_empty_requirements(doc):
    if not _requirements_declares_nothing():
        pytest.skip("requirements.txt declares dependencies again")
    text = (REPO_ROOT / doc).read_text()
    assert "requirements.txt" not in text or "-r requirements.txt" not in text, (
        f"{doc} still runs `pip install -r requirements.txt`, which "
        f"installs nothing from a comments-only file")


def test_ps1_script_gates_the_version_it_prints():
    # PowerShell cannot run on this host, so this pins the gate's
    # presence rather than its behavior (the .sh twin is exercised
    # end-to-end above).
    text = (REPO_ROOT / "quick_install.ps1").read_text()
    assert "versionParts" in text and "-lt 8" in text and "exit 1" in text


# --- MIDI_USAGE.md must describe the module that ships --------------------

def test_midi_usage_does_not_require_mido():
    # midi_analysis writes .mid files with `struct` alone -- verified by
    # running `midi generate`/`compose` on a numpy-free install -- so the
    # guide must not send users to `pip install mido` for a package that
    # nothing imports.
    analysis = (REPO_ROOT / "midi_analysis.py").read_text()
    guide = (REPO_ROOT / "MIDI_USAGE.md").read_text()
    if "import mido" not in analysis:
        # The false claim was mido-as-dependency ("pip install mido",
        # "Mido (for MIDI file generation)"), not the word itself.
        assert "pip install mido" not in guide
        assert "Mido (" not in guide


def test_midi_usage_does_not_claim_ai_features():
    # `enable_composition_ai` exists on MIDIConfig but is inert -- the
    # config field's own comment says so, and CHARTER §4 forbids AI
    # claims. The guide once listed it as "Enable AI features".
    guide = (REPO_ROOT / "MIDI_USAGE.md").read_text()
    assert "Enable AI features" not in guide


def test_midi_usage_loads_audio_through_a_real_symbol():
    # The example workflow called bare `load_audio("song.wav")` -- no
    # top-level function of that name exists anywhere; it would NameError
    # as written. The real path is AudioProcessor().load_audio.
    guide = (REPO_ROOT / "MIDI_USAGE.md").read_text()
    assert "= load_audio(" not in guide
    assert "AudioProcessor" in guide


def test_midi_usage_names_no_style_parameter():
    # "Style-based parameter adjustment" appeared under Composition with
    # no style parameter anywhere in midi_analysis or the CLI.
    guide = (REPO_ROOT / "MIDI_USAGE.md").read_text()
    assert "Style-based" not in guide
