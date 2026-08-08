# Performance profile

## Overview

Chameleon Audio Tool is designed for lightweight, single-process workloads. The CLI performs operations sequentially and relies on the Python standard library. This page explains the practical performance characteristics of v1.0.0 and suggests simple ways to measure throughput on your own system.

## Expected behaviour

- The tool streams WAV data in fixed-size chunks (default `65536` bytes). Adjust `CHAMELEON_CHUNK_SIZE` to experiment with trade-offs between memory usage and throughput.
- Normalisation, trimming, and conversion read and write data once; they are limited mainly by disk speed.
- `batch` runs `analyze` on each file in series. Total time scales linearly with the number of files.

## Measuring performance

Use the standard `time` utility (or PowerShell `Measure-Command`) to estimate elapsed time for your workload:

```bash
time chameleon process input.wav --normalize --target-peak 0.90 --output-dir out/
time chameleon batch ./audio normalize --output-dir out/
```

Record the wall-clock time and compare runs after adjusting environment variables or hardware. For consistent numbers, warm caches by running the command once before measuring.

## Profiling tips

- Install `psutil` to include CPU and memory metrics in command summaries.
- Toggle `CHAMELEON_PERFORMANCE_MODE` between `auto`, `fast`, and `safe` to compare heuristics.
- When working with large directories, sample a smaller subset of files to estimate the total runtime before launching a full scan.

## Known limits

- Processing is sequential; the tool does not spawn worker pools or distributed schedulers.
- Only linear PCM WAV files are supported, and audio is not resampled.
- Memory usage scales with `CHAMELEON_CHUNK_SIZE`; extremely small chunks increase CPU overhead while very large chunks raise peak memory.

## Manual benchmarking checklist

- Warm up the CLI by running the command once before timing it.
- Use identical input data, configuration settings, and system conditions for each measurement.
- Capture command output and timings in a log file to aid later comparisons.
- Experiment with `CHAMELEON_CHUNK_SIZE` values such as `32768`, `65536`, and `131072` to find a suitable balance.
- Note hardware, operating system, Python version, and configuration whenever you record or share results.

For additional configuration options, see `docs/en/advanced_config.md`.
