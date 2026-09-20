"""Commercial-grade CLI contract: stderr separation, --version, quiet default.

Phase 8 polish (CHARTER §9): a scriptable CLI must keep diagnostics out of
stdout, answer --version, and not spam warnings on the supported stdlib-only
default install.
"""

import subprocess
import sys
from pathlib import Path

import pytest

import main
from tests._helpers import write_sine_wave, write_stereo_sine_wave

MAIN_PY = str(Path(__file__).resolve().parent.parent / "main.py")


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, MAIN_PY, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


def test_version_flag_reports_single_source_version(tmp_path):
    result = _run("--version", cwd=str(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == f"chameleon {main.VERSION}"


def test_help_shows_current_version_not_stale_v3(tmp_path):
    result = _run("--help", cwd=str(tmp_path))
    assert result.returncode == 0
    assert "v3.0" not in result.stdout
    assert main.VERSION in result.stdout


def test_errors_go_to_stderr_not_stdout(tmp_path):
    missing = tmp_path / "missing.wav"
    result = _run("analyze", str(missing), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT -- rejected pre-flight
    assert "Error" in result.stderr
    assert "Error" not in result.stdout


def test_input_validation_error_goes_to_stderr(tmp_path):
    result = _run("analyze", "a*.wav", cwd=str(tmp_path))
    assert result.returncode == 3
    assert "Input validation error" in result.stderr
    assert "Input validation error" not in result.stdout


def test_default_run_emits_no_optional_dep_warnings(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("analyze", str(wav), cwd=str(tmp_path))
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "UserWarning" not in combined
    assert "not installed" not in combined


def test_successful_analyze_output_stays_on_stdout(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("analyze", str(wav), cwd=str(tmp_path))
    assert result.returncode == 0
    assert "tone.wav" in result.stdout
    assert result.stderr.strip() == ""


def test_failed_stream_does_not_claim_it_started(tmp_path):
    # Without PyAudio the stream always fails immediately; the banner that
    # claims a live stream must not print anyway, and the exit must not be 0.
    if main.HAS_PYAUDIO:
        pytest.skip("PyAudio present; the failure path cannot be reached")

    result = _run("stream", cwd=str(tmp_path))
    assert result.returncode == 1  # ExitCode.ERROR
    assert "Stream failed" in result.stderr
    assert "Starting real-time audio stream" not in result.stdout


def test_server_banner_not_printed_when_uvicorn_missing(tmp_path):
    # Same class as the stream banner: "Starting API server" used to print
    # unconditionally, before the import that decides whether a server can
    # start at all. On a uvicorn-less install the banner was a lie followed
    # immediately by the real error.
    import importlib.util
    if importlib.util.find_spec("uvicorn") is not None:
        pytest.skip("uvicorn present; the failure path cannot be reached")

    result = _run("server", "--port", "8000", cwd=str(tmp_path))
    assert result.returncode == 1  # ExitCode.ERROR
    assert "requires fastapi and uvicorn" in result.stderr
    assert "Starting API server" not in result.stdout


def test_midi_analyze_error_is_reported_not_swallowed(tmp_path):
    # "No musical content detected" used to print on stdout and still exit 0.
    from tests._helpers import write_wav_raw
    silence = tmp_path / "silence.wav"
    write_wav_raw(silence, frames=b"\x00\x00" * 22050)
    result = _run("midi", "analyze", "--input", str(silence), cwd=str(tmp_path))
    assert result.returncode == 1  # ExitCode.ERROR
    assert "error" in result.stderr.lower()
    assert "Analysis error" not in result.stdout


def _write_effects(path, content: str):
    fx = path / "effects.json"
    fx.write_text(content)
    return fx


def test_effects_file_with_non_object_top_level_is_input_error(tmp_path):
    # A JSON array used to sail through every "in effects" check and write
    # unchanged audio under a "Processed" claim.
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '["compression"]')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "Input validation error" in result.stderr
    assert "Processed" not in result.stdout


def test_effects_file_with_bad_json_is_input_error(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, "{not json")
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "Input validation error" in result.stderr


def test_effects_file_with_non_object_effect_is_input_error(tmp_path):
    # '{"compression": "x"}' used to crash inside apply_effects with
    # "'str' object has no attribute 'get'" and exit 1.
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"compression": "loud"}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "parameter object" in result.stderr


def test_unknown_effect_name_warns_but_still_runs(tmp_path):
    pytest.importorskip("numpy")
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"nonexistent_fx": {"x": 1}}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 0
    assert "unknown effect" in result.stderr.lower()


def test_eq_effect_accepts_list_of_bands(tmp_path):
    """eq's schema is a LIST of band objects (frequency/gain[/q]) — the first
    version of _load_effects wrongly required every effect to be a dict and
    rejected the only schema apply_effects actually consumes."""
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"eq": [{"frequency": 1000, "gain": 3, "q": 1.0}]}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 0
    assert "Processed" in result.stdout or (tmp_path / "tone_processed.wav").exists()


def test_eq_effect_as_dict_is_input_error(tmp_path):
    # A dict eq used to crash inside apply_effects with
    # "string indices must be integers, not 'str'" and exit 1.
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"eq": {"low_shelf": 2.0}}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "list of band objects" in result.stderr


def test_eq_band_missing_gain_is_input_error(tmp_path):
    # Without validation this crashed with KeyError('gain') inside apply_effects.
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"eq": [{"frequency": 1000}]}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "gain" in result.stderr


def test_reverb_effect_on_stereo_input(tmp_path):
    """reverb used to crash on multi-channel audio: convolve((C,N), (N,))
    raised "volume and kernel should have the same dimensionality"."""
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    wav = write_stereo_sine_wave(tmp_path / "stereo.wav")
    fx = _write_effects(tmp_path, '{"reverb": {"room_size": 0.3, "wet": 0.2}}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 0

    import wave as _wave
    out = tmp_path / "stereo_processed.wav"
    assert out.exists()
    with _wave.open(str(out)) as w:
        assert w.getnchannels() == 2


def test_reverb_does_not_amplify_the_mix(tmp_path):
    """The synthetic noise IR carried unnormalized gain — a wet=0.3 mix
    raised the signal ~+10 dB instead of blending. The wet path is now
    normalized to the dry RMS before blending."""
    np_ = pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    import wave as _wave

    wav = tmp_path / "tone.wav"
    sr = 44100
    n = sr
    tone = 0.4 * np_.sin(2 * np_.pi * 220 * np_.arange(n) / sr)
    with _wave.open(str(wav), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((tone * 32767).astype("<i2").tobytes())

    fx = _write_effects(tmp_path, '{"reverb": {"room_size": 0.5, "wet": 0.4}}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 0

    with _wave.open(str(tmp_path / "tone_processed.wav")) as w:
        out = np_.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768
    in_rms = float(np_.sqrt(np_.mean(tone ** 2)))
    out_rms = float(np_.sqrt(np_.mean(out ** 2)))
    change_db = 20 * np_.log10(out_rms / in_rms)
    assert -3.0 < change_db < 3.0, f"reverb changed level by {change_db:+.1f} dB"


def test_effects_file_with_wrong_param_type_is_input_error(tmp_path):
    # '{"reverb": {"room_size": "big"}}' used to reach `params["room_size"] <= 0`
    # and leak a TypeError traceback instead of a validation error.
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"reverb": {"room_size": "big"}}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "Input validation error" in result.stderr
    assert "TypeError" not in result.stderr


def test_effects_file_with_nonfinite_param_is_input_error(tmp_path):
    # JSON NaN/Infinity literals are accepted by json.loads and satisfy
    # isinstance(x, float) while defeating every domain comparison
    # (NaN <= 0 is False) -- a NaN frequency used to run under "Processed".
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"eq": [{"frequency": NaN, "gain": 6}]}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 3  # ExitCode.INPUT
    assert "finite" in result.stderr
    assert "Processed" not in result.stdout


def test_invalid_parallel_env_warns_not_silently_coerced(monkeypatch):
    """CHAMELEON_PARALLEL=banana used to be truthy-tested into parallel=True:
    a garbage value silently meant 'on'. Now it must warn and keep the
    default -- an env knob you can't tell is broken isn't a knob."""
    import warnings
    import main
    monkeypatch.setenv("CHAMELEON_PARALLEL", "banana")
    monkeypatch.delenv("CHAMELEON_MAX_WORKERS", raising=False)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        cfg = main.ProcessingConfig.from_environment()
    assert cfg.parallel is True  # the default, not a coercion of "banana"
    assert any("CHAMELEON_PARALLEL" in str(w.message) for w in seen)


CORE_PY = str(Path(__file__).resolve().parent.parent / "core.py")


def _run_core(*args, cwd=None):
    return subprocess.run(
        [sys.executable, CORE_PY, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


def test_core_mini_cli_rejects_nonnumeric_float_arg(tmp_path):
    # `float(sys.argv[4])` was unguarded: `core.py normalize a b.wav banana`
    # died on a raw ValueError traceback. A bad number is user input, not a
    # crash.
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run_core("normalize", str(wav), "out.wav", "banana", cwd=str(tmp_path))
    assert result.returncode == 1
    assert "must be a number" in result.stdout
    assert "Traceback" not in result.stderr + result.stdout


def test_core_mini_cli_failure_exits_nonzero(tmp_path):
    # Every op printed result.message and fell through to exit 0: a missing
    # input reported its failure and still exited OK.
    result = _run_core("normalize", "missing.wav", "out.wav", cwd=str(tmp_path))
    assert result.returncode == 1
    assert result.stdout.strip()  # the failure message did print


def test_eq_effect_with_empty_band_list_is_a_noop(tmp_path):
    pytest.importorskip("numpy")
    # {} is already accepted as pass-through; {"eq": []} is the same
    # claim spelled differently -- zero bands, nothing to apply. It was
    # rejected with "must map to a list of band objects, got list",
    # which both misdescribed the input and disagreed with {}'s
    # acceptance.
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _write_effects(tmp_path, '{"eq": []}')
    result = _run("process", str(wav), "--effects", str(fx), cwd=str(tmp_path))
    assert result.returncode == 0
    assert "Processed" in result.stdout
