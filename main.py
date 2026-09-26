#!/usr/bin/env python3
"""
Chameleon Audio Processing System - Main Entry Point
CLI for WAV analysis, normalization, batch processing, MIDI extraction, and
loudness metering, with optional real-time streaming and a mastering chain
when the [audio] extra is installed. No ML/AI features (see CHARTER.md §4).
"""

from __future__ import annotations

import os
import sys
import time
import json
import struct
import argparse
import asyncio
import math
import re
import multiprocessing as mp
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, asdict, is_dataclass
from concurrent.futures import ThreadPoolExecutor
import logging
import signal as _signal
import warnings
from collections import Counter
from logging.handlers import RotatingFileHandler

import core
from core import open_secure, SecurityValidator
from plugin_system import PluginManager, PluginConfig, SecurityError

if TYPE_CHECKING:
    import numpy as np
else:
    np = None


class ExitCode(IntEnum):
    """Process exit codes for the CLI.

    A small, conventional table (not the full BSD ``sysexits.h``) so that
    scripts wrapping this tool can distinguish *why* a run failed without us
    taking on a large contract. ``IntEnum`` members are plain ints, so they can
    be returned or passed to ``sys.exit`` directly.

      0  OK           success
      1  ERROR        a processing step failed, or an unexpected error
      2  USAGE        the command line was wrong / incomplete (argparse also
                      uses 2 for its own parse errors)
      3  INPUT        a supplied path failed pre-flight input validation
      4  SECURITY     a path or file was rejected by the security policy
      130 INTERRUPTED interrupted by the user (Ctrl-C); 128 + SIGINT, per the
                      shell convention
    """

    OK = 0
    ERROR = 1
    USAGE = 2
    INPUT = 3
    SECURITY = 4
    INTERRUPTED = 130


_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
_WILDCARD_PATTERN = re.compile(r"[\*\?]")


def _json_export_default(obj):
    """``--export`` JSON serializer: dataclasses become real objects,
    numpy scalars become plain numbers, everything else falls back to str."""
    if is_dataclass(obj) and not isinstance(obj, type):
        d = asdict(obj)
        # Exported defaults read as measurements: [0.0, 0.0] Hz on an
        # install that never computes frequency_range, or 0.0 BPM for
        # "not estimable". The stdlib path already reports null for
        # unmeasured fields -- make the numpy path say the same.
        if d.get("frequency_range") == (0.0, 0.0):
            d["frequency_range"] = None
        if d.get("tempo") == 0.0:
            d["tempo"] = None
        return d
    item = getattr(obj, 'item', None)
    if callable(item):  # numpy scalar -> Python scalar
        return item()
    return str(obj)


def _sanitize_cli_input(value: str, field_name: str) -> str:
    """Ensure CLI-provided strings do not contain control characters or wildcards."""

    if value is None:
        raise ValueError(f"{field_name} is required")

    sanitized = value.strip()

    if not sanitized:
        raise ValueError(f"{field_name} cannot be empty")

    if _CONTROL_CHAR_PATTERN.search(sanitized):
        raise ValueError(f"{field_name} contains control characters")

    if _WILDCARD_PATTERN.search(sanitized):
        raise ValueError(f"{field_name} contains unsupported wildcard characters")

    return sanitized


def _sanitize_optional_input(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    return _sanitize_cli_input(value, field_name)


def _assert_unique_paths(paths: List[str], field_name: str) -> None:
    """Ensure no duplicate filesystem targets appear in CLI arguments."""

    try:
        SecurityValidator.resolve_unique_paths(paths)
    except ValueError as exc:
        message = str(exc).replace("paths", field_name)
        raise ValueError(message) from exc


def _preflight_output_dir(output_dir: Optional[str]) -> Optional[str]:
    """An output dir that is actually a file -- or whose parent chain hits
    one -- only fails later, inside per-file processing, as a raw OSError
    classified ERROR(1). The path is user input: refuse it as INPUT(3)."""
    if output_dir is None:
        return None
    probe = Path(output_dir)
    while not probe.exists():
        probe = probe.parent
        if str(probe) == probe.anchor:
            break
    if probe.exists() and not probe.is_dir():
        raise ValueError(f"output_dir is not a directory: {output_dir}")
    if probe.exists() and not os.access(probe, os.W_OK | os.X_OK):
        raise ValueError(f"output_dir is not writable: {output_dir}")
    return output_dir


class UnsupportedOperationError(ValueError):
    """The operation exists, but this install cannot run it (a required
    extra is missing). A ValueError subclass so existing callers/tests
    still see a clear message, but classified apart from bad input:
    INPUT(3) means a supplied path failed validation, and the input file
    is not what is wrong here."""


def _error_kind(exc: Exception) -> str:
    """Classify a per-file failure as an input problem or an internal one.

    ValueError/FileNotFoundError are this codebase's convention for bad
    user-supplied input ("Could not parse WAV file", unreadable headers,
    out-of-domain values) -- those belong to INPUT(3). Everything else
    (OSError on write, unexpected exceptions) is an internal failure.
    """
    if isinstance(exc, UnsupportedOperationError):
        return "internal"
    # PermissionError on a user-supplied output path is an input problem
    # (the destination can't be written); other OSErrors like ENOSPC are
    # genuinely environmental and stay internal.
    if isinstance(exc, (ValueError, FileNotFoundError, PermissionError)):
        return "input"
    return "internal"


def _load_effects(effects_path: str) -> Dict[str, Any]:
    """Load and validate an effects JSON file.

    Raises ValueError on a malformed file -- every caller converts it to
    ExitCode.INPUT, because a bad effects file is a user-input problem, not
    an internal failure. An unvalidated shape used to fail deeper: a
    non-object top level silently matched no "in effects" checks and wrote
    unchanged audio under a "Processed" message, and a non-object per-effect
    value crashed inside apply_effects with 'str' object has no attribute
    'get'.
    """

    try:
        with open(effects_path) as f:
            effects = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Effects file '{effects_path}' is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Cannot read effects file '{effects_path}': {exc}") from exc

    if not isinstance(effects, dict):
        raise ValueError(
            f"Effects file '{effects_path}' must contain a JSON object mapping "
            f"effect names to parameter objects, got {type(effects).__name__}"
        )

    known = set(AudioProcessor._EFFECT_REQUIREMENTS)

    # Parameter keys apply_effects actually reads per effect. An unknown
    # key (a typo like 'treshold', or 'damping' which nothing consumes)
    # would otherwise be silently ignored.
    known_params = {
        "eq": {"frequency", "gain", "q"},
        "reverb": {"room_size", "wet"},
        "compression": {"threshold", "ratio", "attack", "release", "knee",
                        "makeup_gain"},
    }

    for name, params in effects.items():
        if name == "eq":
            # apply_effects iterates eq as a list of band dicts, each with a
            # numeric 'frequency' and 'gain' (optional 'q').
            if not isinstance(params, list):
                raise ValueError(
                    f"Effect 'eq' must map to a list of band objects, got {type(params).__name__}"
                )
            for i, band in enumerate(params):
                if not isinstance(band, dict):
                    raise ValueError(
                        f"Effect 'eq' band #{i} must be a parameter object, got {type(band).__name__}"
                    )
                for key in ("frequency", "gain"):
                    if (key not in band
                            or not isinstance(band[key], (int, float))
                            or not math.isfinite(band[key])):
                        raise ValueError(
                            f"Effect 'eq' band #{i} needs a finite numeric '{key}'"
                        )
                # A band at/below DC is meaningless; apply_effects used to
                # skip it silently (a +99 dB boost at -100 Hz produced
                # byte-identical output under "Processed").
                if band["frequency"] <= 0:
                    raise ValueError(
                        f"Effect 'eq' band #{i} frequency must be positive, "
                        f"got {band['frequency']}"
                    )
                if "q" in band and (not isinstance(band["q"], (int, float))
                                    or not math.isfinite(band["q"])
                                    or band["q"] <= 0):
                    raise ValueError(
                        f"Effect 'eq' band #{i} 'q' must be a positive number"
                    )
                for key in band:
                    if key not in known_params["eq"]:
                        print(f"Warning: unknown eq parameter '{key}' in band "
                              f"#{i} will be ignored", file=sys.stderr)
        elif not isinstance(params, dict):
            raise ValueError(
                f"Effect '{name}' must map to a parameter object, got {type(params).__name__}"
            )
        else:
            for key in params:
                if name in known_params and key not in known_params[name]:
                    print(f"Warning: unknown parameter '{key}' for effect "
                          f"'{name}' will be ignored", file=sys.stderr)
            if name == "reverb":
                for key in ("room_size", "wet"):
                    if key in params and (not isinstance(params[key], (int, float))
                                          or not math.isfinite(params[key])):
                        raise ValueError(
                            f"Effect 'reverb' '{key}' must be a finite number, "
                            f"got {params[key]!r}"
                        )
                if "room_size" in params and params["room_size"] <= 0:
                    raise ValueError("Effect 'reverb' 'room_size' must be positive")
                if "wet" in params and not 0.0 <= params["wet"] <= 1.0:
                    raise ValueError(
                        f"Effect 'reverb' 'wet' must be within [0, 1], got "
                        f"{params['wet']}"
                    )
            elif name == "compression":
                # Type-check before any domain comparison: a string here used
                # to reach `<=`/`<` and leak a TypeError traceback instead of
                # a validation error.
                for key in ("threshold", "ratio", "attack", "release",
                            "knee", "makeup_gain"):
                    if key in params and (not isinstance(params[key], (int, float))
                                          or not math.isfinite(params[key])):
                        raise ValueError(
                            f"Effect 'compression' '{key}' must be a finite "
                            f"number, got {params[key]!r}"
                        )
                ratio = params.get("ratio")
                if ratio is not None and ratio < 1:
                    raise ValueError(
                        f"Effect 'compression' 'ratio' must be >= 1 "
                        f"(below 1 is expansion, not compression), got {ratio}"
                    )
                for key in ("attack", "release", "knee"):
                    if key in params and params[key] < 0:
                        raise ValueError(
                            f"Effect 'compression' '{key}' must be >= 0, "
                            f"got {params[key]}"
                        )
        if name not in known:
            print(f"Warning: unknown effect '{name}' in effects file will be ignored "
                  f"(known effects: {', '.join(sorted(known))})", file=sys.stderr)

    return effects


def _sanitize_plugin_directory(directory: str) -> Path:
    """Validate and normalize plugin directories for secure use."""

    directory = _sanitize_cli_input(directory, "plugin directory")

    expanded = Path(directory).expanduser()

    try:
        resolved = expanded.resolve(strict=False)
    except Exception as exc:
        raise ValueError(f"Failed to resolve plugin directory '{directory}': {exc}") from exc

    if not resolved.is_absolute():
        raise ValueError(f"Plugin directory must be absolute: {directory}")

    if any(part in {"..", ""} for part in resolved.parts):
        raise ValueError(f"Plugin directory contains unsafe components: {directory}")

    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"Plugin directory is not a directory: {directory}")

    return resolved


def _initialize_plugin_manager(directories: Optional[List[str]]) -> Tuple[PluginManager, List[Path]]:
    """Create and initialize a plugin manager with sanitized directories."""

    config = PluginConfig()

    candidate_directories = directories or config.plugin_directories
    sanitized: List[Path] = []

    for directory in candidate_directories:
        sanitized_path = _sanitize_plugin_directory(directory)
        sanitized.append(sanitized_path)

    config.plugin_directories = [str(path) for path in sanitized]

    manager = PluginManager(config)
    manager.initialize()

    return manager, sanitized


def _serialize_result(value: Any) -> Any:
    """Serialize result payloads (including dataclasses and Paths) into JSON-friendly forms."""

    if isinstance(value, AudioMetadata):
        return asdict(value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {key: _serialize_result(val) for key, val in value.items()}

    if isinstance(value, (list, tuple)):
        return [_serialize_result(item) for item in value]

    return value

# Import audio libraries with graceful fallback
try:
    if not TYPE_CHECKING:
        import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    if not TYPE_CHECKING:
        np = None

# Missing optional dependencies are the NORMAL state of the honest,
# stdlib-only default install (CHARTER §3) — so record them at debug level
# instead of spamming UserWarnings on every invocation. Features that
# actually need a backend raise a clear, actionable error at the point of
# use (e.g. "requires numpy. Install it with: pip install -e .[audio]").
_optional_dep_logger = logging.getLogger("chameleon.optional_deps")
if not HAS_NUMPY:
    _optional_dep_logger.debug("NumPy not installed. Some features will be limited.")

try:
    import scipy.signal as signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    _optional_dep_logger.debug("SciPy not installed. Advanced processing features disabled.")

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    _optional_dep_logger.debug("Librosa not installed. ML features will be limited.")

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    _optional_dep_logger.debug("SoundFile not installed. Audio I/O features limited.")

# Import MIDI analysis module
try:
    from midi_analysis import MIDIAnalyzer, MIDIComposer, MIDIConfig, MIDINote
    HAS_MIDI = True
except ImportError:
    HAS_MIDI = False
    _optional_dep_logger.debug("MIDI analysis module not available.")

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    _optional_dep_logger.debug("PyAudio not installed. Real-time audio disabled.")

# Deep file inspection (stdlib-only). Used to validate that a file claiming a
# .wav extension is actually a WAV container before it enters the batch
# pipeline. Guarded like the other optional imports so a trimmed checkout still
# degrades gracefully (CHARTER.md §6.2) — the batch filter simply skips the
# extra format check when it is unavailable.
try:
    from advanced_validation import DeepFileInspector
    HAS_DEEP_INSPECTOR = True
except ImportError:
    HAS_DEEP_INSPECTOR = False

# Terminal UX helpers (stdlib-only). Guarded for the same reason as the other
# optional imports even though this one has no non-stdlib dependency — a
# trimmed checkout should still run the CLI without progress bars/colour.
try:
    from ux_improvements import ProgressBar, ColorText
    HAS_UX_IMPROVEMENTS = True
except ImportError:
    HAS_UX_IMPROVEMENTS = False

# Deterministic spectral analysis (stdlib-only; uses numpy.fft when available,
# a pure-Python DFT fallback otherwise). Guarded like the other optional
# imports so a trimmed checkout still runs the CLI without --spectrum.
try:
    import spectral_utils
    HAS_SPECTRAL_UTILS = True
except ImportError:
    HAS_SPECTRAL_UTILS = False

# Full mastering chain (EQ/compressor/limiter/loudness). Requires numpy —
# mastering_chain.py imports it unconditionally, so this import simply fails
# under the stdlib-only default install, same as HAS_LIBROSA/HAS_SOUNDFILE
# above; scipy is optional *within* mastering_chain.py itself (it degrades
# each processor individually when scipy is absent).
try:
    import mastering_chain
    from mastering_chain import MasteringChain, create_mastering_preset
    HAS_MASTERING_CHAIN = True
except ImportError:
    HAS_MASTERING_CHAIN = False

# Pure-Python, standard-library-only ITU-R BS.1770 K-weighting + gated
# integrated loudness. mastering_chain.LoudnessMeter now reuses the same
# coefficients (via scipy.signal.lfilter) when scipy is available, falling
# back to a rough RMS approximation otherwise; this module has no
# third-party dependency at all. Guarded like the other optional imports so
# a trimmed checkout still runs the CLI without --loudness.
try:
    import bs1770_loudness
    HAS_BS1770_LOUDNESS = True
except ImportError:
    HAS_BS1770_LOUDNESS = False

# Core constants
VERSION = "1.1.0"
MAX_FILE_SIZE = 500 * 1024 * 1024  # Align with core constraints (500MB)
CHUNK_SIZE = 8192
DEFAULT_SAMPLE_RATE = 44100
# Sample bound for `analyze --loudness`: large enough to be a meaningful
# integrated-loudness window, small enough to keep memory/time predictable
# for a pure-Python filter + block loop regardless of file length (same
# bounded-analysis principle as core.get_samples_for_analysis's own default).
LOUDNESS_MAX_SAMPLES = 15 * 48000
# Upper bound for user-supplied target sample rates. 768kHz (DXD) is the
# practical ceiling for PCM audio; beyond it the resampler's output buffer
# is a memory/disk bomb (1s at 1e9Hz ≈ a 2GB WAV that "succeeded").
MAX_TARGET_SAMPLE_RATE = 768_000

# Operations the dependency-free core can perform on a file, mapping to the
# output suffix and the core call. `analyze` is handled separately because it
# returns metadata rather than writing a file.
#
# core.py has always implemented mono and trim -- they are in
# ALLOWED_BATCH_OPERATIONS and are covered by core's own tests -- but the CLI
# exposed neither, so the only way to reach them was the Python API. That put
# two of the four dependency-free operations out of users' reach while the
# product's whole claim is its dependency-free core.
_STDLIB_FILE_OPERATIONS = {
    "normalize": ("_normalized.wav",
                  lambda src, dst, kw: core.normalize(src, dst, kw.get("target_peak", 0.95))),
    "mono": ("_mono.wav",
             lambda src, dst, kw: core.to_mono(src, dst)),
    "trim": ("_trimmed.wav",
             lambda src, dst, kw: core.trim_silence(src, dst, kw.get("threshold", 0.01))),
}
# WAV is always supported through the standard-library loader. Extra formats are
# advertised only when a backend that can actually decode them is installed, so the
# default dependency-free install stays honestly WAV-only (see CHARTER.md §3) while the
# `[audio]` extra turns mp3/flac/ogg into a real, working input path instead of a gate
# that rejects them at load time even though load_audio (below) is wired for them.
SUPPORTED_FORMATS = {'.wav', '.wave'}
if HAS_LIBROSA or HAS_SOUNDFILE:
    # soundfile/libsndfile and librosa both decode these natively.
    SUPPORTED_FORMATS |= {'.flac', '.ogg', '.oga', '.aiff', '.aif'}
if HAS_LIBROSA:
    # librosa reaches mp3/m4a via audioread/ffmpeg; soundfile alone may not.
    SUPPORTED_FORMATS |= {'.mp3', '.m4a'}

@dataclass
class AudioMetadata:
    """Enhanced audio metadata with comprehensive information"""
    duration: float
    sample_rate: int
    channels: int
    bit_depth: int
    size_bytes: int
    format: str
    codec: Optional[str] = None
    # None = the level pass failed or never ran; 0.0 = measured silence.
    peak_level: Optional[float] = None
    rms_level: Optional[float] = None
    dynamic_range: Optional[float] = None
    frequency_range: Tuple[float, float] = (0.0, 0.0)
    tempo: Optional[float] = None
    key: Optional[str] = None
    loudness_lufs: Optional[float] = None
    true_peak_dbtp: Optional[float] = None
    max_momentary_lufs: Optional[float] = None
    max_short_term_lufs: Optional[float] = None
    loudness_range_lu: Optional[float] = None
    spectral_centroid: Optional[float] = None
    zero_crossing_rate: Optional[float] = None

@dataclass
class ProcessingConfig:
    """Configuration for audio processing operations"""
    sample_rate: int = 44100
    channels: int = 2
    bit_depth: int = 16
    normalize: bool = True
    target_peak: float = 0.95
    apply_dither: bool = False
    parallel: bool = True
    max_workers: int = max(1, min(4, mp.cpu_count() or 1))
    cache_enabled: bool = True
    quality: str = "high"  # standard | high -- only 'high' adds a soft clipper

    @classmethod
    def from_environment(cls) -> "ProcessingConfig":
        """Create configuration using environment overrides when present."""

        config = cls()

        env_max_workers = os.getenv("CHAMELEON_MAX_WORKERS")
        if env_max_workers:
            try:
                parsed = int(env_max_workers)
            except (TypeError, ValueError):
                parsed = config.max_workers
                warnings.warn(
                    f"Ignoring non-numeric CHAMELEON_MAX_WORKERS="
                    f"{env_max_workers!r}; using default {parsed}"
                )
            else:
                if parsed <= 0:
                    warnings.warn(
                        f"Ignoring non-positive CHAMELEON_MAX_WORKERS="
                        f"{parsed}; using default {config.max_workers}"
                    )
                    parsed = config.max_workers
            config.max_workers = parsed

        env_parallel = os.getenv("CHAMELEON_PARALLEL")
        if env_parallel is not None:
            normalized = env_parallel.strip().lower()
            if normalized in {"0", "false", "off", "no"}:
                config.parallel = False
            elif normalized in {"1", "true", "on", "yes"}:
                config.parallel = True
            else:
                warnings.warn(
                    f"Ignoring invalid CHAMELEON_PARALLEL={env_parallel!r}; "
                    f"expected one of 1/0/true/false/on/off/yes/no"
                )

        return config

class AudioProcessor:
    """Audio processor: analysis, normalization, batch processing, and
    (optionally, via the [audio] extra) real-time streaming and a mastering
    chain. No ML/AI features (see CHARTER.md §4)."""

    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        self.max_workers = max(1, min(self.config.max_workers, os.cpu_count() or 1))
        self.cache = {} if self.config.cache_enabled else None
        self.logger = None
        self.setup_logging()

    def update_worker_limits(self, *, max_workers: Optional[int] = None) -> None:
        """Refresh internal worker limits after configuration changes."""

        if max_workers is not None:
            self.config.max_workers = max(1, max_workers)

        self.max_workers = max(1, min(self.config.max_workers, os.cpu_count() or self.config.max_workers))

    def setup_logging(self):
        """Configure logging with rotation and secure storage"""
        log_dir = Path(os.getenv("CHAMELEON_LOG_DIR", Path.home() / ".chameleon" / "logs"))
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                os.chmod(log_dir, 0o700)
        except OSError as exc:
            warnings.warn(f"Could not prepare log directory at {log_dir}: {exc}")
            log_dir = Path.cwd()

        log_file = log_dir / "chameleon.log"

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger = logging.getLogger("chameleon")
        logger.handlers = []
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

        self.logger = logger

    def load_audio(self, file_path: str) -> Tuple['np.ndarray', int]:
        """Load audio file into a numpy array, with multiple backend support.

        Checks for numpy here rather than letting each caller discover it.
        Every backend below returns an ndarray, so without numpy this method
        cannot succeed -- but `np` was left bound to None, and the failure
        surfaced 90 lines away as `AttributeError: 'NoneType' object has no
        attribute 'frombuffer'`. Two commands still reached that traceback
        after the one that prompted the fix was deleted, which is the
        difference between removing an instance and removing the cause.
        """
        if not HAS_NUMPY:
            raise UnsupportedOperationError(
                "Reading audio into arrays requires numpy. "
                "Install it with: pip install -e .[audio]"
            )

        file_path = os.fspath(file_path)

        if Path(file_path).suffix.lower() not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file type: {file_path}")

        if not SecurityValidator.validate_path(file_path):
            raise ValueError(f"Unsafe file path rejected: {file_path}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            raise ValueError(f"File exceeds maximum allowed size: {file_path}")

        # Try librosa first (most features)
        if HAS_LIBROSA:
            try:
                audio, sr = librosa.load(file_path, sr=None, mono=False)
                return audio, sr
            except Exception as e:
                self.logger.warning(f"Librosa failed: {e}")

        # Try soundfile
        if HAS_SOUNDFILE:
            try:
                audio, sr = sf.read(file_path, always_2d=True)
                return audio.T, sr
            except Exception as e:
                self.logger.warning(f"Soundfile failed: {e}")

        # Fallback to basic WAV reading
        return self._load_wav_basic(file_path)

    def _load_wav_basic(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Basic WAV file loader without external dependencies"""
        handle = SecurityValidator.safe_open_file(file_path, 'rb')
        if handle is None:
            raise ValueError(f"Unsafe or unreadable WAV file: {file_path}")

        with handle as f:
            # Read RIFF header
            riff = f.read(12)
            if riff[:4] != b'RIFF' or riff[8:12] != b'WAVE':
                raise ValueError("Not a valid WAV file")

            # PCM subformat GUIDs for WAVE_FORMAT_EXTENSIBLE.
            pcm_guid = (b'\x01\x00\x00\x00\x00\x00\x10\x00'
                        b'\x80\x00\x00\xaa\x00\x38\x9b\x71')
            float_guid = (b'\x03\x00\x00\x00\x00\x00\x10\x00'
                          b'\x80\x00\x00\xaa\x00\x38\x9b\x71')

            audio_format = None

            # Walk the chunk list (fmt may be 16/18/40 bytes; LIST/JUNK/fact
            # chunks may precede data; odd-sized chunks carry a pad byte).
            while True:
                chunk_header = f.read(8)
                if len(chunk_header) != 8:
                    break

                chunk_id = chunk_header[:4]
                chunk_size = struct.unpack('<I', chunk_header[4:8])[0]

                if chunk_id == b'fmt ':
                    fmt_data = f.read(chunk_size)
                    if len(fmt_data) < 16:
                        raise ValueError("Truncated fmt chunk")
                    audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample = \
                        struct.unpack('<HHIIHH', fmt_data[:16])
                    if audio_format == 0xFFFE:
                        if len(fmt_data) < 40:
                            raise ValueError("Truncated WAVE_FORMAT_EXTENSIBLE fmt chunk")
                        guid = fmt_data[24:40]
                        if guid == pcm_guid:
                            audio_format = 1
                        elif guid == float_guid:
                            audio_format = 3
                        else:
                            raise ValueError("Unsupported WAV subformat")

                elif chunk_id == b'data':
                    if audio_format is None:
                        raise ValueError("WAV data chunk before fmt chunk")
                    audio_bytes = f.read(chunk_size)
                    if len(audio_bytes) < chunk_size:
                        self.logger.warning(
                            "Data chunk truncated: declared %d bytes, %d present",
                            chunk_size, len(audio_bytes),
                        )

                    # Decode by (format tag, bit depth) — anything else is an
                    # explicit error rather than silent misdecoding.
                    if audio_format == 1 and bits_per_sample == 8:
                        audio = np.frombuffer(audio_bytes, dtype=np.uint8)
                        audio = (audio.astype(np.float32) - 128.0) / 128.0
                    elif audio_format == 1 and bits_per_sample == 16:
                        audio = np.frombuffer(audio_bytes, dtype=np.int16)
                        audio = audio.astype(np.float32) / 32768.0
                    elif audio_format == 1 and bits_per_sample == 24:
                        raw = np.frombuffer(audio_bytes[:len(audio_bytes) // 3 * 3],
                                            dtype=np.uint8).reshape(-1, 3).astype(np.int32)
                        values = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
                        values = np.where(values >= 1 << 23, values - (1 << 24), values)
                        audio = values.astype(np.float32) / float(1 << 23)
                    elif audio_format == 1 and bits_per_sample == 32:
                        audio = np.frombuffer(audio_bytes, dtype=np.int32)
                        audio = audio.astype(np.float32) / 2147483648.0
                    elif audio_format == 3 and bits_per_sample == 32:
                        audio = np.frombuffer(audio_bytes, dtype=np.float32).copy()
                    else:
                        raise ValueError(
                            f"Unsupported WAV format: tag={audio_format}, "
                            f"bits={bits_per_sample}")

                    # Reshape for channels (drop a trailing partial frame).
                    if channels > 1:
                        usable = (len(audio) // channels) * channels
                        audio = audio[:usable].reshape(-1, channels).T

                    return audio, sample_rate
                else:
                    f.seek(chunk_size, 1)

                if chunk_size % 2 == 1:
                    f.seek(1, 1)  # RIFF pad byte after odd-sized chunks

        raise ValueError("Could not parse WAV file")

    def analyze_audio(self, audio: np.ndarray, sr: int) -> AudioMetadata:
        """Comprehensive audio analysis with ML features"""
        metadata = AudioMetadata(
            duration=len(audio) / sr if audio.ndim == 1 else audio.shape[1] / sr,
            sample_rate=sr,
            channels=1 if audio.ndim == 1 else audio.shape[0],
            bit_depth=16,  # Default, will be updated
            size_bytes=audio.nbytes,
            format="array"
        )

        # Basic statistics -- a 0-frame file measures as silence (0.0), the
        # same value the stdlib path reports for it. None is reserved for a
        # level pass that failed, which cannot happen here: the audio is
        # already decoded in memory.
        if audio.size:
            metadata.peak_level = float(np.abs(audio).max())
            metadata.rms_level = float(np.sqrt(np.mean(audio**2)))
        else:
            metadata.peak_level = metadata.rms_level = 0.0

        # Dynamic range -- a measured-silent file reports the 0.0 dB
        # placeholder; only a level pass that never ran leaves it None.
        if metadata.rms_level is not None and metadata.rms_level > 0:
            metadata.dynamic_range = 20 * np.log10(metadata.peak_level / metadata.rms_level)
        elif metadata.peak_level is not None:
            metadata.dynamic_range = 0.0

        # Advanced features with librosa
        if HAS_LIBROSA and audio.size:
            try:
                # Convert to mono for analysis
                audio_mono = librosa.to_mono(audio) if audio.ndim > 1 else audio

                # librosa's default analysis window is 2048 samples. A shorter
                # signal emits one UserWarning per call (stft, centroid, zcr,
                # beat_track), each printing a source snippet to stderr --
                # noise the user cannot act on, for an input that is simply
                # small. Skip the advanced fields rather than fabricate them;
                # they stay unset and export as null, same as no librosa.
                if audio_mono.size < 2048:
                    return metadata

                # Spectral features
                spectral_centroids = librosa.feature.spectral_centroid(y=audio_mono, sr=sr)[0]
                metadata.spectral_centroid = float(np.mean(spectral_centroids))

                # Zero crossing rate
                zcr = librosa.feature.zero_crossing_rate(audio_mono)[0]
                metadata.zero_crossing_rate = float(np.mean(zcr))

                # Tempo detection -- librosa returns an ndarray, not a
                # scalar; float() on a non-0-dim array raises and aborts the
                # whole advanced block, losing the spectral fields too.
                tempo, _ = librosa.beat.beat_track(y=audio_mono, sr=sr)
                tempo_values = np.asarray(tempo).ravel()
                if tempo_values.size:
                    metadata.tempo = float(tempo_values[0])

                # Frequency range estimation
                stft = np.abs(librosa.stft(audio_mono))
                freq_bins = librosa.fft_frequencies(sr=sr)
                magnitude_sum = np.sum(stft, axis=1)

                # Find frequency range with significant energy
                threshold = magnitude_sum.max() * 0.01
                active_freqs = freq_bins[magnitude_sum > threshold]
                if len(active_freqs) > 0:
                    metadata.frequency_range = (float(active_freqs[0]), float(active_freqs[-1]))

            except Exception as e:
                self.logger.warning(f"Advanced analysis failed: {e}")

        return metadata

    def normalize_audio(self, audio: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
        """Normalize audio with advanced algorithms"""
        if audio.size == 0:
            return audio

        # Find current peak
        current_peak = np.abs(audio).max()
        if current_peak == 0:
            return audio

        # Apply normalization
        gain = target_peak / current_peak
        normalized = audio * gain

        # Apply soft clipping if needed
        if self.config.quality == "high":
            normalized = self._soft_clip(normalized)

        return normalized

    @staticmethod
    def _bandlimited_resample(channel: np.ndarray, source_sr: int, target_sr: int,
                              half_taps: int = 16) -> np.ndarray:
        """Band-limited resample via windowed-sinc interpolation (numpy only).

        Used when neither librosa nor scipy is installed. The anti-aliasing is
        the `cutoff` term: the reconstruction filter has to stop below the
        LOWER of the two Nyquist frequencies, so when downsampling the sinc is
        widened by the conversion ratio (its cutoff moves down to the new
        Nyquist) and the kernel support is widened to match. Without that, a
        plain interpolator -- which is what this branch used to do, via
        np.interp -- folds everything above the new Nyquist back into the
        audible band.

        The taps are a Blackman-windowed sinc normalized to unit DC gain,
        the same construction bs1770_loudness uses for true-peak
        oversampling; only the cutoff scaling is new, since that path
        interpolates but never decimates.
        """

        n_in = len(channel)
        if n_in == 0:
            return channel.astype(np.float32)

        ratio = target_sr / source_sr
        n_out = max(1, int(round(n_in * ratio)))
        cutoff = min(1.0, ratio)
        # Lowering the cutoff widens the impulse response, so keep the same
        # number of zero crossings by widening the support to match.
        taps_half = max(1, int(round(half_taps / cutoff)))

        centers = np.arange(n_out) / ratio
        base = np.floor(centers).astype(np.int64)

        accumulated = np.zeros(n_out, dtype=np.float64)
        tap_sum = np.zeros(n_out, dtype=np.float64)
        for offset in range(-taps_half + 1, taps_half + 1):
            indices = base + offset
            scaled = (centers - indices) * cutoff
            # np.sinc(x) is sin(pi*x)/(pi*x), i.e. already normalized.
            window_position = (scaled / (2.0 * half_taps)) + 0.5
            window = np.where(
                (window_position >= 0.0) & (window_position <= 1.0),
                0.42
                - 0.5 * np.cos(2.0 * np.pi * window_position)
                + 0.08 * np.cos(4.0 * np.pi * window_position),
                0.0,
            )
            taps = np.sinc(scaled) * window
            inside = (indices >= 0) & (indices < n_in)
            values = np.where(inside, channel[np.clip(indices, 0, n_in - 1)], 0.0)
            accumulated += taps * values
            tap_sum += taps

        # Unit DC gain: a constant signal must survive unchanged.
        tap_sum = np.where(np.abs(tap_sum) < 1e-12, 1.0, tap_sum)
        return (accumulated / tap_sum).astype(np.float32)

    def _resample_audio(self, audio: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio data to a new sample rate with minimal dependencies.

        Picks the best resampler available: librosa, then scipy's
        resample_poly, then a built-in windowed-sinc fallback. All three
        band-limit the signal, so downsampling does not alias.
        """

        if target_sr <= 0:
            raise ValueError("Target sample rate must be positive.")

        if target_sr == source_sr:
            return audio

        if audio.ndim == 1:
            channels = [audio]
        else:
            channels = [audio[channel_index] for channel_index in range(audio.shape[0])]

        resampled_channels = []
        for channel in channels:
            if HAS_LIBROSA:
                resampled = librosa.resample(channel, orig_sr=source_sr, target_sr=target_sr)
            elif HAS_SCIPY:
                gcd = math.gcd(source_sr, target_sr)
                up = target_sr // gcd
                down = source_sr // gcd
                resampled = signal.resample_poly(channel, up, down)
            else:
                resampled = self._bandlimited_resample(channel, source_sr, target_sr)

            resampled_channels.append(resampled.astype(np.float32))

        if len(resampled_channels) == 1:
            return resampled_channels[0]

        max_length = max(len(channel) for channel in resampled_channels)
        stacked = []
        for channel in resampled_channels:
            if len(channel) < max_length:
                channel = np.pad(channel, (0, max_length - len(channel)), mode="edge")
            stacked.append(channel)

        return np.vstack(stacked)

    def _soft_clip(self, audio: np.ndarray, threshold: float = 0.95) -> np.ndarray:
        """Apply soft clipping to prevent harsh distortion"""
        if not HAS_SCIPY:
            return np.clip(audio, -1.0, 1.0)

        # Soft clipping using tanh
        over_threshold = np.abs(audio) > threshold
        if np.any(over_threshold):
            audio[over_threshold] = np.sign(audio[over_threshold]) * \
                                   (threshold + (1 - threshold) * np.tanh((np.abs(audio[over_threshold]) - threshold) * 10))

        return audio

    def remove_noise(self, audio: np.ndarray, sr: int, noise_profile: Optional[np.ndarray] = None) -> np.ndarray:
        """Advanced noise reduction using spectral subtraction"""
        if not HAS_SCIPY:
            return audio
        if audio.size == 0:
            # Empty input: an identity return (like normalize/mono) -- the
            # spectral machinery crashes on 0 samples.
            return audio

        # Convert to frequency domain. scipy's default hop is nperseg // 2,
        # so with nperseg=2048 each STFT column advances by 1024 samples.
        # For input shorter than the window, stft silently shrinks nperseg to
        # the input length while a literal 2048 in istft then mismatches and
        # crashes ("operands could not be broadcast (500,) (2048,)").
        nperseg = min(2048, int(audio.shape[-1]))
        hop = nperseg // 2  # scipy default noverlap = nperseg // 2
        stft = signal.stft(audio, fs=sr, nperseg=nperseg)[2]
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # Estimate the noise profile from the QUIETEST frames rather than the
        # first half second. Taking the opening frames assumes every file
        # begins with silence; when one starts straight into music the
        # "noise" estimate is the music's own spectrum, and the subtraction
        # guts the signal -- measured -20.0 dB on the fundamental of a tone
        # that started at t=0, i.e. the floor below was the only thing
        # stopping it from disappearing entirely.
        #
        # Using the low-energy tail of the frame distribution is the standard
        # robust approach (the same idea as minimum-statistics noise
        # estimation): it picks up the true noise floor whether it sits at the
        # start, in a gap, or anywhere else, and degrades gracefully on
        # material with no quiet passage at all.
        # The estimate is taken PER FREQUENCY BIN, over time. Real programme
        # material leaves every bin quiet at some point -- notes change,
        # instruments drop out -- so the low quantile of a bin's history is
        # its noise floor. Selecting whole quiet *frames* instead fails on
        # anything with a steady level, and picking the opening frames fails
        # whenever the file does not begin with silence.
        # A low quantile is deliberately conservative: it will not be dragged
        # up by steady content sitting in a bin. To turn it back into a level
        # estimate, scale it by the ratio the quantile has to the median for
        # noise. The magnitude of a complex-Gaussian bin is Rayleigh
        # distributed, whose quantiles are sigma*sqrt(-2*ln(1-p)), so
        #     median / p10 = sqrt(2*ln 2) / sqrt(-2*ln 0.9) ~= 2.56
        # That constant is derived, not tuned: it recovers the median noise
        # magnitude from the 10th percentile without ever measuring a frame
        # that has to be assumed noise-only.
        if noise_profile is None:
            if magnitude.shape[1] > 0:
                percentile_to_median = math.sqrt(2.0 * math.log(2.0)) / math.sqrt(-2.0 * math.log(0.9))
                estimate = (
                    np.percentile(magnitude, 10, axis=1, keepdims=True) * percentile_to_median
                )
                # A bin that never goes quiet has no observable noise floor:
                # its p10 is the steady content itself, so scaling it
                # "estimates" more noise than 90% of the bin's own
                # magnitudes, and subtraction guts a sustained tone to the
                # -20 dB floor (measured: -21 dB on a 2-second steady note).
                # Subtract only where the estimate sits below the bin's loud
                # tail (p90), i.e. where quiet frames actually existed to be
                # measured. Where they did not, the honest amount of noise
                # reduction is none -- whatever noise sits under a steady
                # tone is masked by it anyway.
                loud_tail = np.percentile(magnitude, 90, axis=1, keepdims=True)
                noise_profile = np.where(estimate < loud_tail, estimate, 0.0)
            else:
                noise_profile = np.zeros((magnitude.shape[0], 1))

        # Spectral subtraction with a floor proportional to the input
        # magnitude, which bounds attenuation at ~20 dB per bin so a bad noise
        # estimate cannot silence the signal outright.
        cleaned_magnitude = magnitude - noise_profile
        cleaned_magnitude = np.maximum(cleaned_magnitude, 0.1 * magnitude)

        # Reconstruct signal. scipy's istft emits frame-aligned output --
        # its boundary extension pads the tail out to a full hop, so the
        # result can be longer than the input (88200 -> 89088 samples,
        # i.e. +20 ms of silence-padding in the written file). A length
        # change is a lie about what denoising did; trim back to the
        # input's exact sample count.
        cleaned_stft = cleaned_magnitude * np.exp(1j * phase)
        _, cleaned_audio = signal.istft(cleaned_stft, fs=sr, nperseg=nperseg)

        return cleaned_audio[..., :audio.shape[-1]]

    # The repairs from audio_restoration.py that are verified to work *and* to
    # leave clean audio alone. "It exists" is not the same as "it is known to
    # help", and shipping the difference is how a tool loses trust.
    #
    # Deliberately absent: declicking. Both candidate detectors have a regime
    # where they destroy material rather than repair it -- the shipped
    # envelope/z-score one reports 354 clicks in one second of white noise
    # (peak 0.473 -> 0.325), and a second-difference/MAD detector reports 1764
    # in hard-clipped audio, one per clipping corner. Crackle removal, gap
    # interpolation and the librosa denoiser are likewise unexposed. See
    # CHARTER.md §9.
    #
    # The order is fixed and is not the order the flags appear on the command
    # line: damage must be undone in the reverse of the order it was done, and
    # clipping happens last in a recording chain. Measured on a 220 Hz tone
    # with hum, hard-clipped, against the undamaged tone: declip->dehum lands
    # 6.8 dB closer (-28.2 dB vs -21.5 dB). Running dehum first is worse than
    # the number suggests -- its filtering ripples the plateaus just enough
    # that declipping then finds 0 of the 720 clipped regions, and the peak it
    # appears to recover is the notch filter ringing on the clipping corners.
    RESTORATION_REPAIRS = ("declip", "dehum")

    def repair_audio(self, audio: np.ndarray, sr: int, repairs) -> np.ndarray:
        """Apply the named restoration repairs, one channel at a time.

        `audio_restoration` is imported here rather than at module scope: it
        warns on import when numpy/scipy/librosa are missing, and the
        dependency-free CLI paths must not print those warnings for a feature
        the user did not ask for.
        """
        import audio_restoration

        unknown = [name for name in repairs if name not in self.RESTORATION_REPAIRS]
        if unknown:
            raise ValueError(f"Unknown repair(s): {', '.join(unknown)}")
        if audio.size == 0:
            # Nothing to repair: identity, consistent with normalize/mono
            # on a 0-frame file.
            return audio

        # AudioRestorer gates its own constructor on this, but the repair
        # path below instantiates DeclippingProcessor/HumRemover directly --
        # on a numpy-only install that meant declip on a *clipped* file died
        # on `interpolate` (scipy) never having been imported, and dehum
        # could do the same on `signal`. Clean audio slipped through as a
        # no-op "success" only because detection found nothing to repair.
        audio_restoration._require_restoration_deps()

        processors = {
            "declip": lambda channel: audio_restoration.DeclippingProcessor()
                                      .restore_clipped(channel, sr),
            "dehum": lambda channel: audio_restoration.HumRemover()
                                     .remove_hum(channel, sr),
        }
        # Apply in canonical order however the caller listed them.
        repairs = [name for name in self.RESTORATION_REPAIRS if name in repairs]

        def repair_channel(channel):
            channel = np.asarray(channel, dtype=np.float64)
            for name in repairs:
                channel = processors[name](channel)
            return channel

        if audio.ndim == 1:
            repaired = repair_channel(audio).astype(audio.dtype, copy=False)
        else:
            repaired = np.stack([repair_channel(audio[index])
                                 for index in range(audio.shape[0])])
            repaired = repaired.astype(audio.dtype, copy=False)

        # Declipping restores crests *above* the clip rail, i.e. peaks > 1.0,
        # which save_audio's [-1, 1] clamp would flatten back into the very
        # plateau that was just repaired — output bit-identical to the
        # clipped input. Attenuate so the repaired peak fits the file format.
        peak = float(np.max(np.abs(repaired)))
        if peak > 0.999:
            repaired = repaired * (0.999 / peak)
        return repaired

    # Effects whose implementation needs a package the default install does
    # not have. Requesting one without the package used to produce an
    # unmodified file and a success message.
    _EFFECT_REQUIREMENTS = {
        "eq": ("scipy", lambda: HAS_SCIPY and HAS_MASTERING_CHAIN),
        "reverb": ("scipy", lambda: HAS_SCIPY),
        "compression": ("numpy", lambda: HAS_MASTERING_CHAIN),
    }

    def apply_effects(self, audio: np.ndarray, sr: int, effects: Dict[str, Any]) -> np.ndarray:
        """Apply various audio effects.

        Raises if an effect was asked for and cannot be applied. Silently
        returning the input is the failure mode that makes a tool untrustworthy:
        the file is written, the command reports success, and the effect simply
        is not there.
        """
        unavailable = [
            f"{name} (needs {package})"
            for name, (package, available) in self._EFFECT_REQUIREMENTS.items()
            # An empty eq band list ({"eq": []}) asks for nothing -- there
            # is no band to compute, so the DSP requirement does not apply.
            # Dict effects still count as a request even when empty:
            # {"compression": {}} applies the documented defaults.
            if name in effects and (name != "eq" or effects[name]) and not available()
        ]
        if unavailable:
            raise ValueError(
                "Cannot apply " + ", ".join(unavailable) +
                ". Install the optional audio extra: pip install -e .[audio]"
            )

        if audio.size == 0:
            # Validation above still ran (a bad effects spec on an empty file
            # is still a bad spec); the DSP itself is identity on empty.
            return audio.copy()

        processed = audio.copy()

        # EQ -- RBJ peaking biquads (see mastering_chain.design_peaking_eq).
        # This used to filter with scipy.iirpeak, a band-pass resonator, and
        # then scale the result, which replaced the signal with its own narrow
        # band: requesting +3 dB at 1 kHz measured -24.6 dB at 200 Hz and
        # -15.3 dB at 3 kHz. A peaking biquad applied once leaves everything
        # outside the band alone.
        if "eq" in effects and HAS_SCIPY and HAS_MASTERING_CHAIN:
            eq_params = effects["eq"]
            for band in eq_params:
                freq = band["frequency"]
                gain = band["gain"]
                q = band.get("q", 1.0)

                if 0 < freq < sr / 2:
                    b, a = mastering_chain.design_peaking_eq(freq, sr, gain, q)
                    # Single forward pass: filtfilt would apply the response
                    # twice and double the requested dB gain.
                    processed = signal.lfilter(b, a, processed)
                elif freq >= sr / 2:
                    # A band above Nyquist cannot be represented; skipping it
                    # silently would report "Processed" for a no-op band.
                    print(f"Warning: eq band at {freq} Hz exceeds Nyquist "
                          f"({sr / 2:.0f} Hz) -- skipped", file=sys.stderr)

        # Reverb (simple convolution)
        if "reverb" in effects and HAS_SCIPY:
            reverb_params = effects["reverb"]
            room_size = reverb_params.get("room_size", 0.5)
            wet = reverb_params.get("wet", 0.3)

            # Synthetic exponentially-decaying noise impulse response -- not a
            # measured room. The generator is seeded so the same input yields
            # the same output: CHARTER §1 sells this tool on reproducible
            # results, and an unseeded np.random.randn made every run differ.
            ir_length = max(1, int(room_size * sr))
            rng = np.random.default_rng(0)
            ir = rng.standard_normal(ir_length) * np.exp(-3 * np.linspace(0, 1, ir_length))

            # Convolve per channel — audio is (channels, samples), so pad the
            # 1-D impulse response to (1, ir_length): 'same' then returns
            # (channels, samples), identical to convolving each channel.
            kernel = ir[np.newaxis, :] if processed.ndim > 1 else ir
            reverb_signal = signal.convolve(processed, kernel, mode='same')
            # The noise IR above is not normalized: a room_size-0.3 kernel
            # applies ~+10 dB of random gain, so the wet path drowned the
            # dry one. Scale the convolved signal to the input's RMS so the
            # 'wet' knob controls the blend ratio, not the loudness.
            dry_rms = float(np.sqrt(np.mean(processed ** 2)))
            wet_rms = float(np.sqrt(np.mean(reverb_signal ** 2)))
            if wet_rms > 0:
                reverb_signal = reverb_signal * (dry_rms / wet_rms)
            processed = (1 - wet) * processed + wet * reverb_signal

        # Compression -- the real dynamics processor in mastering_chain, not
        # a per-sample waveshaper. Remapping |x| every sample reshapes the
        # waveform itself (that is soft-clipping; it adds harmonics), whereas
        # a compressor applies a slowly-varying gain computed from an
        # attack/release envelope and leaves waveform shape intact.
        if "compression" in effects and HAS_MASTERING_CHAIN:
            comp_params = effects["compression"]
            compressor = mastering_chain.Compressor(
                mastering_chain.CompressorConfig(
                    threshold=comp_params.get("threshold", -20.0),
                    ratio=comp_params.get("ratio", 4.0),
                    attack=comp_params.get("attack", 5.0),
                    release=comp_params.get("release", 50.0),
                    knee=comp_params.get("knee", 2.0),
                    makeup_gain=comp_params.get("makeup_gain", 0.0),
                ),
                sample_rate=sr,
            )
            processed, _gain_curve = compressor.process(processed)

        return processed

    def convert_audio(
        self,
        audio: np.ndarray,
        sr: int,
        *,
        target_format: str = "wav",
        target_sample_rate: Optional[int] = None,
        bit_depth: int = 16
    ) -> Tuple[np.ndarray, int, int]:
        """Convert audio to the desired format, sample rate, and bit depth."""

        normalized_format = (target_format or "wav").lower()
        if normalized_format != "wav":
            raise ValueError(f"Unsupported target format: {normalized_format}. Only 'wav' is supported.")

        if bit_depth not in {16, 24, 32}:
            raise ValueError("Bit depth must be one of {16, 24, 32}.")

        new_sr = sr
        converted = audio

        if target_sample_rate is not None:
            try:
                parsed_sr = int(target_sample_rate)
            except (TypeError, ValueError) as exc:
                raise ValueError("Target sample rate must be an integer.") from exc

            if parsed_sr <= 0:
                raise ValueError("Target sample rate must be positive.")

            if parsed_sr != sr:
                if converted.size == 0:
                    # Resampling silence-to-nothing is still a rate change in
                    # name only; report the target rate on the empty result.
                    new_sr = parsed_sr
                else:
                    converted = self._resample_audio(audio, sr, parsed_sr)
                    new_sr = parsed_sr

        if converted.dtype != np.float32:
            converted = converted.astype(np.float32)

        return converted, new_sr, bit_depth

    async def process_stream(self, input_device: Optional[int] = None,
                             output_device: Optional[int] = None,
                             effects: Optional[Dict] = None):
        """Process audio stream in real-time.

        *input_device*/*output_device* are PyAudio device indices; ``None``
        uses PyAudio's default device for that direction.
        """
        if not HAS_PYAUDIO:
            raise RuntimeError(
                "PyAudio not installed. Real-time streaming requires the "
                "optional [audio] extra (pip install 'chameleon[audio]')."
            )

        p = pyaudio.PyAudio()

        def stream_callback(in_data, frame_count, time_info, status):
            # Convert input bytes to numpy
            audio = np.frombuffer(in_data, dtype=np.float32)

            # Apply processing
            if effects:
                audio = self.apply_effects(audio, self.config.sample_rate, effects)

            # Normalize
            if self.config.normalize:
                audio = self.normalize_audio(audio, self.config.target_peak)

            # Convert back to bytes
            out_data = audio.astype(np.float32).tobytes()

            return (out_data, pyaudio.paContinue)

        # Open stream
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            output=True,
            input_device_index=input_device,
            output_device_index=output_device,
            stream_callback=stream_callback
        )

        stream.start_stream()

        # Keep stream running
        try:
            while stream.is_active():
                await asyncio.sleep(0.1)
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def extract_midi(self, audio: np.ndarray, sr: int, config: Optional[MIDIConfig] = None) -> List[MIDINote]:
        """Extract MIDI notes from audio"""
        if not HAS_MIDI:
            self.logger.warning("MIDI analysis not available")
            return []

        try:
            # Convert to list for MIDI analyzer
            audio_list = audio.tolist() if hasattr(audio, 'tolist') else list(audio)

            analyzer = MIDIAnalyzer(config)
            notes = analyzer.parse_midi_from_audio(audio_list, sr)

            self.logger.info(f"Extracted {len(notes)} MIDI notes")
            return notes

        except Exception as e:
            self.logger.error(f"MIDI extraction failed: {e}")
            return []

    def analyze_music(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Comprehensive musical analysis"""
        if not HAS_MIDI:
            return {"error": "MIDI analysis not available"}

        try:
            # Extract MIDI notes
            notes = self.extract_midi(audio, sr)

            if not notes:
                return {"error": "No musical content detected"}

            analyzer = MIDIAnalyzer()

            # Detect key
            key = analyzer.detect_key(notes)

            # Detect chords
            chords = analyzer.detect_chords(notes)

            # Analyze harmony
            harmony = analyzer.analyze_harmony(chords, key)

            # Analyze rhythm
            rhythm = analyzer.analyze_rhythm(notes)

            # Composition suggestions
            composer = MIDIComposer()
            next_chords = composer.suggest_next_chord(chords, key) if chords else []

            return {
                "notes": len(notes),
                "key": {
                    "tonic": key.tonic,
                    "mode": key.mode,
                    "confidence": key.confidence
                },
                "chords": [
                    {
                        "name": chord.name,
                        "start_time": chord.start_time,
                        "duration": chord.duration,
                        "confidence": chord.confidence
                    }
                    for chord in chords
                ],
                "harmony": harmony,
                "rhythm": rhythm,
                "suggestions": {
                    "next_chords": next_chords
                }
            }

        except Exception as e:
            self.logger.error(f"Musical analysis failed: {e}")
            return {"error": str(e)}

    def generate_midi(self, notes: List[MIDINote], output_path: str,
                      tempo_bpm: float = 120.0) -> bool:
        """Generate MIDI file from notes"""
        if not HAS_MIDI:
            self.logger.warning("MIDI generation not available")
            return False

        try:
            analyzer = MIDIAnalyzer()
            success = analyzer.generate_midi_file(notes, output_path,
                                                  tempo_bpm=tempo_bpm)

            if success:
                self.logger.info(f"MIDI file generated: {output_path}")
            else:
                self.logger.error("MIDI file generation failed")

            return success

        except Exception as e:
            self.logger.error(f"MIDI generation error: {e}")
            return False

    def compose_melody(self, chords: List[Dict], key_info: Dict, length: float = 8.0) -> List[MIDINote]:
        """Generate melody over chord progression"""
        if not HAS_MIDI:
            self.logger.warning("MIDI composition not available")
            return []

        try:
            from midi_analysis import Chord, MusicalKey

            # Convert dictionaries back to objects
            chord_objects = []
            for chord_dict in chords:
                chord = Chord(
                    root=chord_dict.get("root", 0),
                    chord_type=chord_dict.get("chord_type", "major"),
                    notes=chord_dict.get("notes", []),
                    start_time=chord_dict.get("start_time", 0.0),
                    duration=chord_dict.get("duration", 2.0)
                )
                chord_objects.append(chord)

            key = MusicalKey(
                tonic=key_info.get("tonic", 0),
                mode=key_info.get("mode", "major"),
                confidence=key_info.get("confidence", 1.0)
            )

            composer = MIDIComposer()
            melody = composer.generate_melody(chord_objects, key, length)

            self.logger.info(f"Generated melody with {len(melody)} notes")
            return melody

        except Exception as e:
            self.logger.error(f"Melody composition failed: {e}")
            return []

    def batch_process(self, files: List[str], operation: str, *,
                      show_progress: bool = False, **kwargs) -> List[Dict]:
        """Process multiple files with secure validation and optional threading.

        *show_progress* renders a live terminal progress bar (opt-in; the CLI
        enables it only when stdout is a real terminal, so captured/piped
        output and tests stay unaffected).
        """

        results: List[Dict] = []
        safe_files, rejections = self._filter_safe_files(files)

        dry_run = bool(kwargs.pop("dry_run", False))
        operation_kwargs = dict(kwargs)

        if not safe_files:
            # Sentinel for "every supplied file was rejected in pre-flight".
            # It has no "file" -- there is no one file to name -- and it
            # carries the exit code the README/ExitCode table promises: INPUT
            # for input-validation rejections, SECURITY when a security
            # policy (trusted roots, size cap) did the rejecting. SECURITY
            # wins when a mixed batch hit both.
            return [{
                "error": "No valid audio files to process.",
                "files": [path for path, _ in rejections],
                "exit_code": (
                    ExitCode.SECURITY
                    if any(kind == "security" for _, kind in rejections)
                    else ExitCode.INPUT
                ),
            }]

        progress = None
        if show_progress and HAS_UX_IMPROVEMENTS:
            progress = ProgressBar(total=len(safe_files), description=operation)

        use_parallel = self.config.parallel and len(safe_files) > 1

        if use_parallel:
            max_workers = min(self.max_workers, len(safe_files))
            executor = ThreadPoolExecutor(max_workers=max_workers)
            try:
                future_map = {
                    executor.submit(
                        self._process_single_file,
                        file_path,
                        operation,
                        dry_run=dry_run,
                        **operation_kwargs
                    ): file_path
                    for file_path in safe_files
                }

                for future, file_path in future_map.items():
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        self.logger.error(f"Failed to process {file_path}: {exc}")
                        results.append({
                            "error": str(exc),
                            "file": file_path,
                            "kind": _error_kind(exc),
                        })
                    if progress is not None:
                        progress.update()
            except BaseException:
                # Ctrl-C: abandon queued work instead of running it to
                # completion inside executor shutdown(wait=True).
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            else:
                executor.shutdown(wait=True)
        else:
            for file_path in safe_files:
                try:
                    results.append(
                        self._process_single_file(
                            file_path,
                            operation,
                            dry_run=dry_run,
                            **operation_kwargs
                        )
                    )
                except Exception as exc:
                    self.logger.error(f"Failed to process {file_path}: {exc}")
                    results.append({
                        "error": str(exc),
                        "file": file_path,
                        "kind": _error_kind(exc),
                    })
                if progress is not None:
                    progress.update()

        if progress is not None:
            progress.finish()

        # Pre-flight rejections are results too: a batch that silently drops
        # half its inputs and exits 0 claims "2/2 processed" while 2 files
        # were refused. Surface them so the denominator and exit code tell
        # the truth (same classification as the all-rejected sentinel).
        for path, kind in rejections:
            results.append({
                "file": path,
                "error": "rejected in pre-flight validation",
                "kind": kind,
            })

        return results

    def _filter_safe_files(
        self, files: List[str]
    ) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Split *files* into processable paths and rejected ones.

        Each rejection is recorded as ``(path, kind)`` where *kind* is
        ``"security"`` when a security policy rejected it (trusted-root or
        size checks) and ``"input"`` for every other pre-flight failure
        (unsupported suffix, missing file, failed WAV inspection) -- the two
        kinds map onto ``ExitCode.SECURITY`` / ``ExitCode.INPUT``.
        """
        safe: List[str] = []
        rejections: List[Tuple[str, str]] = []
        inspector = DeepFileInspector() if HAS_DEEP_INSPECTOR else None
        for original in files:
            file_path = os.fspath(original)
            suffix = Path(file_path).suffix.lower()

            if suffix not in SUPPORTED_FORMATS:
                self.logger.warning(f"Skipping unsupported file type: {file_path}")
                rejections.append((file_path, "input"))
                continue

            if not SecurityValidator.validate_path(file_path):
                self.logger.warning(f"Skipping unsafe path: {file_path}")
                rejections.append((file_path, "security"))
                continue

            if not os.path.exists(file_path):
                self.logger.warning(f"Skipping missing file: {file_path}")
                rejections.append((file_path, "input"))
                continue

            if not SecurityValidator.validate_file_size(file_path):
                self.logger.warning(f"Skipping file outside size limits: {file_path}")
                rejections.append((file_path, "security"))
                continue

            # Deep format inspection for native WAV files: reject anything whose
            # bytes are not actually a WAV container (e.g. an executable renamed
            # to .wav). Only gate on is_valid (the magic number); suspicious
            # byte patterns are logged but never rejected, because a WAV's PCM
            # payload can legitimately contain them. Skipped for mp3/flac/etc.,
            # which the inspector does not understand (those rely on the
            # `[audio]` backend instead).
            if inspector is not None and suffix in {'.wav', '.wave'}:
                result = inspector.validate_for_processing(Path(file_path))
                if not result.is_valid:
                    self.logger.warning(
                        f"Skipping file failing format inspection: {file_path} "
                        f"({'; '.join(result.errors)})"
                    )
                    rejections.append((file_path, "input"))
                    continue
                for note in result.warnings:
                    # WARNING, not INFO. These used to fire on nearly every
                    # real recording -- `#!` is two bytes and 16-bit audio
                    # produces any given pair about once per 65,536 samples --
                    # so INFO was the right level for what was then noise. The
                    # scan now only reports things that mean something.
                    self.logger.warning(f"Inspection note for {file_path}: {note}")

            safe.append(file_path)

        return safe, rejections

    def _process_single_file(self, file_path: str, operation: str, *, dry_run: bool = False, **kwargs) -> Dict:
        """Process a single file"""
        start_time = time.time()

        # Standard-library fallback: the numpy-based pipeline below cannot run
        # without numpy. analyze/normalize are delegated to the dependency-free
        # core so the CLI works out of the box; other operations need numpy.
        # mono/trim/normalize have exact dependency-free implementations in
        # core.py, so route them there whether or not numpy is present -- the
        # stdlib path is the reference behaviour, not a degraded fallback.
        if operation in ("mono", "trim") or (not HAS_NUMPY and operation in ("analyze", "normalize")):
            return self._process_single_file_stdlib(
                file_path, operation, start_time, dry_run=dry_run, **kwargs
            )
        if not HAS_NUMPY:
            raise UnsupportedOperationError(
                f"Operation '{operation}' requires numpy. Install it with: "
                "pip install -e .[audio]"
            )

        # Load audio
        audio, sr = self.load_audio(file_path)

        # The stdlib path (and mono/trim, which always route there) rejects a
        # 0-frame file as INPUT with "No audio signal found". Match that on
        # the numpy path: transforms that have nothing to measure must not
        # crash on empty reductions or write an empty "Processed" output.
        if audio.size == 0 and operation != "analyze":
            raise ValueError("No audio signal found")

        # Perform operation
        if operation == "analyze":
            result = self.analyze_audio(audio, sr)
            # analyze_audio only sees the decoded array: its size_bytes is
            # audio.nbytes, format "array", bit_depth a hardcoded 16 -- while
            # the stdlib path reports the file's real values. Same key, same
            # meaning: backfill from the source file so `analyze --export`
            # doesn't describe a different object per install.
            try:
                result.size_bytes = os.path.getsize(file_path)
                result.format = (Path(file_path).suffix.lstrip('.').lower()
                                 or "wav")
                import wave
                with wave.open(file_path) as wf:
                    result.bit_depth = wf.getsampwidth() * 8
            except (OSError, wave.Error, EOFError):
                pass  # non-WAV inputs keep the array-derived values
            return {
                "file": file_path,
                "metadata": result,
                "time": time.time() - start_time,
                "dry_run": dry_run
            }

        elif operation == "normalize":
            output_path = self._resolve_output_path(
                file_path,
                suffix="_normalized.wav",
                explicit_path=kwargs.get("output_path"),
                output_dir=kwargs.get("output_dir"),
                create_dirs=not dry_run
            )
            if dry_run:
                return {
                    "file": file_path,
                    "planned_output": str(output_path),
                    "time": time.time() - start_time,
                    "dry_run": True
                }

            processed = self.normalize_audio(audio, kwargs.get("target_peak", 0.95))
            self.save_audio(processed, str(output_path), sr)
            return {
                "file": file_path,
                "output": str(output_path),
                "time": time.time() - start_time,
                "dry_run": False
            }

        elif operation == "denoise":
            output_path = self._resolve_output_path(
                file_path,
                suffix="_denoised.wav",
                explicit_path=kwargs.get("output_path"),
                output_dir=kwargs.get("output_dir"),
                create_dirs=not dry_run
            )
            if dry_run:
                return {
                    "file": file_path,
                    "planned_output": str(output_path),
                    "time": time.time() - start_time,
                    "dry_run": True
                }

            processed = self.remove_noise(audio, sr)
            self.save_audio(processed, str(output_path), sr)
            return {
                "file": file_path,
                "output": str(output_path),
                "time": time.time() - start_time,
                "dry_run": False
            }

        elif operation == "restore":
            repairs = kwargs.get("repairs") or list(self.RESTORATION_REPAIRS)
            output_path = self._resolve_output_path(
                file_path,
                suffix="_restored.wav",
                explicit_path=kwargs.get("output_path"),
                output_dir=kwargs.get("output_dir"),
                create_dirs=not dry_run
            )
            if dry_run:
                return {
                    "file": file_path,
                    "planned_output": str(output_path),
                    "time": time.time() - start_time,
                    "dry_run": True
                }

            processed = self.repair_audio(audio, sr, repairs)
            self.save_audio(processed, str(output_path), sr)
            return {
                "file": file_path,
                "output": str(output_path),
                "repairs": list(repairs),
                "time": time.time() - start_time,
                "dry_run": False
            }

        elif operation == "effects":
            effects = kwargs.get("effects", {})
            output_path = self._resolve_output_path(
                file_path,
                suffix="_processed.wav",
                explicit_path=kwargs.get("output_path"),
                output_dir=kwargs.get("output_dir"),
                create_dirs=not dry_run
            )
            if dry_run:
                return {
                    "file": file_path,
                    "planned_output": str(output_path),
                    "time": time.time() - start_time,
                    "dry_run": True
                }

            processed = self.apply_effects(audio, sr, effects)
            self.save_audio(processed, str(output_path), sr)
            return {
                "file": file_path,
                "output": str(output_path),
                "time": time.time() - start_time,
                "dry_run": False
            }

        elif operation == "master":
            if not HAS_MASTERING_CHAIN:
                raise ValueError(
                    "The --master operation requires mastering_chain.py to be importable "
                    "(needs numpy)."
                )
            output_path = self._resolve_output_path(
                file_path,
                suffix="_mastered.wav",
                explicit_path=kwargs.get("output_path"),
                output_dir=kwargs.get("output_dir"),
                create_dirs=not dry_run
            )
            if dry_run:
                return {
                    "file": file_path,
                    "planned_output": str(output_path),
                    "time": time.time() - start_time,
                    "dry_run": True
                }

            preset = kwargs.get("master_preset", "default")
            config = create_mastering_preset(preset)
            chain = MasteringChain(config, sr)
            processed, info = chain.process(audio)
            self.save_audio(processed, str(output_path), sr)
            return {
                "file": file_path,
                "output": str(output_path),
                "time": time.time() - start_time,
                "dry_run": False,
                "lufs_before": info["input_analysis"]["lufs"],
                "lufs_after": info["output_analysis"]["lufs"],
                "peak_change_db": info["peak_change"],
                "true_peak_after_db": info["output_analysis"]["true_peak_db"],
                # MasteringChain.analyze() already computes an EBU-Tech-3342
                # loudness range; it used to be discarded here and never shown.
                "loudness_range_after_lu": info["output_analysis"].get("range"),
            }

        elif operation == "convert":
            target_format = kwargs.get("format", "wav") or "wav"
            target_sample_rate = kwargs.get("sample_rate")
            bit_depth = kwargs.get("bit_depth") or 16

            try:
                bit_depth = int(bit_depth)
            except (TypeError, ValueError) as exc:
                raise ValueError("Bit depth must be an integer value.") from exc

            suffix_components = ["converted"]
            planned_sr = target_sample_rate or sr
            try:
                resolved_bit_depth = int(bit_depth)
            except (TypeError, ValueError):
                resolved_bit_depth = 16

            if resolved_bit_depth not in {16, 24, 32}:
                resolved_bit_depth = 16

            if planned_sr != sr:
                suffix_components.append(f"{planned_sr}Hz")
            if resolved_bit_depth:
                suffix_components.append(f"{resolved_bit_depth}bit")
            suffix = "_" + "_".join(suffix_components) + ".wav"

            output_path = self._resolve_output_path(
                file_path,
                suffix=suffix,
                explicit_path=kwargs.get("output_path"),
                output_dir=kwargs.get("output_dir"),
                create_dirs=not dry_run
            )

            if dry_run:
                return {
                    "file": file_path,
                    "planned_output": str(output_path),
                    "time": time.time() - start_time,
                    "sample_rate": planned_sr,
                    "bit_depth": resolved_bit_depth,
                    "dry_run": True
                }

            converted, converted_sr, resolved_bit_depth = self.convert_audio(
                audio,
                sr,
                target_format=target_format,
                target_sample_rate=target_sample_rate,
                bit_depth=resolved_bit_depth
            )

            saved_bit_depth = self.save_audio(converted, str(output_path), converted_sr, bit_depth=resolved_bit_depth)

            return {
                "file": file_path,
                "output": str(output_path),
                "time": time.time() - start_time,
                "sample_rate": converted_sr,
                "bit_depth": saved_bit_depth,
                "dry_run": False
            }

        else:
            raise ValueError(f"Unknown operation: {operation}")

    def _process_single_file_stdlib(self, file_path: str, operation: str, start_time: float,
                                    *, dry_run: bool = False, **kwargs) -> Dict:
        """analyze/normalize via the dependency-free core (numpy unavailable)."""
        if operation == "analyze":
            result = core.analyze(file_path)
            if not result.success:
                # A valid file in a non-PCM encoding is a capability gap,
                # not bad input -- ERROR(1), same as a missing extra.
                kind = ("internal" if result.message.startswith("Unsupported")
                        else "input")
                return {"file": file_path, "error": result.message,
                        "kind": kind,
                        "time": time.time() - start_time, "dry_run": dry_run}
            info = result.data
            metadata = AudioMetadata(
                duration=info.duration,
                sample_rate=info.sample_rate,
                channels=info.channels,
                bit_depth=info.bit_depth,
                size_bytes=info.size_bytes,
                format="wav",
                peak_level=info.peak_level,
                rms_level=info.rms_level,
                # Crest factor, from two numbers the stdlib core already
                # reports. Leaving it at the dataclass default meant
                # `analyze --detailed` printed "Dynamic Range: 0.0dB" for a
                # sine whose crest factor is 3.01 dB -- a default presented as
                # a measurement, on the install this project leads with.
                dynamic_range=(20 * math.log10(info.peak_level / info.rms_level)
                               if info.rms_level and info.peak_level
                               else (0.0 if info.peak_level is not None else None)),
            )
            return {"file": file_path, "metadata": metadata,
                    "time": time.time() - start_time, "dry_run": dry_run}

        # The remaining stdlib operations all follow the same shape: resolve an
        # output path, then hand off to the dependency-free core.
        suffix, run = _STDLIB_FILE_OPERATIONS[operation]
        output_path = self._resolve_output_path(
            file_path,
            suffix=suffix,
            explicit_path=kwargs.get("output_path"),
            output_dir=kwargs.get("output_dir"),
            create_dirs=not dry_run,
        )
        if dry_run:
            return {"file": file_path, "planned_output": str(output_path),
                    "time": time.time() - start_time, "dry_run": True}
        result = run(file_path, str(output_path), kwargs)
        if not result.success:
            kind = ("internal" if result.message.startswith("Unsupported")
                    else "input")
            return {"file": file_path, "error": result.message,
                    "kind": kind,
                    "time": time.time() - start_time, "dry_run": False}
        return {"file": file_path, "output": str(output_path),
                "time": time.time() - start_time, "dry_run": False}

    def save_audio(self, audio: np.ndarray, file_path: str, sr: int, *, bit_depth: int = 16) -> int:
        """Save audio to file with multiple backend support.

        Returns the bit depth that was ultimately written."""
        # Ensure audio is in correct format
        if not SecurityValidator.validate_path(file_path):
            raise ValueError(f"Unsafe output path rejected: {file_path}")

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Values beyond [-1, 1] hard-clip on int PCM write -- report the
        # count so an overdriven effects chain surfaces as a warning
        # instead of silent distortion.
        over = int(np.count_nonzero(np.abs(audio) > 1.0))
        if over and self.logger:
            self.logger.warning(
                "%d samples exceed [-1, 1] and will hard-clip on write to %s",
                over, file_path,
            )
        audio = np.clip(audio, -1.0, 1.0)

        target_bit_depth = bit_depth if bit_depth in {16, 24, 32} else 16
        if bit_depth not in {16, 24, 32} and self.logger:
            self.logger.warning("Unsupported bit depth %s requested; defaulting to 16-bit PCM.", bit_depth)

        # Try soundfile first
        if HAS_SOUNDFILE:
            subtype_map = {16: "PCM_16", 24: "PCM_24", 32: "PCM_32"}
            subtype = subtype_map.get(target_bit_depth)
            try:
                sf.write(
                    file_path,
                    audio.T if audio.ndim > 1 else audio,
                    sr,
                    subtype=subtype
                )
                return target_bit_depth
            except Exception as e:
                self.logger.warning(f"Soundfile save failed: {e}")

        # Fallback to basic WAV writing
        if target_bit_depth != 16 and self.logger:
            self.logger.warning(
                "Falling back to 16-bit WAV output for %s (requested %s-bit).",
                file_path,
                target_bit_depth
            )

        self._save_wav_basic(audio, file_path, sr, bit_depth=16)
        return 16

    def _resolve_output_path(
        self,
        source_file: str,
        *,
        suffix: str,
        explicit_path: Optional[str],
        output_dir: Optional[str],
        create_dirs: bool = True
    ) -> Path:
        source_path = Path(source_file)

        if explicit_path:
            if not SecurityValidator.validate_path(explicit_path):
                raise ValueError(f"Unsafe explicit output path: {explicit_path}")
            destination = Path(explicit_path)
        else:
            if output_dir:
                if not SecurityValidator.validate_directory(output_dir):
                    raise ValueError(f"Unsafe output directory: {output_dir}")
                destination_dir = Path(output_dir)
                if create_dirs:
                    destination_dir.mkdir(parents=True, exist_ok=True)
            else:
                destination_dir = source_path.parent

            sanitized_name = SecurityValidator.sanitize_filename(f"{source_path.stem}{suffix}")
            destination = destination_dir / sanitized_name

        if create_dirs:
            destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def _save_wav_basic(self, audio: np.ndarray, file_path: str, sr: int, *, bit_depth: int = 16):
        """Basic WAV file writer without external dependencies.

        Always writes 16-bit PCM regardless of `bit_depth` (callers that need
        24/32-bit go through soundfile); the parameter is kept for signature
        compatibility with that path.

        Quantisation rounds to nearest. It previously used `.astype(np.int16)`,
        which truncates toward zero -- a biased quantiser whose error is
        correlated with the signal rather than centred on zero. Rounding
        removes that bias and halves the worst-case error.

        Dither is applied only when `ProcessingConfig.apply_dither` is set. It
        is off by default on purpose: TPDF dither is the right choice for
        audio quality when reducing bit depth, but it adds noise from a random
        source, and CHARTER §1 sells this tool on being deterministic and
        reproducible -- the same input must produce the same bytes. Opting in
        trades that guarantee for the better-behaved noise floor.
        """
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        scaled = np.clip(audio, -1.0, 1.0) * 32767.0

        if getattr(self.config, "apply_dither", False):
            # TPDF (triangular) dither, 2 LSB peak-to-peak: the sum of two
            # independent uniform variables. Triangular rather than
            # rectangular because it makes the quantisation error independent
            # of the signal, which is what removes noise modulation.
            rng = np.random.default_rng()
            scaled = scaled + (rng.random(scaled.shape) - rng.random(scaled.shape))

        pcm_audio = np.clip(np.round(scaled), -32768, 32767).astype(np.int16)

        channels = 1 if pcm_audio.ndim == 1 else pcm_audio.shape[0]

        with open_secure(file_path, 'wb') as f:
            # RIFF header
            f.write(b'RIFF')
            f.write(struct.pack('<I', 0))  # File size (will update later)
            f.write(b'WAVE')

            # fmt chunk
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))  # Chunk size
            f.write(struct.pack('<H', 1))   # Audio format (PCM)
            f.write(struct.pack('<H', channels))
            f.write(struct.pack('<I', sr))
            f.write(struct.pack('<I', sr * channels * 2))  # Byte rate
            f.write(struct.pack('<H', channels * 2))  # Block align
            f.write(struct.pack('<H', 16))  # Bits per sample

            # data chunk
            f.write(b'data')

            # Prepare audio data
            if channels > 1:
                # Interleave channels
                audio_data = pcm_audio.T.flatten()
            else:
                audio_data = pcm_audio

            audio_bytes = audio_data.tobytes()
            f.write(struct.pack('<I', len(audio_bytes)))
            f.write(audio_bytes)

            # Update file size
            file_size = f.tell() - 8
            f.seek(4)
            f.write(struct.pack('<I', file_size))

_MIDI_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
_MIDI_FLATS = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}


def _midi_tonic(key: Optional[str]) -> Optional[int]:
    """Resolve a --key argument to a tonic pitch class, or None if unknown."""
    if not key:
        return 0
    name = _MIDI_FLATS.get(key, key)
    return _MIDI_NOTE_NAMES.index(name) if name in _MIDI_NOTE_NAMES else None


def create_cli():
    """Create comprehensive CLI interface"""
    parser = argparse.ArgumentParser(
        description=f"Chameleon Audio Processing System v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--version", action="version", version=f"chameleon {VERSION}")
    parser.add_argument("--max-workers", type=int, help="Limit worker threads for batch operations")
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel execution even when available")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command
    analyze = subparsers.add_parser("analyze", help="Analyze audio files")
    analyze.add_argument("files", nargs="+", help="Audio files to analyze")
    analyze.add_argument("--detailed", action="store_true", help="Show detailed analysis")
    analyze.add_argument("--export", help="Export analysis to JSON file")
    analyze.add_argument("--spectrum", action="store_true",
                         help="Also report dominant frequencies, bandwidth, and RMS "
                              "via deterministic spectral analysis (stdlib-only)")
    analyze.add_argument("--loudness", action="store_true",
                         help="Also report integrated loudness (LUFS) via a pure "
                              "Python ITU-R BS.1770 K-weighted gated meter (stdlib-only). "
                              "Applies the standard surround weighting when the WAV "
                              "carries a dwChannelMask (equal weights otherwise) and "
                              "reports a 4x-oversampled true-peak estimate; bounded to "
                              "a prefix of the file -- not a certified full-track measurement.")

    # Process command
    process = subparsers.add_parser("process", help="Process audio files")
    process.add_argument("files", nargs="+", help="Audio files to process")
    process.add_argument("--normalize", action="store_true", help="Normalize audio")
    process.add_argument("--target-peak", type=float,
                         help="Target peak level for --normalize, 0.0-1.0 (default 0.95)")
    process.add_argument("--mono", action="store_true",
                         help="Downmix to mono (standard library only)")
    process.add_argument("--trim", action="store_true",
                         help="Trim leading/trailing silence (standard library only)")
    process.add_argument("--threshold", type=float,
                         help="Silence threshold for --trim, 0.0-1.0 (default 0.01)")
    process.add_argument("--denoise", action="store_true", help="Remove noise")
    process.add_argument("--dehum", action="store_true",
                         help="Remove 50/60 Hz mains hum and its harmonics, if present "
                              "(requires the [audio] extra)")
    process.add_argument("--declip", action="store_true",
                         help="Reconstruct peaks flattened by clipping "
                              "(requires the [audio] extra)")
    process.add_argument("--master", choices=["default", "streaming", "cd", "vinyl"],
                         help="Apply a full mastering chain (EQ/compressor/limiter/loudness); "
                              "requires numpy, scipy recommended for the full chain")
    process.add_argument("--effects", help="Apply effects (JSON file)")
    process.add_argument("--output-dir", help="Output directory")
    process.add_argument("--convert", action="store_true", help="Convert audio format or resolution")
    process.add_argument("--convert-format", choices=["wav"],
                         help="Target format (only wav is supported)")
    process.add_argument("--convert-sample-rate", type=int, help="Target sample rate for conversion")
    process.add_argument("--convert-bit-depth", type=int, choices=[16, 24, 32], help="Target bit depth for conversion")
    process.add_argument("--dry-run", action="store_true", help="Preview planned operations without writing files")
    process.add_argument("--json", action="store_true", help="Emit structured JSON output summarizing operations")

    # Stream command
    stream = subparsers.add_parser("stream", help="Real-time audio processing")
    stream.add_argument("--input-device", type=int, help="Input device index")
    stream.add_argument("--output-device", type=int, help="Output device index")
    stream.add_argument("--effects", help="Effects configuration (JSON)")

    # Batch command
    batch = subparsers.add_parser("batch", help="Batch processing")
    batch.add_argument("directory", help="Directory to process")
    batch.add_argument("operation",
                       choices=["analyze", "normalize", "mono", "trim", "denoise", "restore",
                                "convert", "effects"])
    batch.add_argument("--recursive", action="store_true", help="Process recursively")
    batch.add_argument("--output-dir", help="Output directory")
    # Only 'wav' exists as a converter; a free-form value used to parse and
    # then fail identically on every file in the batch.
    batch.add_argument("--format", choices=["wav"], help="Output format")
    batch.add_argument("--quality", choices=["standard", "high", "low", "medium", "lossless"],
                       default=None,
                       help="Normalize only: 'high' applies soft-clipping headroom, "
                            "'standard' does not. Legacy values low/medium/lossless are "
                            "accepted but equivalent to 'standard' -- they never had "
                            "separate behavior.")
    batch.add_argument("--target-peak", type=float,
                       help="Target peak level for the normalize operation, 0.0-1.0 (default 0.95)")
    batch.add_argument("--sample-rate", type=int, help="Target sample rate for conversion")
    batch.add_argument("--bit-depth", type=int, choices=[16, 24, 32], help="Target bit depth for conversion")
    batch.add_argument("--effects", help="Effects configuration for the effects operation (JSON file)")
    batch.add_argument("--dry-run", action="store_true",
                       help="Preview planned operations without writing files")

    # The `ml` command was removed in 2026-08. Its one operation, `enhance`,
    # called remove_noise() then normalize_audio() -- two pieces of
    # deterministic DSP, no model and no learning -- and was exactly
    # `process --denoise --normalize`. A machine-learning name over
    # spectral subtraction is the §4 claim this project mechanizes against,
    # sitting on the first screen a user reads. See CHARTER.md §9.

    # MIDI command
    midi = subparsers.add_parser("midi", help="MIDI analysis and composition")
    midi.add_argument("operation", choices=["extract", "analyze", "compose", "generate"])
    midi.add_argument("--input", help="Input audio file")
    midi.add_argument("--output", help="Output MIDI file")
    # Defaults are None so the dispatcher can tell an explicitly-typed flag
    # from an unset one; per-operation defaults are applied where consumed.
    midi.add_argument("--key", help="Musical key (e.g., C, G, F#)")
    midi.add_argument("--mode", choices=["major", "minor"], default=None)
    midi.add_argument("--tempo", type=float, default=None, help="Tempo in BPM")
    midi.add_argument("--length", type=float, default=None, help="Length in seconds")

    # Plugins command
    plugins_cmd = subparsers.add_parser("plugins", help="Inspect and audit plugins")
    plugins_cmd.add_argument(
        "--directory",
        action="append",
        help="Absolute plugin directory to inspect; may be specified multiple times"
    )
    plugins_cmd.add_argument("--json", action="store_true", help="Emit structured JSON output")
    plugin_subparsers = plugins_cmd.add_subparsers(dest="plugins_command", help="Plugin operations")
    if hasattr(plugin_subparsers, "required"):
        plugin_subparsers.required = True

    # Shared flags are also accepted after the subcommand (`plugins list
    # --json`), matching the documented form. A subparser flag cannot share
    # the parent's dest: the subparser's default would clobber the parent's
    # already-parsed value, and append would drop earlier --directory values.
    # Distinct dests are merged onto args.directory/args.json at dispatch.
    list_parser = plugin_subparsers.add_parser(
        "list", help="List discovered plugins and metadata")
    audit = plugin_subparsers.add_parser(
        "audit", help="Audit plugin files for sandbox compliance")
    audit.add_argument("--fail-fast", action="store_true", help="Stop on first plugin failure")
    for sub in (list_parser, audit):
        sub.add_argument(
            "--directory", action="append", dest="plugins_sub_directory", metavar="DIR",
            help="Absolute plugin directory to inspect; may be specified multiple times")
        sub.add_argument(
            "--json", action="store_true", dest="plugins_sub_json",
            help="Emit structured JSON output")

    # Server command
    server = subparsers.add_parser("server", help="Start API server")
    server.add_argument("--port", type=int, default=8000, help="Server port")
    server.add_argument("--host", default="localhost", help="Server host")
    server.add_argument("--workers", type=int, default=1,
                        help="Number of workers (must be 1: sessions, jobs and the "
                             "audit log live in per-process memory)")

    return parser

async def main():
    """Main entry point"""
    # asyncio.Runner installs a SIGINT handler that cancels the main task --
    # which is only delivered at await points. Nearly every command here is
    # synchronous work inside the coroutine, so Ctrl-C would be queued and
    # silently dropped when the task finishes (measured: exit 0, all files
    # processed). Restore the default handler so the interrupt is a real
    # KeyboardInterrupt wherever it lands.
    try:
        _signal.signal(_signal.SIGINT, _signal.default_int_handler)
    except (ValueError, OSError):
        pass  # not the main thread (embedded/test use) -- leave it alone

    parser = create_cli()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return ExitCode.USAGE

    exit_code = ExitCode.OK

    # Create processor
    config = ProcessingConfig.from_environment()
    if args.max_workers is not None:
        if args.max_workers <= 0:
            print(f"Error: --max-workers must be positive, got "
                  f"{args.max_workers}")
            return ExitCode.INPUT
        config.max_workers = args.max_workers
    if args.no_parallel:
        config.parallel = False

    processor = AudioProcessor(config)
    processor.update_worker_limits()

    if args.command == "analyze":
        try:
            files = [_sanitize_cli_input(path, "files") for path in args.files]
            _assert_unique_paths(files, "file input")
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        results = processor.batch_process(files, "analyze")

        if len(results) == 1 and "exit_code" in results[0]:
            # Every supplied file was rejected in pre-flight; per-file reasons
            # were already logged by _filter_safe_files.
            print(f"Error: {results[0]['error']}", file=sys.stderr)
            return results[0]["exit_code"]

        had_error = False
        for result in results:
            if "error" in result:
                had_error = True
                print(
                    f"Error processing {result.get('file', '<input>')}: "
                    f"{result['error']}",
                    file=sys.stderr,
                )
            else:
                metadata = result["metadata"]
                print(f"\n{result['file']}:")
                print(f"  Duration: {metadata.duration:.2f}s")
                print(f"  Sample Rate: {metadata.sample_rate}Hz")
                print(f"  Channels: {metadata.channels}")
                if metadata.peak_level is None:
                    print("  Peak Level: not measured")
                else:
                    print(f"  Peak Level: {metadata.peak_level:.3f}")
                    print(f"  RMS Level: {metadata.rms_level:.3f}")

                if args.detailed:
                    if metadata.dynamic_range is not None:
                        print(f"  Dynamic Range: {metadata.dynamic_range:.1f}dB")
                    # Only librosa populates this, and librosa is in no extra,
                    # so for almost every install the line used to read
                    # "Frequency Range: 0.0-0.0Hz" -- the dataclass default
                    # printed as though it were a measurement of the audio.
                    # `--spectrum` measures the same thing for real, in pure
                    # Python, on every install.
                    if metadata.frequency_range != (0.0, 0.0):
                        print(f"  Frequency Range: {metadata.frequency_range[0]:.1f}-{metadata.frequency_range[1]:.1f}Hz")
                    elif not args.spectrum:
                        print("  Frequency Range: not measured (use --spectrum)")
                    if metadata.tempo:
                        print(f"  Tempo: {metadata.tempo:.1f} BPM")
                    if metadata.spectral_centroid:
                        print(f"  Spectral Centroid: {metadata.spectral_centroid:.1f}Hz")

                if args.spectrum:
                    if not HAS_SPECTRAL_UTILS:
                        print("  Spectrum: unavailable (spectral_utils not importable)")
                    else:
                        samples_result = core.get_samples_for_analysis(result['file'])
                        if not samples_result.success:
                            print(f"  Spectrum: {samples_result.message}")
                        else:
                            report = spectral_utils.analyze_spectrum(
                                samples_result.data["samples"],
                                samples_result.data["sample_rate"],
                            )
                            print(f"  Spectrum RMS: {report.rms_level:.3f}")
                            print(f"  Spectrum Bandwidth: {report.bandwidth[0]:.1f}-{report.bandwidth[1]:.1f}Hz")
                            peaks = ", ".join(
                                f"{peak.frequency_hz:.1f}Hz" for peak in report.dominant_peaks
                            )
                            print(f"  Dominant Frequencies: {peaks or 'none detected'}")

                if args.loudness:
                    if not HAS_BS1770_LOUDNESS:
                        print("  Loudness: unavailable (bs1770_loudness not importable)")
                    else:
                        # separate_channels=True + measure_integrated_loudness_multichannel
                        # sums per-channel energy per BS.1770 instead of averaging
                        # samples to mono before filtering, which under-reads real
                        # stereo content by 3-6 LU (see bs1770_loudness.py). This is
                        # exact for mono too (a single-channel list), so it's used
                        # unconditionally rather than branching on channel count.
                        samples_result = core.get_samples_for_analysis(
                            result['file'], max_samples=LOUDNESS_MAX_SAMPLES,
                            separate_channels=True,
                        )
                        if not samples_result.success:
                            print(f"  Loudness: {samples_result.message}")
                        else:
                            try:
                                lufs = bs1770_loudness.measure_integrated_loudness_multichannel(
                                    samples_result.data["channels"],
                                    samples_result.data["sample_rate"],
                                    samples_result.data.get("channel_mask", 0),
                                )
                            except ValueError as exc:
                                print(f"  Loudness: unsupported ({exc})")
                            else:
                                if not math.isfinite(lufs):
                                    print("  Loudness: below measurement gate (silent or too short)")
                                else:
                                    weighting_label = (
                                        "BS.1770 surround weighting"
                                        if any(w != 1.0 for w in
                                               bs1770_loudness._channel_weights(
                                                   samples_result.data.get("channel_mask", 0),
                                                   len(samples_result.data["channels"])))
                                        else "no surround weighting"
                                    )
                                    metadata.loudness_lufs = lufs
                                    print(f"  Loudness: {lufs:.1f} LUFS (integrated, "
                                          f"ITU-R BS.1770 K-weighting, {weighting_label}, first "
                                          f"{LOUDNESS_MAX_SAMPLES / samples_result.data['sample_rate']:.0f}s max)")
                                # True-peak (dBTP) over the same bounded prefix -- 4x
                                # oversampled inter-sample peak per BS.1770-4 Annex 2,
                                # pure stdlib (no numpy needed for --loudness).
                                true_peak = bs1770_loudness.measure_true_peak_multichannel(
                                    samples_result.data["channels"]
                                )
                                if math.isfinite(true_peak):
                                    metadata.true_peak_dbtp = true_peak
                                    print(f"  True Peak: {true_peak:+.1f} dBTP "
                                          f"(4x-oversampled inter-sample peak estimate)")
                                # EBU Mode (Tech 3341) completes the integrated
                                # reading with the two ungated sliding-window
                                # meters: Max-M (400ms) and Max-S (3s).
                                max_m = bs1770_loudness.measure_max_momentary_loudness(
                                    samples_result.data["channels"],
                                    samples_result.data["sample_rate"],
                                )
                                max_s = bs1770_loudness.measure_max_short_term_loudness(
                                    samples_result.data["channels"],
                                    samples_result.data["sample_rate"],
                                )
                                if math.isfinite(max_m):
                                    metadata.max_momentary_lufs = max_m
                                    print(f"  Max Momentary: {max_m:.1f} LUFS (400ms window, ungated)")
                                if math.isfinite(max_s):
                                    metadata.max_short_term_lufs = max_s
                                    print(f"  Max Short-term: {max_s:.1f} LUFS (3s window, ungated)")
                                # Loudness range (EBU Tech 3342) completes EBU Mode.
                                lra = bs1770_loudness.measure_loudness_range(
                                    samples_result.data["channels"],
                                    samples_result.data["sample_rate"],
                                )
                                if math.isfinite(lra):
                                    metadata.loudness_range_lu = lra
                                    analysed_seconds = (
                                        len(samples_result.data["channels"][0])
                                        / samples_result.data["sample_rate"]
                                    )
                                    # Tech 3342 asks meters to flag an LRA as not
                                    # yet stable during the first 60s. This path
                                    # reads a bounded prefix, so say so plainly
                                    # rather than presenting a settled figure.
                                    stability = (
                                        "" if analysed_seconds >= 60
                                        else f", not yet stable — only {analysed_seconds:.0f}s analysed, "
                                             f"Tech 3342 considers LRA unsettled below 60s"
                                    )
                                    print(f"  Loudness Range: {lra:.1f} LU "
                                          f"(EBU Tech 3342, P95-P10 of gated short-term{stability})")

        if args.export:
            # The export destination is user input: an unwritable or
            # nonsensical path is bad input, not a traceback. OSError covers
            # the whole family (missing dir, directory-as-file, permissions).
            try:
                export_path = _sanitize_cli_input(args.export, "export path")
                with open(export_path, 'w') as f:
                    json.dump(results, f, indent=2, default=_json_export_default)
            except (OSError, ValueError) as exc:
                print(f"Error: cannot write analysis export: {exc}",
                      file=sys.stderr)
                return ExitCode.INPUT
            print(f"\nAnalysis exported to {export_path}")

        if had_error:
            exit_code = ExitCode.ERROR
            # Unparseable/corrupt files are input problems, not internal
            # failures -- a file that "could not parse" belongs in
            # INPUT(3) the same way a missing file does. Internal errors
            # still win over input errors when both appear.
            kinds = {r.get("kind") for r in results if "error" in r}
            if kinds and kinds <= {"input"}:
                exit_code = ExitCode.INPUT
            elif kinds and "security" in kinds:
                exit_code = ExitCode.SECURITY

    elif args.command == "process":
        operations: List[str] = []
        try:
            files = [_sanitize_cli_input(path, "files") for path in args.files]
            output_dir = _preflight_output_dir(
                _sanitize_optional_input(args.output_dir, "output_dir"))
            effects_path = _sanitize_optional_input(args.effects, "effects")
            _assert_unique_paths(files, "file input")
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        if output_dir:
            # Inputs sharing a stem all write the same output name
            # (stem + op suffix) into --output-dir: the later result
            # silently overwrites the earlier one. Warn now, while the
            # user can still pick distinct names or a per-file run.
            dupes = sorted(s for s, n in
                           Counter(Path(f).stem for f in files).items()
                           if n > 1)
            if dupes:
                print(f"Warning: inputs sharing the name(s) "
                      f"{', '.join(dupes)} will overwrite each other's "
                      f"output in {output_dir}", file=sys.stderr)

        kwargs: Dict[str, Any] = {
            "output_dir": output_dir,
            "dry_run": args.dry_run
        }

        # Op-specific flags on a command that did not request the op are
        # silently ignored otherwise -- the user reads a flag they typed as
        # part of the operation's behavior, so reject rather than pretend.
        if args.target_peak is not None and not args.normalize:
            print("Error: --target-peak requires --normalize", file=sys.stderr)
            return ExitCode.USAGE
        if args.threshold is not None and not args.trim:
            print("Error: --threshold requires --trim", file=sys.stderr)
            return ExitCode.USAGE
        if args.threshold is not None and not 0.0 < args.threshold < 1.0:
            # trim_silence rejects the same range downstream; validating here
            # answers INPUT instead of a per-file ERROR, and matches the docs.
            print(f"Error: --threshold must be within (0.0, 1.0), got "
                  f"{args.threshold}", file=sys.stderr)
            return ExitCode.INPUT
        convert_flags = {"--convert-format": args.convert_format,
                         "--convert-sample-rate": args.convert_sample_rate,
                         "--convert-bit-depth": args.convert_bit_depth}
        if not args.convert:
            used = [name for name, v in convert_flags.items() if v is not None]
            if used:
                print(f"Error: {used[0]} requires --convert", file=sys.stderr)
                return ExitCode.USAGE
        if (args.convert_sample_rate is not None
                and not 0 < args.convert_sample_rate <= MAX_TARGET_SAMPLE_RATE):
            print(f"Error: --convert-sample-rate must be within "
                  f"(0, {MAX_TARGET_SAMPLE_RATE}], got "
                  f"{args.convert_sample_rate}", file=sys.stderr)
            return ExitCode.INPUT

        if args.normalize:
            operations.append("normalize")
            if args.target_peak is not None:
                # Help advertises 0.0-1.0; enforce it. A target above 1.0
                # cannot be reached without clipping, so silently clamping
                # it would lie about what happened to the audio.
                if not 0.0 < args.target_peak <= 1.0:
                    print(f"Error: --target-peak must be within (0, 1.0], "
                          f"got {args.target_peak}", file=sys.stderr)
                    return ExitCode.INPUT
                kwargs["target_peak"] = args.target_peak
        if args.mono:
            operations.append("mono")
        if args.trim:
            operations.append("trim")
            if args.threshold is not None:
                kwargs["threshold"] = args.threshold
        if args.denoise:
            operations.append("denoise")
        # Canonical order, not command-line order -- see RESTORATION_REPAIRS.
        requested = {"dehum": args.dehum, "declip": args.declip}
        repairs = [name for name in AudioProcessor.RESTORATION_REPAIRS
                   if requested[name]]
        if repairs:
            operations.append("restore")
            kwargs["repairs"] = repairs
        if args.master:
            operations.append("master")
            kwargs["master_preset"] = args.master
        if effects_path:
            try:
                effects = _load_effects(effects_path)
            except ValueError as exc:
                print(f"Input validation error: {exc}", file=sys.stderr)
                return ExitCode.INPUT
            kwargs["effects"] = effects
            operations.append("effects")

        if args.convert:
            operations.append("convert")
            kwargs["format"] = args.convert_format or "wav"
            kwargs["sample_rate"] = args.convert_sample_rate
            kwargs["bit_depth"] = args.convert_bit_depth or 16

        if not operations:
            print("Error: specify at least one processing option (e.g., --normalize, --denoise, --declip, --effects, or --convert).", file=sys.stderr)
            return ExitCode.USAGE

        if args.no_parallel:
            processor.config.parallel = False
        processor.update_worker_limits()

        for operation in operations:
            results = processor.batch_process(files, operation, **kwargs)

            if len(results) == 1 and "exit_code" in results[0]:
                print(f"Error: {results[0]['error']}", file=sys.stderr)
                return results[0]["exit_code"]

            had_error = False
            for result in results:
                if "error" in result:
                    had_error = True
                    print(f"Error: {result['error']}", file=sys.stderr)
                    continue

                converted_details = []
                if operation == "convert":
                    if "sample_rate" in result:
                        converted_details.append(f"{result['sample_rate']}Hz")
                    if "bit_depth" in result:
                        converted_details.append(f"{result['bit_depth']}bit")
                if operation == "master" and "lufs_after" in result:
                    # LoudnessMeter is real ITU-R BS.1770-4 when scipy + bs1770_loudness
                    # are both available (the common case); otherwise it falls back to a
                    # rough RMS-based approximation. Label honestly either way, rather
                    # than a blanket "(approx)" that understates the common case.
                    is_bs1770 = HAS_MASTERING_CHAIN and mastering_chain.HAS_SCIPY and mastering_chain.HAS_BS1770
                    label = "LUFS" if is_bs1770 else "LUFS (approx)"
                    converted_details.append(f"{result['lufs_after']:.1f} {label}")
                    converted_details.append(f"{result['peak_change_db']:+.1f}dB peak")
                    tp = result.get("true_peak_after_db")
                    # scipy powers the 4x-oversampled true-peak; without it the
                    # value falls back to sample peak, so only advertise "dBTP"
                    # when the real oversampled path ran.
                    if tp is not None and math.isfinite(tp):
                        tp_label = "dBTP" if (HAS_MASTERING_CHAIN and mastering_chain.HAS_SCIPY) else "dBTP (sample-peak fallback)"
                        converted_details.append(f"{tp:+.1f} {tp_label}")
                    # Loudness range is only meaningful on the real BS.1770
                    # path; without scipy the meter returns a placeholder 0.0,
                    # so don't present that as a measurement.
                    lra_after = result.get("loudness_range_after_lu")
                    if is_bs1770 and lra_after is not None and math.isfinite(lra_after):
                        converted_details.append(f"{lra_after:.1f} LU range")
                if result.get("dry_run"):
                    converted_details.append("dry-run")
                detail_suffix = f" [{', '.join(converted_details)}]" if converted_details else ""

                if args.json:
                    print(json.dumps({
                        "operation": operation,
                        "result": _serialize_result(result)
                    }, default=str))
                else:
                    output_path = result.get("output") or result.get("planned_output") or "done"
                    print(f"Processed {result['file']} -> {output_path} ({result['time']:.2f}s){detail_suffix}")

            if had_error:
                exit_code = ExitCode.ERROR
                # Same classification as analyze: when every failure is an
                # input problem (unparseable file, bad header), INPUT(3) is
                # the honest answer; internal failures keep ERROR(1).
                kinds = {r.get("kind") for r in results if "error" in r}
                if kinds and kinds <= {"input"}:
                    exit_code = ExitCode.INPUT
                elif kinds and "security" in kinds:
                    exit_code = ExitCode.SECURITY

    elif args.command == "stream":
        # Device indices are non-negative PyAudio indexes; a negative one
        # would reach the backend and fail opaquely.
        for flag, dev in (("--input-device", args.input_device),
                          ("--output-device", args.output_device)):
            if dev is not None and dev < 0:
                print(f"Error: {flag} must be >= 0, got {dev}",
                      file=sys.stderr)
                return ExitCode.INPUT
        input_device = args.input_device
        output_device = args.output_device
        try:
            effects_path = _sanitize_optional_input(args.effects, "effects")
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        if effects_path:
            try:
                effects = _load_effects(effects_path)
            except ValueError as exc:
                print(f"Input validation error: {exc}", file=sys.stderr)
                return ExitCode.INPUT
        else:
            effects = None

        # The banner claims a stream is starting; when PyAudio is absent the
        # call below always fails, so the claim must not be printed.
        if HAS_PYAUDIO:
            print("Starting real-time audio stream... Press Ctrl+C to stop")

        try:
            await processor.process_stream(input_device, output_device, effects)
        except KeyboardInterrupt:
            print("\nStream stopped")
            exit_code = ExitCode.INTERRUPTED
        except Exception as exc:
            print(f"Stream failed: {exc}", file=sys.stderr)
            exit_code = ExitCode.ERROR

    elif args.command == "plugins":
        # --directory/--json are accepted both before and after the plugin
        # subcommand; the subcommand positions use separate dests (see the
        # parser) so merge them here.
        sub_dirs = getattr(args, "plugins_sub_directory", None)
        if sub_dirs:
            args.directory = (args.directory or []) + sub_dirs
        if getattr(args, "plugins_sub_json", False):
            args.json = True
        try:
            directories = None
            if args.directory:
                directories = [_sanitize_cli_input(d, "plugin directory") for d in args.directory]
                _assert_unique_paths(directories, "plugin directory")

            manager, sanitized_dirs = _initialize_plugin_manager(directories)
        except ValueError as exc:
            print(f"Plugin directory error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        if args.plugins_command == "list":
            plugins = manager.list_plugins()

            if args.json:
                payload = {
                    "directories": [str(path) for path in sanitized_dirs],
                    "plugins": {
                        name: {
                            "version": metadata.version,
                            "author": metadata.author,
                            "category": metadata.category,
                            "enabled": metadata.enabled,
                            "tags": metadata.tags,
                            "description": metadata.description,
                        }
                        for name, metadata in plugins.items()
                    },
                    # A file that failed to load is not the same as a file
                    # that does not exist -- "plugins": {} must not swallow
                    # broken plugins for machine consumers.
                    "load_failures": getattr(manager, "load_failures", {}),
                }
                print(json.dumps(payload, indent=2))
            else:
                print("Registered directories:")
                for directory in sanitized_dirs:
                    print(f"  - {directory}")

                load_failures = getattr(manager, "load_failures", {})
                if load_failures:
                    print("\nFailed to load:")
                    for path, reason in load_failures.items():
                        print(f"  - {path}: {reason}")

                if not plugins:
                    print("\nNo plugins discovered.")
                else:
                    print("\nDiscovered plugins:")
                    for name, metadata in plugins.items():
                        print(f"  - {name} v{metadata.version} ({metadata.category})")
                        if metadata.tags:
                            print(f"      Tags: {', '.join(metadata.tags)}")
                        if metadata.description:
                            print(f"      {metadata.description}")

        elif args.plugins_command == "audit":
            audit_results: List[Dict[str, Any]] = []
            loader = manager.loader
            plugin_files = loader.discover_plugins()

            had_failure = False

            for plugin_path in plugin_files:
                record: Dict[str, Any] = {
                    "path": plugin_path,
                    "passed": True,
                    "errors": []
                }

                try:
                    loader._check_module_safety(Path(plugin_path))
                except SecurityError as exc:
                    record["passed"] = False
                    record["errors"].append(str(exc))

                audit_results.append(record)

                if not record["passed"] and args.fail_fast:
                    had_failure = True
                    break

            if args.json:
                payload = {
                    "directories": [str(path) for path in sanitized_dirs],
                    "results": audit_results
                }
                print(json.dumps(payload, indent=2))
            else:
                print("Plugin audit summary:")
                for record in audit_results:
                    status = "PASSED" if record["passed"] else "FAILED"
                    print(f"  - {record['path']}: {status}")
                    for error in record["errors"]:
                        print(f"      Error: {error}")

            if any(not record["passed"] for record in audit_results) or had_failure:
                exit_code = ExitCode.SECURITY

    elif args.command == "batch":
        try:
            directory_arg = _sanitize_cli_input(args.directory, "directory")
            directory = Path(directory_arg)
            output_dir = _preflight_output_dir(
                _sanitize_optional_input(args.output_dir, "output_dir"))
            format_arg = _sanitize_optional_input(args.format, "format")
            effects_path = _sanitize_optional_input(args.effects, "effects")
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        if not directory.exists():
            print(f"Error: directory not found: {directory}", file=sys.stderr)
            return ExitCode.INPUT

        if not directory.is_dir():
            print(f"Error: specified path is not a directory: {directory}", file=sys.stderr)
            return ExitCode.INPUT

        # Flags scoped to an operation that was not requested would be
        # silently ignored -- reject them instead of pretending they ran.
        if args.operation != "convert":
            for flag, value in (("--format", args.format),
                                ("--sample-rate", args.sample_rate),
                                ("--bit-depth", args.bit_depth)):
                if value is not None:
                    print(f"Error: {flag} only applies to the convert operation",
                          file=sys.stderr)
                    return ExitCode.USAGE
        if args.operation != "normalize":
            if args.target_peak is not None:
                print("Error: --target-peak only applies to the normalize operation",
                      file=sys.stderr)
                return ExitCode.USAGE
            if args.quality is not None:
                print("Error: --quality only applies to the normalize operation",
                      file=sys.stderr)
                return ExitCode.USAGE
        if (args.sample_rate is not None
                and not 0 < args.sample_rate <= MAX_TARGET_SAMPLE_RATE):
            # convert_audio raises per-file downstream; an out-of-domain rate
            # is bad input, not a batch of identical failures.
            print(f"Error: --sample-rate must be within "
                  f"(0, {MAX_TARGET_SAMPLE_RATE}], got "
                  f"{args.sample_rate}", file=sys.stderr)
            return ExitCode.INPUT
        if args.operation != "effects" and args.effects:
            print("Error: --effects only applies to the effects operation",
                  file=sys.stderr)
            return ExitCode.USAGE

        pattern = "**/*" if args.recursive else "*"

        gathered_files: List[Path] = []
        for ext in SUPPORTED_FORMATS:
            gathered_files.extend(directory.glob(f"{pattern}{ext}"))

        if not gathered_files:
            print("Warning: no supported audio files found.", file=sys.stderr)
            return ExitCode.INPUT

        try:
            resolved_files = SecurityValidator.resolve_unique_paths([str(f) for f in gathered_files])
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        file_list = [str(path) for path in resolved_files]
        print(f"Found {len(file_list)} audio files")

        if output_dir:
            # Recursive gathers can hold identically-named files from
            # different subdirs; each op writes stem+suffix into
            # --output-dir, so later results overwrite earlier ones.
            dupes = sorted(s for s, n in
                           Counter(Path(f).stem for f in file_list).items()
                           if n > 1)
            if dupes:
                print(f"Warning: files sharing the name(s) "
                      f"{', '.join(dupes)} will overwrite each other's "
                      f"output in {output_dir}", file=sys.stderr)

            # Outputs written inside the scanned tree are
            # indistinguishable from inputs on the next run -- every
            # re-run re-ingests them (a_normalized_normalized.wav, ...).
            # The scan happens upfront so this run is unaffected, but the
            # compounding deserves a warning while the user can pick a
            # directory outside it.
            try:
                if Path(output_dir).resolve().is_relative_to(
                        directory.resolve()):
                    print(f"Warning: --output-dir {output_dir} is inside "
                          f"the scanned directory; its outputs will be "
                          f"re-processed as inputs on future runs",
                          file=sys.stderr)
            except OSError:
                pass

        kwargs: Dict[str, Any] = {
            "output_dir": output_dir,
            "format": format_arg,
        }
        if args.dry_run:
            kwargs["dry_run"] = True

        if args.operation == "convert":
            kwargs["format"] = format_arg or "wav"
            kwargs["sample_rate"] = args.sample_rate
            kwargs["bit_depth"] = args.bit_depth or 16

        if args.operation == "normalize" and args.target_peak is not None:
            if not 0.0 < args.target_peak <= 1.0:
                print(f"Error: --target-peak must be within (0, 1.0], "
                      f"got {args.target_peak}", file=sys.stderr)
                return ExitCode.INPUT
            kwargs["target_peak"] = args.target_peak

        if args.operation == "effects":
            if not effects_path:
                print("Error: --effects <file> is required for the effects operation", file=sys.stderr)
                return ExitCode.USAGE
            try:
                kwargs["effects"] = _load_effects(effects_path)
            except ValueError as exc:
                print(f"Input validation error: {exc}", file=sys.stderr)
                return ExitCode.INPUT

        if args.no_parallel:
            processor.config.parallel = False
        if args.quality:
            # The four-tier knob only ever had one behavior: 'high' adds a
            # soft clipper during normalize, every other value did nothing.
            # Accept the legacy names rather than break scripts, but say so
            # instead of letting them imply a difference that is not there.
            if args.quality in ("low", "medium", "lossless"):
                print(f"Note: --quality {args.quality} is equivalent to 'standard' "
                      "(no soft clipping); only 'high' enables it.", file=sys.stderr)
                args.quality = "standard"
            processor.config.quality = args.quality
        processor.update_worker_limits()

        results = processor.batch_process(
            file_list, args.operation, show_progress=sys.stdout.isatty(), **kwargs
        )

        if len(results) == 1 and "exit_code" in results[0]:
            print(f"Error: {results[0]['error']}", file=sys.stderr)
            return results[0]["exit_code"]

        successful = sum(1 for r in results if "error" not in r)
        verb = "Would process" if args.dry_run else "Processed"
        summary = f"{verb} {successful}/{len(results)} files successfully"
        if HAS_UX_IMPROVEMENTS:
            summary = ColorText.success(summary) if successful == len(results) else ColorText.error(summary)
        print(f"\n{summary}")

        if successful != len(results):
            exit_code = ExitCode.ERROR
            kinds = {r.get("kind") for r in results if "error" in r}
            if kinds and kinds <= {"input"}:
                exit_code = ExitCode.INPUT
            elif kinds and "security" in kinds:
                exit_code = ExitCode.SECURITY

    elif args.command == "midi":
        # Each operation consumes a different flag subset; a flag outside that
        # subset is silently ignored unless rejected here. Same rule as
        # process/batch: name the operation that owns the flag.
        midi_flag_owners = {
            "--input": {"extract", "analyze"},
            "--key": {"compose", "generate"},
            "--mode": {"compose", "generate"},
            "--tempo": {"extract", "compose", "generate"},
            "--length": {"compose"},
            "--output": {"extract", "compose", "generate"},
        }
        midi_flag_values = {
            "--input": args.input,
            "--key": args.key,
            "--mode": args.mode,
            "--tempo": args.tempo,
            "--length": args.length,
            "--output": args.output,
        }
        for flag, value in midi_flag_values.items():
            if value is not None and args.operation not in midi_flag_owners[flag]:
                owners = "/".join(sorted(midi_flag_owners[flag]))
                print(f"Error: {flag} only applies to midi {owners}", file=sys.stderr)
                return ExitCode.USAGE

        # Ranges for flags that feed binary encodings, checked where the
        # flags are actually consumed: us-per-quarter-note is a 24-bit field
        # (60e6/BPM <= 0xFFFFFF, i.e. tempo can't go below ~3.6 BPM), and a
        # non-positive tempo/length used to reach the encoder as a raw
        # ZeroDivisionError/OverflowError instead of a bad-input answer.
        if args.tempo is not None:
            # isfinite first: NaN defeats `<= 0` (it's False) and inf makes
            # us-per-quarter 0 -- both reached the encoder as int(nan) errors.
            if not math.isfinite(args.tempo) \
                    or args.tempo <= 0 or 60_000_000 / args.tempo > 0xFFFFFF:
                print("Error: --tempo must be a finite positive BPM encodable "
                      "in the MIDI 24-bit us-per-quarter field (>= ~3.6)",
                      file=sys.stderr)
                return ExitCode.INPUT
        if (args.length is not None
                and (not math.isfinite(args.length) or args.length <= 0)):
            # inf would loop forever generating notes; NaN defeats <= 0.
            print(f"Error: --length must be a positive finite duration, got "
                  f"{args.length}", file=sys.stderr)
            return ExitCode.INPUT

        # The MIDI writer builds the file in memory and opens once at the
        # end -- a bad destination surfaces as "Error generating MIDI file:
        # <errno>" with ERROR(1). A path the user typed is input, so
        # sanitize it and pre-flight the destination up front.
        try:
            output_path = _sanitize_optional_input(args.output, "output")
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT
        if output_path:
            parent = os.path.dirname(output_path) or "."
            if os.path.isdir(output_path) or not os.path.isdir(parent):
                print(f"Error: cannot write MIDI output to '{output_path}' "
                      f"(missing parent directory, or path is a directory)",
                      file=sys.stderr)
                return ExitCode.INPUT
            if not os.access(parent, os.W_OK | os.X_OK):
                print(f"Error: cannot write MIDI output to '{output_path}' "
                      f"(parent directory not writable)",
                      file=sys.stderr)
                return ExitCode.INPUT

        print(f"MIDI operation '{args.operation}'")

        if args.operation in ["extract", "analyze"] and not args.input:
            print("Error: --input required for extract/analyze operations", file=sys.stderr)
            return ExitCode.USAGE

        if args.operation in ("extract", "analyze") and args.input:
            # The most natural input for `midi analyze` is a .mid file --
            # and these commands analyze *audio* for musical content.
            # "Unsupported file type" leaves the user guessing which part
            # was wrong, so name the trap.
            if os.path.splitext(args.input)[1].lower() in (".mid", ".midi"):
                print("Error: midi extract/analyze take an audio file "
                      "(e.g. .wav) and analyze its musical content; a .mid "
                      "file is already MIDI -- there is nothing to extract "
                      "or analyze.", file=sys.stderr)
                return ExitCode.INPUT

        if args.operation == "extract":
            # Extract MIDI from audio
            audio, sr = processor.load_audio(args.input)

            tempo = args.tempo if args.tempo is not None else 120.0
            config = MIDIConfig(tempo=tempo) if HAS_MIDI else None
            notes = processor.extract_midi(audio, sr, config)

            if notes:
                print(f"Extracted {len(notes)} MIDI notes:")
                n_samples = (audio.shape[-1] if hasattr(audio, 'shape')
                             else len(audio))
                duration_s = n_samples / sr if sr else 0
                # Extraction is monophonic (YIN): a plausible melody stays
                # under ~20 notes/sec. Denser output means the input was
                # probably polyphonic and most of these notes are spurious.
                if duration_s > 0 and len(notes) / duration_s > 25:
                    print("  Warning: note density is implausibly high for a "
                          "monophonic source -- the input likely contains chords; "
                          "this extractor tracks one pitch per frame.",
                          file=sys.stderr)
                for i, note in enumerate(notes[:10]):  # Show first 10
                    print(f"  {i+1}. {note.note_name} (vel: {note.velocity}, time: {note.start_time:.2f}s)")
                if len(notes) > 10:
                    print(f"  ... and {len(notes)-10} more notes")

                # Save to MIDI file if output specified
                if output_path:
                    success = processor.generate_midi(notes, output_path, tempo_bpm=tempo)
                    if success:
                        print(f"MIDI file saved to {args.output}")
                    else:
                        print(f"Error: failed to write MIDI file to {args.output}", file=sys.stderr)
                        exit_code = ExitCode.ERROR
            else:
                print("No MIDI notes extracted")

        elif args.operation == "analyze":
            # Comprehensive musical analysis
            audio, sr = processor.load_audio(args.input)
            analysis = processor.analyze_music(audio, sr)

            if "error" in analysis:
                print(f"Analysis error: {analysis['error']}", file=sys.stderr)
                exit_code = ExitCode.ERROR
            else:
                print("\n🎵 Musical Analysis Results:")
                print(f"📊 Notes extracted: {analysis['notes']}")

                key_info = analysis['key']
                note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                key_name = note_names[key_info['tonic']]
                print(f"🎼 Key: {key_name} {key_info['mode']} (confidence: {key_info['confidence']:.3f})")

                if analysis['chords']:
                    print(f"🎸 Chords detected: {len(analysis['chords'])}")
                    for i, chord in enumerate(analysis['chords'][:5]):  # Show first 5
                        print(f"  {i+1}. {chord['name']} (time: {chord['start_time']:.1f}s)")

                if analysis['rhythm']:
                    rhythm = analysis['rhythm']
                    if rhythm['tempo'] > 0:
                        print(f"🥁 Estimated tempo: {rhythm['tempo']:.1f} BPM")
                    else:
                        print("🥁 Estimated tempo: not estimable (insufficient onsets)")

                if analysis['suggestions']['next_chords']:
                    print("🤖 Next chord suggestions:")
                    for chord, prob in analysis['suggestions']['next_chords'][:3]:
                        print(f"  {chord} (probability: {prob:.2f})")

        elif args.operation == "compose":
            # Generate a basic composition
            print("🎵 Generating musical composition...")

            # --key selects the tonic, --mode the scale intervals used by
            # compose_melody; both were previously ignored and every
            # composition came out in C major.
            tonic = _midi_tonic(args.key)
            if tonic is None:
                print(f"Error: unknown key '{args.key}' "
                      f"(expected e.g. C, F#, Bb)", file=sys.stderr)
                return ExitCode.INPUT

            mode = args.mode if args.mode is not None else "major"
            tempo = args.tempo if args.tempo is not None else 120.0
            length = args.length if args.length is not None else 8.0

            # Progression transposed into the requested key. I-V-vi-IV in
            # major; i-v-VI-iv in minor -- running the major progression
            # under a minor scale would inject out-of-mode chord tones
            # (e.g. F# into G minor).
            if mode == "major":
                progression = [
                    (0, "major", [0, 4, 7]),
                    (7, "major", [7, 11, 2]),
                    (9, "minor", [9, 0, 4]),
                    (5, "major", [5, 9, 0]),
                ]
            else:
                progression = [
                    (0, "minor", [0, 3, 7]),
                    (7, "minor", [7, 10, 2]),
                    (8, "major", [8, 0, 3]),
                    (5, "minor", [5, 8, 0]),
                ]
            basic_chords = [
                {
                    "root": (root + tonic) % 12,
                    "chord_type": chord_type,
                    "notes": [(n + tonic) % 12 for n in notes],
                    "start_time": i * 2.0,
                    "duration": 2.0,
                }
                for i, (root, chord_type, notes) in enumerate(progression)
            ]

            key_info = {"tonic": tonic, "mode": mode, "confidence": 1.0}

            melody = processor.compose_melody(basic_chords, key_info, length)

            # generate_melody works in beats (note_duration=0.5 = an eighth
            # note); the MIDI writer expects seconds, so rescale by the
            # tempo that will be written into the file.
            beats_to_seconds = 60.0 / tempo
            for n in melody:
                n.start_time *= beats_to_seconds
                n.duration *= beats_to_seconds

            if melody:
                print(f"Generated melody with {len(melody)} notes")
                if output_path:
                    success = processor.generate_midi(melody, output_path, tempo_bpm=tempo)
                    if success:
                        print(f"Composition saved to {args.output}")
                    else:
                        print(f"Error: failed to write composition to {args.output}", file=sys.stderr)
                        exit_code = ExitCode.ERROR
            else:
                print("Error: failed to generate composition", file=sys.stderr)
                exit_code = ExitCode.ERROR

        elif args.operation == "generate":
            # Generate MIDI file from scratch
            if not output_path:
                print("Error: --output required for generate operation", file=sys.stderr)
                return ExitCode.USAGE

            print("🎼 Generating MIDI demo...")

            tonic = _midi_tonic(args.key)
            if tonic is None:
                print(f"Error: unknown key '{args.key}' "
                      f"(expected e.g. C, F#, Bb)", file=sys.stderr)
                return ExitCode.INPUT

            mode = args.mode if args.mode is not None else "major"
            tempo = args.tempo if args.tempo is not None else 120.0

            # A one-octave scale in the requested key/mode starting at C4-ish
            # (MIDI 60 + tonic). Major and natural minor intervals.
            intervals = [0, 2, 4, 5, 7, 9, 11] if mode == "major" else [0, 2, 3, 5, 7, 8, 10]
            scale_notes = [60 + tonic + i for i in intervals] + [60 + tonic + 12]
            demo_notes = []

            for i, pitch in enumerate(scale_notes):
                note = MIDINote(
                    pitch=pitch,
                    velocity=80,
                    start_time=i * 0.5,
                    duration=0.4
                ) if HAS_MIDI else None

                if note:
                    demo_notes.append(note)

            if demo_notes:
                success = processor.generate_midi(demo_notes, output_path, tempo_bpm=tempo)
                if success:
                    print(f"Demo MIDI file generated: {args.output}")
                else:
                    print(f"Error: failed to write MIDI demo to {args.output}", file=sys.stderr)
                    exit_code = ExitCode.ERROR
            else:
                print("Error: failed to generate MIDI demo", file=sys.stderr)
                exit_code = ExitCode.ERROR

    elif args.command == "server":
        # Port 0 is technically bindable (ephemeral) but the banner would
        # advertise a port nobody is listening on; negative values crash
        # inside uvicorn with an OverflowError traceback.
        if not 1 <= args.port <= 65535:
            print(f"Error: --port must be 1-65535, got {args.port}",
                  file=sys.stderr)
            return ExitCode.INPUT
        if args.workers != 1:
            # api_state (sessions, token index, job registry, audit log,
            # circuit breaker) is per-process memory; uvicorn workers do
            # not share it, so N>1 randomly routes requests to a process
            # that does not know the caller's session -> spurious 401s.
            print(
                "Error: --workers must be 1. Session, job and audit state "
                "live in this process's memory; multiple uvicorn workers "
                "cannot share it. Run several processes behind a real "
                "load balancer instead (each with its own state).",
                file=sys.stderr)
            return ExitCode.INPUT
        # The banner claims a server is starting; when uvicorn is absent
        # the call below always fails, so the claim must not be printed.
        try:
            import uvicorn  # type: ignore
        except ImportError:
            print("The API server requires fastapi and uvicorn. "
                  "Install them with: pip install -e .[api]",
                  file=sys.stderr)
            exit_code = ExitCode.ERROR
        else:
            print(f"Starting API server on {args.host}:{args.port}")
            uvicorn.run(
                "api_server:app",
                host=args.host,
                port=args.port,
                workers=getattr(args, "workers", 1),
            )

    return exit_code


def cli() -> int:
    """Synchronous console-script entry point (wraps the async ``main``)."""
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return ExitCode.INTERRUPTED
    except (ValueError, FileNotFoundError) as exc:
        # The errors this CLI raises deliberately to tell the user something
        # they can act on -- an unsupported file type, a missing file, a
        # missing optional dependency. They reached the terminal as tracebacks,
        # which buries the one line that mattered.
        #
        # Deliberately not `except Exception`. A genuine bug should still show
        # its traceback: turning a crash into a tidy "Error:" line would make
        # the tool wrong about itself in a new way, which is the failure mode
        # this project keeps having to undo.
        print(f"Error: {exc}", file=sys.stderr)
        return ExitCode.ERROR


if __name__ == "__main__":
    sys.exit(cli())