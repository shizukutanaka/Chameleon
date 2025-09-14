#!/usr/bin/env python3
"""
Comprehensive Error Handling and Validation System
Provides robust error handling, input validation, and recovery mechanisms
"""

import os
import sys
import traceback
import functools
import logging
from pathlib import Path
from typing import Any, Callable, Optional, Union, List, Dict
from enum import Enum

# Safe imports with compatibility
try:
    from compatibility import HAS_NUMPY, max_abs, mean
    if HAS_NUMPY:
        import numpy as np
except ImportError:
    HAS_NUMPY = False
    def max_abs(arr):
        return max(abs(x) for x in arr) if arr else 0
    def mean(arr):
        return sum(arr) / len(arr) if arr else 0

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AudioError(Exception):
    """Base exception for audio processing errors"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 context: Optional[Dict] = None):
        super().__init__(message)
        self.severity = severity
        self.context = context or {}

class FileValidationError(AudioError):
    """Audio file validation errors"""
    pass

class ProcessingError(AudioError):
    """Audio processing errors"""
    pass

class ConfigurationError(AudioError):
    """Configuration and setup errors"""
    pass

class ResourceError(AudioError):
    """Resource availability errors (memory, disk, etc.)"""
    pass

class ValidationResult:
    """Result of validation operations"""
    def __init__(self, is_valid: bool, message: str = "", warnings: List[str] = None):
        self.is_valid = is_valid
        self.message = message
        self.warnings = warnings or []

class ErrorHandler:
    """
    Centralized error handling and validation system
    """
    
    def __init__(self, log_file: Optional[str] = None, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.error_log = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG if debug_mode else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file) if log_file else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def handle_error(self, error: Exception, context: Optional[Dict] = None, 
                    recovery_action: Optional[Callable] = None) -> Optional[Any]:
        """
        Central error handling with logging and optional recovery
        """
        error_info = {
            'type': type(error).__name__,
            'message': str(error),
            'context': context or {},
            'traceback': traceback.format_exc() if self.debug_mode else None
        }
        
        self.error_log.append(error_info)
        
        # Determine severity
        severity = getattr(error, 'severity', ErrorSeverity.MEDIUM)
        
        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"CRITICAL ERROR: {error_info['message']}")
            if self.debug_mode:
                self.logger.critical(f"Traceback: {error_info['traceback']}")
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(f"ERROR: {error_info['message']}")
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"WARNING: {error_info['message']}")
        else:
            self.logger.info(f"INFO: {error_info['message']}")
        
        # Attempt recovery if provided
        if recovery_action:
            try:
                return recovery_action()
            except Exception as recovery_error:
                self.logger.error(f"Recovery failed: {recovery_error}")
        
        # Re-raise critical errors
        if severity == ErrorSeverity.CRITICAL:
            raise error
        
        return None

    def with_error_handling(self, recovery_action: Optional[Callable] = None,
                           reraise_on: Optional[List[type]] = None):
        """
        Decorator for automatic error handling
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if we should re-raise
                    if reraise_on and type(e) in reraise_on:
                        raise
                    
                    context = {
                        'function': func.__name__,
                        'args': str(args)[:100],  # Limit log size
                        'kwargs': str(kwargs)[:100]
                    }
                    
                    return self.handle_error(e, context, recovery_action)
            return wrapper
        return decorator

class AudioValidator:
    """
    Comprehensive audio data and file validation
    """
    
    # Supported audio formats
    SUPPORTED_FORMATS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac'}
    
    # Audio constraints
    MIN_SAMPLE_RATE = 8000
    MAX_SAMPLE_RATE = 192000
    MIN_CHANNELS = 1
    MAX_CHANNELS = 8
    MIN_BIT_DEPTH = 8
    MAX_BIT_DEPTH = 32
    MAX_FILE_SIZE_MB = 500
    
    def __init__(self, error_handler: Optional[ErrorHandler] = None):
        self.error_handler = error_handler or ErrorHandler()
    
    def validate_file_path(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate audio file path and basic properties"""
        try:
            path = Path(file_path)
            
            # Check if file exists
            if not path.exists():
                return ValidationResult(False, f"File does not exist: {path}")
            
            # Check if it's a file (not directory)
            if not path.is_file():
                return ValidationResult(False, f"Path is not a file: {path}")
            
            # Check file extension
            if path.suffix.lower() not in self.SUPPORTED_FORMATS:
                return ValidationResult(False, 
                    f"Unsupported format: {path.suffix}. Supported: {', '.join(self.SUPPORTED_FORMATS)}")
            
            # Check file size
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.MAX_FILE_SIZE_MB:
                return ValidationResult(False, 
                    f"File too large: {size_mb:.1f}MB (max: {self.MAX_FILE_SIZE_MB}MB)")
            
            # Check read permissions
            if not os.access(path, os.R_OK):
                return ValidationResult(False, f"No read permission for file: {path}")
            
            warnings = []
            if size_mb > 100:  # Large file warning
                warnings.append(f"Large file size: {size_mb:.1f}MB")
            
            return ValidationResult(True, "File validation passed", warnings)
            
        except Exception as e:
            self.error_handler.handle_error(e, {'file_path': str(file_path)})
            return ValidationResult(False, f"Validation error: {e}")
    
    def validate_output_path(self, output_path: Union[str, Path]) -> ValidationResult:
        """Validate output file path"""
        try:
            path = Path(output_path)
            
            # Check if parent directory exists or can be created
            parent = path.parent
            if not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    return ValidationResult(False, f"Cannot create output directory: {e}")
            
            # Check write permissions
            if parent.exists() and not os.access(parent, os.W_OK):
                return ValidationResult(False, f"No write permission for directory: {parent}")
            
            # Check if file exists and warn about overwrite
            warnings = []
            if path.exists():
                warnings.append(f"Output file exists and will be overwritten: {path}")
            
            return ValidationResult(True, "Output path validation passed", warnings)
            
        except Exception as e:
            self.error_handler.handle_error(e, {'output_path': str(output_path)})
            return ValidationResult(False, f"Output validation error: {e}")
    
    def validate_audio_data(self, samples: Union[Any, List, bytes], 
                           sample_rate: int, channels: int = 1) -> ValidationResult:
        """Validate audio sample data"""
        try:
            warnings = []
            
            # Convert data to list for processing
            if isinstance(samples, bytes):
                import array
                arr = array.array('h')
                arr.frombytes(samples)
                samples = list(arr)
            elif HAS_NUMPY and hasattr(samples, 'tolist'):
                samples = samples.tolist()
            elif not isinstance(samples, list):
                samples = list(samples)
            
            # Check if data is empty
            if len(samples) == 0:
                return ValidationResult(False, "Audio data is empty")
            
            # Check sample rate
            if not (self.MIN_SAMPLE_RATE <= sample_rate <= self.MAX_SAMPLE_RATE):
                return ValidationResult(False, 
                    f"Invalid sample rate: {sample_rate}. Must be {self.MIN_SAMPLE_RATE}-{self.MAX_SAMPLE_RATE}")
            
            # Check channels
            if not (self.MIN_CHANNELS <= channels <= self.MAX_CHANNELS):
                return ValidationResult(False, 
                    f"Invalid channels: {channels}. Must be {self.MIN_CHANNELS}-{self.MAX_CHANNELS}")
            
            # Check data range (assuming int16 format)
            max_val = max_abs(samples)
            if max_val == 0:
                warnings.append("Audio contains only silence")
            elif max_val > 32767:
                warnings.append("Audio may be clipped (values exceed int16 range)")
            
            # Check for potential issues
            if len(samples) < sample_rate * 0.1:  # Less than 100ms
                warnings.append("Very short audio duration (< 100ms)")
            
            # Check for DC offset
            if len(samples) > 1000:
                dc_offset = mean(samples)
                if abs(dc_offset) > max_val * 0.1:
                    warnings.append(f"Significant DC offset detected: {dc_offset:.2f}")
            
            return ValidationResult(True, "Audio data validation passed", warnings)
            
        except Exception as e:
            self.error_handler.handle_error(e, {'sample_rate': sample_rate, 'channels': channels})
            return ValidationResult(False, f"Audio data validation error: {e}")
    
    def validate_processing_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate audio processing parameters"""
        try:
            warnings = []
            
            # Validate common parameters
            if 'gain' in params:
                gain = params['gain']
                if not isinstance(gain, (int, float)):
                    return ValidationResult(False, "Gain must be numeric")
                if not (0.1 <= gain <= 10.0):
                    warnings.append(f"Unusual gain value: {gain} (typical range: 0.1-10.0)")
            
            if 'pitch' in params:
                pitch = params['pitch']
                if not isinstance(pitch, (int, float)):
                    return ValidationResult(False, "Pitch must be numeric")
                if not (0.5 <= pitch <= 2.0):
                    return ValidationResult(False, f"Pitch out of range: {pitch} (must be 0.5-2.0)")
            
            if 'speed' in params:
                speed = params['speed']
                if not isinstance(speed, (int, float)):
                    return ValidationResult(False, "Speed must be numeric")
                if not (0.5 <= speed <= 2.0):
                    return ValidationResult(False, f"Speed out of range: {speed} (must be 0.5-2.0)")
            
            if 'formant' in params:
                formant = params['formant']
                if not isinstance(formant, (int, float)):
                    return ValidationResult(False, "Formant must be numeric")
                if not (0.5 <= formant <= 2.0):
                    return ValidationResult(False, f"Formant out of range: {formant} (must be 0.5-2.0)")
            
            # Validate effect parameters
            for effect in ['reverb', 'delay', 'chorus', 'distortion']:
                if effect in params:
                    value = params[effect]
                    if not isinstance(value, (int, float)):
                        return ValidationResult(False, f"{effect} must be numeric")
                    if not (0.0 <= value <= 1.0):
                        warnings.append(f"{effect} value outside typical range: {value} (0.0-1.0)")
            
            return ValidationResult(True, "Parameter validation passed", warnings)
            
        except Exception as e:
            self.error_handler.handle_error(e, {'params': params})
            return ValidationResult(False, f"Parameter validation error: {e}")

class ResourceMonitor:
    """
    Monitor system resources and prevent resource exhaustion
    """
    
    def __init__(self, max_memory_mb: int = 1000, max_cpu_percent: int = 90):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent
        
    def check_memory_usage(self) -> ValidationResult:
        """Check current memory usage"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            if memory_mb > self.max_memory_mb:
                return ValidationResult(False, 
                    f"Memory usage too high: {memory_mb:.1f}MB (max: {self.max_memory_mb}MB)")
            
            warnings = []
            if memory_mb > self.max_memory_mb * 0.8:
                warnings.append(f"High memory usage: {memory_mb:.1f}MB")
            
            return ValidationResult(True, f"Memory usage OK: {memory_mb:.1f}MB", warnings)
            
        except ImportError:
            return ValidationResult(True, "Memory monitoring unavailable (psutil not installed)")
        except Exception as e:
            return ValidationResult(False, f"Memory check failed: {e}")
    
    def check_disk_space(self, path: Union[str, Path], required_mb: float) -> ValidationResult:
        """Check available disk space"""
        try:
            import shutil
            free_bytes, _, _ = shutil.disk_usage(Path(path).parent)
            free_mb = free_bytes / (1024 * 1024)
            
            if free_mb < required_mb:
                return ValidationResult(False, 
                    f"Insufficient disk space: {free_mb:.1f}MB available, {required_mb:.1f}MB required")
            
            warnings = []
            if free_mb < required_mb * 2:
                warnings.append(f"Low disk space: {free_mb:.1f}MB available")
            
            return ValidationResult(True, f"Disk space OK: {free_mb:.1f}MB available", warnings)
            
        except Exception as e:
            return ValidationResult(False, f"Disk space check failed: {e}")

# Global instances for easy use
default_error_handler = ErrorHandler()
default_validator = AudioValidator(default_error_handler)
default_monitor = ResourceMonitor()

# Convenience functions
def validate_input_file(file_path: Union[str, Path]) -> ValidationResult:
    """Quick input file validation"""
    return default_validator.validate_file_path(file_path)

def validate_output_file(file_path: Union[str, Path]) -> ValidationResult:
    """Quick output file validation"""
    return default_validator.validate_output_path(file_path)

def safe_execute(func: Callable, *args, **kwargs) -> Any:
    """Execute function with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return default_error_handler.handle_error(e, {
            'function': func.__name__,
            'args': str(args)[:100],
            'kwargs': str(kwargs)[:100]
        })

# Decorators for common validation patterns
def validate_audio_file(input_param: str = 'input_file', output_param: str = None):
    """Decorator to validate audio file parameters"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get input file from kwargs or args
            input_file = kwargs.get(input_param)
            if not input_file and args:
                input_file = args[0]  # Assume first arg is input file
            
            if input_file:
                result = validate_input_file(input_file)
                if not result.is_valid:
                    raise FileValidationError(result.message)
                
                # Log warnings
                for warning in result.warnings:
                    default_error_handler.logger.warning(warning)
            
            # Validate output file if specified
            if output_param:
                output_file = kwargs.get(output_param)
                if not output_file and len(args) > 1:
                    output_file = args[1]  # Assume second arg is output file
                
                if output_file:
                    result = validate_output_file(output_file)
                    if not result.is_valid:
                        raise FileValidationError(result.message)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator