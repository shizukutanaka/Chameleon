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
import hashlib
import argparse
import asyncio
import math
import re
import multiprocessing as mp
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, TYPE_CHECKING
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import logging
import warnings
from logging.handlers import RotatingFileHandler

import core
from core import open_secure, SecurityValidator
from plugin_system import PluginManager, PluginConfig, PluginLoader, SecurityError

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
    import scipy.fft as fft
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
    from ux_improvements import ProgressBar, ErrorFormatter, ColorText
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
VERSION = "1.0.0"
MAX_FILE_SIZE = 500 * 1024 * 1024  # Align with core constraints (500MB)
CHUNK_SIZE = 8192
DEFAULT_SAMPLE_RATE = 44100
# Sample bound for `analyze --loudness`: large enough to be a meaningful
# integrated-loudness window, small enough to keep memory/time predictable
# for a pure-Python filter + block loop regardless of file length (same
# bounded-analysis principle as core.get_samples_for_analysis's own default).
LOUDNESS_MAX_SAMPLES = 15 * 48000
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
    peak_level: float = 0.0
    rms_level: float = 0.0
    dynamic_range: float = 0.0
    frequency_range: Tuple[float, float] = (0.0, 0.0)
    tempo: Optional[float] = None
    key: Optional[str] = None
    loudness_lufs: Optional[float] = None
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
    remove_dc_offset: bool = True
    apply_dither: bool = False
    use_gpu: bool = False
    parallel: bool = True
    max_workers: int = max(1, min(4, mp.cpu_count() or 1))
    cache_enabled: bool = True
    quality: str = "high"  # low, medium, high, lossless

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
            else:
                parsed = max(1, parsed)
            config.max_workers = parsed

        env_parallel = os.getenv("CHAMELEON_PARALLEL")
        if env_parallel is not None:
            config.parallel = env_parallel.strip().lower() not in {"0", "false", "off", "no"}

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
        """Load audio file with multiple backend support"""
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

        # Basic statistics
        if audio.ndim == 1:
            metadata.peak_level = float(np.abs(audio).max())
            metadata.rms_level = float(np.sqrt(np.mean(audio**2)))
        else:
            metadata.peak_level = float(np.abs(audio).max())
            metadata.rms_level = float(np.sqrt(np.mean(audio**2)))

        # Dynamic range
        if metadata.rms_level > 0:
            metadata.dynamic_range = 20 * np.log10(metadata.peak_level / metadata.rms_level)

        # Advanced features with librosa
        if HAS_LIBROSA:
            try:
                # Convert to mono for analysis
                audio_mono = librosa.to_mono(audio) if audio.ndim > 1 else audio

                # Spectral features
                spectral_centroids = librosa.feature.spectral_centroid(y=audio_mono, sr=sr)[0]
                metadata.spectral_centroid = float(np.mean(spectral_centroids))

                # Zero crossing rate
                zcr = librosa.feature.zero_crossing_rate(audio_mono)[0]
                metadata.zero_crossing_rate = float(np.mean(zcr))

                # Tempo detection
                tempo, _ = librosa.beat.beat_track(y=audio_mono, sr=sr)
                metadata.tempo = float(tempo)

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

    def _resample_audio(self, audio: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio data to a new sample rate with minimal dependencies."""

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
                num_samples = max(1, int(round(len(channel) * target_sr / source_sr)))
                x_old = np.linspace(0.0, len(channel) - 1, num=len(channel), endpoint=True)
                x_new = np.linspace(0.0, len(channel) - 1, num=num_samples, endpoint=True)
                resampled = np.interp(x_new, x_old, channel)

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

        # Convert to frequency domain. scipy's default hop is nperseg // 2,
        # so with nperseg=2048 each STFT column advances by 1024 samples.
        nperseg = 2048
        hop = nperseg // 2  # scipy default noverlap = nperseg // 2
        stft = signal.stft(audio, fs=sr, nperseg=nperseg)[2]
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # Estimate noise profile if not provided
        if noise_profile is None:
            # Use the first ~0.5 seconds as the noise profile. Frame count must
            # be derived from the actual hop (1024), not 512, or the window is
            # ~2x too long.
            noise_frames = max(1, int(0.5 * sr / hop))
            noise_profile = np.median(magnitude[:, :noise_frames], axis=1, keepdims=True)

        # Spectral subtraction
        cleaned_magnitude = magnitude - noise_profile
        cleaned_magnitude = np.maximum(cleaned_magnitude, 0.1 * magnitude)  # Avoid over-subtraction

        # Reconstruct signal
        cleaned_stft = cleaned_magnitude * np.exp(1j * phase)
        _, cleaned_audio = signal.istft(cleaned_stft, fs=sr, nperseg=2048)

        return cleaned_audio

    def apply_effects(self, audio: np.ndarray, sr: int, effects: Dict[str, Any]) -> np.ndarray:
        """Apply various audio effects"""
        processed = audio.copy()

        # EQ
        if "eq" in effects and HAS_SCIPY:
            eq_params = effects["eq"]
            for band in eq_params:
                freq = band["frequency"]
                gain = band["gain"]
                q = band.get("q", 1.0)

                # Design filter
                nyquist = sr / 2
                normalized_freq = freq / nyquist

                if normalized_freq < 1:
                    b, a = signal.iirpeak(normalized_freq, q)
                    processed = signal.filtfilt(b, a, processed) * (10 ** (gain / 20))

        # Reverb (simple convolution)
        if "reverb" in effects and HAS_SCIPY:
            reverb_params = effects["reverb"]
            room_size = reverb_params.get("room_size", 0.5)
            wet = reverb_params.get("wet", 0.3)

            # Generate simple impulse response
            ir_length = int(room_size * sr)
            ir = np.random.randn(ir_length) * np.exp(-3 * np.linspace(0, 1, ir_length))

            # Convolve
            reverb_signal = signal.convolve(processed, ir, mode='same')
            processed = (1 - wet) * processed + wet * reverb_signal

        # Compression
        if "compression" in effects:
            comp_params = effects["compression"]
            threshold = comp_params.get("threshold", -20)  # dB
            ratio = comp_params.get("ratio", 4)

            # Convert to dB
            db = 20 * np.log10(np.abs(processed) + 1e-10)

            # Apply compression
            over_threshold = db > threshold
            db[over_threshold] = threshold + (db[over_threshold] - threshold) / ratio

            # Convert back
            processed = np.sign(processed) * (10 ** (db / 20))

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
            raise RuntimeError("PyAudio not installed. Cannot process streams.")

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

    def generate_midi(self, notes: List[MIDINote], output_path: str) -> bool:
        """Generate MIDI file from notes"""
        if not HAS_MIDI:
            self.logger.warning("MIDI generation not available")
            return False

        try:
            analyzer = MIDIAnalyzer()
            success = analyzer.generate_midi_file(notes, output_path)

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
        safe_files = self._filter_safe_files(files)

        dry_run = bool(kwargs.pop("dry_run", False))
        operation_kwargs = dict(kwargs)

        if not safe_files:
            return [{"error": "No valid audio files to process."}]

        progress = None
        if show_progress and HAS_UX_IMPROVEMENTS:
            progress = ProgressBar(total=len(safe_files), description=operation)

        use_parallel = self.config.parallel and len(safe_files) > 1

        if use_parallel:
            max_workers = min(self.max_workers, len(safe_files))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
                        results.append({"error": str(exc), "file": file_path})
                    if progress is not None:
                        progress.update()
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
                    results.append({"error": str(exc), "file": file_path})
                if progress is not None:
                    progress.update()

        if progress is not None:
            progress.finish()

        return results

    def _filter_safe_files(self, files: List[str]) -> List[str]:
        safe: List[str] = []
        inspector = DeepFileInspector() if HAS_DEEP_INSPECTOR else None
        for original in files:
            file_path = os.fspath(original)
            suffix = Path(file_path).suffix.lower()

            if suffix not in SUPPORTED_FORMATS:
                self.logger.warning(f"Skipping unsupported file type: {file_path}")
                continue

            if not SecurityValidator.validate_path(file_path):
                self.logger.warning(f"Skipping unsafe path: {file_path}")
                continue

            if not os.path.exists(file_path):
                self.logger.warning(f"Skipping missing file: {file_path}")
                continue

            if not SecurityValidator.validate_file_size(file_path):
                self.logger.warning(f"Skipping file outside size limits: {file_path}")
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
                    continue
                for note in result.warnings:
                    self.logger.info(f"Inspection note for {file_path}: {note}")

            safe.append(file_path)

        return safe

    def _process_single_file(self, file_path: str, operation: str, *, dry_run: bool = False, **kwargs) -> Dict:
        """Process a single file"""
        start_time = time.time()

        # Standard-library fallback: the numpy-based pipeline below cannot run
        # without numpy. analyze/normalize are delegated to the dependency-free
        # core so the CLI works out of the box; other operations need numpy.
        if not HAS_NUMPY:
            if operation in ("analyze", "normalize"):
                return self._process_single_file_stdlib(
                    file_path, operation, start_time, dry_run=dry_run, **kwargs
                )
            raise ValueError(
                f"Operation '{operation}' requires numpy. Install it with: "
                "pip install -e .[audio]"
            )

        # Load audio
        audio, sr = self.load_audio(file_path)

        # Perform operation
        if operation == "analyze":
            result = self.analyze_audio(audio, sr)
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
                output_dir=kwargs.get("output_dir")
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
                output_dir=kwargs.get("output_dir")
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

        elif operation == "effects":
            effects = kwargs.get("effects", {})
            output_path = self._resolve_output_path(
                file_path,
                suffix="_processed.wav",
                explicit_path=kwargs.get("output_path"),
                output_dir=kwargs.get("output_dir")
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
                output_dir=kwargs.get("output_dir")
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
                output_dir=kwargs.get("output_dir")
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
                return {"file": file_path, "error": result.message,
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
            )
            return {"file": file_path, "metadata": metadata,
                    "time": time.time() - start_time, "dry_run": dry_run}

        # operation == "normalize"
        output_path = self._resolve_output_path(
            file_path,
            suffix="_normalized.wav",
            explicit_path=kwargs.get("output_path"),
            output_dir=kwargs.get("output_dir"),
        )
        if dry_run:
            return {"file": file_path, "planned_output": str(output_path),
                    "time": time.time() - start_time, "dry_run": True}
        result = core.normalize(file_path, str(output_path), kwargs.get("target_peak", 0.95))
        if not result.success:
            return {"file": file_path, "error": result.message,
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

        # Ensure audio is in range [-1, 1]
        audio = np.clip(audio, -1.0, 1.0)

        target_bit_depth = bit_depth if bit_depth in {16, 24, 32} else 16
        if bit_depth not in {16, 24, 32} and self.logger:
            self.logger.warning("Unsupported bit depth %s requested; defaulting to 16-bit PCM.", bit_depth)

        # Try soundfile first
        if HAS_SOUNDFILE:
            subtype_map = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}
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
        output_dir: Optional[str]
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
                destination_dir.mkdir(parents=True, exist_ok=True)
            else:
                destination_dir = source_path.parent

            sanitized_name = SecurityValidator.sanitize_filename(f"{source_path.stem}{suffix}")
            destination = destination_dir / sanitized_name

        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def _save_wav_basic(self, audio: np.ndarray, file_path: str, sr: int, *, bit_depth: int = 16):
        """Basic WAV file writer without external dependencies"""
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        pcm_audio = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

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
                              "Sums per-channel energy correctly (mono/stereo), but omits "
                              "surround-channel weighting and true-peak, and is bounded to "
                              "a prefix of the file -- not a certified full-track measurement.")

    # Process command
    process = subparsers.add_parser("process", help="Process audio files")
    process.add_argument("files", nargs="+", help="Audio files to process")
    process.add_argument("--normalize", action="store_true", help="Normalize audio")
    process.add_argument("--target-peak", type=float,
                         help="Target peak level for --normalize, 0.0-1.0 (default 0.95)")
    process.add_argument("--denoise", action="store_true", help="Remove noise")
    process.add_argument("--master", choices=["default", "streaming", "cd", "vinyl"],
                         help="Apply a full mastering chain (EQ/compressor/limiter/loudness); "
                              "requires numpy, scipy recommended for the full chain")
    process.add_argument("--effects", help="Apply effects (JSON file)")
    process.add_argument("--output-dir", help="Output directory")
    process.add_argument("--convert", action="store_true", help="Convert audio format or resolution")
    process.add_argument("--convert-format", help="Target format (currently only wav supported)")
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
    batch.add_argument("operation", choices=["analyze", "normalize", "denoise", "convert", "effects"])
    batch.add_argument("--recursive", action="store_true", help="Process recursively")
    batch.add_argument("--output-dir", help="Output directory")
    batch.add_argument("--format", help="Output format")
    batch.add_argument("--quality", choices=["low", "medium", "high", "lossless"], default="high")
    batch.add_argument("--target-peak", type=float,
                       help="Target peak level for the normalize operation, 0.0-1.0 (default 0.95)")
    batch.add_argument("--sample-rate", type=int, help="Target sample rate for conversion")
    batch.add_argument("--bit-depth", type=int, choices=[16, 24, 32], help="Target bit depth for conversion")
    batch.add_argument("--effects", help="Effects configuration for the effects operation (JSON file)")

    # ML command — only 'enhance' is implemented; classify/separate/transcribe
    # require trained models or external tools that are explicitly out of scope
    # per CHARTER §4 (non-goals: AI transcription, source separation, ML features).
    ml = subparsers.add_parser("ml", help="Audio enhancement (numpy/scipy required)")
    ml.add_argument("operation", choices=["enhance"],
                    help="enhance: apply noise reduction + normalization")
    ml.add_argument("--input", required=True, help="Input audio file")
    ml.add_argument("--output", help="Output file/directory")

    # MIDI command
    midi = subparsers.add_parser("midi", help="MIDI analysis and composition")
    midi.add_argument("operation", choices=["extract", "analyze", "compose", "generate"])
    midi.add_argument("--input", help="Input audio file")
    midi.add_argument("--output", help="Output MIDI file")
    midi.add_argument("--key", help="Musical key (e.g., C, G, F#)")
    midi.add_argument("--mode", choices=["major", "minor"], default="major")
    midi.add_argument("--tempo", type=float, default=120.0, help="Tempo in BPM")
    midi.add_argument("--length", type=float, default=8.0, help="Length in seconds")

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

    plugin_subparsers.add_parser("list", help="List discovered plugins and metadata")
    audit = plugin_subparsers.add_parser("audit", help="Audit plugin files for sandbox compliance")
    audit.add_argument("--fail-fast", action="store_true", help="Stop on first plugin failure")

    # Server command
    server = subparsers.add_parser("server", help="Start API server")
    server.add_argument("--port", type=int, default=8000, help="Server port")
    server.add_argument("--host", default="localhost", help="Server host")
    server.add_argument("--workers", type=int, default=4, help="Number of workers")

    return parser

async def main():
    """Main entry point"""
    parser = create_cli()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return ExitCode.USAGE

    exit_code = ExitCode.OK

    # Create processor
    config = ProcessingConfig.from_environment()
    if args.max_workers is not None:
        config.max_workers = max(1, args.max_workers)
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

        had_error = False
        for result in results:
            if "error" in result:
                had_error = True
                print(f"Error processing {result['file']}: {result['error']}", file=sys.stderr)
            else:
                metadata = result["metadata"]
                print(f"\n{result['file']}:")
                print(f"  Duration: {metadata.duration:.2f}s")
                print(f"  Sample Rate: {metadata.sample_rate}Hz")
                print(f"  Channels: {metadata.channels}")
                print(f"  Peak Level: {metadata.peak_level:.3f}")
                print(f"  RMS Level: {metadata.rms_level:.3f}")

                if args.detailed:
                    print(f"  Dynamic Range: {metadata.dynamic_range:.1f}dB")
                    print(f"  Frequency Range: {metadata.frequency_range[0]:.1f}-{metadata.frequency_range[1]:.1f}Hz")
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
                                )
                            except ValueError as exc:
                                print(f"  Loudness: unsupported ({exc})")
                            else:
                                if not math.isfinite(lufs):
                                    print("  Loudness: below measurement gate (silent or too short)")
                                else:
                                    metadata.loudness_lufs = lufs
                                    print(f"  Loudness: {lufs:.1f} LUFS (integrated, "
                                          f"ITU-R BS.1770 K-weighting, no surround weighting, first "
                                          f"{LOUDNESS_MAX_SAMPLES / samples_result.data['sample_rate']:.0f}s max)")

        if args.export:
            with open(args.export, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\nAnalysis exported to {args.export}")

        if had_error:
            exit_code = ExitCode.ERROR

    elif args.command == "process":
        operations: List[str] = []
        try:
            files = [_sanitize_cli_input(path, "files") for path in args.files]
            output_dir = _sanitize_optional_input(args.output_dir, "output_dir")
            effects_path = _sanitize_optional_input(args.effects, "effects")
            _assert_unique_paths(files, "file input")
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        kwargs: Dict[str, Any] = {
            "output_dir": output_dir,
            "dry_run": args.dry_run
        }

        if args.normalize:
            operations.append("normalize")
            if args.target_peak is not None:
                kwargs["target_peak"] = args.target_peak
        if args.denoise:
            operations.append("denoise")
        if args.master:
            operations.append("master")
            kwargs["master_preset"] = args.master
        if effects_path:
            with open(effects_path) as f:
                effects = json.load(f)
            kwargs["effects"] = effects
            operations.append("effects")

        if args.convert:
            operations.append("convert")
            kwargs["format"] = args.convert_format or "wav"
            kwargs["sample_rate"] = args.convert_sample_rate
            kwargs["bit_depth"] = args.convert_bit_depth or 16

        if not operations:
            print("Error: specify at least one processing option (e.g., --normalize, --denoise, --effects, or --convert).", file=sys.stderr)
            return ExitCode.USAGE

        if args.no_parallel:
            processor.config.parallel = False
        processor.update_worker_limits()

        for operation in operations:
            results = processor.batch_process(files, operation, **kwargs)

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

    elif args.command == "stream":
        input_device = args.input_device
        output_device = args.output_device
        try:
            effects_path = _sanitize_optional_input(args.effects, "effects")
        except ValueError as exc:
            print(f"Input validation error: {exc}", file=sys.stderr)
            return ExitCode.INPUT

        if effects_path:
            with open(effects_path) as f:
                effects = json.load(f)
        else:
            effects = None

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
                    }
                }
                print(json.dumps(payload, indent=2))
            else:
                print("Registered directories:")
                for directory in sanitized_dirs:
                    print(f"  - {directory}")

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
            output_dir = _sanitize_optional_input(args.output_dir, "output_dir")
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

        kwargs: Dict[str, Any] = {
            "output_dir": output_dir,
            "format": format_arg,
        }

        if args.operation == "convert":
            kwargs["format"] = format_arg or "wav"
            kwargs["sample_rate"] = args.sample_rate
            kwargs["bit_depth"] = args.bit_depth or 16

        if args.operation == "normalize" and args.target_peak is not None:
            kwargs["target_peak"] = args.target_peak

        if args.operation == "effects":
            if not effects_path:
                print("Error: --effects <file> is required for the effects operation", file=sys.stderr)
                return ExitCode.USAGE
            with open(effects_path) as f:
                kwargs["effects"] = json.load(f)

        if args.no_parallel:
            processor.config.parallel = False
        if args.quality:
            processor.config.quality = args.quality
        processor.update_worker_limits()

        results = processor.batch_process(
            file_list, args.operation, show_progress=sys.stdout.isatty(), **kwargs
        )

        successful = sum(1 for r in results if "error" not in r)
        summary = f"Processed {successful}/{len(results)} files successfully"
        if HAS_UX_IMPROVEMENTS:
            summary = ColorText.success(summary) if successful == len(results) else ColorText.error(summary)
        print(f"\n{summary}")

        if successful != len(results):
            exit_code = ExitCode.ERROR

    elif args.command == "ml":
        # Only 'enhance' is a real operation; classify/separate/transcribe were removed
        # because they require trained models or external services — CHARTER §4 non-goals.
        audio, sr = processor.load_audio(args.input)

        if args.operation == "enhance":
            enhanced = processor.remove_noise(audio, sr)
            enhanced = processor.normalize_audio(enhanced)
            output = args.output or args.input.replace(".wav", "_enhanced.wav")
            processor.save_audio(enhanced, output, sr)
            print(f"Enhanced audio saved to {output}")

    elif args.command == "midi":
        print(f"MIDI operation '{args.operation}'")

        if args.operation in ["extract", "analyze"] and not args.input:
            print("Error: --input required for extract/analyze operations", file=sys.stderr)
            return ExitCode.USAGE

        if args.operation == "extract":
            # Extract MIDI from audio
            audio, sr = processor.load_audio(args.input)

            config = MIDIConfig(tempo=args.tempo) if HAS_MIDI else None
            notes = processor.extract_midi(audio, sr, config)

            if notes:
                print(f"Extracted {len(notes)} MIDI notes:")
                for i, note in enumerate(notes[:10]):  # Show first 10
                    print(f"  {i+1}. {note.note_name} (vel: {note.velocity}, time: {note.start_time:.2f}s)")
                if len(notes) > 10:
                    print(f"  ... and {len(notes)-10} more notes")

                # Save to MIDI file if output specified
                if args.output:
                    success = processor.generate_midi(notes, args.output)
                    if success:
                        print(f"MIDI file saved to {args.output}")
            else:
                print("No MIDI notes extracted")

        elif args.operation == "analyze":
            # Comprehensive musical analysis
            audio, sr = processor.load_audio(args.input)
            analysis = processor.analyze_music(audio, sr)

            if "error" in analysis:
                print(f"Analysis error: {analysis['error']}")
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
                    print(f"🥁 Estimated tempo: {rhythm['tempo']:.1f} BPM")

                if analysis['suggestions']['next_chords']:
                    print("🤖 Next chord suggestions:")
                    for chord, prob in analysis['suggestions']['next_chords'][:3]:
                        print(f"  {chord} (probability: {prob:.2f})")

        elif args.operation == "compose":
            # Generate a basic composition
            print("🎵 Generating musical composition...")

            # Create basic chord progression (I-V-vi-IV)
            basic_chords = [
                {"root": 0, "chord_type": "major", "notes": [0, 4, 7], "start_time": 0.0, "duration": 2.0},
                {"root": 7, "chord_type": "major", "notes": [7, 11, 2], "start_time": 2.0, "duration": 2.0},
                {"root": 9, "chord_type": "minor", "notes": [9, 0, 4], "start_time": 4.0, "duration": 2.0},
                {"root": 5, "chord_type": "major", "notes": [5, 9, 0], "start_time": 6.0, "duration": 2.0}
            ]

            key_info = {"tonic": 0, "mode": "major", "confidence": 1.0}  # C major

            melody = processor.compose_melody(basic_chords, key_info, args.length)

            if melody:
                print(f"Generated melody with {len(melody)} notes")
                if args.output:
                    success = processor.generate_midi(melody, args.output)
                    if success:
                        print(f"Composition saved to {args.output}")
            else:
                print("Failed to generate composition")

        elif args.operation == "generate":
            # Generate MIDI file from scratch
            if not args.output:
                print("Error: --output required for generate operation", file=sys.stderr)
                return ExitCode.USAGE

            print("🎼 Generating MIDI demo...")

            # Create a simple scale
            demo_notes = []
            scale_notes = [60, 62, 64, 65, 67, 69, 71, 72]  # C major scale

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
                success = processor.generate_midi(demo_notes, args.output)
                if success:
                    print(f"Demo MIDI file generated: {args.output}")
            else:
                print("Failed to generate MIDI demo")

    elif args.command == "server":
        print(f"Starting API server on {args.host}:{args.port}")
        try:
            import uvicorn  # type: ignore
        except ImportError:
            print("The API server requires fastapi and uvicorn. "
                  "Install them with: pip install -e .[api]",
                  file=sys.stderr)
            exit_code = ExitCode.ERROR
        else:
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


if __name__ == "__main__":
    sys.exit(cli())