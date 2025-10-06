# Batch processing

## Overview

The `batch` command runs `analyze` for every WAV file found under a directory. The processing is sequential and uses only Python standard library modules.

## Usage

```
chameleon batch ./audio --skip-errors
chameleon batch ./audio --format json --output report.json
```

The command walks directories recursively. Files without a `.wav` extension are ignored.

## Options

- `--skip-errors`: Continue when a file fails. Failures are listed in the summary.
- `--format`: Choose `text` (default), `json`, or `csv` for the aggregated report.
- `--output`: Write the summary to a file path instead of standard output.
- `--max-files`: Limit how many files are processed (default is unlimited).

## Output

For text output, each analyzed file is followed by a summary similar to:

```
Processed files: 24
Successful: 23
Failed: 1
Elapsed: 00:01:05
```

JSON and CSV formats emit one record per file with the same fields that `analyze` reports.

## Error handling

- Files with invalid WAV headers or read errors are counted as failures.
- Without `--skip-errors`, the first failure stops the batch.
- The command never modifies, deletes, or renames input files.

## Limitations

- Only linear PCM WAV files are supported.
- Execution is single-threaded; there is no worker pool or distributed scheduling.
- Resource metrics (CPU and memory) are reported only when `psutil` is installed.

Refer to `docs/en/commands.md` for the detailed output fields produced by `analyze`.
