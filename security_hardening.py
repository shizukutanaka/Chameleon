#!/usr/bin/env python3
"""
Security Hardening Module for Chameleon Audio System
Provides encryption, rate limiting, and secrets management
"""

import os
import time
import json
import hashlib
import secrets
import hmac
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import threading
import logging

logger = logging.getLogger("chameleon.security")


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    max_requests: int = 100
    window_seconds: int = 60
    block_duration: int = 300


class RateLimiter:
    """Thread-safe rate limiter to prevent DoS attacks"""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._requests: Dict[str, list] = defaultdict(list)
        self._blocked: Dict[str, float] = {}
        self._lock = threading.Lock()

    def check_limit(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """Check if identifier is within rate limits.

        Returns (allowed, error_message)
        """
        current_time = time.time()

        with self._lock:
            # Check if blocked
            if identifier in self._blocked:
                block_until = self._blocked[identifier]
                if current_time < block_until:
                    remaining = int(block_until - current_time)
                    return False, f"Rate limit exceeded. Try again in {remaining} seconds"
                else:
                    del self._blocked[identifier]

            # Clean old requests
            cutoff = current_time - self.config.window_seconds
            if identifier in self._requests:
                self._requests[identifier] = [
                    ts for ts in self._requests[identifier] if ts > cutoff
                ]

            # Check request count
            request_count = len(self._requests[identifier])
            if request_count >= self.config.max_requests:
                self._blocked[identifier] = current_time + self.config.block_duration
                return False, f"Rate limit exceeded ({self.config.max_requests} requests per {self.config.window_seconds}s)"

            # Record request
            self._requests[identifier].append(current_time)
            return True, None

    def reset(self, identifier: str) -> None:
        """Reset rate limit for identifier"""
        with self._lock:
            self._requests.pop(identifier, None)
            self._blocked.pop(identifier, None)


class SecretsManager:
    """Secure secrets management without external dependencies"""

    def __init__(self, secrets_dir: Optional[Path] = None):
        self.secrets_dir = secrets_dir or Path.home() / ".chameleon" / "secrets"
        self.secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._cache: Dict[str, Any] = {}

    def store_secret(self, key: str, value: str) -> None:
        """Store encrypted secret"""
        secret_path = self.secrets_dir / f"{self._hash_key(key)}.enc"

        # Simple XOR encryption with generated key
        encryption_key = self._get_or_create_encryption_key()
        encrypted = self._xor_encrypt(value.encode('utf-8'), encryption_key)

        with open(secret_path, 'wb') as f:
            f.write(encrypted)

        os.chmod(secret_path, 0o600)
        self._cache[key] = value

    def retrieve_secret(self, key: str) -> Optional[str]:
        """Retrieve and decrypt secret"""
        if key in self._cache:
            return self._cache[key]

        secret_path = self.secrets_dir / f"{self._hash_key(key)}.enc"
        if not secret_path.exists():
            return None

        encryption_key = self._get_or_create_encryption_key()
        with open(secret_path, 'rb') as f:
            encrypted = f.read()

        decrypted = self._xor_encrypt(encrypted, encryption_key)
        value = decrypted.decode('utf-8')
        self._cache[key] = value
        return value

    def delete_secret(self, key: str) -> None:
        """Delete secret"""
        secret_path = self.secrets_dir / f"{self._hash_key(key)}.enc"
        if secret_path.exists():
            secret_path.unlink()
        self._cache.pop(key, None)

    def _hash_key(self, key: str) -> str:
        """Hash key for filename"""
        return hashlib.sha256(key.encode('utf-8')).hexdigest()[:32]

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create master encryption key"""
        key_path = self.secrets_dir / ".master.key"

        if key_path.exists():
            with open(key_path, 'rb') as f:
                return f.read()

        # Generate new key
        key = secrets.token_bytes(32)
        with open(key_path, 'wb') as f:
            f.write(key)
        os.chmod(key_path, 0o600)
        return key

    def _xor_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption (not production-grade, but dependency-free)"""
        key_len = len(key)
        return bytes(data[i] ^ key[i % key_len] for i in range(len(data)))


class FileEncryption:
    """File encryption at rest using XOR + HMAC"""

    def __init__(self, secrets_manager: SecretsManager):
        self.secrets_manager = secrets_manager

    def encrypt_file(self, input_path: Path, output_path: Path, key_name: str = "default") -> None:
        """Encrypt file and write to output"""
        encryption_key = self._get_encryption_key(key_name)

        with open(input_path, 'rb') as f:
            plaintext = f.read()

        # Generate IV
        iv = secrets.token_bytes(16)

        # Encrypt (XOR for simplicity)
        ciphertext = self._xor_encrypt(plaintext, encryption_key, iv)

        # Generate HMAC
        mac = hmac.new(encryption_key, iv + ciphertext, hashlib.sha256).digest()

        # Write: IV || MAC || Ciphertext
        with open(output_path, 'wb') as f:
            f.write(iv)
            f.write(mac)
            f.write(ciphertext)

        os.chmod(output_path, 0o600)

    def decrypt_file(self, input_path: Path, output_path: Path, key_name: str = "default") -> None:
        """Decrypt file and write to output"""
        encryption_key = self._get_encryption_key(key_name)

        with open(input_path, 'rb') as f:
            data = f.read()

        # Extract components
        iv = data[:16]
        mac = data[16:48]
        ciphertext = data[48:]

        # Verify HMAC
        expected_mac = hmac.new(encryption_key, iv + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("File integrity check failed - possible tampering")

        # Decrypt
        plaintext = self._xor_encrypt(ciphertext, encryption_key, iv)

        with open(output_path, 'wb') as f:
            f.write(plaintext)

        os.chmod(output_path, 0o600)

    def _get_encryption_key(self, key_name: str) -> bytes:
        """Get or generate encryption key"""
        key_str = self.secrets_manager.retrieve_secret(f"encryption_key_{key_name}")
        if key_str:
            return bytes.fromhex(key_str)

        # Generate new key
        key = secrets.token_bytes(32)
        self.secrets_manager.store_secret(f"encryption_key_{key_name}", key.hex())
        return key

    def _xor_encrypt(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        """XOR encryption with IV"""
        combined_key = hashlib.sha256(key + iv).digest()
        key_len = len(combined_key)
        return bytes(data[i] ^ combined_key[i % key_len] for i in range(len(data)))


class SecurityAuditor:
    """Security event auditing"""

    def __init__(self, audit_dir: Optional[Path] = None):
        self.audit_dir = audit_dir or Path.home() / ".chameleon" / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._setup_logging()

    def _setup_logging(self):
        """Setup audit logging"""
        from logging.handlers import RotatingFileHandler

        audit_file = self.audit_dir / "security.log"
        handler = RotatingFileHandler(
            audit_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))

        self.logger = logging.getLogger("chameleon.security.audit")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log security event"""
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "details": details
        }
        self.logger.info(json.dumps(event))

    def log_access(self, path: str, operation: str, success: bool, user: str = "system") -> None:
        """Log file access"""
        self.log_event("file_access", {
            "path": path,
            "operation": operation,
            "success": success,
            "user": user
        })

    def log_rate_limit(self, identifier: str, blocked: bool) -> None:
        """Log rate limiting event"""
        self.log_event("rate_limit", {
            "identifier": identifier,
            "blocked": blocked
        })

    def log_authentication(self, user: str, success: bool, method: str = "api_key") -> None:
        """Log authentication attempt"""
        self.log_event("authentication", {
            "user": user,
            "success": success,
            "method": method
        })


# Global instances
_rate_limiter: Optional[RateLimiter] = None
_secrets_manager: Optional[SecretsManager] = None
_file_encryption: Optional[FileEncryption] = None
_security_auditor: Optional[SecurityAuditor] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_secrets_manager() -> SecretsManager:
    """Get global secrets manager instance"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def get_file_encryption() -> FileEncryption:
    """Get global file encryption instance"""
    global _file_encryption
    if _file_encryption is None:
        _file_encryption = FileEncryption(get_secrets_manager())
    return _file_encryption


def get_security_auditor() -> SecurityAuditor:
    """Get global security auditor instance"""
    global _security_auditor
    if _security_auditor is None:
        _security_auditor = SecurityAuditor()
    return _security_auditor


if __name__ == "__main__":
    # Test security features
    print("Testing Security Hardening Module...")

    # Test rate limiter
    limiter = get_rate_limiter()
    for i in range(105):
        allowed, msg = limiter.check_limit("test_user")
        if not allowed:
            print(f"Rate limited after {i} requests: {msg}")
            break

    # Test secrets manager
    secrets = get_secrets_manager()
    secrets.store_secret("api_key", "secret_value_123")
    retrieved = secrets.retrieve_secret("api_key")
    print(f"Secret stored and retrieved: {retrieved == 'secret_value_123'}")

    # Test file encryption
    from tempfile import NamedTemporaryFile
    encryption = get_file_encryption()

    with NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"Test data for encryption")
        tmp_path = Path(tmp.name)

    encrypted_path = tmp_path.with_suffix('.enc')
    decrypted_path = tmp_path.with_suffix('.dec')

    encryption.encrypt_file(tmp_path, encrypted_path)
    encryption.decrypt_file(encrypted_path, decrypted_path)

    with open(decrypted_path, 'rb') as f:
        decrypted = f.read()

    print(f"Encryption/decryption: {decrypted == b'Test data for encryption'}")

    # Cleanup
    tmp_path.unlink()
    encrypted_path.unlink()
    decrypted_path.unlink()

    # Test auditor
    auditor = get_security_auditor()
    auditor.log_access("/path/to/file.wav", "read", True)
    auditor.log_rate_limit("test_user", True)

    print("Security hardening tests completed")
