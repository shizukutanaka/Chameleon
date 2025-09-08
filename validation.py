#!/usr/bin/env python3
"""
Centralized validation and error handling for Chameleon.
Provides robust validation functions with specific error types.
"""

import os
import re
from typing import Tuple, Any, Optional, List
from pathlib import Path

# Import logger
try:
    from .logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Base class for validation errors"""
    pass

class AudioParameterError(ValidationError):
    """Raised when audio parameters are invalid"""
    pass

class FileValidationError(ValidationError):
    """Raised when file validation fails"""
    pass

class PathValidationError(ValidationError):
    """Raised when path validation fails"""
    pass

class AudioValidator:
    """Centralized audio parameter validation"""
    
    # Audio parameter limits
    MIN_FREQUENCY = 1.0
    MAX_FREQUENCY = 96000.0
    MIN_DURATION = 0.001
    MAX_DURATION = 3600.0  # 1 hour max
    MIN_SAMPLE_RATE = 8000
    MAX_SAMPLE_RATE = 192000
    VALID_CHANNELS = [1, 2, 4, 6, 8]
    VALID_BIT_DEPTHS = [8, 16, 24, 32]
    
    @classmethod
    def validate_frequency(cls, frequency: float) -> Tuple[bool, str]:
        """Validate audio frequency parameter"""
        try:
            freq = float(frequency)
            if not (cls.MIN_FREQUENCY <= freq <= cls.MAX_FREQUENCY):
                return False, f"Frequency {freq}Hz outside valid range ({cls.MIN_FREQUENCY}-{cls.MAX_FREQUENCY}Hz)"
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid frequency value: {frequency}"
    
    @classmethod
    def validate_duration(cls, duration: float) -> Tuple[bool, str]:
        """Validate audio duration parameter"""
        try:
            dur = float(duration)
            if not (cls.MIN_DURATION <= dur <= cls.MAX_DURATION):
                return False, f"Duration {dur}s outside valid range ({cls.MIN_DURATION}-{cls.MAX_DURATION}s)"
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid duration value: {duration}"
    
    @classmethod
    def validate_sample_rate(cls, sample_rate: int) -> Tuple[bool, str]:
        """Validate sample rate parameter"""
        try:
            sr = int(sample_rate)
            if not (cls.MIN_SAMPLE_RATE <= sr <= cls.MAX_SAMPLE_RATE):
                return False, f"Sample rate {sr}Hz outside valid range ({cls.MIN_SAMPLE_RATE}-{cls.MAX_SAMPLE_RATE}Hz)"
            
            # Check if it's a common sample rate
            common_rates = [8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000, 176400, 192000]
            if sr not in common_rates:
                logger.warning(f"Unusual sample rate: {sr}Hz. Common rates: {common_rates}")
            
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid sample rate value: {sample_rate}"
    
    @classmethod
    def validate_channels(cls, channels: int) -> Tuple[bool, str]:
        """Validate channel count parameter"""
        try:
            ch = int(channels)
            if ch not in cls.VALID_CHANNELS:
                return False, f"Invalid channel count: {ch}. Valid values: {cls.VALID_CHANNELS}"
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid channel count value: {channels}"
    
    @classmethod
    def validate_bit_depth(cls, bit_depth: int) -> Tuple[bool, str]:
        """Validate bit depth parameter"""
        try:
            bd = int(bit_depth)
            if bd not in cls.VALID_BIT_DEPTHS:
                return False, f"Invalid bit depth: {bd}. Valid values: {cls.VALID_BIT_DEPTHS}"
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid bit depth value: {bit_depth}"
    
    @classmethod
    def validate_audio_params(cls, frequency: float, duration: float, 
                            sample_rate: int, channels: int = 1, 
                            bit_depth: int = 16) -> Tuple[bool, str]:
        """Comprehensive audio parameter validation"""
        validations = [
            cls.validate_frequency(frequency),
            cls.validate_duration(duration),
            cls.validate_sample_rate(sample_rate),
            cls.validate_channels(channels),
            cls.validate_bit_depth(bit_depth)
        ]
        
        for valid, message in validations:
            if not valid:
                return False, message
        
        # Cross-parameter validation
        estimated_size_mb = (duration * sample_rate * channels * bit_depth / 8) / (1024 * 1024)
        if estimated_size_mb > 100:  # 100MB limit
            return False, f"Estimated file size too large: {estimated_size_mb:.1f}MB (max 100MB)"
        
        return True, ""
    
    @classmethod
    def validate_volume_factor(cls, factor: float) -> Tuple[bool, str]:
        """Validate volume adjustment factor"""
        try:
            vol = float(factor)
            if not (0.0 <= vol <= 10.0):
                return False, f"Volume factor {vol} outside valid range (0.0-10.0)"
            if vol > 3.0:
                logger.warning(f"High volume factor: {vol}. May cause audio distortion.")
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid volume factor: {factor}"

class FileValidator:
    """Centralized file and path validation"""
    
    AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.aac', '.m4a', '.wma', '.aiff', '.au'}
    MAX_PATH_LENGTH = 260  # Windows limitation
    DANGEROUS_PATTERNS = ['../', '..\\', '~/', '/etc/', '/proc/', '/sys/', 'CON', 'PRN', 'AUX', 'NUL']
    
    @classmethod
    def validate_file_path(cls, path: str, must_exist: bool = False, 
                         must_be_audio: bool = True) -> Tuple[bool, str]:
        """Comprehensive file path validation"""
        try:
            if not path or not isinstance(path, str):
                return False, "Empty or invalid path"
            
            # Length check
            if len(path) > cls.MAX_PATH_LENGTH:
                return False, f"Path too long: {len(path)} > {cls.MAX_PATH_LENGTH} characters"
            
            # Dangerous pattern check
            path_lower = path.lower()
            for pattern in cls.DANGEROUS_PATTERNS:
                if pattern.lower() in path_lower:
                    return False, f"Dangerous path pattern detected: {pattern}"
            
            # Path normalization and security
            try:
                normalized_path = os.path.normpath(os.path.abspath(path))
                current_dir = os.path.abspath('.')
                
                # Prevent directory traversal
                if not normalized_path.startswith(current_dir):
                    logger.warning(f"Path outside current directory: {normalized_path}")
            except Exception:
                return False, "Path normalization failed"
            
            # Extension check for audio files
            if must_be_audio:
                extension = Path(path).suffix.lower()
                if extension not in cls.AUDIO_EXTENSIONS:
                    return False, f"Invalid audio file extension: {extension}. Valid: {cls.AUDIO_EXTENSIONS}"
            
            # Existence check
            if must_exist and not os.path.exists(path):
                return False, f"File does not exist: {path}"
            
            # File vs directory check
            if must_exist and os.path.exists(path):
                if os.path.isdir(path):
                    return False, f"Path is a directory, not a file: {path}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Path validation error: {e}"
    
    @classmethod
    def validate_output_directory(cls, directory: str, create_if_missing: bool = True) -> Tuple[bool, str]:
        """Validate output directory"""
        try:
            if not directory or not isinstance(directory, str):
                return False, "Empty or invalid directory path"
            
            # Length check
            if len(directory) > cls.MAX_PATH_LENGTH:
                return False, f"Directory path too long: {len(directory)} characters"
            
            # Normalize path
            normalized_dir = os.path.normpath(os.path.abspath(directory))
            
            # Check if it exists
            if os.path.exists(normalized_dir):
                if not os.path.isdir(normalized_dir):
                    return False, f"Path exists but is not a directory: {normalized_dir}"
                
                # Check write permission
                if not os.access(normalized_dir, os.W_OK):
                    return False, f"No write permission for directory: {normalized_dir}"
            else:
                if create_if_missing:
                    try:
                        os.makedirs(normalized_dir, exist_ok=True)
                        logger.info(f"Created output directory: {normalized_dir}")
                    except Exception as e:
                        return False, f"Failed to create directory: {e}"
                else:
                    return False, f"Directory does not exist: {normalized_dir}"
            
            return True, normalized_dir
            
        except Exception as e:
            return False, f"Directory validation error: {e}"
    
    @classmethod
    def validate_file_size(cls, filepath: str, max_size_mb: int = 100) -> Tuple[bool, str]:
        """Validate file size"""
        try:
            if not os.path.exists(filepath):
                return False, f"File does not exist: {filepath}"
            
            size_bytes = os.path.getsize(filepath)
            size_mb = size_bytes / (1024 * 1024)
            
            if size_mb > max_size_mb:
                return False, f"File too large: {size_mb:.1f}MB > {max_size_mb}MB"
            
            return True, f"File size: {size_mb:.2f}MB"
            
        except Exception as e:
            return False, f"File size validation error: {e}"

class DataValidator:
    """Data format and content validation"""
    
    @classmethod
    def validate_audio_data(cls, audio_data) -> Tuple[bool, str]:
        """Validate audio data tuple format"""
        try:
            if not audio_data:
                return False, "No audio data provided"
            
            if not isinstance(audio_data, (tuple, list)) or len(audio_data) != 4:
                return False, "Audio data must be (data, sample_rate, channels, sample_width) tuple"
            
            data, sample_rate, channels, sample_width = audio_data
            
            # Data validation
            if not isinstance(data, bytes):
                return False, "Audio data must be bytes"
            
            if len(data) == 0:
                return False, "Audio data is empty"
            
            if len(data) % 2 != 0 and sample_width == 2:
                return False, "Invalid data length for 16-bit audio (must be even)"
            
            # Parameter validation
            valid_sr, sr_msg = AudioValidator.validate_sample_rate(sample_rate)
            if not valid_sr:
                return False, sr_msg
            
            valid_ch, ch_msg = AudioValidator.validate_channels(channels)
            if not valid_ch:
                return False, ch_msg
            
            valid_bd, bd_msg = AudioValidator.validate_bit_depth(sample_width * 8)
            if not valid_bd:
                return False, bd_msg
            
            # Cross-validation
            expected_bytes_per_sample = sample_width * channels
            if len(data) % expected_bytes_per_sample != 0:
                return False, f"Data length {len(data)} not divisible by bytes per sample {expected_bytes_per_sample}"
            
            return True, "Audio data validation passed"
            
        except Exception as e:
            return False, f"Audio data validation error: {e}"
    
    @classmethod
    def validate_frequency_list(cls, frequencies: List[float], max_count: int = 100) -> Tuple[bool, str]:
        """Validate list of frequencies"""
        try:
            if not frequencies:
                return False, "Empty frequency list"
            
            if len(frequencies) > max_count:
                return False, f"Too many frequencies: {len(frequencies)} > {max_count}"
            
            for i, freq in enumerate(frequencies):
                valid, message = AudioValidator.validate_frequency(freq)
                if not valid:
                    return False, f"Frequency {i}: {message}"
            
            # Check for duplicates
            unique_freqs = set(frequencies)
            if len(unique_freqs) != len(frequencies):
                logger.warning(f"Duplicate frequencies detected. Unique: {len(unique_freqs)}, Total: {len(frequencies)}")
            
            return True, f"Validated {len(frequencies)} frequencies"
            
        except Exception as e:
            return False, f"Frequency list validation error: {e}"

# Convenience functions for backward compatibility
def validate_audio_params(frequency: float, duration: float, sample_rate: int) -> bool:
    """Legacy validation function for backward compatibility"""
    valid, _ = AudioValidator.validate_audio_params(frequency, duration, sample_rate)
    return valid

def validate_file_path(path: str, must_exist: bool = False) -> bool:
    """Legacy file path validation for backward compatibility"""
    valid, _ = FileValidator.validate_file_path(path, must_exist)
    return valid

def validate_audio_data(audio_data) -> bool:
    """Legacy audio data validation for backward compatibility"""
    valid, _ = DataValidator.validate_audio_data(audio_data)
    return valid

# Enhanced validation functions
def strict_validate_audio_params(frequency: float, duration: float, sample_rate: int, 
                                channels: int = 1, bit_depth: int = 16) -> Tuple[bool, str]:
    """Strict validation with detailed error messages"""
    return AudioValidator.validate_audio_params(frequency, duration, sample_rate, channels, bit_depth)

def strict_validate_file_path(path: str, must_exist: bool = False, 
                             must_be_audio: bool = True) -> Tuple[bool, str]:
    """Strict file path validation with detailed error messages"""
    return FileValidator.validate_file_path(path, must_exist, must_be_audio)

def validate_batch_operation(frequencies: List[float], output_dir: str) -> Tuple[bool, str]:
    """Validate batch operation parameters"""
    # Validate frequencies
    valid_freqs, freq_msg = DataValidator.validate_frequency_list(frequencies)
    if not valid_freqs:
        return False, f"Frequency validation failed: {freq_msg}"
    
    # Validate output directory
    valid_dir, dir_msg = FileValidator.validate_output_directory(output_dir)
    if not valid_dir:
        return False, f"Directory validation failed: {dir_msg}"
    
    return True, "Batch operation validation passed"

if __name__ == '__main__':
    # Test validation functionality
    print("Validation System Test")
    print("=" * 40)
    
    # Test audio parameter validation
    test_cases = [
        (440.0, 1.0, 44100, 1, 16),  # Valid
        (-100.0, 1.0, 44100, 1, 16),  # Invalid frequency
        (440.0, -1.0, 44100, 1, 16),  # Invalid duration
        (440.0, 1.0, 1000, 1, 16),   # Invalid sample rate
    ]
    
    for i, params in enumerate(test_cases):
        valid, message = AudioValidator.validate_audio_params(*params)
        status = "PASS" if valid else "FAIL"
        print(f"Test {i+1}: {status} - {message}")
    
    # Test file path validation
    test_paths = [
        "test.wav",           # Valid
        "../etc/passwd",      # Dangerous
        "test.txt",           # Non-audio
        "a" * 300 + ".wav",   # Too long
    ]
    
    for path in test_paths:
        valid, message = FileValidator.validate_file_path(path, must_exist=False)
        status = "PASS" if valid else "FAIL"
        print(f"Path '{path[:20]}...': {status} - {message}")
    
    print("Validation system test completed")