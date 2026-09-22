# Batch processing

## Overview

The `batch` command applies **one operation** to every audio file found
under a directory. It runs on a worker pool (`ThreadPoolExecutor`,
default `min(4, cpu_count)` workers) and writes a derived output file per
input — inputs are never modified, moved, or deleted.

```
chameleon batch <directory> <operation> [options]
```

`operation` is one of
`{analyze, normalize, mono, trim, denoise, restore, convert, effects}`.

```bash
chameleon batch ./audio normalize --output-dir out/
chameleon batch ./audio analyze --recursive
chameleon batch ./audio convert --sample-rate 44100 --bit-depth 16 --output-dir out/
```

## Options

- `--recursive`: descend into subdirectories. Without it only the top
  level of `directory` is scanned.
- `--output-dir <dir>`: write derived files to a directory instead of
  beside the inputs.
- `--dry-run`: report what would run without writing anything.
- `--format wav`: output format for `convert` (`wav` is the only
  converter that exists).
- `--quality`: normalize-only quality preset (`standard` or `high`;
  legacy `low`/`medium`/`lossless` are accepted and behave as
  `standard`).
- `--target-peak <float>`: normalize-only peak target in `(0.0, 1.0]`
  (default `0.95`).
- `--sample-rate`, `--bit-depth`: conversion targets for `convert`.
- `--effects <file>`: JSON effects chain for the `effects` operation.

Global flags go **before** the command:

```bash
chameleon --max-workers 4 --no-parallel batch ./audio normalize
```

- `--max-workers N`: cap the worker pool.
- `--no-parallel`: run files sequentially.

## Output files

File-writing operations emit `<stem><suffix>.wav` next to the input (or
inside `--output-dir`): `_normalized`, `_mono`, `_trimmed`, `_denoised`,
`_restored`, `_processed` (effects), and the `convert` variant from
`--format`/`--sample-rate`/`--bit-depth`. (`_mastered` belongs to
`process`, which has its own `master` operation; `batch` does not.)
`analyze` is the exception — it writes no audio file; its per-file result
carries the measured metadata into the summary JSON.

When a recursive gather pulls in identically-named files from different
subdirectories, each op writes `stem+suffix` into `--output-dir`, so the
later result overwrites the earlier — the CLI warns about the colliding
names while you can still pick a different output tree.

## File discovery

- `.wav` and `.wave` files are discovered (plus `mp3`, `flac`, `ogg`,
  `aiff`, `m4a` with the `[audio]` extra). Discovery matches on the
  lowercase extension; on a case-sensitive filesystem an uppercase
  `A.WAV` is skipped — keep file extensions lowercase.
- Every discovered file passes the deep-inspection gate before any work
  runs — a `.wav` whose bytes are not a WAV container is skipped and
  reported among the rejected files.
- Symlinked entries (file links, and `*.wav`-named directory links) are
  skipped: a link's target can live outside the scanned directory, so
  the batch only ever processes real files inside it.

## Error handling

- A bad directory or unsupported operation fails up front (one error,
  exit `INPUT`), not one failure per file.
- Per-file failures are recorded in the per-file results and the
  summary's error count; other files still complete. The run exits
  `ERROR` when any file failed.
- `--dry-run` reports the resolved output paths and performs no writes.

## Resource notes

- CPU and memory metrics appear in the run summary only when `psutil`
  is installed.
- `CHAMELEON_MAX_WORKERS`, `CHAMELEON_PARALLEL=0`, and
  `CHAMELEON_CHUNK_SIZE` tune the pool and the streaming block size; see
  `docs/en/advanced_config.md`.

Refer to `docs/en/commands.md` for the flag table and to
`docs/en/advanced_config.md` for the environment variables.
