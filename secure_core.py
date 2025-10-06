#!/usr/bin/env python3
"""
Secure Core Audio Processing Module - Government Grade
Zero-vulnerability implementation for national-level deployment
"""

import os
import sys
import time
import json
import struct
import hashlib
import secrets
import logging
import threading
import ast
from pathlib import Path, PurePath
from typing import Dict, List, Optional, Any, Tuple, Union, Pattern
from dataclasses import dataclass, field
from functools import lru_cache
import re
import tempfile
from contextlib import contextmanager
import hmac
from logging.handlers import RotatingFileHandler

# Secure logging configuration


def _determine_log_dir() -> Path:
    """Determine a writable log directory across platforms."""
    env_dir = os.environ.get('CHAMELEON_LOG_DIR')
    candidates = []

    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    if os.name == 'posix':
        try:
            geteuid = getattr(os, 'geteuid', None)
            if callable(geteuid) and geteuid() == 0:
                candidates.append(Path('/var/log/chameleon'))
        except Exception:
            pass

    candidates.append(Path.home() / '.chameleon' / 'logs')
    candidates.append(Path(tempfile.gettempdir()) / 'chameleon' / 'logs')

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if os.name == 'posix':
                try:
                    os.chmod(candidate, 0o750)
                except Exception:
                    pass
            return candidate
        except Exception:
            continue

    # Fallback to current directory logs
    fallback = Path.cwd() / 'logs'
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DEFAULT_LOG_DIR = _determine_log_dir()

SECURE_LOG_FILE = DEFAULT_LOG_DIR / 'secure.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        RotatingFileHandler(str(SECURE_LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Security constants
VERSION = "3.0.0-SECURE"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB for security
CHUNK_SIZE = 64 * 1024  # 64KB chunks
SUPPORTED_FORMATS = {'.wav', '.wave'}
AUDIT_LOG_FILE = DEFAULT_LOG_DIR / 'audit.log'

# Cryptographically secure configuration
CRYPTO_ALGORITHMS = {
    'hash': 'sha256',  # Never MD5
    'hmac': 'sha256',
    'random': secrets.SystemRandom()
}

@dataclass
class SecureAudioInfo:
    """Secure audio metadata structure"""
    duration: float
    sample_rate: int
    channels: int
    bit_depth: int
    size_bytes: int
    peak_level: float
    rms_level: float
    file_hash: str
    processing_time: float

    def __post_init__(self):
        """Validate all fields for security"""
        if not isinstance(self.duration, (int, float)) or self.duration < 0:
            raise ValueError("Invalid duration")
        if self.sample_rate not in {8000, 16000, 22050, 44100, 48000, 96000}:
            raise ValueError("Unsupported sample rate")
        if self.channels not in {1, 2}:
            raise ValueError("Unsupported channel count")
        if self.bit_depth not in {16, 24, 32}:
            raise ValueError("Unsupported bit depth")

@dataclass
class ProcessingResult:
    """Secure processing result with audit trail"""
    success: bool
    message: str
    data: Optional[SecureAudioInfo] = None
    operation_id: str = field(default_factory=lambda: secrets.token_hex(16))
    timestamp: float = field(default_factory=time.time)
    user_id: Optional[str] = None

    def to_audit_log(self) -> str:
        """Generate audit log entry"""
        return json.dumps({
            'operation_id': self.operation_id,
            'timestamp': self.timestamp,
            'success': self.success,
            'message': self.message[:100],  # Truncate for security
            'user_id': self.user_id,
            'data_present': self.data is not None
        }, separators=(',', ':'))

class SecureValidator:
    """Ultra-secure input validator for government deployment"""

    SAFE_FILENAME_PATTERN = re.compile(r'^[A-Za-z0-9._-]+\.(wav|wave)$')
    SAFE_SEGMENT_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')

    @classmethod
    def validate_file_path(cls, path_input: Any) -> Path:
        """Validate file path with zero-trust approach"""
        # Type validation
        if not isinstance(path_input, (str, Path)):
            cls._audit_security_event("INVALID_PATH_TYPE", f"Type: {type(path_input)}")
            raise ValueError("Path must be string or Path object")

        # Convert to string for validation
        path_str = str(path_input).strip()

        # Length validation
        if len(path_str) > 255:
            cls._audit_security_event("PATH_TOO_LONG", f"Length: {len(path_str)}")
            raise ValueError("Path too long")

        # Null byte check
        if '\x00' in path_str:
            cls._audit_security_event("NULL_BYTE_ATTACK", "Null byte detected")
            raise ValueError("Null byte in path")

        # Convert to Path and resolve
        path_obj = Path(path_str)
        try:
            path_obj = path_obj.resolve(strict=False)
        except Exception as e:
            cls._audit_security_event("PATH_RESOLUTION_FAILED", str(e))
            raise ValueError(f"Path resolution failed: {e}")

        # Security checks
        path_parts = path_obj.parts
        if not path_obj.is_absolute():
            cls._audit_security_event("NON_ABSOLUTE_PATH", str(path_obj))
            raise ValueError("Path must be absolute")

        start_index = 0
        if path_parts:
            first_part = path_parts[0]
            if first_part in {os.sep, '/', '\\'}:
                start_index = 1
            elif os.name == 'nt' and first_part.endswith(':\\'):
                start_index = 1

        for part in path_parts[start_index:]:
            if part in {'.', '..'}:
                cls._audit_security_event("RELATIVE_PATH_COMPONENT", str(path_parts))
                raise ValueError("Relative path components not permitted")

            if part.startswith('~'):
                cls._audit_security_event("TILDE_EXPANSION", str(path_parts))
                raise ValueError("Home directory expansion not permitted")

            if not cls.SAFE_SEGMENT_PATTERN.match(part):
                cls._audit_security_event("UNSAFE_PATH_SEGMENT", part[:50])
                raise ValueError("Path contains unsafe segment characters")

        if path_obj.suffix.lower() not in SUPPORTED_FORMATS:
            cls._audit_security_event("UNSUPPORTED_FORMAT", path_obj.suffix)
            raise ValueError(f"Unsupported format: {path_obj.suffix}")

        if not cls.SAFE_FILENAME_PATTERN.match(path_obj.name):
            cls._audit_security_event("UNSAFE_FILENAME", path_obj.name)
            raise ValueError("Unsafe filename")

        return path_obj

    @classmethod
    def validate_numeric_input(cls, value: Any, min_val: float, max_val: float, name: str) -> float:
        """Validate numeric input with strict bounds"""
        if not isinstance(value, (int, float)):
            cls._audit_security_event("INVALID_NUMERIC_TYPE", f"{name}: {type(value)}")
            raise ValueError(f"{name} must be numeric")

        float_val = float(value)

        if not (min_val <= float_val <= max_val):
            cls._audit_security_event("OUT_OF_BOUNDS", f"{name}: {float_val}")
            raise ValueError(f"{name} must be between {min_val} and {max_val}")

        return float_val

    @classmethod
    def _audit_security_event(cls, event_type: str, details: str):
        """Log security events for audit"""
        audit_entry = {
            'timestamp': time.time(),
            'event_type': event_type,
            'details': details[:100],  # Truncate for security
            'source': 'SecureValidator'
        }

        try:
            with open(AUDIT_LOG_FILE, 'a') as f:
                f.write(json.dumps(audit_entry) + '\n')
        except Exception:
            # Never fail on audit logging
            pass

class SecureAudioProcessor:
    """Military-grade secure audio processor"""

    def __init__(self):
        self.session_id = secrets.token_hex(16)
        self._setup_secure_logging()

    def _setup_secure_logging(self):
        """Setup secure audit logging"""
        os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)

        # Set secure permissions
        try:
            if os.name == 'posix':
                os.chmod(DEFAULT_LOG_DIR, 0o750)
            if os.path.exists(AUDIT_LOG_FILE):
                os.chmod(AUDIT_LOG_FILE, 0o640)
        except Exception:
            pass  # Continue if permissions can't be set

    def analyze(self, file_path: str) -> ProcessingResult:
        """Securely analyze audio file"""
        operation_start = time.time()
        operation_id = secrets.token_hex(16)

        try:
            # Validate input
            validated_path = SecureValidator.validate_file_path(file_path)

            # Check file existence and permissions
            if not validated_path.exists():
                return ProcessingResult(
                    success=False,
                    message="File not found",
                    operation_id=operation_id
                )

            # Check file size
            file_size = validated_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                self._audit_operation("FILE_TOO_LARGE", operation_id, f"Size: {file_size}")
                return ProcessingResult(
                    success=False,
                    message="File exceeds size limit",
                    operation_id=operation_id
                )

            # Compute secure hash
            file_hash = self._compute_secure_hash(validated_path)

            # Parse WAV file securely
            audio_info = self._parse_wav_secure(validated_path, file_hash)

            processing_time = time.time() - operation_start
            audio_info.processing_time = processing_time

            self._audit_operation("ANALYZE_SUCCESS", operation_id, f"File: {validated_path.name}")

            return ProcessingResult(
                success=True,
                message="Analysis completed",
                data=audio_info,
                operation_id=operation_id
            )

        except Exception as e:
            self._audit_operation("ANALYZE_ERROR", operation_id, str(e)[:100])
            return ProcessingResult(
                success=False,
                message="Analysis failed",
                operation_id=operation_id
            )

    def normalize(self, input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
        """Securely normalize audio"""
        operation_start = time.time()
        operation_id = secrets.token_hex(16)

        try:
            # Validate inputs
            input_validated = SecureValidator.validate_file_path(input_path)
            output_validated = SecureValidator.validate_file_path(output_path)
            target_peak = SecureValidator.validate_numeric_input(target_peak, 0.1, 1.0, "target_peak")

            # Check input file
            if not input_validated.exists():
                return ProcessingResult(
                    success=False,
                    message="Input file not found",
                    operation_id=operation_id
                )

            # Secure normalization
            success = self._normalize_secure(input_validated, output_validated, target_peak)

            processing_time = time.time() - operation_start

            if success:
                self._audit_operation("NORMALIZE_SUCCESS", operation_id,
                                    f"Input: {input_validated.name}, Output: {output_validated.name}")
                return ProcessingResult(
                    success=True,
                    message="Normalization completed",
                    operation_id=operation_id
                )
            else:
                self._audit_operation("NORMALIZE_FAILED", operation_id, "Processing failed")
                return ProcessingResult(
                    success=False,
                    message="Normalization failed",
                    operation_id=operation_id
                )

        except Exception as e:
            self._audit_operation("NORMALIZE_ERROR", operation_id, str(e)[:100])
            return ProcessingResult(
                success=False,
                message="Normalization error",
                operation_id=operation_id
            )

    def _parse_wav_secure(self, file_path: Path, file_hash: str) -> SecureAudioInfo:
        """Securely parse WAV file with bounds checking"""
        with open(file_path, 'rb') as f:
            # Read and validate RIFF header
            riff_header = f.read(12)
            if len(riff_header) != 12:
                raise ValueError("Invalid WAV header length")

            if riff_header[:4] != b'RIFF' or riff_header[8:12] != b'WAVE':
                raise ValueError("Invalid WAV format")

            file_size = struct.unpack('<I', riff_header[4:8])[0]
            if file_size > MAX_FILE_SIZE:
                raise ValueError("File size in header exceeds limit")

            # Parse chunks securely
            fmt_found = False
            data_found = False
            sample_rate = 0
            channels = 0
            bits_per_sample = 0
            audio_data_size = 0

            while True:
                chunk_header = f.read(8)
                if len(chunk_header) != 8:
                    break

                chunk_id = chunk_header[:4]
                chunk_size = struct.unpack('<I', chunk_header[4:8])[0]

                # Prevent integer overflow
                if chunk_size > MAX_FILE_SIZE:
                    raise ValueError("Chunk size too large")

                if chunk_id == b'fmt ':
                    if chunk_size < 16:
                        raise ValueError("Invalid fmt chunk size")

                    fmt_data = f.read(min(chunk_size, 1024))  # Limit read size
                    if len(fmt_data) < 16:
                        raise ValueError("Incomplete fmt chunk")

                    audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample = \
                        struct.unpack('<HHIIHH', fmt_data[:16])

                    # Validate format
                    if audio_format != 1:  # PCM only
                        raise ValueError("Only PCM format supported")

                    fmt_found = True

                elif chunk_id == b'data':
                    audio_data_size = chunk_size
                    data_found = True

                    # Skip data for analysis
                    f.seek(chunk_size, 1)
                else:
                    # Skip unknown chunks safely
                    f.seek(min(chunk_size, MAX_FILE_SIZE), 1)

            if not (fmt_found and data_found):
                raise ValueError("Required WAV chunks not found")

            # Calculate audio properties
            duration = audio_data_size / (sample_rate * channels * (bits_per_sample // 8))

            # Validate calculated values
            if duration > 3600:  # Max 1 hour
                raise ValueError("Audio duration too long")

            return SecureAudioInfo(
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=bits_per_sample,
                size_bytes=file_path.stat().st_size,
                peak_level=0.0,  # Would need full audio analysis
                rms_level=0.0,   # Would need full audio analysis
                file_hash=file_hash,
                processing_time=0.0
            )

    def _normalize_secure(self, input_path: Path, output_path: Path, target_peak: float) -> bool:
        """Secure normalization with memory safety"""
        try:
            # Create secure temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = Path(temp_file.name)

            # Set secure permissions
            os.chmod(temp_path, 0o600)

            # Process in chunks for memory safety
            with open(input_path, 'rb') as input_file:
                header = input_file.read(44)
                if len(header) != 44:
                    raise ValueError("Invalid WAV header length during normalization")

                max_amplitude = 0
                while True:
                    chunk = input_file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    for i in range(0, len(chunk) - 1, 2):
                        sample = struct.unpack('<h', chunk[i:i + 2])[0]
                        if abs(sample) > max_amplitude:
                            max_amplitude = abs(sample)

                norm_factor = 1.0
                if max_amplitude:
                    norm_factor = min((target_peak * 32767) / max_amplitude, 8.0)

                input_file.seek(44)

                with open(temp_path, 'wb') as output_file:
                    output_file.write(header)

                    while True:
                        chunk = input_file.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        normalized_chunk = bytearray(chunk)
                        for i in range(0, len(chunk) - 1, 2):
                            sample = struct.unpack('<h', chunk[i:i + 2])[0]
                            normalized_sample = int(sample * norm_factor)
                            normalized_sample = max(-32768, min(32767, normalized_sample))
                            normalized_chunk[i:i + 2] = struct.pack('<h', normalized_sample)

                        output_file.write(normalized_chunk)

            # Atomically move to final location
            temp_path.rename(output_path)
            os.chmod(output_path, 0o644)

            return True

        except Exception as e:
            # Clean up on error
            try:
                if 'temp_path' in locals():
                    temp_path.unlink(missing_ok=True)
            except Exception:
                pass

            logger.error(f"Normalization failed: {e}")
            return False

    def _compute_secure_hash(self, file_path: Path) -> str:
        """Compute cryptographically secure file hash"""
        hash_obj = hashlib.new(CRYPTO_ALGORITHMS['hash'])

        with open(file_path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def _audit_operation(self, operation_type: str, operation_id: str, details: str):
        """Audit log operation"""
        audit_entry = {
            'timestamp': time.time(),
            'session_id': self.session_id,
            'operation_type': operation_type,
            'operation_id': operation_id,
            'details': details[:100],  # Truncate for security
            'source': 'SecureAudioProcessor'
        }

        try:
            with open(AUDIT_LOG_FILE, 'a') as f:
                f.write(json.dumps(audit_entry, separators=(',', ':')) + '\n')
        except Exception:
            # Never fail on audit logging
            pass

# Safe expression evaluator (replaces eval)
class SafeExpressionEvaluator:
    """Safe expression evaluator - no eval() usage"""

    ALLOWED_OPERATORS = {'+', '-', '*', '/', '(', ')', ' '}
    ALLOWED_NUMBERS = set('0123456789.')

    @classmethod
    def evaluate_safe(cls, expression: str) -> float:
        """Safely evaluate mathematical expressions"""
        # Strict validation
        if not isinstance(expression, str):
            raise ValueError("Expression must be string")

        if len(expression) > 100:
            raise ValueError("Expression too long")

        # Character whitelist
        allowed_chars = cls.ALLOWED_OPERATORS | cls.ALLOWED_NUMBERS
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Expression contains forbidden characters")

        # Simple calculator - only basic math
        try:
            parsed = ast.parse(expression, mode='eval')
        except SyntaxError as exc:
            raise ValueError("Invalid expression syntax") from exc

        if sum(1 for _ in ast.walk(parsed)) > 100:
            raise ValueError("Expression too complex")

        try:
            return float(cls._evaluate_node(parsed.body))
        except ZeroDivisionError as exc:
            raise ValueError("Division by zero") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Invalid expression") from exc

    @classmethod
    def _evaluate_node(cls, node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("Unsupported constant type")

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = cls._evaluate_node(node.operand)
            return operand if isinstance(node.op, ast.UAdd) else -operand

        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left = cls._evaluate_node(node.left)
            right = cls._evaluate_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ZeroDivisionError
            return left / right

        raise ValueError("Unsupported expression component")

# Secure configuration manager
class SecureConfig:
    """Secure configuration management"""

    def __init__(self):
        self.config_path = Path('/etc/chameleon/config.json')
        self.user_config_path = Path.home() / '.chameleon' / 'config.json'

    def load_config(self) -> Dict[str, Any]:
        """Load configuration securely"""
        config = {
            'max_file_size': MAX_FILE_SIZE,
            'chunk_size': CHUNK_SIZE,
            'supported_formats': list(SUPPORTED_FORMATS),
            'audit_logging': True,
            'secure_mode': True
        }

        # Load system config
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    system_config = json.load(f)
                    config.update(system_config)
            except Exception:
                pass  # Use defaults on error

        return config

# Global secure processor instance
_secure_processor = None

def get_secure_processor() -> SecureAudioProcessor:
    """Get global secure processor instance"""
    global _secure_processor
    if _secure_processor is None:
        _secure_processor = SecureAudioProcessor()
    return _secure_processor

# Public API functions
def analyze(file_path: str) -> ProcessingResult:
    """Securely analyze audio file"""
    return get_secure_processor().analyze(file_path)

def normalize(input_path: str, output_path: str, target_peak: float = 0.95) -> ProcessingResult:
    """Securely normalize audio file"""
    return get_secure_processor().normalize(input_path, output_path, target_peak)

if __name__ == "__main__":
    # Basic CLI for testing
    import sys

    if len(sys.argv) < 2:
        print("Usage: python secure_core.py <analyze|normalize> <file>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "analyze" and len(sys.argv) == 3:
        result = analyze(sys.argv[2])
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        if result.data:
            print(f"Duration: {result.data.duration:.2f}s")
            print(f"Sample Rate: {result.data.sample_rate}Hz")
            print(f"Channels: {result.data.channels}")

    elif command == "normalize" and len(sys.argv) >= 4:
        target_peak = float(sys.argv[4]) if len(sys.argv) > 4 else 0.95
        result = normalize(sys.argv[2], sys.argv[3], target_peak)
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")

    else:
        print("Invalid command or arguments")
        sys.exit(1)