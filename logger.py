#!/usr/bin/env python3
"""
Enhanced logging system for Chameleon audio processor.
Provides structured logging with configurable levels and outputs.
"""

import os
import sys
import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

class LogLevel:
    """Log level constants"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    @classmethod
    def get_name(cls, level: int) -> str:
        """Get log level name from numeric value"""
        level_map = {
            cls.DEBUG: 'DEBUG',
            cls.INFO: 'INFO', 
            cls.WARNING: 'WARNING',
            cls.ERROR: 'ERROR',
            cls.CRITICAL: 'CRITICAL'
        }
        return level_map.get(level, 'UNKNOWN')

class StructuredLogger:
    """Structured logger with JSON output support"""
    
    def __init__(self, name: str = 'chameleon', level: int = LogLevel.INFO, 
                 log_file: Optional[str] = None, max_file_size_mb: int = 10):
        self.name = name
        self.level = level
        self.log_file = log_file
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.session_id = self._generate_session_id()
        
        # Ensure log directory exists
        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return f"session_{int(time.time() * 1000)}"
    
    def _should_log(self, level: int) -> bool:
        """Check if message should be logged based on current level"""
        return level >= self.level
    
    def _format_message(self, level: int, message: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format log message as structured data"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': LogLevel.get_name(level),
            'logger': self.name,
            'session_id': self.session_id,
            'message': message
        }
        
        if extra:
            log_entry['extra'] = extra
            
        return log_entry
    
    def _rotate_log_if_needed(self):
        """Rotate log file if it exceeds maximum size"""
        if not self.log_file or not os.path.exists(self.log_file):
            return
            
        if os.path.getsize(self.log_file) > self.max_file_size:
            # Create backup
            backup_path = f"{self.log_file}.{int(time.time())}"
            try:
                os.rename(self.log_file, backup_path)
            except OSError:
                pass
    
    def _write_to_file(self, log_entry: Dict[str, Any]):
        """Write log entry to file"""
        if not self.log_file:
            return
            
        try:
            self._rotate_log_if_needed()
            with open(self.log_file, 'a', encoding='utf-8') as f:
                json.dump(log_entry, f, separators=(',', ':'))
                f.write('\n')
        except Exception as e:
            # Fallback to stderr if file write fails
            print(f"Log write failed: {e}", file=sys.stderr)
    
    def _write_to_console(self, log_entry: Dict[str, Any]):
        """Write formatted log entry to console"""
        timestamp = log_entry['timestamp'][:19].replace('T', ' ')
        level = log_entry['level']
        message = log_entry['message']
        
        # Color coding for different levels
        color_codes = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green  
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m'  # Magenta
        }
        reset_code = '\033[0m'
        
        color = color_codes.get(level, '')
        
        if sys.stdout.isatty():  # Only use colors in terminal
            formatted = f"{color}[{timestamp}] {level:8} {self.name}: {message}{reset_code}"
        else:
            formatted = f"[{timestamp}] {level:8} {self.name}: {message}"
        
        print(formatted)
        
        # Print extra data if present
        if 'extra' in log_entry and log_entry['extra']:
            extra_str = json.dumps(log_entry['extra'], indent=2)
            print(f"  Extra: {extra_str}")
    
    def log(self, level: int, message: str, **kwargs):
        """Log message with given level"""
        if not self._should_log(level):
            return
            
        extra = {k: v for k, v in kwargs.items() if v is not None}
        log_entry = self._format_message(level, message, extra if extra else None)
        
        self._write_to_console(log_entry)
        self._write_to_file(log_entry)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.log(LogLevel.CRITICAL, message, **kwargs)
    
    def set_level(self, level: int):
        """Set logging level"""
        self.level = level

class PerformanceLogger:
    """Specialized logger for performance tracking"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.start_times: Dict[str, float] = {}
    
    def start_timing(self, operation: str):
        """Start timing an operation"""
        self.start_times[operation] = time.perf_counter()
        self.logger.debug(f"Started timing: {operation}")
    
    def end_timing(self, operation: str) -> Optional[float]:
        """End timing and log duration"""
        if operation not in self.start_times:
            self.logger.warning(f"No start time found for operation: {operation}")
            return None
        
        duration = time.perf_counter() - self.start_times[operation]
        duration_ms = duration * 1000
        
        del self.start_times[operation]
        
        self.logger.info(f"Operation completed: {operation}", 
                        duration_ms=duration_ms,
                        operation=operation)
        
        return duration

class AudioOperationLogger:
    """Specialized logger for audio operations"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.operation_count = 0
    
    def log_audio_generation(self, frequency: float, duration: float, 
                           sample_rate: int, success: bool, file_size: int = None):
        """Log audio generation operation"""
        self.operation_count += 1
        self.logger.info("Audio generation completed",
                        operation_id=self.operation_count,
                        operation_type="generation",
                        frequency=frequency,
                        duration=duration,
                        sample_rate=sample_rate,
                        success=success,
                        file_size_bytes=file_size)
    
    def log_audio_processing(self, operation_type: str, input_file: str,
                           output_file: str = None, success: bool = True,
                           processing_time_ms: float = None):
        """Log audio processing operation"""
        self.operation_count += 1
        self.logger.info(f"Audio processing: {operation_type}",
                        operation_id=self.operation_count,
                        operation_type=operation_type,
                        input_file=input_file,
                        output_file=output_file,
                        success=success,
                        processing_time_ms=processing_time_ms)
    
    def log_batch_operation(self, operation_type: str, total_files: int,
                          successful_files: int, failed_files: int,
                          total_time_ms: float):
        """Log batch operation results"""
        self.logger.info(f"Batch operation completed: {operation_type}",
                        operation_type="batch_" + operation_type,
                        total_files=total_files,
                        successful_files=successful_files,
                        failed_files=failed_files,
                        success_rate=successful_files / total_files if total_files > 0 else 0,
                        total_time_ms=total_time_ms)

# Global logger instances
_default_logger = None
_performance_logger = None  
_audio_logger = None

def get_logger(name: str = 'chameleon', level: int = LogLevel.INFO,
               log_file: Optional[str] = None) -> StructuredLogger:
    """Get or create logger instance"""
    global _default_logger
    if _default_logger is None:
        _default_logger = StructuredLogger(name, level, log_file)
    return _default_logger

def get_performance_logger() -> PerformanceLogger:
    """Get performance logger instance"""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = PerformanceLogger(get_logger())
    return _performance_logger

def get_audio_logger() -> AudioOperationLogger:
    """Get audio operation logger instance"""
    global _audio_logger
    if _audio_logger is None:
        _audio_logger = AudioOperationLogger(get_logger())
    return _audio_logger

def configure_logging(level: int = LogLevel.INFO, log_file: Optional[str] = None,
                     max_file_size_mb: int = 10):
    """Configure global logging settings"""
    global _default_logger, _performance_logger, _audio_logger
    
    _default_logger = StructuredLogger('chameleon', level, log_file, max_file_size_mb)
    _performance_logger = PerformanceLogger(_default_logger)
    _audio_logger = AudioOperationLogger(_default_logger)

# Convenience functions
def debug(message: str, **kwargs):
    """Log debug message"""
    get_logger().debug(message, **kwargs)

def info(message: str, **kwargs):
    """Log info message"""
    get_logger().info(message, **kwargs)

def warning(message: str, **kwargs):
    """Log warning message"""
    get_logger().warning(message, **kwargs)

def error(message: str, **kwargs):
    """Log error message"""
    get_logger().error(message, **kwargs)

def critical(message: str, **kwargs):
    """Log critical message"""
    get_logger().critical(message, **kwargs)

if __name__ == '__main__':
    # Test logging functionality
    configure_logging(LogLevel.DEBUG, 'test_chameleon.log')
    
    logger = get_logger()
    perf_logger = get_performance_logger()
    audio_logger = get_audio_logger()
    
    # Test basic logging
    logger.info("Logging system test started")
    logger.debug("Debug message with extra data", test_param="value", number=42)
    logger.warning("Warning message")
    logger.error("Error message")
    
    # Test performance logging
    perf_logger.start_timing("test_operation")
    time.sleep(0.1)
    perf_logger.end_timing("test_operation")
    
    # Test audio operation logging
    audio_logger.log_audio_generation(440.0, 1.0, 44100, True, 88200)
    audio_logger.log_batch_operation("tone_generation", 5, 4, 1, 123.45)
    
    logger.info("Logging system test completed")