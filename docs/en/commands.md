# Chameleon Audio Tool – Command Reference

Every command and flag below was verified against `main.py --help` and by
running it. If you find something here that the CLI does not accept, that is a
bug in this document — please report it.

Invoke either as `python main.py <command>` or, after `pip install -e .`, as
`chameleon <command>`.

```
chameleon [--version] [--max-workers N] [--no-parallel]
          {analyze,process,stream,batch,ml,midi,plugins,server} ...
```

Global options:

| Flag | Meaning |
|------|---------|
| `--version` | Print the version and exit |
| `--max-workers N` | Limit worker threads for batch operations |
| `--no-parallel` | Disable parallel execution even when available |

---

## Core commands

### `analyze`

Analyze one or more audio files.

```bash
chameleon analyze input.wav
chameleon analyze input.wav --detailed
chameleon analyze *.wav --export report.json
chameleon analyze input.wav --spectrum
chameleon analyze input.wav --loudness
```

| Flag | Meaning |
|------|---------|
| `--detailed` | Show detailed analysis |
| `--export FILE` | Export the analysis to a JSON file |
| `--spectrum` | Also report dominant frequencies, bandwidth and RMS (stdlib-only, deterministic) |
| `--loudness` | Also report loudness metering (stdlib-only) — see below |

`--loudness` reports, over a bounded prefix of the file:

- **Integrated loudness (LUFS)** — ITU-R BS.1770 K-weighted, gated. Sums
  per-channel energy correctly for mono/stereo; no surround-channel weighting.
- **True Peak (dBTP)** — 4×-oversampled inter-sample peak estimate
  (BS.1770-4 Annex 2 method).
- **Max Momentary (LUFS)** — loudest 400 ms window, ungated (EBU Mode).
- **Max Short-term (LUFS)** — loudest 3 s window, ungated (EBU Mode).

These are honest measurements, not a certified meter: see
`bs1770_loudness.py`'s module docstring for the exact scope of each claim.

### `process`

Process one or more files. Operations combine; output goes to `--output-dir`
(or alongside the input if omitted).

```bash
# Normalize to a target peak
chameleon process input.wav --normalize --target-peak 0.90 --output-dir out/

# Noise reduction
chameleon process input.wav --denoise --output-dir out/

# Convert sample rate / bit depth
chameleon process input.wav --convert --convert-sample-rate 44100 \
    --convert-bit-depth 16 --output-dir out/

# Preview without writing anything
chameleon process input.wav --normalize --dry-run

# Machine-readable summary
chameleon process input.wav --normalize --json
```

| Flag | Meaning |
|------|---------|
| `--normalize` | Normalize audio |
| `--target-peak F` | Target peak for `--normalize`, 0.0–1.0 (default 0.95) |
| `--denoise` | Remove noise |
| `--master {default,streaming,cd,vinyl}` | Apply a full mastering chain (EQ/compressor/limiter/loudness). Requires numpy; scipy recommended |
| `--effects FILE` | Apply effects from a JSON file |
| `--convert` | Convert format or resolution |
| `--convert-format FMT` | Target format (currently only `wav`) |
| `--convert-sample-rate N` | Target sample rate |
| `--convert-bit-depth {16,24,32}` | Target bit depth |
| `--output-dir DIR` | Output directory |
| `--dry-run` | Preview planned operations without writing files |
| `--json` | Emit a structured JSON summary |

### `batch`

Apply one operation to every audio file in a directory.

```bash
chameleon batch ./audio analyze
chameleon batch ./audio normalize --target-peak 0.9 --output-dir out/
chameleon batch ./audio convert --sample-rate 44100 --bit-depth 16 --output-dir out/
chameleon batch ./audio denoise --recursive --output-dir out/
```

Positional: `directory` then one of
`{analyze, normalize, denoise, convert, effects}`.

| Flag | Meaning |
|------|---------|
| `--recursive` | Process subdirectories too |
| `--output-dir DIR` | Output directory |
| `--format FMT` | Output format |
| `--quality {low,medium,high,lossless}` | Output quality |
| `--target-peak F` | Target peak for the `normalize` operation |
| `--sample-rate N` | Target sample rate for `convert` |
| `--bit-depth {16,24,32}` | Target bit depth for `convert` |
| `--effects FILE` | Effects configuration for the `effects` operation |

### `midi`

MIDI analysis and composition (pure standard library).

```bash
chameleon midi extract --input song.wav --output song.mid
chameleon midi analyze --input song.wav
chameleon midi compose --key C --mode major --tempo 120 --length 30 --output out.mid
chameleon midi generate --key G --mode minor --output out.mid
```

Positional: one of `{extract, analyze, compose, generate}`.

| Flag | Meaning |
|------|---------|
| `--input FILE` | Input audio file |
| `--output FILE` | Output MIDI file |
| `--key K` | Musical key (e.g. `C`, `G`, `F#`) |
| `--mode {major,minor}` | Mode |
| `--tempo N` | Tempo in BPM |
| `--length N` | Length in seconds |

### `plugins`

Inspect and audit plugins.

```bash
chameleon plugins list
chameleon plugins audit
chameleon plugins list --directory /abs/path/to/plugins --json
```

Sub-commands: `list` (discovered plugins and metadata), `audit` (check plugin
files for sandbox compliance).

| Flag | Meaning |
|------|---------|
| `--directory DIR` | Absolute plugin directory to inspect (repeatable) |
| `--json` | Emit structured JSON output |

---

## Commands requiring optional extras

These do **not** work on the default, dependency-free install. Install the
relevant extra first (see `README.md`).

### `ml` — requires numpy/scipy

Audio enhancement: noise reduction plus normalization.

```bash
pip install -e .[audio]
chameleon ml enhance --input noisy.wav --output clean.wav
```

Positional: `enhance`. Flags: `--input FILE` (required), `--output FILE`.

> Naming note: this subcommand applies conventional DSP (noise reduction and
> normalization). It does not perform machine learning — see `CHARTER.md` §4.

### `stream` — requires pyaudio

Real-time audio processing.

```bash
pip install -e .[audio]
chameleon stream --input-device 1 --output-device 2 --effects effects.json
```

| Flag | Meaning |
|------|---------|
| `--input-device N` | Input device index |
| `--output-device N` | Output device index |
| `--effects FILE` | Effects configuration (JSON) |

### `server` — requires fastapi/uvicorn

Start the local REST API adapter.

```bash
pip install -e .[api]
chameleon server --host 127.0.0.1 --port 8000 --workers 1
```

| Flag | Meaning |
|------|---------|
| `--host H` | Server host |
| `--port P` | Server port |
| `--workers N` | Number of workers |

The API is a thin, authenticated adapter over the same stdlib core — not a
hosted service or a separate product (`CHARTER.md` §3, §7).

---

## Exit codes

`chameleon` returns `0` on success and a non-zero code on failure, so it can be
used in shell pipelines and CI:

```bash
if chameleon analyze input.wav; then
    echo "ok"
else
    echo "failed with code $?"
fi
```

---

## Scope

This tool is WAV-focused by default. MP3/FLAC/OGG input works only once the
`[audio]` extra is installed, and the core analysis/normalization/batch/MIDI
paths deliberately run with no third-party packages at all. See `CHARTER.md`
for the full statement of scope and non-goals.
