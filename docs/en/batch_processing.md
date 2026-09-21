# Batch processing

## Overview

The `batch` command applies one operation to every supported audio file found
under a directory. Files are processed by a `ThreadPoolExecutor` worker pool
(default `min(4, cpu_count)`; tune with `--max-workers` /
`CHAMELEON_MAX_WORKERS`, or disable with `--no-parallel` /
`CHAMELEON_PARALLEL=0`).

## Usage

```
chameleon batch ./audio analyze
chameleon batch ./audio normalize --target-peak 0.9 --output-dir out/
chameleon batch ./audio convert --sample-rate 48000 --bit-depth 24 --output-dir out/
```

The directory is scanned non-recursively by default; pass `--recursive` to
descend into subdirectories. Files are matched against `SUPPORTED_FORMATS` —
`.wav`/`.wave` always, plus `.flac`, `.ogg`, `.aiff`, `.mp3`, `.m4a` when the
`[audio]` extras are installed. Inputs are never modified; each result is
written as `<stem>_<op>.<ext>` into `--output-dir` (or alongside the input
when no output directory is given).

## Options

- `--recursive`: Descend into subdirectories.
- `--output-dir DIR`: Directory for processed outputs. Pointing it inside the
  scanned directory prints a warning — outputs are re-ingested as inputs on
  the next run.
- `--dry-run`: Report what would be processed without writing files.
- `--effects FILE`: JSON effects configuration; required for the `effects`
  operation.
- `--format {wav}`: Output container (currently `wav`), `convert` only.
- `--sample-rate` / `--bit-depth {16,24,32}`: `convert` only.
- `--target-peak (0,1]` / `--quality`: `normalize` only. `high` enables the
  soft clipper; `low`/`medium`/`lossless` are accepted as aliases for
  `standard` and print a note saying so.
- `--max-workers N` / `--no-parallel`: global flags, placed before `batch`.

Flags that belong to an operation you did not request are rejected with
`USAGE` instead of being silently ignored.

## Output

Each file reports one line — successes on stdout, failures on stderr with the
reason — followed by a summary:

```
Found 24 audio files
...
Processed 23/24 files successfully
```

`batch <dir> analyze` prints the same per-file statistics `analyze` reports
and, with `--output-dir`, writes `<stem>_analysis.json` per file.

## Error handling

- Invalid headers or read errors fail that file only; the batch continues and
  lists every failure in the summary.
- Exit code is `0` when all files succeed, `INPUT` (3) when every failure was
  an input problem, `SECURITY` (4) if any failure was security-related, else
  `ERROR` (1).

## Limitations

- Execution stays inside one process — no distributed scheduling.
- Resource metrics (CPU and memory) are reported only when `psutil` is
  installed.

Refer to `docs/en/commands.md` for the per-operation output fields.
