#!/usr/bin/env python3
"""
Common types, constants and shared utilities for Chameleon.
Centralizes frequently used definitions to eliminate duplication.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List, Union
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

# === Core Data Types ===

AudioData = Tuple[bytes, int, int, int]  # (data, sample_rate, channels, sample_width)
AudioInfo = Dict[str, Any]

# === Audio Constants ===

class AudioConstants:
    """Audio processing constants"""
    
    # Sample rates (Hz)
    SAMPLE_RATE_8K = 8000
    SAMPLE_RATE_16K = 16000
    SAMPLE_RATE_22K = 22050
    SAMPLE_RATE_44K = 44100
    SAMPLE_RATE_48K = 48000
    SAMPLE_RATE_96K = 96000
    
    STANDARD_SAMPLE_RATES = [
        SAMPLE_RATE_8K, SAMPLE_RATE_16K, SAMPLE_RATE_22K,
        SAMPLE_RATE_44K, SAMPLE_RATE_48K, SAMPLE_RATE_96K
    ]
    
    # Bit depths
    BIT_DEPTH_8 = 8
    BIT_DEPTH_16 = 16
    BIT_DEPTH_24 = 24
    BIT_DEPTH_32 = 32
    
    VALID_BIT_DEPTHS = [BIT_DEPTH_8, BIT_DEPTH_16, BIT_DEPTH_24, BIT_DEPTH_32]
    
    # Channels
    MONO = 1
    STEREO = 2
    SURROUND_4 = 4
    SURROUND_6 = 6
    SURROUND_8 = 8
    
    VALID_CHANNELS = [MONO, STEREO, SURROUND_4, SURROUND_6, SURROUND_8]
    
    # Audio formats
    FORMAT_WAV = 'wav'
    FORMAT_MP3 = 'mp3'
    FORMAT_FLAC = 'flac'
    FORMAT_OGG = 'ogg'
    FORMAT_AAC = 'aac'
    FORMAT_M4A = 'm4a'
    
    SUPPORTED_FORMATS = [
        FORMAT_WAV, FORMAT_MP3, FORMAT_FLAC, 
        FORMAT_OGG, FORMAT_AAC, FORMAT_M4A
    ]
    
    # Quality settings
    QUALITY_LOW = 'low'
    QUALITY_MEDIUM = 'medium'
    QUALITY_HIGH = 'high'
    QUALITY_LOSSLESS = 'lossless'
    
    VALID_QUALITIES = [QUALITY_LOW, QUALITY_MEDIUM, QUALITY_HIGH, QUALITY_LOSSLESS]
    
    # Frequency ranges
    MIN_FREQUENCY = 1.0
    MAX_FREQUENCY = 96000.0
    HUMAN_HEARING_MIN = 20.0
    HUMAN_HEARING_MAX = 20000.0
    
    # Duration limits
    MIN_DURATION = 0.001
    MAX_DURATION = 3600.0  # 1 hour
    
    # Performance optimization
    LUT_SIZE = 8192
    CACHE_SIZE_DEFAULT = 32
    MAX_WORKERS_DEFAULT = 4

class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class ProcessingMode(Enum):
    """Processing mode enumeration"""
    FAST = auto()
    STANDARD = auto()
    HIGH_QUALITY = auto()

# === Common Data Classes ===

@dataclass
class AudioSettings:
    """Unified audio processing settings"""
    frequency: float = 440.0
    duration: float = 1.0
    sample_rate: int = AudioConstants.SAMPLE_RATE_44K
    channels: int = AudioConstants.MONO
    bit_depth: int = AudioConstants.BIT_DEPTH_16
    format: str = AudioConstants.FORMAT_WAV
    quality: str = AudioConstants.QUALITY_HIGH
    amplitude: float = 0.8

@dataclass
class ProcessingSettings:
    """Processing performance settings"""
    max_workers: int = AudioConstants.MAX_WORKERS_DEFAULT
    enable_cache: bool = True
    cache_size: int = AudioConstants.CACHE_SIZE_DEFAULT
    fast_mode: bool = True
    parallel_processing: bool = True
    mode: ProcessingMode = ProcessingMode.STANDARD

@dataclass
class FileSettings:
    """File handling settings"""
    output_dir: str = './output'
    temp_dir: str = './temp'
    organize_by_date: bool = False
    organize_by_format: bool = True
    preserve_metadata: bool = True
    max_file_size_mb: int = 100

# === Exception Classes ===

class ChameleonError(Exception):
    """Base exception for Chameleon audio processing"""
    pass

class AudioProcessingError(ChameleonError):
    """Audio processing specific errors"""
    pass

class FileOperationError(ChameleonError):
    """File I/O specific errors"""
    pass

class ValidationError(ChameleonError):
    """Parameter validation errors"""
    pass

class ConfigurationError(ChameleonError):
    """Configuration and setup errors"""
    pass

# === Common Utilities ===

def get_fallback_logger(name: str = 'chameleon') -> logging.Logger:
    """Get fallback logger with standard configuration"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def detect_audio_format(filepath: str) -> str:
    """Detect audio format from file extension"""
    ext = Path(filepath).suffix.lower().lstrip('.')
    return ext if ext in AudioConstants.SUPPORTED_FORMATS else AudioConstants.FORMAT_WAV

def validate_sample_rate(sample_rate: int) -> bool:
    """Validate if sample rate is supported"""
    return sample_rate in AudioConstants.STANDARD_SAMPLE_RATES

def validate_bit_depth(bit_depth: int) -> bool:
    """Validate if bit depth is supported"""
    return bit_depth in AudioConstants.VALID_BIT_DEPTHS

def validate_channels(channels: int) -> bool:
    """Validate if channel count is supported"""
    return channels in AudioConstants.VALID_CHANNELS

def validate_frequency(frequency: float) -> bool:
    """Validate if frequency is in valid range"""
    return AudioConstants.MIN_FREQUENCY <= frequency <= AudioConstants.MAX_FREQUENCY

def validate_duration(duration: float) -> bool:
    """Validate if duration is in valid range"""
    return AudioConstants.MIN_DURATION <= duration <= AudioConstants.MAX_DURATION

def get_quality_bitrate(quality: str, format: str = 'mp3') -> int:
    """Get bitrate for quality setting"""
    if format == 'mp3':
        return {
            AudioConstants.QUALITY_LOW: 128,
            AudioConstants.QUALITY_MEDIUM: 192,
            AudioConstants.QUALITY_HIGH: 320,
        }.get(quality, 192)
    return 0

def ensure_dir_exists(path: str) -> bool:
    """Ensure directory exists, create if necessary"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False

def get_file_size_mb(filepath: str) -> float:
    """Get file size in megabytes"""
    try:
        size_bytes = Path(filepath).stat().st_size
        return size_bytes / (1024 * 1024)
    except OSError:
        return 0.0