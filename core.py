#!/usr/bin/env python3
"""
Chameleon Core - Clean audio processing engine
Functional approach with minimal interface design
"""

import os
import sys
import math
import wave
import struct
import time
try:
    from .types import (
        AudioData, AudioInfo, AudioConstants, AudioSettings, ProcessingSettings,
        ChameleonError, AudioProcessingError, FileOperationError, ValidationError,
        get_fallback_logger, validate_sample_rate, validate_frequency, validate_duration
    )
    from .logger import get_logger, get_performance_logger, get_audio_logger
    from .security import (
        SecurityConfig, InputValidator, FileSystemSecurity, memory_guard,
        security_check_decorator, SecurityLogger
    )
    from .validation import (
        AudioValidator, FileValidator, DataValidator,
        strict_validate_audio_params, strict_validate_file_path,
        validate_batch_operation, AudioParameterError, FileValidationError
    )
    LOGGER_AVAILABLE = True
    VALIDATION_AVAILABLE = True
    TYPES_AVAILABLE = True
    SECURITY_AVAILABLE = True
except ImportError:
    # Fallback for standalone usage
    import logging
    from typing import Tuple, Dict, Any
    AudioData = Tuple[bytes, int, int, int]
    AudioInfo = Dict[str, Any]
    
    class ChameleonError(Exception): pass
    class AudioProcessingError(ChameleonError): pass
    class FileOperationError(ChameleonError): pass
    class ValidationError(ChameleonError): pass
    
    LOGGER_AVAILABLE = False
    VALIDATION_AVAILABLE = False
    TYPES_AVAILABLE = False
    SECURITY_AVAILABLE = False
    
import importlib.util
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

# Configure logging
if LOGGER_AVAILABLE:
    logger = get_logger()
    perf_logger = get_performance_logger()
    audio_logger = get_audio_logger()
else:
    logger = get_fallback_logger('chameleon.core') if TYPES_AVAILABLE else logging.getLogger('chameleon.core')
    perf_logger = None
    audio_logger = None

# === Error Handling Decorators ===

from functools import wraps

def safe_audio_operation(func):
    """Decorator for safe audio operations with consistent error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except ValueError as e:
            logger.error(f"Parameter validation error in {func.__name__}: {e}")
            return None
        except MemoryError as e:
            logger.error(f"Memory error in {func.__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            return None
    return wrapper

def validate_audio_data(audio_data: AudioData) -> bool:
    """Comprehensive audio data validation"""
    if not audio_data:
        return False
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if not isinstance(data, bytes):
            return False
        if not isinstance(sample_rate, int) or sample_rate <= 0 or sample_rate > 192000:
            return False
        if not isinstance(channels, int) or channels <= 0 or channels > 32:
            return False
        if not isinstance(sample_width, int) or sample_width not in [1, 2, 4]:
            return False
        
        # Check data consistency
        if len(data) % (sample_width * channels) != 0:
            return False
            
        return True
    except (ValueError, TypeError):
        return False

# === WAV File Helper Functions ===

def _create_wav_header(data_size: int, sample_rate: int, channels: int, sample_width: int) -> bytes:
    """Create WAV file header"""
    # WAV header format
    header = b'RIFF'
    header += struct.pack('<I', data_size + 36)  # File size - 8
    header += b'WAVE'
    header += b'fmt '
    header += struct.pack('<I', 16)  # PCM format chunk size
    header += struct.pack('<H', 1)   # PCM format
    header += struct.pack('<H', channels)
    header += struct.pack('<I', sample_rate)
    header += struct.pack('<I', sample_rate * channels * sample_width)  # Byte rate
    header += struct.pack('<H', channels * sample_width)  # Block align
    header += struct.pack('<H', sample_width * 8)  # Bits per sample
    header += b'data'
    header += struct.pack('<I', data_size)
    
    return header

# === Audio Processing Functions ===

# Performance optimization cache
_SINE_LUT_SIZE = AudioConstants.LUT_SIZE if TYPES_AVAILABLE else 8192
_SINE_LUT = None

def _init_sine_lut():
    """Initialize sine lookup table for performance"""
    global _SINE_LUT
    if _SINE_LUT is None:
        _SINE_LUT = [math.sin(2.0 * math.pi * i / _SINE_LUT_SIZE) for i in range(_SINE_LUT_SIZE)]

@security_check_decorator
def generate_sine_wave(frequency: float, duration: float, sample_rate: int = None, use_lut: bool = True, channels: int = 1) -> AudioData:
    """Generate sine wave with optimized performance, security validation, and multi-channel support"""
    
    # Set default sample rate
    if sample_rate is None:
        sample_rate = AudioConstants.SAMPLE_RATE_44K if TYPES_AVAILABLE else 44100
    
    # Comprehensive security validation
    if SECURITY_AVAILABLE:
        is_valid, error_msg = InputValidator.validate_audio_parameters(
            frequency, duration, sample_rate, channels
        )
        if not is_valid:
            SecurityLogger.log_security_event(
                'INVALID_AUDIO_PARAMS',
                f"Audio parameter validation failed: {error_msg}",
                {'frequency': frequency, 'duration': duration, 'sample_rate': sample_rate, 'channels': channels},
                severity='WARNING'
            )
            raise ValueError(f"Security validation failed: {error_msg}")
    
    # Fallback validation for systems without security module
    elif TYPES_AVAILABLE:
        if not validate_frequency(frequency):
            raise ValueError(f"Frequency {frequency}Hz is out of valid range ({AudioConstants.MIN_FREQUENCY}-{AudioConstants.MAX_FREQUENCY}Hz)")
        if not validate_duration(duration):
            raise ValueError(f"Duration {duration}s is out of valid range ({AudioConstants.MIN_DURATION}-{AudioConstants.MAX_DURATION}s)")
        if not validate_sample_rate(sample_rate):
            raise ValueError(f"Sample rate {sample_rate}Hz is not supported")
    
    # Basic safety checks
    if frequency <= 0 or duration <= 0 or sample_rate <= 0 or channels <= 0:
        raise ValueError("All parameters must be positive values")
    
    frames = int(duration * sample_rate)
    total_samples = frames * channels
    
    # Enhanced memory protection
    estimated_size = total_samples * 2  # 16-bit samples
    max_size = SecurityConfig.MAX_FILE_SIZE_BYTES if SECURITY_AVAILABLE else 200 * 1024 * 1024
    
    if estimated_size > max_size:
        raise MemoryError(f"Requested audio size {estimated_size/1024/1024:.1f}MB exceeds limit {max_size/1024/1024:.1f}MB")
    
    if use_lut and frames > 1000:  # Use LUT for longer audio
        _init_sine_lut()
        angular_frequency = frequency * _SINE_LUT_SIZE / sample_rate
        amplitude = 32767.0
        
        samples = []
        phase = 0.0
        for i in range(frames):
            index = int(phase) % _SINE_LUT_SIZE
            sample_value = int(amplitude * _SINE_LUT[index])
            samples.append(sample_value)
            phase += angular_frequency
            
        data = struct.pack('<' + 'h' * frames, *samples)
    else:
        # Direct calculation for short audio or when LUT disabled
        angular_frequency = 2.0 * math.pi * frequency / sample_rate
        amplitude = 32767.0
        
        samples = [int(amplitude * math.sin(angular_frequency * i)) for i in range(frames)]
        data = struct.pack('<' + 'h' * frames, *samples)
    
    return (data, sample_rate, 1, 2)

@security_check_decorator  
def write_wav_file(filename: str, audio_data: AudioData, allow_overwrite: bool = True) -> bool:
    """Write audio data to WAV file with enterprise-grade security and validation"""
    
    # Input sanitization and validation
    if not filename or not filename.strip():
        logger.error("Empty filename provided")
        return False
    
    filename = str(filename).strip()
    
    # Security validation
    if SECURITY_AVAILABLE:
        # Validate filename security
        is_valid_filename, filename_msg = InputValidator.validate_filename(os.path.basename(filename))
        if not is_valid_filename:
            SecurityLogger.log_security_event(
                'INVALID_FILENAME',
                f"Filename validation failed: {filename_msg}",
                {'filename': filename},
                severity='WARNING'
            )
            logger.error(f"Filename validation failed: {filename_msg}")
            return False
        
        # Validate file path security
        is_valid_path, path_msg = InputValidator.validate_file_path(filename)
        if not is_valid_path:
            SecurityLogger.log_security_event(
                'INVALID_FILEPATH',
                f"File path validation failed: {path_msg}",
                {'filepath': filename},
                severity='WARNING'
            )
            logger.error(f"File path validation failed: {path_msg}")
            return False
    
    if not audio_data:
        logger.error("No audio data provided")
        return False
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        # Comprehensive audio data validation
        if not validate_audio_data(audio_data):
            logger.error("Audio data validation failed")
            return False
        
        # Enhanced file existence check
        if os.path.exists(filename):
            if not allow_overwrite:
                logger.error(f"File already exists and overwrite is disabled: {filename}")
                return False
            
            # Check if file is being used
            try:
                with open(filename, 'r+b') as test_file:
                    pass
            except (PermissionError, OSError) as e:
                logger.error(f"Cannot write to file (in use or permission denied): {filename} - {e}")
                return False
            
            logger.warning(f"Overwriting existing file: {filename}")
            
            # Log security event for file overwrite
            if SECURITY_AVAILABLE:
                SecurityLogger.log_security_event(
                    'FILE_OVERWRITE',
                    f"Overwriting existing file: {filename}",
                    {'filename': filename, 'size_bytes': len(data)},
                    severity='INFO'
                )
        
        # Use secure file writing if available
        if SECURITY_AVAILABLE:
            success, message = FileSystemSecurity.safe_file_write(filename, data)
            if not success:
                logger.error(f"Secure file write failed: {message}")
                return False
            
            # Write WAV header using the secure temporary approach
            try:
                with open(filename, 'r+b') as f:
                    f.seek(0)
                    # Write proper WAV header
                    wav_header = _create_wav_header(len(data), sample_rate, channels, sample_width)
                    temp_data = wav_header + data
                    f.seek(0)
                    f.truncate()
                    f.write(temp_data)
                    f.flush()
                    os.fsync(f.fileno())
                
                logger.info(f"Successfully wrote WAV file using secure method: {filename} ({len(data)} bytes)")
                return True
                
            except Exception as e:
                logger.error(f"WAV header write failed: {e}")
                # Try to clean up partial file
                try:
                    os.remove(filename)
                except Exception:
                    pass
                return False
        
        else:
            # Fallback to standard method with safety checks
            parent_dir = os.path.dirname(filename)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, mode=0o755, exist_ok=True)
                except Exception as e:
                    logger.error(f"Failed to create directory {parent_dir}: {e}")
                    return False
        
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(data)
        
        logger.debug(f"Successfully wrote WAV file: {filename} ({len(data)} bytes)")
        return True
        
    except PermissionError as e:
        logger.error(f"Permission denied writing WAV file {filename}: {e}")
        return False
    except OSError as e:
        logger.error(f"OS error writing WAV file {filename}: {e}")
        return False
    except wave.Error as e:
        logger.error(f"WAV format error for file {filename}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error writing WAV file {filename}: {e}")
        return False

@security_check_decorator
def read_wav_file(filename: str, max_size_mb: int = None) -> Optional[Tuple[AudioData, AudioInfo]]:
    """Read WAV file with enterprise-grade security validation and metadata extraction"""
    
    # Input validation and sanitization
    if not filename or not filename.strip():
        logger.error("Empty filename provided to read_wav_file")
        return None
    
    filename = str(filename).strip()
    
    # Security validation
    if SECURITY_AVAILABLE:
        # Validate file path security
        is_valid_path, path_msg = InputValidator.validate_file_path(filename)
        if not is_valid_path:
            SecurityLogger.log_security_event(
                'INVALID_READ_PATH',
                f"File path validation failed for read: {path_msg}",
                {'filepath': filename},
                severity='WARNING'
            )
            logger.error(f"File path validation failed: {path_msg}")
            return None
        
        # Log file access attempt
        SecurityLogger.log_security_event(
            'FILE_ACCESS_ATTEMPT',
            f"Attempting to read file: {filename}",
            {'filename': filename},
            severity='INFO'
        )
    
    # Enhanced file existence and type checks
    if not os.path.exists(filename):
        logger.error(f"File not found: {filename}")
        return None
    
    if not os.path.isfile(filename):
        logger.error(f"Path is not a file: {filename}")
        return None
        
    try:
        # Check file size
        file_size = os.path.getsize(filename)
        if file_size == 0:
            logger.warning(f"Empty file: {filename}")
            return None
        if file_size > 100 * 1024 * 1024:  # 100MB limit
            logger.warning(f"Large file detected ({file_size / 1024 / 1024:.1f}MB): {filename}")
        
        with wave.open(filename, 'rb') as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            
            # Validate WAV parameters
            if channels <= 0 or channels > 32:
                logger.error(f"Invalid channel count: {channels} in file: {filename}")
                return None
            if sample_rate <= 0 or sample_rate > 192000:
                logger.error(f"Invalid sample rate: {sample_rate} in file: {filename}")
                return None
            if sample_width not in [1, 2, 4]:
                logger.error(f"Unsupported sample width: {sample_width} in file: {filename}")
                return None
                
            data = wav_file.readframes(frames)
            
            if len(data) == 0:
                logger.warning(f"No audio data in file: {filename}")
                return None
            
            audio_data = (data, sample_rate, channels, sample_width)
            audio_info = {
                'filename': filename,
                'duration': float(frames) / sample_rate if sample_rate > 0 else 0,
                'frames': frames,
                'size_bytes': len(data),
                'channels': channels,
                'sample_rate': sample_rate,
                'sample_width': sample_width
            }
            
            logger.debug(f"Successfully read WAV file: {filename} ({len(data)} bytes, {channels}ch, {sample_rate}Hz)")
            return (audio_data, audio_info)
            
    except PermissionError as e:
        logger.error(f"Permission denied reading WAV file {filename}: {e}")
        return None
    except wave.Error as e:
        logger.error(f"WAV format error in file {filename}: {e}")
        return None
    except OSError as e:
        logger.error(f"OS error reading WAV file {filename}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading WAV file {filename}: {e}")
        return None

def get_system_capabilities() -> Dict[str, bool]:
    """Detect available system capabilities"""
    caps = {'basic_audio': True}
    
    # Check for optional dependencies
    
    for module in ['soundfile', 'sounddevice', 'librosa', 'numpy', 'yaml', 'psutil']:
        try:
            spec = importlib.util.find_spec(module)
            caps[module] = spec is not None
        except Exception:
            caps[module] = False
    
    # Additional feature flags
    caps['advanced_audio_available'] = caps.get('librosa', False) and caps.get('numpy', False)
    caps['io_available'] = caps.get('soundfile', False) and caps.get('sounddevice', False)
    caps['yaml_available'] = caps.get('yaml', False)
    
    return caps

def validate_audio_params(frequency: float, duration: float, sample_rate: int) -> bool:
    """Validate audio parameters"""
    return (
        20.0 <= frequency <= 20000.0 and
        0.01 <= duration <= 60.0 and
        8000 <= sample_rate <= 192000
    )

# === Utility Functions ===

def ensure_output_dir(path: str) -> bool:
    """Ensure output directory exists"""
    if not path or not path.strip():
        logger.error("Empty path provided to ensure_output_dir")
        return False
        
    try:
        directory = os.path.dirname(path) if os.path.dirname(path) else '.'
        
        # Check if directory already exists
        if os.path.exists(directory):
            if not os.path.isdir(directory):
                logger.error(f"Path exists but is not a directory: {directory}")
                return False
            if not os.access(directory, os.W_OK):
                logger.error(f"No write permission for directory: {directory}")
                return False
            return True
        
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Created directory: {directory}")
        return True
        
    except PermissionError as e:
        logger.error(f"Permission denied creating directory for path {path}: {e}")
        return False
    except OSError as e:
        logger.error(f"OS error creating directory for path {path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating directory for path {path}: {e}")
        return False


# Note: batch_generate_tones has been moved to batch_processor.py for better organization
# Import from batch_processor if you need this functionality

def normalize_audio(audio_data: AudioData, target_amplitude: float = 0.8) -> Optional[AudioData]:
    """Normalize audio data amplitude with optimized performance"""
    if not audio_data:
        logger.error("No audio data provided to normalize_audio")
        return None
        
    if not (0.1 <= target_amplitude <= 1.0):
        logger.error(f"Invalid target amplitude: {target_amplitude} (must be 0.1-1.0)")
        return None
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        # Fast validation
        if not data or sample_width != 2 or len(data) % 2 != 0:
            return None
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        if not samples:
            return audio_data
        
        # Optimized max amplitude calculation
        max_amplitude = max(abs(s) for s in samples)
        
        if max_amplitude == 0:
            logger.debug("Silent audio detected, no normalization needed")
            return audio_data
        
        # Calculate normalization factor
        scale_factor = (32767 * target_amplitude) / max_amplitude
        
        # Vectorized normalization with clipping
        normalized_samples = [
            max(-32768, min(32767, int(sample * scale_factor)))
            for sample in samples
        ]
        
        normalized_data = struct.pack('<' + 'h' * len(normalized_samples), *normalized_samples)
        
        logger.debug(f"Successfully normalized audio: {len(samples)} samples")
        return (normalized_data, sample_rate, channels, sample_width)
        
    except struct.error as e:
        logger.error(f"Struct packing error in normalize_audio: {e}")
        return None
    except ValueError as e:
        logger.error(f"Value error in normalize_audio: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in normalize_audio: {e}")
        return None

def trim_silence(audio_data: AudioData, threshold: float = 0.01) -> Optional[AudioData]:
    """Trim silence from audio data with optimized search"""
    if not audio_data or not (0.001 <= threshold <= 0.1):
        return None
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        # Fast validation
        if not data or sample_width != 2 or len(data) % 2 != 0:
            return None
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        if not samples:
            return audio_data
        
        # Convert threshold to absolute value once
        threshold_abs = int(32767 * threshold)
        
        # Optimized search for start position
        start_idx = 0
        for i, sample in enumerate(samples):
            if abs(sample) > threshold_abs:
                start_idx = i
                break
        else:
            # Entirely silent
            return audio_data
        
        # Optimized search for end position (reverse)
        end_idx = len(samples) - 1
        for i in range(len(samples) - 1, start_idx - 1, -1):
            if abs(samples[i]) > threshold_abs:
                end_idx = i
                break
        
        # Early return if no trimming needed
        if start_idx == 0 and end_idx == len(samples) - 1:
            return audio_data
        
        # Perform trimming
        trimmed_samples = samples[start_idx:end_idx + 1]
        trimmed_data = struct.pack('<' + 'h' * len(trimmed_samples), *trimmed_samples)
        
        logger.debug(f"Trimmed silence: {len(samples)} -> {len(trimmed_samples)} samples")
        return (trimmed_data, sample_rate, channels, sample_width)
        
    except struct.error as e:
        logger.error(f"Struct packing error in trim_silence: {e}")
        return None
    except ValueError as e:
        logger.error(f"Value error in trim_silence: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in trim_silence: {e}")
        return None

def mix_audio(audio1: AudioData, audio2: AudioData, ratio: float = 0.5) -> Optional[AudioData]:
    """Mix two audio streams with optimized processing"""
    if not audio1 or not audio2 or not (0.0 <= ratio <= 1.0):
        return None
    
    try:
        data1, sr1, ch1, sw1 = audio1
        data2, sr2, ch2, sw2 = audio2
        
        # Fast compatibility check
        if (not data1 or not data2 or sr1 != sr2 or ch1 != ch2 or 
            sw1 != sw2 or sw1 != 2 or len(data1) % 2 != 0 or len(data2) % 2 != 0):
            return None
        
        samples1 = struct.unpack('<' + 'h' * (len(data1) // 2), data1)
        samples2 = struct.unpack('<' + 'h' * (len(data2) // 2), data2)
        
        if not samples1 or not samples2:
            return None
        
        # Mix samples up to minimum length
        min_len = min(len(samples1), len(samples2))
        if min_len == 0:
            return None
        
        # Pre-calculate ratio complement
        ratio_comp = 1.0 - ratio
        
        # Vectorized mixing with clipping
        mixed_samples = [
            max(-32768, min(32767, int(samples1[i] * ratio + samples2[i] * ratio_comp)))
            for i in range(min_len)
        ]
        
        mixed_data = struct.pack('<' + 'h' * len(mixed_samples), *mixed_samples)
        
        logger.debug(f"Mixed audio: {len(mixed_samples)} samples")
        return (mixed_data, sr1, ch1, sw1)
        
    except struct.error as e:
        logger.error(f"Struct packing error in mix_audio: {e}")
        return None
    except ValueError as e:
        logger.error(f"Value error in mix_audio: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in mix_audio: {e}")
        return None


def adjust_volume(audio_data: AudioData, volume_factor: float) -> Optional[AudioData]:
    """Adjust audio volume by factor with optimized processing"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if sample_width != 2 or not (0.0 <= volume_factor <= 10.0):
            return None
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        # Optimized volume adjustment with vectorized clipping
        adjusted_samples = [
            max(-32768, min(32767, int(sample * volume_factor)))
            for sample in samples
        ]
        
        adjusted_data = struct.pack('<' + 'h' * len(adjusted_samples), *adjusted_samples)
        
        return (adjusted_data, sample_rate, channels, sample_width)
        
    except Exception:
        return None



def get_file_size(path: str) -> int:
    """ファイルサイズ取得の単一責任"""
    try:
        return os.path.getsize(path)
    except Exception:
        return 0

def get_file_size_mb(filepath: str) -> float:
    """Get file size in MB"""
    try:
        return Path(filepath).stat().st_size / (1024 * 1024)
    except Exception:
        return 0.0

def is_audio_file(filepath: str) -> bool:
    """Check if file is audio format by extension"""
    audio_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac'}
    return Path(filepath).suffix.lower() in audio_extensions

def format_duration(seconds: float) -> str:
    """Format seconds to human-readable time format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

class PerformanceTimer:
    """Lightweight performance measurement"""
    def __init__(self, name: str = "Operation", log_result: bool = True):
        self.name = name
        self.log_result = log_result
        self.start_time = None
        self.elapsed_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.elapsed_time = time.perf_counter() - self.start_time
            if self.log_result:
                if LOGGER_AVAILABLE and perf_logger:
                    perf_logger.info(f"{self.name}: {self.elapsed_time:.3f}s")
                else:
                    print(f"{self.name}: {self.elapsed_time:.3f}s")
        return False
    
    def get_elapsed(self) -> Optional[float]:
        """Get elapsed time after context exit"""
        return self.elapsed_time

# === Pike原則: 組み合わせ可能なユーティリティ ===

def chain_audio_processors(*processors):
    """関数の組み合わせによる音声処理パイプライン"""
    def process(audio_data: AudioData) -> AudioData:
        result = audio_data
        for processor in processors:
            if result is None:
                break
            result = processor(result)
        return result
    return process

def create_waveform_data(audio_data: AudioData, width: int = 800) -> Optional[List[float]]:
    """Generate waveform data for visualization with optimized sampling"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if sample_width != 2:
            return None
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        if not samples:
            return None
        
        # Optimized downsampling to screen width
        step = max(1, len(samples) // width)
        
        # Pre-allocate list for better performance
        waveform = []
        waveform_append = waveform.append  # Cache method reference
        
        for i in range(0, len(samples), step):
            # Calculate chunk average more efficiently
            chunk_end = min(i + step, len(samples))
            chunk_sum = sum(samples[i:chunk_end])
            chunk_avg = chunk_sum / (chunk_end - i)
            # Normalize to -1.0 to 1.0 range
            waveform_append(chunk_avg / 32767.0)
        
        return waveform
        
    except Exception:
        return None

def concatenate_audio(*audio_list) -> Optional[AudioData]:
    """Concatenate multiple audio clips with optimized processing"""
    try:
        if not audio_list:
            return None
        
        # Use first audio as reference for format
        first_audio = audio_list[0]
        data0, sr0, ch0, sw0 = first_audio
        
        # Pre-allocate combined samples list
        combined_samples = []
        
        for audio_data in audio_list:
            data, sample_rate, channels, sample_width = audio_data
            
            # Skip incompatible audio
            if sample_rate != sr0 or channels != ch0 or sample_width != sw0:
                continue
            
            samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            combined_samples.extend(samples)
        
        if not combined_samples:
            return None
        
        combined_data = struct.pack('<' + 'h' * len(combined_samples), *combined_samples)
        
        return (combined_data, sr0, ch0, sw0)
        
    except Exception:
        return None


def apply_low_pass_filter(audio_data: AudioData, cutoff_ratio: float = 0.3) -> Optional[AudioData]:
    """Simple low-pass filter (reduces high frequency components)"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if sample_width != 2 or cutoff_ratio <= 0:
            return None if sample_width != 2 else audio_data
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        if not samples:
            return audio_data
        
        # Simple moving average filter
        window_size = max(1, int(1.0 / cutoff_ratio))
        half_window = window_size // 2
        
        # Optimized filtering with list comprehension
        filtered_samples = [
            sum(samples[max(0, i - half_window):min(len(samples), i + half_window + 1)]) //
            (min(len(samples), i + half_window + 1) - max(0, i - half_window))
            for i in range(len(samples))
        ]
        
        filtered_data = struct.pack('<' + 'h' * len(filtered_samples), *filtered_samples)
        
        return (filtered_data, sample_rate, channels, sample_width)
        
    except Exception:
        return None

def generate_chord(frequencies: List[float], duration: float = 1.0, sample_rate: int = 44100) -> Optional[AudioData]:
    """和音（複数周波数の重ね合わせ）を生成"""
    try:
        if not frequencies:
            return None
        
        # 各周波数の音声を生成
        audio_list = []
        for freq in frequencies:
            if validate_audio_params(freq, duration, sample_rate):
                audio = generate_sine_wave(freq, duration, sample_rate)
                audio_list.append(audio)
        
        if not audio_list:
            return None
        
        # 最初の音声をベースにして、他を重ね合わせる
        result = audio_list[0]
        for audio in audio_list[1:]:
            result = mix_audio(result, audio, 0.5)
            if result is None:
                break
        
        # 音量を調整（重ね合わせで音量が大きくなりすぎるのを防ぐ）
        if result:
            volume_factor = 1.0 / len(frequencies)
            result = adjust_volume(result, volume_factor)
        
        return result
        
    except Exception:
        return None


# === Error Handling ===

class ChameleonError(Exception):
    """Base exception for Chameleon operations"""
    pass

def safe_file_operation(operation: callable, filepath: str, *args, **kwargs) -> Tuple[bool, str]:
    """Execute file operations safely with validation"""
    try:
        # File path validation (Windows MAX_PATH limit consideration)
        if not filepath or len(filepath) > 260:
            return False, "Invalid file path"
        
        # Dangerous character validation
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in filepath for char in dangerous_chars):
            return False, "File path contains dangerous characters"
        
        # Execute operation
        result = operation(filepath, *args, **kwargs)
        return True, "Success" if result else "Operation failed"
        
    except PermissionError:
        return False, "File access permission denied"
    except FileNotFoundError:
        return False, "File not found"
    except OSError as e:
        return False, f"File system error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def validate_audio_data(audio_data: AudioData) -> Tuple[bool, str]:
    """Validate audio data integrity"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        # Basic checks
        if not data:
            return False, "Audio data is empty"
        
        if sample_rate <= 0 or sample_rate > 192000:
            return False, f"Invalid sample rate: {sample_rate}"
        
        if channels <= 0 or channels > 8:
            return False, f"Invalid channel count: {channels}"
        
        if sample_width not in [1, 2, 3, 4]:
            return False, f"Invalid sample width: {sample_width}"
        
        # Data consistency check
        expected_size = len(data) // (channels * sample_width)
        if expected_size * channels * sample_width != len(data):
            return False, "Audio data size inconsistency"
        
        # Size validation (100MB limit)
        if len(data) > 100 * 1024 * 1024:
            return False, "Audio data too large"
        
        return True, "Audio data is valid"
        
    except Exception as e:
        return False, f"Audio data validation error: {e}"

def robust_generate_sine_wave(frequency: float, duration: float, 
                             sample_rate: int = 44100, use_lut: bool = True) -> Optional[AudioData]:
    """Generate sine wave with robust error handling and optimized performance"""
    try:
        # Parameter validation
        if not validate_audio_params(frequency, duration, sample_rate):
            logger.warning(f"Invalid parameters: freq={frequency}, dur={duration}, sr={sample_rate}")
            return None
        
        # Audio generation with performance timer
        with PerformanceTimer(f"Sine wave generation {frequency}Hz", log_result=False):
            audio_data = generate_sine_wave(frequency, duration, sample_rate, use_lut)
        
        # Generated data validation
        is_valid, message = validate_audio_data(audio_data)
        if not is_valid:
            logger.error(f"Generated audio data invalid: {message}")
            return None
        
        return audio_data
        
    except MemoryError:
        logger.error("Memory insufficient: generate shorter audio")
        return None
    except OverflowError:
        logger.error("Numeric overflow: adjust parameters")
        return None
    except Exception as e:
        logger.error(f"Audio generation error: {e}")
        return None

def system_health_check() -> Dict[str, Any]:
    """Perform comprehensive system health check"""
    health_status = {
        'overall': True,
        'checks': {},
        'warnings': [],
        'errors': []
    }
    
    try:
        # Memory usage check
        try:
            import psutil
            process = psutil.Process()
            memory_percent = process.memory_percent()
            health_status['checks']['memory'] = memory_percent < 80
            if memory_percent > 80:
                health_status['warnings'].append(f"High memory usage: {memory_percent:.1f}%")
        except ImportError:
            health_status['checks']['memory'] = True  # Skip if psutil unavailable
        
        # Disk space check
        import shutil
        free_space = shutil.disk_usage('.').free / (1024**3)  # GB
        health_status['checks']['disk_space'] = free_space > 1
        if free_space < 1:
            health_status['warnings'].append(f"Low disk space: {free_space:.1f}GB")
        
        # Basic function check
        test_audio = robust_generate_sine_wave(440, 0.01)
        health_status['checks']['audio_generation'] = test_audio is not None
        if not test_audio:
            health_status['errors'].append("Audio generation function has issues")
        
        # Configuration check
        try:
            config = load_config()
            health_status['checks']['configuration'] = len(config) > 0
        except Exception:
            health_status['checks']['configuration'] = False
            health_status['errors'].append("Configuration loading failed")
        
        # Overall health determination
        health_status['overall'] = (
            all(health_status['checks'].values()) and 
            len(health_status['errors']) == 0
        )
        
        return health_status
        
    except Exception as e:
        return {
            'overall': False,
            'checks': {},
            'warnings': [],
            'errors': [f"Health check execution error: {e}"]
        }

# === Configuration Management ===

DEFAULT_CONFIG = {
    'sample_rate': 44100,
    'channels': 1,
    'format': 'wav',
    'app': {
        'name': 'Chameleon Voice Processor',
        'lang': 'en'
    },
    'audio': {
        'sample_rate': 44100,
        'channels': 1,
        'format': 'wav',
        'default_frequency': 440.0,
        'default_duration': 1.0
    },
    'performance': {
        'enable_cache': True,
        'max_cache_size': 100
    }
}

def load_config(path: str = 'config.yaml') -> Dict[str, Any]:
    """Load configuration from YAML or JSON file"""
    config = DEFAULT_CONFIG.copy()
    
    if not os.path.exists(path):
        return config
    
    try:
        if path.endswith('.yaml') or path.endswith('.yml'):
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    _merge_config(config, loaded)
        
        elif path.endswith('.json'):
            import json
            with open(path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    _merge_config(config, loaded)
                    
    except Exception:
        pass
    
    return config

def _merge_config(base: Dict[str, Any], update: Dict[str, Any]) -> None:
    """Recursively merge configuration dictionaries"""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge_config(base[key], value)
        else:
            base[key] = value


# Performance optimization functions
def get_performance_stats() -> Dict[str, Any]:
    """Get current performance statistics"""
    stats = {
        'sine_lut_initialized': _SINE_LUT is not None,
        'lut_size': _SINE_LUT_SIZE
    }
    
    try:
        import psutil
        process = psutil.Process()
        stats.update({
            'memory_usage_mb': process.memory_info().rss / (1024 * 1024),
            'cpu_percent': process.cpu_percent()
        })
    except ImportError:
        pass
    
    return stats

def optimize_for_batch_processing():
    """Optimize system for batch processing operations"""
    # Pre-initialize sine LUT for better performance
    _init_sine_lut()
    logger.info("System optimized for batch processing")

def get_file_size(filepath: str) -> int:
    """Get file size in bytes with error handling"""
    try:
        return os.path.getsize(filepath)
    except OSError:
        return 0

def is_valid_audio_file(filepath: str) -> bool:
    """Check if file is a valid audio file"""
    if not os.path.exists(filepath):
        return False
    
    try:
        result = read_wav_file(filepath)
        return result is not None
    except Exception:
        return False

def create_silence(duration: float, sample_rate: int = None, channels: int = 1) -> AudioData:
    """Create silence audio data with support for multi-channel"""
    if sample_rate is None:
        sample_rate = AudioConstants.SAMPLE_RATE_44K if TYPES_AVAILABLE else 44100
    
    frames = int(duration * sample_rate)
    total_samples = frames * channels
    data = struct.pack('<' + 'h' * total_samples, *([0] * total_samples))
    return (data, sample_rate, channels, 2)

def loop_audio(audio_data: AudioData, loop_count: int) -> Optional[AudioData]:
    """Loop audio data specified number of times"""
    if not audio_data or loop_count <= 0:
        return None
    
    if loop_count == 1:
        return audio_data
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        looped_data = data * loop_count
        return (looped_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Audio looping failed: {e}")
        return None

def calculate_rms(audio_data: AudioData) -> Optional[float]:
    """Calculate RMS (Root Mean Square) amplitude"""
    try:
        data, _, _, sample_width = audio_data
        
        if sample_width != 2 or not data:
            return None
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        if not samples:
            return 0.0
            
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        return rms / 32767.0  # Normalize to 0-1 range
        
    except Exception as e:
        logger.error(f"RMS calculation failed: {e}")
        return None

def mono_to_stereo(audio_data: AudioData) -> Optional[AudioData]:
    """Convert mono audio to stereo by duplicating the channel"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if channels != 1 or sample_width != 2:
            return audio_data  # Already stereo or unsupported format
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        # Duplicate each sample for stereo
        stereo_samples = []
        for sample in samples:
            stereo_samples.extend([sample, sample])
        
        stereo_data = struct.pack('<' + 'h' * len(stereo_samples), *stereo_samples)
        return (stereo_data, sample_rate, 2, sample_width)
        
    except Exception as e:
        logger.error(f"Mono to stereo conversion failed: {e}")
        return None

def stereo_to_mono(audio_data: AudioData) -> Optional[AudioData]:
    """Convert stereo audio to mono by averaging channels"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if channels != 2 or sample_width != 2:
            return audio_data  # Already mono or unsupported format
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        # Average left and right channels
        mono_samples = []
        for i in range(0, len(samples), 2):
            if i + 1 < len(samples):
                avg = (samples[i] + samples[i + 1]) // 2
                mono_samples.append(avg)
        
        mono_data = struct.pack('<' + 'h' * len(mono_samples), *mono_samples)
        return (mono_data, sample_rate, 1, sample_width)
        
    except Exception as e:
        logger.error(f"Stereo to mono conversion failed: {e}")
        return None

def concatenate_audio(audio_list: List[AudioData]) -> Optional[AudioData]:
    """Concatenate multiple audio data objects"""
    if not audio_list:
        return None
    
    try:
        first_audio = audio_list[0]
        _, sample_rate, channels, sample_width = first_audio
        
        # Validate all audio has same format
        for audio in audio_list[1:]:
            _, sr, ch, sw = audio
            if sr != sample_rate or ch != channels or sw != sample_width:
                logger.error("Audio format mismatch in concatenation")
                return None
        
        # Concatenate data
        combined_data = b''.join(audio[0] for audio in audio_list)
        
        return (combined_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Error concatenating audio: {e}")
        return None

def adjust_volume(audio_data: AudioData, volume_factor: float) -> Optional[AudioData]:
    """Adjust audio volume by factor"""
    if not audio_data or volume_factor <= 0:
        return None
    
    try:
        data, sample_rate, channels, sample_width = audio_data
        
        if sample_width != 2:
            return None
        
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        
        # Apply volume adjustment with clipping
        adjusted_samples = [
            max(-32768, min(32767, int(sample * volume_factor)))
            for sample in samples
        ]
        
        adjusted_data = struct.pack('<' + 'h' * len(adjusted_samples), *adjusted_samples)
        
        return (adjusted_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Error adjusting volume: {e}")
        return None

def detect_audio_properties(filepath: str) -> Optional[Dict[str, Any]]:
    """Detect comprehensive audio file properties"""
    result = read_wav_file(filepath)
    if not result:
        return None
    
    audio_data, audio_info = result
    data, sample_rate, channels, sample_width = audio_data
    
    # Calculate additional properties
    duration = audio_info.get('duration', 0)
    file_size = get_file_size(filepath)
    
    # Analyze audio content
    if sample_width == 2 and len(data) > 0:
        samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
        max_amplitude = max(abs(s) for s in samples) if samples else 0
        rms_amplitude = (sum(s * s for s in samples) / len(samples)) ** 0.5 if samples else 0
        
        properties = {
            'filepath': filepath,
            'format': 'wav',
            'duration_seconds': duration,
            'file_size_bytes': file_size,
            'file_size_mb': file_size / (1024 * 1024),
            'sample_rate': sample_rate,
            'channels': channels,
            'bit_depth': sample_width * 8,
            'frame_count': len(samples) // channels if channels > 0 else 0,
            'max_amplitude': max_amplitude,
            'max_amplitude_ratio': max_amplitude / 32767 if max_amplitude > 0 else 0,
            'rms_amplitude': rms_amplitude,
            'rms_amplitude_ratio': rms_amplitude / 32767 if rms_amplitude > 0 else 0,
            'estimated_quality': 'high' if sample_rate >= 44100 else 'medium' if sample_rate >= 22050 else 'low',
            'is_clipped': max_amplitude >= 32767,
            'is_silent': max_amplitude == 0,
            'dynamic_range_db': 20 * math.log10(max_amplitude / max(1, rms_amplitude)) if rms_amplitude > 0 else 0
        }
        
        return properties
    
    return None

def get_audio_summary(filepath: str) -> str:
    """Get human-readable audio file summary"""
    props = detect_audio_properties(filepath)
    if not props:
        return "Unable to analyze audio file"
    
    duration = props['duration_seconds']
    quality = props['estimated_quality']
    size_mb = props['file_size_mb']
    
    summary = f"{duration:.1f}s, {quality} quality ({props['sample_rate']}Hz)"
    if props['channels'] > 1:
        summary += f", {props['channels']} channels"
    summary += f", {size_mb:.1f}MB"
    
    if props['is_silent']:
        summary += " [SILENT]"
    elif props['is_clipped']:
        summary += " [CLIPPED]"
        
    return summary

if __name__ == '__main__':
    # Lightweight core functionality test
    print("🧪 Core Function Test")
    
    # Test 1: Audio generation with performance timing
    with PerformanceTimer("Audio generation test"):
        audio = generate_sine_wave(440, 0.1)
        success = write_wav_file('test.wav', audio)
    print(f"Audio generation: {'✅' if success else '❌'}")
    
    # Test 2: File reading
    result = read_wav_file('test.wav')
    print(f"Audio reading: {'✅' if result else '❌'}")
    
    # Test 3: Capability detection
    caps = get_system_capabilities()
    print(f"Capability detection: {sum(caps.values())}/{len(caps)} available")
    
    # Test 4: Performance optimization
    print("Performance stats:", get_performance_stats())
    
    # Cleanup
    try:
        os.remove('test.wav')
    except Exception:
        pass