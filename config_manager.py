#!/usr/bin/env python3
"""Configuration management utilities for the Chameleon Audio Tool."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable

LOGGER = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KiB
MIN_CHUNK_SIZE = 4 * 1024  # 4 KiB
MAX_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB
MIN_TIMEOUT_SECONDS = 5
MAX_TIMEOUT_SECONDS = 3_600
MAX_WORKERS_UPPER_BOUND = 64

CONFIG_DEFAULTS: Dict[str, Any] = {
    "performance_mode": "auto",
    "max_workers": 4,
    "chunk_size": DEFAULT_CHUNK_SIZE,
    "enable_colors": True,
    "log_level": "INFO",
    "backup_enabled": True,
    "timeout_seconds": 300,
}

CONFIG_SCOPES = {
    "user": Path.home() / ".chameleon_audio_config.json",
    "project": Path.cwd() / "chameleon_audio_config.json",
}

ALLOWED_PERFORMANCE_MODES = {"auto", "fast", "safe"}
ALLOWED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ValueError("Unable to interpret boolean value")


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid integer value")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid integer value") from exc


def _coerce_setting(name: str, value: Any) -> Any:
    if name == "performance_mode":
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ALLOWED_PERFORMANCE_MODES:
                return lowered
        raise ValueError("performance_mode must be one of: auto, fast, safe")

    if name == "max_workers":
        numeric = _coerce_int(value)
        if numeric < 1 or numeric > MAX_WORKERS_UPPER_BOUND:
            raise ValueError("max_workers must be between 1 and 64")
        return numeric

    if name == "chunk_size":
        numeric = _coerce_int(value)
        if numeric < MIN_CHUNK_SIZE or numeric > MAX_CHUNK_SIZE:
            raise ValueError("chunk_size must be between 4096 and 4194304")
        return numeric

    if name == "enable_colors":
        return _coerce_bool(value)

    if name == "log_level":
        if isinstance(value, str):
            upper = value.strip().upper()
            if upper in ALLOWED_LOG_LEVELS:
                return upper
        raise ValueError("log_level must be a valid logging level name")

    if name == "backup_enabled":
        return _coerce_bool(value)

    if name == "timeout_seconds":
        numeric = _coerce_int(value)
        if numeric < MIN_TIMEOUT_SECONDS or numeric > MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds must be between 5 and 3600")
        return numeric

    raise KeyError(f"Unknown configuration key: {name}")


def _read_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        LOGGER.warning("Failed to load configuration file %s: %s", path, error)
        return {}

    if not isinstance(payload, dict):
        LOGGER.warning("Configuration file %s must contain a JSON object", path)
        return {}

    validated: Dict[str, Any] = {}
    for key, value in payload.items():
        if key not in CONFIG_DEFAULTS:
            LOGGER.debug("Ignoring unknown configuration key '%s' in %s", key, path)
            continue
        try:
            validated[key] = _coerce_setting(key, value)
        except (ValueError, KeyError) as error:
            LOGGER.warning("Invalid value for '%s' in %s: %s", key, path, error)
    return validated


def _apply_environment_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}

    env_mode = os.getenv("CHAMELEON_PERFORMANCE_MODE")
    if env_mode:
        try:
            overrides["performance_mode"] = _coerce_setting("performance_mode", env_mode)
        except ValueError:
            LOGGER.warning("Ignoring invalid CHAMELEON_PERFORMANCE_MODE: %s", env_mode)

    env_chunk = os.getenv("CHAMELEON_CHUNK_SIZE")
    if env_chunk:
        try:
            overrides["chunk_size"] = _coerce_setting("chunk_size", env_chunk)
        except ValueError:
            LOGGER.warning("Ignoring invalid CHAMELEON_CHUNK_SIZE: %s", env_chunk)

    env_workers = os.getenv("CHAMELEON_MAX_WORKERS")
    if env_workers:
        try:
            overrides["max_workers"] = _coerce_setting("max_workers", env_workers)
        except ValueError:
            LOGGER.warning("Ignoring invalid CHAMELEON_MAX_WORKERS: %s", env_workers)

    env_timeout = os.getenv("CHAMELEON_TIMEOUT")
    if env_timeout:
        try:
            overrides["timeout_seconds"] = _coerce_setting("timeout_seconds", env_timeout)
        except ValueError:
            LOGGER.warning("Ignoring invalid CHAMELEON_TIMEOUT: %s", env_timeout)

    env_backup = os.getenv("CHAMELEON_BACKUP")
    if env_backup:
        try:
            overrides["backup_enabled"] = _coerce_setting("backup_enabled", env_backup)
        except ValueError:
            LOGGER.warning("Ignoring invalid CHAMELEON_BACKUP: %s", env_backup)

    log_level = os.getenv("CHAMELEON_LOG_LEVEL")
    if log_level:
        try:
            overrides["log_level"] = _coerce_setting("log_level", log_level)
        except ValueError:
            LOGGER.warning("Ignoring invalid CHAMELEON_LOG_LEVEL: %s", log_level)

    if os.getenv("NO_COLOR") == "1":
        overrides["enable_colors"] = False

    if overrides:
        new_config = config.copy()
        new_config.update(overrides)
        return new_config
    return config


def _resolve_scope(scope: str) -> str:
    if scope not in CONFIG_SCOPES:
        raise ValueError(f"Unknown configuration scope '{scope}'")
    return scope


def _write_config_file(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = {key: data.get(key, CONFIG_DEFAULTS[key]) for key in CONFIG_DEFAULTS}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(serialized, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _delete_file_if_exists(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError as error:
        LOGGER.warning("Unable to remove configuration file %s: %s", path, error)


def load_config() -> Dict[str, Any]:
    """Load configuration from defaults, user file, and project file."""
    config = CONFIG_DEFAULTS.copy()
    # User-level overrides
    config.update(_read_config_file(CONFIG_SCOPES["user"]))
    # Project-level overrides
    config.update(_read_config_file(CONFIG_SCOPES["project"]))
    return config


def get_runtime_config() -> Dict[str, Any]:
    """Return configuration including environment overrides."""
    base = load_config()
    return _apply_environment_overrides(base)


def get_setting(name: str, default: Any = None) -> Any:
    if name not in CONFIG_DEFAULTS:
        raise KeyError(f"Unknown configuration setting '{name}'")
    return get_runtime_config().get(name, default if default is not None else CONFIG_DEFAULTS[name])


def export_config(target_path: Path, *, include_environment: bool = False) -> None:
    """Export configuration to a JSON file."""
    if include_environment:
        config = get_runtime_config()
    else:
        config = load_config()
    _write_config_file(target_path, config)


def import_config(source_path: Path, *, scope: str = "user") -> None:
    """Import configuration overrides from JSON file into the selected scope."""
    scope = _resolve_scope(scope)
    payload = _read_config_file(source_path)
    if not payload:
        LOGGER.info("No valid settings found in %s; nothing imported", source_path)
        return
    target_path = CONFIG_SCOPES[scope]
    merged = load_config()
    merged.update(payload)
    _write_config_file(target_path, merged)


def reset_config(scope: str = "user") -> None:
    """Remove configuration file for the selected scope."""
    scope = _resolve_scope(scope)
    _delete_file_if_exists(CONFIG_SCOPES[scope])


def refresh() -> None:
    """Reset any cached configuration state."""
    # Currently a placeholder for future caching mechanisms.
    pass


def iter_config_sources() -> Iterable[Path]:
    """Return all known configuration file locations."""
    return CONFIG_SCOPES.values()
