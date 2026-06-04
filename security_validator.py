"""
Security validation primitives for Chameleon.

This is the single source of truth for the security-related types that the rest
of the codebase depends on:

    SecurityError          - exception raised on a rejected operation
    SecurityConfig         - validation policy (extensions, size limits, roots)
    SecurityValidator      - path / file validation
    SecureFileOperations   - hardened file open helpers

The validators are deliberately dependency-free (standard library only) so the
core CLI keeps working even when optional packages (numpy, fastapi, ...) are not
installed.

The public validation methods can be called either on the class (using a default
configuration derived from the environment) or on an instance (using that
instance's configuration), because callers use both styles:

    SecurityValidator.validate_path(path)          # class-level, main.py
    SecurityValidator(SecurityConfig()).validate_file_path(path)   # instance
"""

from __future__ import annotations

import os
import re
import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set


# Mirror the practical limits used elsewhere in the project.
DEFAULT_MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
MAX_PATH_LENGTH = 4096

# Patterns / characters that should never appear in a path we are willing to open.
_TRAVERSAL_PATTERNS = ('../', '..\\', '/..', '\\..', '%2e%2e', '%2f', '..%2f', '%2e%2e%2f')
_SUSPICIOUS_CHARS = ('<', '>', '|', '"', '?', '*', '\0')
_FILENAME_SCRUB = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]')


class SecurityError(Exception):
    """Raised when a path or file fails a security check."""


@dataclass
class SecurityConfig:
    """Validation policy.

    Attributes:
        allowed_extensions: if set, only these extensions are accepted
            (lower-case, leading dot, e.g. ``{'.wav'}``). ``None`` means any.
        max_file_size: reject files larger than this (bytes).
        trusted_roots: if non-empty, every validated path must live under one
            of these directories. Populated from ``CHAMELEON_TRUSTED_ROOTS`` /
            ``ALLOWED_DIRECTORIES`` when read from the environment.
        log_security_events: kept for API compatibility with callers that pass
            it; this module performs no logging of its own.
    """

    allowed_extensions: Optional[Set[str]] = None
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    trusted_roots: Set[str] = field(default_factory=set)
    log_security_events: bool = True

    @classmethod
    def from_environment(cls) -> "SecurityConfig":
        """Build a configuration from CHAMELEON_* environment variables."""
        roots: Set[str] = set()
        for var in ("CHAMELEON_TRUSTED_ROOTS", "ALLOWED_DIRECTORIES"):
            raw = os.getenv(var, "")
            for entry in raw.replace(";", ":" if os.sep == "/" else ";").split(os.pathsep):
                entry = entry.strip()
                if entry:
                    roots.add(str(Path(entry).expanduser()))

        max_size = DEFAULT_MAX_FILE_SIZE
        env_max = os.getenv("CHAMELEON_MAX_FILE_SIZE")
        if env_max:
            try:
                parsed = int(env_max)
                if parsed > 0:
                    max_size = parsed
            except (TypeError, ValueError):
                pass

        return cls(max_file_size=max_size, trusted_roots=roots)


class _hybridmethod:
    """Descriptor: bind to the instance when called on one, otherwise bind to a
    cached default instance so the method also works as a class method."""

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, owner):
        target = obj if obj is not None else owner._default()
        return self.func.__get__(target, type(target))


class SecurityValidator:
    """Validate paths and files against a :class:`SecurityConfig`."""

    _default_instance: Optional["SecurityValidator"] = None

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig.from_environment()

    @classmethod
    def _default(cls) -> "SecurityValidator":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    # -- internal helpers -------------------------------------------------

    def _is_path_shape_safe(self, path_str: str) -> bool:
        lowered = path_str.lower()
        if any(pat in lowered for pat in _TRAVERSAL_PATTERNS):
            return False
        if any(ch in path_str for ch in _SUSPICIOUS_CHARS):
            return False
        if len(path_str) > MAX_PATH_LENGTH:
            return False
        return True

    def _is_within_trusted_roots(self, resolved: Path) -> bool:
        if not self.config.trusted_roots:
            return True
        resolved_str = str(resolved)
        return any(resolved_str.startswith(root) for root in self.config.trusted_roots)

    def _extension_allowed(self, path: Path) -> bool:
        allowed = self.config.allowed_extensions
        if not allowed:
            return True
        return path.suffix.lower() in {ext.lower() for ext in allowed}

    # -- public API -------------------------------------------------------

    @_hybridmethod
    def validate_path(self, file_path) -> bool:
        """Return True if *file_path* is safe to access under this policy."""
        try:
            resolved = Path(file_path).resolve()
        except (OSError, ValueError, RuntimeError):
            return False
        if not self._is_path_shape_safe(str(resolved)):
            return False
        if not self._is_within_trusted_roots(resolved):
            return False
        if not self._extension_allowed(resolved):
            return False
        if resolved.exists() and resolved.is_file():
            try:
                if resolved.stat().st_size > self.config.max_file_size:
                    return False
            except OSError:
                return False
        return True

    @_hybridmethod
    def validate_file_size(self, file_path) -> bool:
        """Return True if the file exists and is within the size limit."""
        try:
            size = Path(file_path).stat().st_size
        except OSError:
            return False
        return size <= self.config.max_file_size

    @_hybridmethod
    def validate_directory(self, directory, require_exists: bool = False,
                           allow_create: bool = False) -> Path:
        """Validate (and optionally create) a directory.

        Returns the resolved :class:`~pathlib.Path` on success. Raises
        :class:`SecurityError` if the path is unsafe, missing when required, or
        cannot be created.
        """
        try:
            resolved = Path(directory).expanduser().resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            raise SecurityError(f"Invalid directory path: {directory}") from exc

        if not self._is_path_shape_safe(str(resolved)):
            raise SecurityError(f"Unsafe directory path: {directory}")
        if not self._is_within_trusted_roots(resolved):
            raise SecurityError(f"Directory outside trusted roots: {directory}")

        if resolved.exists():
            if not resolved.is_dir():
                raise SecurityError(f"Not a directory: {directory}")
        elif allow_create:
            try:
                resolved.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise SecurityError(f"Could not create directory: {directory}") from exc
        elif require_exists:
            raise SecurityError(f"Directory does not exist: {directory}")

        return resolved

    @_hybridmethod
    def validate_file_path(self, file_path, operation: str = "read") -> Path:
        """Validate a file path for *operation* ('read' or 'write').

        Returns the resolved path. Raises :class:`SecurityError` on rejection.
        """
        try:
            resolved = Path(file_path).expanduser().resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            raise SecurityError(f"Invalid file path: {file_path}") from exc

        if not self._is_path_shape_safe(str(resolved)):
            raise SecurityError(f"Unsafe file path: {file_path}")
        if not self._is_within_trusted_roots(resolved):
            raise SecurityError(f"File outside trusted roots: {file_path}")
        if not self._extension_allowed(resolved):
            raise SecurityError(f"Extension not allowed: {resolved.suffix}")

        if operation == "read":
            if not resolved.exists() or not resolved.is_file():
                raise SecurityError(f"File not found: {file_path}")
            try:
                if resolved.stat().st_size > self.config.max_file_size:
                    raise SecurityError(f"File too large: {file_path}")
            except OSError as exc:
                raise SecurityError(f"Cannot stat file: {file_path}") from exc

        return resolved

    @_hybridmethod
    def safe_open_file(self, file_path, mode: str = "rb"):
        """Open *file_path* after validation. Returns the handle, or ``None``
        if the path is unsafe (callers treat ``None`` as failure)."""
        if not self.validate_path(file_path):
            return None
        try:
            return open(file_path, mode)
        except OSError:
            return None

    @_hybridmethod
    def validate_audio_content(self, file_path) -> bool:
        """Lightweight content check: accept recognised audio headers and reject
        files whose header looks like an embedded script/markup payload."""
        try:
            with open(file_path, "rb") as fh:
                header = fh.read(12)
        except OSError:
            return False
        if header.startswith(b"RIFF") and b"WAVE" in header:
            return True
        # Reject obvious script/markup smuggled into an "audio" file.
        if b"<?" in header or b"<!" in header or b"<script" in header.lower():
            return False
        # Other audio container signatures we still allow through.
        if header[:4] in (b"fLaC", b"OggS", b"ID3\x03", b"ID3\x04") or header[:3] == b"ID3":
            return True
        # Unknown but not obviously hostile: allow (the WAV parser will reject
        # anything it cannot actually read).
        return True

    @_hybridmethod
    def sanitize_filename(self, filename: str) -> str:
        """Strip dangerous characters from a filename component."""
        sanitized = _FILENAME_SCRUB.sub("_", filename)
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:255 - len(ext)] + ext
        return sanitized or "untitled"

    @_hybridmethod
    def resolve_unique_paths(self, paths: Iterable) -> List[Path]:
        """Resolve *paths* and raise ``ValueError`` if two map to the same target."""
        resolved: List[Path] = []
        seen = {}
        for raw in paths:
            try:
                target = Path(raw).expanduser().resolve()
            except (OSError, ValueError, RuntimeError) as exc:
                raise ValueError(f"Invalid path in paths: {raw}") from exc
            if target in seen:
                raise ValueError(
                    f"Duplicate target in paths: {raw} resolves to {seen[target]}"
                )
            seen[target] = raw
            resolved.append(target)
        return resolved


class SecureFileOperations:
    """File open helpers bound to a :class:`SecurityValidator`."""

    def __init__(self, validator: Optional[SecurityValidator] = None):
        self.validator = validator or SecurityValidator()

    @contextlib.contextmanager
    def secure_open(self, path, mode: str = "rb", *, encoding: Optional[str] = None):
        """Context manager that validates *path* and opens it.

        Write/append modes create the file with restrictive 0o600 permissions and
        refuse to follow symlinks (mirrors ``core.open_secure``).
        """
        writing = "w" in mode or "a" in mode
        operation = "write" if writing else "read"
        self.validator.validate_file_path(path, operation=operation)

        if writing:
            flags = os.O_WRONLY
            flags |= os.O_CREAT | (os.O_APPEND if "a" in mode else os.O_TRUNC)
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(os.fspath(path), flags, 0o600)
            handle = os.fdopen(fd, mode, encoding=encoding)
        else:
            handle = open(path, mode, encoding=encoding)

        try:
            yield handle
        finally:
            handle.close()


__all__ = [
    "SecurityError",
    "SecurityConfig",
    "SecurityValidator",
    "SecureFileOperations",
]
