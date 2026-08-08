# Advanced configuration

Chameleon is configured entirely through **environment variables** and
command-line flags. There is no configuration file and no `config`
sub-command — every variable below was verified against the code that reads it.

## Environment variables

| Variable | Read by | Effect |
|----------|---------|--------|
| `CHAMELEON_PERFORMANCE_MODE` | `core.py` | `auto` (default), `fast`, or `safe`. `fast` doubles the default chunk size (capped at 4 MiB); `safe` halves it (floored at 4 KiB); `auto` keeps the 64 KiB default. |
| `CHAMELEON_CHUNK_SIZE` | `core.py` | Chunk size in bytes. Values outside 4096–4194304 fall back to the 65536 default. Overrides the performance-mode preset. |
| `CHAMELEON_TIMEOUT` | `core.py` | Caps the duration of long-running batch operations, in seconds. |
| `CHAMELEON_STATE_DIR` | `core.py` | Directory for batch state files. Defaults to a per-user location. |
| `CHAMELEON_MAX_WORKERS` | `main.py` | Worker count for batch operations. Non-numeric values are ignored. |
| `CHAMELEON_PARALLEL` | `main.py` | Set to `0`, `false`, `off`, or `no` to disable parallel execution. Any other value enables it. |
| `CHAMELEON_LOG_DIR` | `main.py` | Log directory. Defaults to `~/.chameleon/logs`, created with `0700` permissions on POSIX systems. |

```bash
export CHAMELEON_PERFORMANCE_MODE=fast
export CHAMELEON_MAX_WORKERS=2
chameleon batch ./audio normalize --output-dir out/
```

## Command-line equivalents

Two of these have global flags, which take effect for the single invocation
and override the environment:

```bash
chameleon --max-workers 4 batch ./audio normalize --output-dir out/
chameleon --no-parallel  batch ./audio normalize --output-dir out/
```

## Validation behaviour

Values are validated when read. A malformed integer, or one outside the
accepted range, falls back to the documented default rather than raising —
so a typo degrades performance settings, it does not break the run.

## What is deliberately absent

- **No configuration file.** Nothing in `main.py` or `core.py` reads a JSON,
  YAML, or INI config. Configuration is environment variables plus flags.
- **No `config` sub-command.** Use `env` / `export` to inspect and set values.

`personal_config.py` maintains its own separate JSON file for its personal-use
helper flows, but it is a standalone script and does not configure the CLI.
