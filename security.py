#!/usr/bin/env python3
"""
Security module for Chameleon Audio Processing Framework.
Implements comprehensive security measures for production environments.
"""

import os
import re
import hashlib
import secrets
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import urlparse

try:
    from .types import get_fallback_logger
    logger = get_fallback_logger('chameleon.security')
except ImportError:
    import logging
    logger = logging.getLogger('chameleon.security')

class SecurityConfig:
    """Security configuration constants and limits"""
    
    # File system security
    MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB
    MAX_PATH_LENGTH = 260
    MAX_FILENAME_LENGTH = 255
    
    # Audio processing limits
    MAX_SAMPLE_RATE = 192000
    MAX_CHANNELS = 32
    MAX_DURATION_SECONDS = 3600  # 1 hour
    MAX_FREQUENCY_HZ = 96000
    
    # Memory and resource limits
    MAX_MEMORY_USAGE_MB = 1024  # 1GB
    MAX_PROCESSING_TIME_SEC = 600  # 10 minutes
    MAX_CONCURRENT_OPERATIONS = 10
    
    # Path traversal protection
    FORBIDDEN_PATHS = {
        '..', '../', '..\\', './', '.\\',
        '/etc', '/proc', '/sys', '/dev', '/root',
        'C:\\Windows', 'C:\\System32', 'C:\\Program Files'
    }
    
    # Dangerous file extensions
    FORBIDDEN_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
        '.vbs', '.js', '.jar', '.ps1', '.sh', '.dll',
        '.sys', '.ini', '.reg', '.msi'
    }
    
    # Safe audio file extensions
    ALLOWED_AUDIO_EXTENSIONS = {
        '.wav', '.mp3', '.flac', '.ogg', '.aac', '.m4a'
    }

class InputValidator:
    """Comprehensive input validation and sanitization"""
    
    @staticmethod
    def validate_filename(filename: str) -> Tuple[bool, str]:
        """Validate and sanitize filename"""
        if not filename:
            return False, "Filename cannot be empty"
        
        # Check length
        if len(filename) > SecurityConfig.MAX_FILENAME_LENGTH:
            return False, f"Filename too long (max {SecurityConfig.MAX_FILENAME_LENGTH} chars)"
        
        # Check for dangerous characters
        dangerous_chars = r'[<>:"|?*\x00-\x1f]'
        if re.search(dangerous_chars, filename):
            return False, "Filename contains illegal characters"
        
        # Check for reserved names (Windows)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        base_name = Path(filename).stem.upper()
        if base_name in reserved_names:
            return False, f"Filename '{filename}' is a reserved system name"
        
        return True, "Valid filename"
    
    @staticmethod
    def validate_file_path(file_path: str) -> Tuple[bool, str]:
        """Validate file path for security"""
        if not file_path:
            return False, "File path cannot be empty"
        
        # Normalize path
        try:
            normalized_path = os.path.normpath(file_path)
        except Exception:
            return False, "Invalid file path format"
        
        # Check length
        if len(normalized_path) > SecurityConfig.MAX_PATH_LENGTH:
            return False, f"Path too long (max {SecurityConfig.MAX_PATH_LENGTH} chars)"
        
        # Check for path traversal
        for forbidden in SecurityConfig.FORBIDDEN_PATHS:
            if forbidden in normalized_path:
                return False, f"Path contains forbidden sequence: {forbidden}"
        
        # Check file extension
        file_ext = Path(normalized_path).suffix.lower()
        if file_ext in SecurityConfig.FORBIDDEN_EXTENSIONS:
            return False, f"File extension '{file_ext}' not allowed"
        
        # For audio operations, ensure audio extension
        if file_ext and file_ext not in SecurityConfig.ALLOWED_AUDIO_EXTENSIONS:
            logger.warning(f"Non-audio file extension detected: {file_ext}")
        
        return True, "Valid file path"
    
    @staticmethod
    def validate_audio_parameters(frequency: float, duration: float, 
                                 sample_rate: int, channels: int = 1) -> Tuple[bool, str]:
        """Validate audio processing parameters"""
        # Frequency validation
        if not (0.1 <= frequency <= SecurityConfig.MAX_FREQUENCY_HZ):
            return False, f"Frequency {frequency}Hz out of safe range (0.1-{SecurityConfig.MAX_FREQUENCY_HZ})"
        
        # Duration validation
        if not (0.001 <= duration <= SecurityConfig.MAX_DURATION_SECONDS):
            return False, f"Duration {duration}s out of safe range (0.001-{SecurityConfig.MAX_DURATION_SECONDS})"
        
        # Sample rate validation
        if not (8000 <= sample_rate <= SecurityConfig.MAX_SAMPLE_RATE):
            return False, f"Sample rate {sample_rate} out of safe range (8000-{SecurityConfig.MAX_SAMPLE_RATE})"
        
        # Channels validation
        if not (1 <= channels <= SecurityConfig.MAX_CHANNELS):
            return False, f"Channel count {channels} out of safe range (1-{SecurityConfig.MAX_CHANNELS})"
        
        # Memory usage estimation
        estimated_size = duration * sample_rate * channels * 2  # 16-bit samples
        if estimated_size > SecurityConfig.MAX_FILE_SIZE_BYTES:
            return False, f"Estimated file size {estimated_size/1024/1024:.1f}MB exceeds limit"
        
        return True, "Valid audio parameters"
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """Sanitize string input for safe processing"""
        if not input_str:
            return ""
        
        # Truncate to max length
        sanitized = str(input_str)[:max_length]
        
        # Remove control characters except newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', sanitized)
        
        # Strip whitespace
        sanitized = sanitized.strip()
        
        return sanitized

class FileSystemSecurity:
    """File system operations security"""
    
    @staticmethod
    def safe_file_write(filepath: str, data: bytes) -> Tuple[bool, str]:
        """Securely write file with validation"""
        # Validate file path
        is_valid, message = InputValidator.validate_file_path(filepath)
        if not is_valid:
            return False, message
        
        # Check data size
        if len(data) > SecurityConfig.MAX_FILE_SIZE_BYTES:
            return False, f"Data size {len(data)/1024/1024:.1f}MB exceeds limit"
        
        try:
            # Create parent directories safely
            parent_dir = os.path.dirname(filepath)
            if parent_dir:
                os.makedirs(parent_dir, mode=0o755, exist_ok=True)
            
            # Write to temporary file first
            temp_path = filepath + '.tmp.' + secrets.token_hex(8)
            
            try:
                with open(temp_path, 'wb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk
                
                # Atomic move
                if os.name == 'nt':  # Windows
                    if os.path.exists(filepath):
                        os.remove(filepath)
                os.rename(temp_path, filepath)
                
                return True, "File written successfully"
                
            except Exception as e:
                # Cleanup temp file on error
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
                raise e
                
        except Exception as e:
            logger.error(f"File write failed: {e}")
            return False, f"File write error: {e}"
    
    @staticmethod
    def safe_file_read(filepath: str, max_size: int = None) -> Tuple[bool, bytes, str]:
        """Securely read file with validation"""
        # Validate file path
        is_valid, message = InputValidator.validate_file_path(filepath)
        if not is_valid:
            return False, b'', message
        
        if not os.path.exists(filepath):
            return False, b'', "File not found"
        
        if not os.path.isfile(filepath):
            return False, b'', "Path is not a file"
        
        try:
            file_size = os.path.getsize(filepath)
            max_allowed = max_size or SecurityConfig.MAX_FILE_SIZE_BYTES
            
            if file_size > max_allowed:
                return False, b'', f"File size {file_size/1024/1024:.1f}MB exceeds limit"
            
            with open(filepath, 'rb') as f:
                data = f.read()
            
            return True, data, "File read successfully"
            
        except Exception as e:
            logger.error(f"File read failed: {e}")
            return False, b'', f"File read error: {e}"
    
    @staticmethod
    def create_secure_temp_file(suffix: str = '.tmp') -> Tuple[bool, str, str]:
        """Create secure temporary file"""
        try:
            # Validate suffix
            if not suffix.startswith('.'):
                suffix = '.' + suffix
            
            # Use secure temporary directory
            temp_dir = tempfile.gettempdir()
            
            # Create unique filename
            temp_name = secrets.token_hex(16) + suffix
            temp_path = os.path.join(temp_dir, temp_name)
            
            # Create with restricted permissions
            fd = os.open(temp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            
            return True, temp_path, "Temporary file created"
            
        except Exception as e:
            logger.error(f"Temp file creation failed: {e}")
            return False, "", f"Temp file error: {e}"

class MemoryGuard:
    """Memory usage monitoring and protection"""
    
    def __init__(self):
        self.peak_memory = 0
        self.current_operations = 0
    
    def check_memory_limit(self) -> Tuple[bool, str]:
        """Check if memory usage is within safe limits"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            if memory_mb > SecurityConfig.MAX_MEMORY_USAGE_MB:
                return False, f"Memory usage {memory_mb:.1f}MB exceeds limit"
            
            self.peak_memory = max(self.peak_memory, memory_mb)
            return True, f"Memory usage: {memory_mb:.1f}MB"
            
        except ImportError:
            # psutil not available, skip check
            return True, "Memory monitoring not available"
        except Exception as e:
            logger.warning(f"Memory check failed: {e}")
            return True, "Memory check failed"
    
    def acquire_operation_slot(self) -> Tuple[bool, str]:
        """Acquire slot for concurrent operation"""
        if self.current_operations >= SecurityConfig.MAX_CONCURRENT_OPERATIONS:
            return False, "Too many concurrent operations"
        
        self.current_operations += 1
        return True, f"Operation slot acquired ({self.current_operations}/{SecurityConfig.MAX_CONCURRENT_OPERATIONS})"
    
    def release_operation_slot(self):
        """Release operation slot"""
        if self.current_operations > 0:
            self.current_operations -= 1

class SecurityLogger:
    """Security-focused logging utilities"""
    
    @staticmethod
    def log_security_event(event_type: str, message: str, 
                          details: Dict[str, Any] = None, 
                          severity: str = 'INFO'):
        """Log security-related events"""
        details = details or {}
        
        # Sanitize sensitive information
        safe_details = SecurityLogger._sanitize_log_data(details)
        
        log_entry = {
            'event_type': event_type,
            'message': message,
            'details': safe_details,
            'timestamp': None  # Will be added by logger
        }
        
        if severity == 'ERROR':
            logger.error(f"SECURITY[{event_type}]: {message} - {safe_details}")
        elif severity == 'WARNING':
            logger.warning(f"SECURITY[{event_type}]: {message} - {safe_details}")
        else:
            logger.info(f"SECURITY[{event_type}]: {message} - {safe_details}")
    
    @staticmethod
    def _sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from log data"""
        sensitive_keys = {'password', 'token', 'key', 'secret', 'auth', 'credential'}
        
        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:100] + '...[TRUNCATED]'
            else:
                sanitized[key] = value
        
        return sanitized

# Global security instances
memory_guard = MemoryGuard()
security_logger = SecurityLogger()

def initialize_security():
    """Initialize security subsystem"""
    security_logger.log_security_event(
        'INIT', 
        'Security subsystem initialized',
        {'max_file_size_mb': SecurityConfig.MAX_FILE_SIZE_BYTES / (1024 * 1024)}
    )

def security_check_decorator(func):
    """Decorator for adding security checks to functions"""
    def wrapper(*args, **kwargs):
        # Check memory limit
        memory_ok, memory_msg = memory_guard.check_memory_limit()
        if not memory_ok:
            security_logger.log_security_event('MEMORY_LIMIT', memory_msg, severity='ERROR')
            raise MemoryError(memory_msg)
        
        # Acquire operation slot
        slot_ok, slot_msg = memory_guard.acquire_operation_slot()
        if not slot_ok:
            security_logger.log_security_event('RATE_LIMIT', slot_msg, severity='WARNING')
            raise RuntimeError(slot_msg)
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            memory_guard.release_operation_slot()
    
    return wrapper

# Initialize on import
initialize_security()