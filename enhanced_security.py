#!/usr/bin/env python3
"""
Enhanced Security Module for Government-Grade Deployment
Provides advanced security features for national-level usage
"""

import os
import sys
import time
import hmac
import hashlib
import secrets
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger("chameleon.enhanced_security")


@dataclass
class SecurityPolicy:
    """Security policy configuration for government-grade deployment"""

    # Authentication
    require_api_key: bool = True
    api_key_min_length: int = 32
    api_key_rotation_days: int = 90

    # Authorization
    enable_rbac: bool = True
    default_role: str = "user"

    # Data protection
    require_encryption: bool = True
    encryption_algorithm: str = "AES-256-GCM"

    # Audit
    audit_all_operations: bool = True
    audit_retention_days: int = 2555  # 7 years

    # Rate limiting
    max_requests_per_minute: int = 60
    max_concurrent_operations: int = 10

    # File validation
    max_file_size_bytes: int = 500 * 1024 * 1024
    allowed_extensions: List[str] = field(default_factory=lambda: ['.wav', '.wave'])
    deep_file_inspection: bool = True

    # Network security
    allowed_ip_ranges: List[str] = field(default_factory=list)
    deny_by_default: bool = True


class APIKeyManager:
    """Secure API key management with rotation and revocation"""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path.home() / ".chameleon" / "api_keys"
        self.storage_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._keys_file = self.storage_dir / "keys.json"
        self._revoked_file = self.storage_dir / "revoked.json"

    def generate_api_key(self, user_id: str, expiry_days: int = 90) -> str:
        """Generate new API key with expiration"""

        # Generate cryptographically secure key
        key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Store key metadata
        keys_data = self._load_keys()
        keys_data[key_hash] = {
            "user_id": user_id,
            "created": datetime.now().isoformat(),
            "expires": (datetime.now() + timedelta(days=expiry_days)).isoformat(),
            "active": True
        }
        self._save_keys(keys_data)

        logger.info(f"API key generated for user {user_id}")
        return key

    def validate_api_key(self, key: str) -> Tuple[bool, Optional[str]]:
        """Validate API key and return user_id if valid"""

        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Check if revoked
        if self._is_revoked(key_hash):
            return False, None

        # Check if exists and not expired
        keys_data = self._load_keys()
        if key_hash not in keys_data:
            return False, None

        key_info = keys_data[key_hash]

        if not key_info.get("active", False):
            return False, None

        # Check expiration
        expires = datetime.fromisoformat(key_info["expires"])
        if datetime.now() > expires:
            return False, None

        return True, key_info["user_id"]

    def revoke_api_key(self, key: str) -> None:
        """Revoke API key"""

        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Mark as revoked
        revoked_data = self._load_revoked()
        revoked_data[key_hash] = {
            "revoked_at": datetime.now().isoformat()
        }
        self._save_revoked(revoked_data)

        # Update keys file
        keys_data = self._load_keys()
        if key_hash in keys_data:
            keys_data[key_hash]["active"] = False
            self._save_keys(keys_data)

        logger.warning(f"API key revoked: {key_hash[:8]}...")

    def rotate_expiring_keys(self, days_before: int = 7) -> List[str]:
        """Find keys expiring soon"""

        expiring = []
        keys_data = self._load_keys()
        threshold = datetime.now() + timedelta(days=days_before)

        for key_hash, info in keys_data.items():
            expires = datetime.fromisoformat(info["expires"])
            if expires < threshold and info.get("active", False):
                expiring.append(info["user_id"])

        return expiring

    def _load_keys(self) -> Dict:
        if not self._keys_file.exists():
            return {}
        with open(self._keys_file, 'r') as f:
            return json.load(f)

    def _save_keys(self, data: Dict) -> None:
        with open(self._keys_file, 'w') as f:
            json.dump(data, f, indent=2)
        os.chmod(self._keys_file, 0o600)

    def _load_revoked(self) -> Dict:
        if not self._revoked_file.exists():
            return {}
        with open(self._revoked_file, 'r') as f:
            return json.load(f)

    def _save_revoked(self, data: Dict) -> None:
        with open(self._revoked_file, 'w') as f:
            json.dump(data, f, indent=2)
        os.chmod(self._revoked_file, 0o600)

    def _is_revoked(self, key_hash: str) -> bool:
        revoked = self._load_revoked()
        return key_hash in revoked


class RoleBasedAccessControl:
    """Role-based access control system"""

    ROLES = {
        "admin": {
            "permissions": ["read", "write", "delete", "configure", "audit"],
            "description": "Full system access"
        },
        "operator": {
            "permissions": ["read", "write", "audit"],
            "description": "Process files and view audit logs"
        },
        "analyst": {
            "permissions": ["read", "audit"],
            "description": "Read-only access with audit viewing"
        },
        "user": {
            "permissions": ["read"],
            "description": "Basic read-only access"
        }
    }

    def __init__(self):
        self.user_roles: Dict[str, str] = {}

    def assign_role(self, user_id: str, role: str) -> None:
        """Assign role to user"""
        if role not in self.ROLES:
            raise ValueError(f"Invalid role: {role}")

        self.user_roles[user_id] = role
        logger.info(f"Role {role} assigned to {user_id}")

    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has permission"""

        role = self.user_roles.get(user_id, "user")
        permissions = self.ROLES.get(role, {}).get("permissions", [])

        return permission in permissions

    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for user"""

        role = self.user_roles.get(user_id, "user")
        return self.ROLES.get(role, {}).get("permissions", [])


class ComplianceLogger:
    """Compliance-focused audit logging for government requirements"""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path.home() / ".chameleon" / "compliance_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._setup_logging()

    def _setup_logging(self):
        """Setup tamper-evident logging"""
        from logging.handlers import RotatingFileHandler

        log_file = self.log_dir / "compliance.jsonl"

        # JSON Lines format for easy parsing
        handler = RotatingFileHandler(
            log_file,
            maxBytes=100*1024*1024,  # 100MB
            backupCount=50,  # Keep 50 files = ~5GB
            encoding='utf-8'
        )

        self.logger = logging.getLogger("chameleon.compliance")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def log_access(
        self,
        user_id: str,
        action: str,
        resource: str,
        success: bool,
        metadata: Optional[Dict] = None
    ) -> None:
        """Log access event in compliance format"""

        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "access",
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "success": success,
            "metadata": metadata or {},
            "signature": self._sign_event({
                "user_id": user_id,
                "action": action,
                "resource": resource
            })
        }

        self.logger.info(json.dumps(event))

    def log_data_modification(
        self,
        user_id: str,
        file_path: str,
        operation: str,
        checksum_before: Optional[str] = None,
        checksum_after: Optional[str] = None
    ) -> None:
        """Log data modification with checksums"""

        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "data_modification",
            "user_id": user_id,
            "file_path": file_path,
            "operation": operation,
            "checksum_before": checksum_before,
            "checksum_after": checksum_after,
            "signature": self._sign_event({
                "user_id": user_id,
                "file_path": file_path,
                "operation": operation
            })
        }

        self.logger.info(json.dumps(event))

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        details: Optional[Dict] = None
    ) -> None:
        """Log security event"""

        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "security",
            "severity": severity,
            "description": description,
            "details": details or {},
            "signature": self._sign_event({
                "event_type": event_type,
                "severity": severity
            })
        }

        self.logger.info(json.dumps(event))

    def _sign_event(self, event_data: Dict) -> str:
        """Create tamper-evident signature for event"""

        # Use HMAC for event signing
        secret = self._get_signing_key()
        message = json.dumps(event_data, sort_keys=True).encode()
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()

        return signature

    def _get_signing_key(self) -> bytes:
        """Get or create signing key"""

        key_file = self.log_dir / ".signing_key"

        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()

        # Generate new key
        key = secrets.token_bytes(32)
        with open(key_file, 'wb') as f:
            f.write(key)
        os.chmod(key_file, 0o600)

        return key


class IPWhitelist:
    """IP address whitelist for network access control"""

    def __init__(self):
        self.allowed_ips: List[str] = []
        self.allowed_ranges: List[Tuple[int, int]] = []

    def add_ip(self, ip: str) -> None:
        """Add single IP to whitelist"""
        self.allowed_ips.append(ip)

    def add_range(self, cidr: str) -> None:
        """Add IP range in CIDR notation"""
        # Simple CIDR parsing
        ip, mask = cidr.split('/')
        mask_bits = int(mask)

        ip_int = self._ip_to_int(ip)
        range_start = ip_int & (0xFFFFFFFF << (32 - mask_bits))
        range_end = range_start | ((1 << (32 - mask_bits)) - 1)

        self.allowed_ranges.append((range_start, range_end))

    def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed"""

        # Check exact matches
        if ip in self.allowed_ips:
            return True

        # Check ranges
        ip_int = self._ip_to_int(ip)
        for start, end in self.allowed_ranges:
            if start <= ip_int <= end:
                return True

        return False

    def _ip_to_int(self, ip: str) -> int:
        """Convert IP string to integer"""
        parts = ip.split('.')
        return (int(parts[0]) << 24) + (int(parts[1]) << 16) + \
               (int(parts[2]) << 8) + int(parts[3])


class DataClassification:
    """Data classification and handling requirements"""

    CLASSIFICATIONS = {
        "public": {
            "encryption_required": False,
            "audit_level": "basic",
            "retention_days": 365
        },
        "internal": {
            "encryption_required": True,
            "audit_level": "standard",
            "retention_days": 1095  # 3 years
        },
        "confidential": {
            "encryption_required": True,
            "audit_level": "detailed",
            "retention_days": 2555  # 7 years
        },
        "secret": {
            "encryption_required": True,
            "audit_level": "comprehensive",
            "retention_days": 3650  # 10 years
        }
    }

    @classmethod
    def get_requirements(cls, classification: str) -> Dict:
        """Get handling requirements for classification level"""
        return cls.CLASSIFICATIONS.get(classification, cls.CLASSIFICATIONS["internal"])


# Global instances
_api_key_manager: Optional[APIKeyManager] = None
_rbac: Optional[RoleBasedAccessControl] = None
_compliance_logger: Optional[ComplianceLogger] = None
_ip_whitelist: Optional[IPWhitelist] = None


def get_api_key_manager() -> APIKeyManager:
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_rbac() -> RoleBasedAccessControl:
    global _rbac
    if _rbac is None:
        _rbac = RoleBasedAccessControl()
    return _rbac


def get_compliance_logger() -> ComplianceLogger:
    global _compliance_logger
    if _compliance_logger is None:
        _compliance_logger = ComplianceLogger()
    return _compliance_logger


def get_ip_whitelist() -> IPWhitelist:
    global _ip_whitelist
    if _ip_whitelist is None:
        _ip_whitelist = IPWhitelist()
    return _ip_whitelist


if __name__ == "__main__":
    print("Testing Enhanced Security Module...")

    # Test API key management
    key_mgr = get_api_key_manager()
    api_key = key_mgr.generate_api_key("user123", expiry_days=90)
    print(f"Generated API key: {api_key[:16]}...")

    valid, user_id = key_mgr.validate_api_key(api_key)
    print(f"Validation: {valid}, User: {user_id}")

    # Test RBAC
    rbac = get_rbac()
    rbac.assign_role("user123", "operator")
    can_write = rbac.check_permission("user123", "write")
    print(f"User can write: {can_write}")

    # Test compliance logging
    comp_log = get_compliance_logger()
    comp_log.log_access("user123", "read", "/data/file.wav", True)
    comp_log.log_security_event("login_attempt", "info", "User logged in")

    # Test IP whitelist
    whitelist = get_ip_whitelist()
    whitelist.add_range("192.168.1.0/24")
    allowed = whitelist.is_allowed("192.168.1.100")
    print(f"IP allowed: {allowed}")

    # Test data classification
    requirements = DataClassification.get_requirements("confidential")
    print(f"Confidential data requirements: {requirements}")

    print("Enhanced security tests completed")
