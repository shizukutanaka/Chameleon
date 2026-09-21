"""Covers the Phase 7 excess/deficiency fixes in main.py's CLI:

- Ghost parameters removed (process --parallel, ml enhance --model,
  stream --monitor) now correctly rejected by argparse.
- Previously-unreachable options wired for real: batch --quality,
  process/batch --target-peak, batch effects.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

import main
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


def _peak(wav_path) -> float:
    import wave
    with wave.open(str(wav_path), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
    import array
    samples = array.array("h", frames)
    return max(abs(s) for s in samples) / 32768.0


# -- removed ghost parameters: argparse must now reject them (exit 2) --------

def test_process_parallel_flag_removed(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--normalize", "--parallel", cwd=str(tmp_path))
    assert result.returncode == 2


def test_ml_command_removed(tmp_path):
    # The `--model` flag went first; the command followed it in 2026-08. Its
    # one operation was remove_noise() + normalize_audio() -- no model, no
    # learning -- and `process --denoise --normalize` does the same work under
    # a name that is true. See CHARTER.md §9.
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("ml", "enhance", "--input", str(wav), cwd=str(tmp_path))
    assert result.returncode == 2


def test_stream_monitor_flag_removed(tmp_path):
    result = _run("stream", "--monitor", cwd=str(tmp_path))
    assert result.returncode == 2


def test_stream_device_flags_require_int(tmp_path):
    result = _run("stream", "--input-device", "not-a-number", cwd=str(tmp_path))
    assert result.returncode == 2


# -- --target-peak wired end-to-end ------------------------------------------

def test_process_target_peak_is_honored(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav", amplitude=8000)
    out_dir = tmp_path / "out"
    result = _run(
        "process", str(wav), "--normalize", "--target-peak", "0.5",
        "--output-dir", str(out_dir), cwd=str(tmp_path),
    )
    assert result.returncode == 0
    produced = list(out_dir.glob("*.wav"))
    assert produced, result.stdout + result.stderr
    assert abs(_peak(produced[0]) - 0.5) < 0.02


def test_batch_target_peak_is_honored(tmp_path):
    write_sine_wave(tmp_path / "tone.wav", amplitude=8000)
    out_dir = tmp_path / "out"
    result = _run(
        "batch", str(tmp_path), "normalize", "--target-peak", "0.4",
        "--output-dir", str(out_dir), cwd=str(tmp_path),
    )
    assert result.returncode == 0
    produced = list(out_dir.glob("*.wav"))
    assert produced, result.stdout + result.stderr
    assert abs(_peak(produced[0]) - 0.4) < 0.02


# -- batch effects operation --------------------------------------------------

def test_batch_effects_requires_effects_flag(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    result = _run("batch", str(tmp_path), "effects", cwd=str(tmp_path))
    assert result.returncode == 2


@pytest.mark.skipif(not main.HAS_NUMPY,
                    reason="the effects operation needs numpy; the stdlib core has no effects")
def test_batch_effects_runs_with_effects_file(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    effects_file = tmp_path / "effects.json"
    effects_file.write_text(json.dumps({}))
    out_dir = tmp_path / "out"
    result = _run(
        "batch", str(tmp_path), "effects", "--effects", str(effects_file),
        "--output-dir", str(out_dir), cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr


# -- batch --quality now sets the shared AudioProcessor config --------------

def test_batch_quality_flag_sets_processor_config(tmp_path, monkeypatch):
    write_sine_wave(tmp_path / "tone.wav")
    captured = {}
    original_init = main.AudioProcessor.__init__

    def spy_init(self, *a, **kw):
        original_init(self, *a, **kw)
        captured["processor"] = self

    monkeypatch.setattr(main.AudioProcessor, "__init__", spy_init)
    monkeypatch.setattr(
        sys, "argv",
        ["main.py", "batch", str(tmp_path), "normalize", "--quality", "low"],
    )
    monkeypatch.chdir(tmp_path)

    asyncio.run(main.main())

    # Legacy tier names never had distinct behavior; they map to 'standard'
    # (the flag is still wired end to end).
    assert captured["processor"].config.quality == "standard"


# -- midi --key/--mode: wired for real (previously accepted and ignored) -----

def _midi_pitch_classes(mid_path):
    """Pitch classes of note-on/note-off events in a SMF file."""
    data = Path(mid_path).read_bytes()
    pitches = [
        data[i - 1] for i in range(2, len(data))
        if data[i - 2] in (0x90, 0x80) and 0 < data[i - 1] < 128
    ]
    return {p % 12 for p in pitches}


def test_midi_generate_honors_key_and_mode(tmp_path):
    out = tmp_path / "ebm.mid"
    result = _run(
        "midi", "generate", "--key", "Eb", "--mode", "minor", "--output", str(out),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Eb natural minor pitch classes: Eb F Gb Ab Bb Cb Db -> {1,3,5,6,8,10,11}
    pcs = _midi_pitch_classes(out)
    assert pcs <= {1, 3, 5, 6, 8, 10, 11}, pcs
    assert 3 in pcs  # the tonic actually moves


def test_midi_compose_honors_key_and_mode(tmp_path):
    out = tmp_path / "gm.mid"
    result = _run(
        "midi", "compose", "--key", "G", "--mode", "minor", "--output", str(out),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Melody AND chords must stay inside G natural minor; a transposed
    # major-mode progression would inject F# (pc 6).
    assert _midi_pitch_classes(out) <= {0, 2, 3, 5, 7, 9, 10}


def test_midi_generate_rejects_an_unknown_key(tmp_path):
    result = _run(
        "midi", "generate", "--key", "ZZ", "--output", str(tmp_path / "x.mid"),
        cwd=str(tmp_path),
    )
    assert result.returncode == 3  # INPUT -- a bad key is a bad argument
    assert not (tmp_path / "x.mid").exists()


# -- --target-peak range: the documented (0, 1.0] contract is enforced ------

def test_process_rejects_target_peak_above_one(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--normalize", "--target-peak", "2.0",
                  cwd=str(tmp_path))
    assert result.returncode == 3  # INPUT
    # Above-unity targets used to "succeed" while the soft clipper silently
    # crushed the overshoot; nothing may be written on rejection.
    assert not (tmp_path / "tone_normalized.wav").exists()


def test_batch_rejects_target_peak_zero(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    result = _run("batch", str(tmp_path), "normalize", "--target-peak", "0",
                  cwd=str(tmp_path))
    assert result.returncode == 3  # INPUT


# -- plugins flags work in the documented post-subcommand position ----------

def test_plugins_list_accepts_json_after_subcommand(tmp_path):
    result = _run("plugins", "list", "--json", cwd=str(tmp_path))
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "directories" in payload and "plugins" in payload


def test_plugins_directory_positions_merge(tmp_path):
    a = tmp_path / "dir_a"
    b = tmp_path / "dir_b"
    a.mkdir()
    b.mkdir()
    result = _run("plugins", "--directory", str(a), "list",
                  "--directory", str(b), "--json", cwd=str(tmp_path))
    assert result.returncode == 0
    dirs = json.loads(result.stdout)["directories"]
    assert str(a) in dirs and str(b) in dirs, dirs


def test_plugins_directory_that_is_a_file_exits_input(tmp_path):
    not_a_dir = tmp_path / "a_file"
    not_a_dir.write_text("x")
    result = _run("plugins", "list", "--directory", str(not_a_dir),
                  cwd=str(tmp_path))
    assert result.returncode == 3  # INPUT
    assert "not a directory" in result.stderr


def test_batch_dry_run_writes_nothing(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    out = tmp_path / "out"
    result = _run("batch", str(tmp_path), "normalize", "--dry-run",
                  "--output-dir", str(out), cwd=str(tmp_path))
    assert result.returncode == 0
    # README promises a preview; nothing may be written, and the summary
    # must not claim files were processed.
    assert not out.exists()
    assert list(tmp_path.glob("*_normalized.wav")) == []
    assert "Would process" in result.stdout


# -- Op-scoped flags are rejected when their operation is absent ---------

def test_process_rejects_threshold_without_trim(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--normalize", "--threshold", "0.5",
                  cwd=str(tmp_path))
    # --threshold only feeds --trim; without it the flag was silently ignored.
    assert result.returncode == 2  # USAGE


def test_process_rejects_convert_flag_without_convert(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--mono", "--convert-bit-depth", "24",
                  cwd=str(tmp_path))
    assert result.returncode == 2


def test_batch_rejects_convert_flags_on_normalize(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    result = _run("batch", str(tmp_path), "normalize", "--sample-rate", "22050",
                  cwd=str(tmp_path))
    assert result.returncode == 2


def test_batch_rejects_quality_on_mono(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    result = _run("batch", str(tmp_path), "mono", "--quality", "high",
                  cwd=str(tmp_path))
    assert result.returncode == 2


def test_batch_rejects_effects_on_normalize(tmp_path):
    write_sine_wave(tmp_path / "tone.wav")
    fx = tmp_path / "fx.json"
    fx.write_text('{"reverb": {"wet": 0.3}}')
    result = _run("batch", str(tmp_path), "normalize", "--effects", str(fx),
                  cwd=str(tmp_path))
    assert result.returncode == 2


def test_analyze_export_metadata_is_structured(tmp_path):
    """--export must emit JSON objects, not a repr string containing
    np.float64(...) -- a JSON export consumers cannot index is broken."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    out = tmp_path / "analysis.json"
    result = _run("analyze", str(wav), "--export", str(out), cwd=str(tmp_path))
    assert result.returncode == 0
    entry = json.loads(out.read_text())[0]
    assert isinstance(entry["metadata"], dict)
    assert isinstance(entry["metadata"]["duration"], float)
    assert "np.float64" not in out.read_text()


def test_midi_compose_tempo_reaches_the_file(tmp_path):
    """--tempo was accepted but never written: the file had no FF 51 03
    meta event, so every composition played at the player's default 120."""
    out = tmp_path / "t.mid"
    result = _run("midi", "compose", "--key", "C", "--tempo", "60",
                  "--output", str(out), cwd=str(tmp_path))
    assert result.returncode == 0
    data = out.read_bytes()
    i = data.find(b"\xff\x51\x03")
    assert i >= 0, "no tempo meta-event in file"
    uspq = int.from_bytes(data[i+3:i+6], "big")
    assert uspq == 1_000_000  # 60 BPM


# -- midi op-scoped flags: a flag the operation ignores must be rejected ----

def test_midi_analyze_rejects_output_flags(tmp_path):
    """`midi analyze` only consumes --input; every other flag used to be
    silently ignored (same class as the process/batch scoping fix)."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    for flag, value in [("--tempo", "90"), ("--key", "G"),
                        ("--output", str(tmp_path / "x.mid"))]:
        result = _run("midi", "analyze", "--input", str(wav), flag, value,
                      cwd=str(tmp_path))
        assert result.returncode == 2, (flag, result.stdout + result.stderr)
        assert flag in result.stderr


def test_midi_compose_rejects_input(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("midi", "compose", "--input", str(wav), cwd=str(tmp_path))
    assert result.returncode == 2
    assert "--input" in result.stderr


def test_midi_generate_rejects_length(tmp_path):
    result = _run("midi", "generate", "--output", str(tmp_path / "x.mid"),
                  "--length", "30", cwd=str(tmp_path))
    assert result.returncode == 2
    assert "--length" in result.stderr


# -- numeric flag ranges: values that crash the encoder are bad input -------

def test_midi_tempo_out_of_encodable_range_rejected(tmp_path):
    """--tempo 0 used to surface as 'float division by zero' inside the file
    writer, and --tempo 2 overflowed the 24-bit us-per-quarter field. Both
    are input errors, not encoder crashes."""
    for bad in ("0", "-120", "2"):
        result = _run("midi", "generate",
                      "--output", str(tmp_path / "x.mid"),
                      "--tempo", bad, cwd=str(tmp_path))
        assert result.returncode == 3, (bad, result.stdout + result.stderr)
        assert "--tempo" in result.stderr
        assert not (tmp_path / "x.mid").exists()


def test_midi_compose_rejects_nonpositive_length(tmp_path):
    result = _run("midi", "compose", "--length", "-5",
                  "--output", str(tmp_path / "x.mid"), cwd=str(tmp_path))
    assert result.returncode == 3
    assert "--length" in result.stderr


def test_server_rejects_out_of_range_port_and_workers(tmp_path):
    """`server --port -1` used to die inside uvicorn with an OverflowError
    traceback."""
    for args in (("--port", "-1"), ("--port", "70000"), ("--workers", "0")):
        result = _run("server", *args, cwd=str(tmp_path))
        assert result.returncode == 3, (args, result.stdout + result.stderr)


def test_process_rejects_out_of_range_threshold(tmp_path):
    """--threshold is documented 0-1; an out-of-range value used to become
    a per-file ERROR(1) deep in core instead of an upfront INPUT."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--trim", "--threshold", "5",
                  cwd=str(tmp_path))
    assert result.returncode == 3
    assert "--threshold" in result.stderr


# -- effects-file parameter domains: nonsense values are bad input ---------

def _effects_file(tmp_path, payload: dict):
    p = tmp_path / "fx.json"
    p.write_text(json.dumps(payload))
    return str(p)


def test_effects_rejects_nonpositive_eq_frequency(tmp_path):
    """A -100 Hz/+99 dB band used to be silently skipped by the DSP guard,
    producing byte-identical output under 'Processed'."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _effects_file(tmp_path, {"eq": [{"frequency": -100, "gain": 99}]})
    result = _run("process", str(wav), "--effects", fx, cwd=str(tmp_path))
    assert result.returncode == 3
    assert "frequency" in result.stderr


def test_effects_rejects_sub_unity_compression_ratio(tmp_path):
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _effects_file(tmp_path, {"compression": {"ratio": -1}})
    result = _run("process", str(wav), "--effects", fx, cwd=str(tmp_path))
    assert result.returncode == 3
    assert "ratio" in result.stderr


def test_effects_warns_on_unknown_parameters(tmp_path):
    """A typo like 'treshold' (or a documented-looking knob nothing reads,
    e.g. reverb 'damping') used to be silently ignored. The warning fires at
    load time, before any DSP dependency is needed."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    fx = _effects_file(tmp_path, {"compression": {"treshold": -10, "ratio": 2}})
    result = _run("process", str(wav), "--effects", fx, cwd=str(tmp_path))
    assert "unknown parameter 'treshold'" in result.stderr


def test_analyze_export_unwritable_path_is_input_error(tmp_path):
    """A directory or missing-dir export path used to leak an OSError
    traceback (IsADirectoryError/NotADirectoryError/PermissionError are not
    FileNotFoundError, so cli()'s tidy handler never saw them)."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    for bad in (str(tmp_path), str(tmp_path / "no-such-dir" / "x.json")):
        result = _run("analyze", str(wav), "--export", bad,
                      cwd=str(tmp_path))
        assert result.returncode == 3, (bad, result.stdout + result.stderr)
        assert "Traceback" not in result.stderr


def test_midi_output_path_is_preflighted(tmp_path):
    """A bad --output destination used to reach the writer and surface as
    'Error generating MIDI file: <errno>' with ERROR(1)."""
    for bad in (str(tmp_path), str(tmp_path / "no-dir" / "x.mid")):
        result = _run("midi", "generate", "--output", bad,
                      cwd=str(tmp_path))
        assert result.returncode == 3, (bad, result.stdout + result.stderr)
        assert not (tmp_path / "x.mid").exists()


def test_batch_rejects_unknown_format_upfront(tmp_path):
    """--format had no choices: 'mp3' parsed and then every file failed
    identically inside convert_audio."""
    write_sine_wave(tmp_path / "tone.wav")
    result = _run("batch", str(tmp_path), "convert", "--format", "mp3",
                  cwd=str(tmp_path))
    assert result.returncode == 2  # argparse invalid choice


def test_negative_sample_rate_rejected_upfront(tmp_path):
    """--sample-rate -1 used to parse and then fail identically on every
    file inside convert_audio."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    batch = _run("batch", str(tmp_path), "convert", "--sample-rate", "-1",
                 cwd=str(tmp_path))
    assert batch.returncode == 3
    single = _run("process", str(wav), "--convert", "--convert-sample-rate",
                  "0", cwd=str(tmp_path))
    assert single.returncode == 3


def test_stream_rejects_negative_device_index(tmp_path):
    """PyAudio device indices are >= 0; a negative index used to reach the
    backend (or fail opaquely when PyAudio is absent)."""
    result = _run("stream", "--input-device", "-1", cwd=str(tmp_path))
    assert result.returncode == 3
    assert "--input-device" in result.stderr


def test_analyze_export_unmeasured_fields_are_null_not_defaults(tmp_path):
    """frequency_range [0.0, 0.0] and tempo 0.0 in the export look like
    measurements but were only dataclass defaults. Unmeasured must
    serialize as null on every install configuration."""
    wav = write_sine_wave(tmp_path / "tone.wav")
    out = tmp_path / "analysis.json"
    result = _run("analyze", str(wav), "--export", str(out), cwd=str(tmp_path))
    assert result.returncode == 0
    meta = json.loads(out.read_text())[0]["metadata"]
    assert meta["frequency_range"] != [0.0, 0.0] or meta["frequency_range"] is None
    assert meta["tempo"] is None or meta["tempo"] > 0
    # File-derived fields must describe the file, not the decoded array
    assert meta["size_bytes"] == wav.stat().st_size
    assert meta["format"] == "wav"
    assert meta["bit_depth"] == 16


def test_zero_frame_wav_analyze_and_transforms_are_identity(tmp_path):
    """A valid 0-frame WAV must not crash the numpy path: analyze reports
    all-zero stats (matching the stdlib path) and transforms write an
    empty file, the same way normalize/mono already did."""
    import subprocess, sys, wave
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")
    wav = tmp_path / "zero.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b"")

    proc = subprocess.run(
        [sys.executable, main_py, "analyze", str(wav)],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert "Peak Level: 0.000" in proc.stdout

    # Transforms on a file with no signal are INPUT rejections in both
    # tiers (the stdlib path's own convention: "No audio signal found");
    # --mono is the exception that writes an empty identity output.
    import importlib.util
    try:
        has_numpy = importlib.util.find_spec("numpy") is not None
    except ModuleNotFoundError:
        # The stdlib-gate sitecustomize raises from find_spec itself.
        has_numpy = False
    ops = (["--declip"], ["--dehum"], ["--denoise"], ["--convert"]) if has_numpy else ()
    for op in (*ops, ["--normalize"], ["--trim"]):
        proc = subprocess.run(
            [sys.executable, main_py, "process", str(wav)] + op,
            capture_output=True, text=True, timeout=30)
        assert proc.returncode == 3, f"{op}: {proc.returncode} {proc.stderr}"
        assert "No audio" in proc.stderr


def test_process_warns_when_inputs_collide_in_output_dir(tmp_path):
    """Two inputs sharing a stem both write <stem>_normalized.wav into
    --output-dir; the second silently clobbers the first. The user must
    hear about it."""
    import subprocess, sys
    from pathlib import Path
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")
    d1, d2, out = tmp_path/"d1", tmp_path/"d2", tmp_path/"out"
    d1.mkdir(); d2.mkdir()
    import wave
    for d in (d1, d2):
        with wave.open(str(d/"same.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x01\x00" * 1000)
    proc = subprocess.run(
        [sys.executable, main_py, "process",
         str(d1/"same.wav"), str(d2/"same.wav"),
         "--normalize", "--output-dir", str(out)],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "overwrite" in proc.stderr
    assert "same" in proc.stderr


def test_docs_synopsis_lists_only_real_subcommands():
    """docs/*/commands.md show a `{a,b,c}` choice list in their usage synopsis.
    The deleted `ml` command survived there as a bare token for months because
    no fantasy-feature grep matches a comma-list entry -- the doc synopsis must
    be compared against the parser's actual choices, not pattern-scanned."""
    import re, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    help_out = subprocess.run(
        [sys.executable, str(root / "main.py"), "--help"],
        capture_output=True, text=True, timeout=30).stdout
    real = set(re.search(r"\{([a-z,]+)\}", help_out).group(1).split(","))
    for doc in (root / "docs").rglob("commands.md"):
        m = re.search(r"\{([a-z,]+)\}", doc.read_text())
        assert m, f"{doc} has no subcommand synopsis to check"
        listed = set(m.group(1).split(","))
        assert listed == real, (
            f"{doc}: synopsis {sorted(listed)} != parser {sorted(real)}")


def test_server_rejects_multi_worker():
    # api_state (sessions, tokens, jobs, audit log) is per-process memory;
    # N>1 workers each import api_server fresh and cannot share it, so a
    # session created on worker A 401s when routed to worker B. The flag
    # must refuse loudly rather than start an API that forgets logins.
    result = subprocess.run(
        [sys.executable, MAIN_PY, "server", "--workers", "2"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 3
    assert "--workers must be 1" in result.stderr


def test_convert_bit_depth_32_writes_pcm_not_float(tmp_path):
    # soundfile's "FLOAT" subtype produced a format-tag-3 WAV that the
    # project's own dependency-free parser rejects -- convert must emit
    # PCM_32 so the artifact stays readable without the [audio] extra.
    pytest.importorskip("soundfile")
    wav = write_sine_wave(tmp_path / "tone.wav")
    result = _run("process", str(wav), "--convert", "--convert-bit-depth", "32",
                  cwd=str(tmp_path))
    assert result.returncode == 0, result.stderr

    out = tmp_path / "tone_converted_32bit.wav"
    body = out.read_bytes()
    fmt_off = body.find(b"fmt ")
    assert fmt_off > 0
    format_tag = int.from_bytes(body[fmt_off + 8:fmt_off + 10], "little")
    assert format_tag == 1  # PCM, not IEEE float (3)


# -- process --json describes failures, not just successes -------------------

def test_process_json_emits_error_record_when_every_file_fails(tmp_path):
    """`--json` promises structured output; a total failure used to print
    nothing to stdout -- a consumer can't tell 'nothing ran' from 'all
    failed'. Now failures are JSON records too."""
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav file")
    result = _run("process", str(bad), "--normalize", "--json",
                  cwd=str(tmp_path))
    assert result.returncode == 3  # INPUT
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["operation"] == "normalize"
    assert "error" in payload["result"]
    # The pre-flight sentinel carries the classified exit code the process
    # will exit with -- INPUT(3) for input-validation rejections.
    assert payload["result"]["exit_code"] == 3


def test_process_json_mixed_batch_reports_each_outcome(tmp_path):
    """Partial failure must not silently drop the failures: stdout carries
    one JSON record per file, successes and errors alike."""
    write_sine_wave(tmp_path / "good.wav")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav file")
    result = _run("process", str(tmp_path / "good.wav"), str(bad),
                  "--normalize", "--json",
                  "--output-dir", str(tmp_path / "out"), cwd=str(tmp_path))
    assert result.returncode == 3
    records = [json.loads(line) for line in result.stdout.strip().splitlines()]
    assert len(records) == 2
    statuses = sorted("error" in r["result"] for r in records)
    assert statuses == [False, True]
