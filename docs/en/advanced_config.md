# Advanced configuration


## Environment variables

The CLI reads the following variables when set:

- `CHAMELEON_PERFORMANCE_MODE` (`auto` | `fast` | `safe`). Controls chunk sizing presets. `fast` doubles the default chunk size (capped at 4 MiB) while `safe` halves it (floored at 4 KiB). `auto` keeps the default 64 KiB.
- `CHAMELEON_CHUNK_SIZE` (integer). Overrides the chunk size in bytes. Values outside 4096–4194304 fall back to the default 65536 automatically.
- `CHAMELEON_MAX_WORKERS` (integer). Limits worker count for batch operations; default is `4`.
- `CHAMELEON_BACKUP` (`true` | `false`). Enables backup creation before destructive operations; default is `true`.
- `CHAMELEON_TIMEOUT` (integer seconds). Caps the duration of long-running operations; default is `300`.
- `CHAMELEON_LOG_LEVEL` (`DEBUG`, `INFO`, etc.). Adjusts diagnostic verbosity; default is `INFO`.
- `NO_COLOR` (`1` disables colour output). Any other value keeps colour enabled.

Environment variables always override values loaded from JSON configuration files.

```bash
export CHAMELEON_PERFORMANCE_MODE=fast
export CHAMELEON_MAX_WORKERS=2
export NO_COLOR=1
```

## JSON configuration file

If present, the tool loads overrides from `~/.chameleon_audio_config.json` (and from `chameleon_audio_config.json` in the current directory). The file must contain a JSON object whose keys correspond to the entries below:

- `performance_mode`
- `max_workers`
- `chunk_size`
- `enable_colors`
- `log_level`
- `backup_enabled`
- `timeout_seconds`

Example:

```json
{
  "performance_mode": "fast",
  "max_workers": 3,
  "chunk_size": 32768,
  "enable_colors": false,
  "log_level": "DEBUG",
  "backup_enabled": true,
  "timeout_seconds": 180
}
```

Values in the JSON file override internal defaults. Environment variables always take precedence over the file.

## Inspecting configuration

Use the `config` command to view or persist the active settings:

```bash
# Show the merged configuration
chameleon config --show

# Export to JSON for review or editing
chameleon config --export --output my_config.json

# Import a previously saved JSON file
chameleon config --import --input my_config.json

# Reset to defaults
chameleon config --reset
```

The tool validates numeric ranges and boolean fields when reading either environment variables or JSON content. Invalid values fall back to the defaults shown above and a warning is printed to `stderr`.
