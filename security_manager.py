#!/usr/bin/env python3
"""
Security Manager - 包括的セキュリティ機能
入力検証、認証、認可、データ保護を提供
"""

import hashlib
import hmac
import secrets
import re
import json
import time
import base64
from typing import Dict, Any, Optional, List, Set, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import threading
import logging

# Import error handling
try:
    from robust_error_handler import (
        with_error_handling, get_error_handler,
        ErrorSeverity, ErrorCategory
    )
    ERROR_HANDLING_AVAILABLE = True
except ImportError:
    def with_error_handling(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    ERROR_HANDLING_AVAILABLE = False

class SecurityLevel(Enum):
    """セキュリティレベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AuthenticationMethod(Enum):
    """認証方式"""
    NONE = "none"
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    OAUTH = "oauth"
    CERTIFICATE = "certificate"

@dataclass
class SecurityPolicy:
    """セキュリティポリシー"""
    min_password_length: int = 8
    require_special_chars: bool = True
    require_numbers: bool = True
    require_uppercase: bool = True
    max_login_attempts: int = 5
    session_timeout_minutes: int = 60
    require_https: bool = True
    allowed_file_types: Set[str] = field(default_factory=lambda: {'.wav', '.mp3', '.flac'})
    max_file_size_mb: int = 100
    rate_limit_per_minute: int = 100
    enable_audit_logging: bool = True

@dataclass
class SecurityContext:
    """セキュリティコンテキスト"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    authenticated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class InputValidator:
    """入力検証クラス"""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self.logger = logging.getLogger("InputValidator")
        
        # 危険なパターン
        self.dangerous_patterns = [
            r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>',  # Script tags
            r'javascript:',  # JavaScript URLs
            r'on\w+\s*=',   # Event handlers
            r'eval\s*\(',   # eval() calls
            r'exec\s*\(',   # exec() calls
            r'import\s+\w+', # Python imports
            r'__\w+__',     # Python magic methods
            r'\.\.\/',      # Directory traversal
            r'\.\.\\',      # Windows directory traversal
        ]
        
        self.sql_injection_patterns = [
            r';\s*(drop|delete|insert|update|create|alter)\s+',
            r'union\s+select',
            r'or\s+1\s*=\s*1',
            r'and\s+1\s*=\s*1',
            r'--\s*',
            r'/\*.*?\*/',
        ]
    
    @with_error_handling("InputValidator", 
                        category=ErrorCategory.VALIDATION,
                        severity=ErrorSeverity.WARNING)
    def validate_string(self, value: str, 
                       max_length: int = 1000,
                       allow_html: bool = False,
                       allow_sql: bool = False) -> bool:
        """文字列入力を検証"""
        if not isinstance(value, str):
            raise TypeError(f"Expected string, got {type(value)}")
        
        if len(value) > max_length:
            raise ValueError(f"String too long: {len(value)} > {max_length}")
        
        # XSS攻撃パターンチェック
        if not allow_html:
            for pattern in self.dangerous_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise ValueError(f"Potentially dangerous content detected: {pattern}")
        
        # SQLインジェクション攻撃パターンチェック
        if not allow_sql:
            for pattern in self.sql_injection_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise ValueError(f"Potential SQL injection detected: {pattern}")
        
        return True
    
    def validate_email(self, email: str) -> bool:
        """メールアドレス検証"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError("Invalid email format")
        return True
    
    def validate_file_upload(self, filename: str, file_size: int, content: bytes) -> bool:
        """ファイルアップロード検証"""
        # ファイル名検証
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            raise ValueError("Invalid filename")
        
        # 拡張子チェック
        file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
        if file_ext not in self.policy.allowed_file_types:
            raise ValueError(f"File type not allowed: {file_ext}")
        
        # ファイルサイズチェック
        max_size = self.policy.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise ValueError(f"File too large: {file_size} > {max_size}")
        
        # ファイルコンテンツの基本チェック
        if not content:
            raise ValueError("Empty file content")
        
        # マジックバイトチェック（簡易版）
        if file_ext == '.wav' and not content.startswith(b'RIFF'):
            raise ValueError("Invalid WAV file format")
        elif file_ext == '.mp3' and not (content.startswith(b'ID3') or content.startswith(b'\xff\xfb')):
            raise ValueError("Invalid MP3 file format")
        
        return True
    
    def sanitize_input(self, value: str) -> str:
        """入力のサニタイズ"""
        if not isinstance(value, str):
            return str(value)
        
        # HTMLエスケープ
        value = value.replace('&', '&amp;')
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        value = value.replace('"', '&quot;')
        value = value.replace("'", '&#x27;')
        
        # 制御文字除去
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        return value.strip()

class AuthenticationManager:
    """認証管理クラス"""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self.logger = logging.getLogger("AuthenticationManager")
        self.failed_attempts = {}
        self.active_sessions = {}
        self.api_keys = set()
        self.lock = threading.RLock()
        
        # セッション用のsecret key
        self.secret_key = secrets.token_bytes(32)
    
    def generate_api_key(self) -> str:
        """API キー生成"""
        api_key = secrets.token_urlsafe(32)
        with self.lock:
            self.api_keys.add(api_key)
        self.logger.info("New API key generated")
        return api_key
    
    def validate_api_key(self, api_key: str) -> bool:
        """API キー検証"""
        with self.lock:
            return api_key in self.api_keys
    
    def create_session(self, user_id: str, 
                      ip_address: str,
                      permissions: Set[str] = None) -> SecurityContext:
        """セッション作成"""
        session_id = secrets.token_urlsafe(32)
        now = datetime.now()
        expires_at = now + timedelta(minutes=self.policy.session_timeout_minutes)
        
        context = SecurityContext(
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            permissions=permissions or set(),
            authenticated_at=now,
            expires_at=expires_at
        )
        
        with self.lock:
            self.active_sessions[session_id] = context
        
        self.logger.info(f"Session created for user {user_id}: {session_id}")
        return context
    
    def validate_session(self, session_id: str) -> Optional[SecurityContext]:
        """セッション検証"""
        with self.lock:
            context = self.active_sessions.get(session_id)
            
            if not context:
                return None
            
            # 期限チェック
            if context.expires_at and datetime.now() > context.expires_at:
                del self.active_sessions[session_id]
                self.logger.info(f"Session expired: {session_id}")
                return None
            
            return context
    
    def revoke_session(self, session_id: str):
        """セッション無効化"""
        with self.lock:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
                self.logger.info(f"Session revoked: {session_id}")
    
    def check_rate_limit(self, identifier: str) -> bool:
        """レート制限チェック"""
        current_time = time.time()
        minute_ago = current_time - 60
        
        with self.lock:
            if identifier not in self.failed_attempts:
                self.failed_attempts[identifier] = []
            
            # 古い試行を削除
            self.failed_attempts[identifier] = [
                attempt_time for attempt_time in self.failed_attempts[identifier]
                if attempt_time > minute_ago
            ]
            
            # レート制限チェック
            if len(self.failed_attempts[identifier]) >= self.policy.rate_limit_per_minute:
                return False
            
            # 現在の試行を記録
            self.failed_attempts[identifier].append(current_time)
            return True

class EncryptionManager:
    """暗号化管理クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger("EncryptionManager")
        self.key = secrets.token_bytes(32)  # AES-256用のキー
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
        """パスワードハッシュ化"""
        if salt is None:
            salt = secrets.token_bytes(32)
        
        # PBKDF2でハッシュ化
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        
        return base64.b64encode(hashed).decode('ascii'), base64.b64encode(salt).decode('ascii')
    
    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """パスワード検証"""
        try:
            salt_bytes = base64.b64decode(salt.encode('ascii'))
            hashed_bytes = base64.b64decode(hashed.encode('ascii'))
            
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000)
            return hmac.compare_digest(hashed_bytes, new_hash)
        except Exception:
            return False
    
    def generate_hmac(self, data: str, key: Optional[bytes] = None) -> str:
        """HMAC生成"""
        if key is None:
            key = self.key
        
        mac = hmac.new(key, data.encode('utf-8'), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode('ascii')
    
    def verify_hmac(self, data: str, signature: str, key: Optional[bytes] = None) -> bool:
        """HMAC検証"""
        if key is None:
            key = self.key
        
        try:
            expected_signature = self.generate_hmac(data, key)
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False

class SecurityManager:
    """統合セキュリティマネージャー"""
    
    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self.logger = logging.getLogger("SecurityManager")
        
        # 各種マネージャー初期化
        self.validator = InputValidator(self.policy)
        self.auth_manager = AuthenticationManager(self.policy)
        self.encryption_manager = EncryptionManager()
        
        # 監査ログ
        self.audit_log = []
        self.lock = threading.RLock()
        
        if ERROR_HANDLING_AVAILABLE:
            self.error_handler = get_error_handler("SecurityManager")
    
    @with_error_handling("SecurityManager",
                        category=ErrorCategory.SECURITY,
                        severity=ErrorSeverity.CRITICAL)
    def validate_and_sanitize_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """入力データの検証とサニタイズ"""
        sanitized = {}
        
        for key, value in data.items():
            # キーの検証
            if not isinstance(key, str) or not key.isalnum():
                raise ValueError(f"Invalid key format: {key}")
            
            # 値の検証とサニタイズ
            if isinstance(value, str):
                self.validator.validate_string(value)
                sanitized[key] = self.validator.sanitize_input(value)
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, list):
                sanitized[key] = [
                    self.validator.sanitize_input(str(item)) if isinstance(item, str) else item
                    for item in value
                ]
            elif isinstance(value, dict):
                sanitized[key] = self.validate_and_sanitize_input(value)
            else:
                self.logger.warning(f"Unsupported data type for key {key}: {type(value)}")
                sanitized[key] = str(value)
        
        return sanitized
    
    def authenticate_request(self, headers: Dict[str, str], 
                           ip_address: str) -> Optional[SecurityContext]:
        """リクエスト認証"""
        # レート制限チェック
        if not self.auth_manager.check_rate_limit(ip_address):
            self.audit_log_event("RATE_LIMIT_EXCEEDED", {"ip": ip_address})
            raise PermissionError("Rate limit exceeded")
        
        # API キー認証
        api_key = headers.get('X-API-Key') or headers.get('Authorization', '').replace('Bearer ', '')
        if api_key and self.auth_manager.validate_api_key(api_key):
            context = SecurityContext(
                ip_address=ip_address,
                permissions={'api_access'},
                security_level=SecurityLevel.MEDIUM,
                authenticated_at=datetime.now()
            )
            self.audit_log_event("API_AUTH_SUCCESS", {"ip": ip_address})
            return context
        
        # セッション認証
        session_id = headers.get('X-Session-ID')
        if session_id:
            context = self.auth_manager.validate_session(session_id)
            if context:
                self.audit_log_event("SESSION_AUTH_SUCCESS", 
                                   {"user_id": context.user_id, "ip": ip_address})
                return context
        
        self.audit_log_event("AUTH_FAILURE", {"ip": ip_address})
        return None
    
    def check_permissions(self, context: SecurityContext, 
                         required_permissions: Set[str]) -> bool:
        """権限チェック"""
        if not context.permissions:
            return False
        
        # 管理者権限チェック
        if 'admin' in context.permissions:
            return True
        
        # 必要な権限をすべて持っているかチェック
        return required_permissions.issubset(context.permissions)
    
    def audit_log_event(self, event_type: str, details: Dict[str, Any]):
        """監査ログ記録"""
        if not self.policy.enable_audit_logging:
            return
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': details
        }
        
        with self.lock:
            self.audit_log.append(log_entry)
            if len(self.audit_log) > 10000:  # ログサイズ制限
                self.audit_log = self.audit_log[-5000:]
        
        self.logger.info(f"Audit: {event_type} - {details}")
    
    def get_security_report(self) -> Dict[str, Any]:
        """セキュリティレポート生成"""
        with self.lock:
            return {
                'policy': {
                    'min_password_length': self.policy.min_password_length,
                    'require_https': self.policy.require_https,
                    'session_timeout_minutes': self.policy.session_timeout_minutes,
                    'max_file_size_mb': self.policy.max_file_size_mb,
                    'rate_limit_per_minute': self.policy.rate_limit_per_minute
                },
                'sessions': {
                    'active_count': len(self.auth_manager.active_sessions),
                    'api_keys_count': len(self.auth_manager.api_keys)
                },
                'audit_log_entries': len(self.audit_log),
                'recent_events': self.audit_log[-10:] if self.audit_log else []
            }

# Security decorators
def require_authentication(required_permissions: Set[str] = None):
    """認証が必要なエンドポイント用デコレーター"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # セキュリティコンテキストを取得（実装は具体的なフレームワークに依存）
            context = kwargs.get('security_context')
            if not context:
                raise PermissionError("Authentication required")
            
            # 権限チェック
            if required_permissions:
                security_manager = get_security_manager()
                if not security_manager.check_permissions(context, required_permissions):
                    raise PermissionError("Insufficient permissions")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def validate_input(validation_rules: Dict[str, Any] = None):
    """入力検証用デコレーター"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            security_manager = get_security_manager()
            
            # kwargs の検証
            if validation_rules:
                for key, rules in validation_rules.items():
                    if key in kwargs:
                        value = kwargs[key]
                        if 'max_length' in rules and len(str(value)) > rules['max_length']:
                            raise ValueError(f"Value too long for {key}")
            
            # 一般的な入力サニタイズ
            sanitized_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, str):
                    sanitized_kwargs[key] = security_manager.validator.sanitize_input(value)
                else:
                    sanitized_kwargs[key] = value
            
            return func(*args, **sanitized_kwargs)
        return wrapper
    return decorator

# Global security manager
_global_security_manager = None
_security_lock = threading.RLock()

def get_security_manager() -> SecurityManager:
    """グローバルセキュリティマネージャー取得"""
    global _global_security_manager
    with _security_lock:
        if _global_security_manager is None:
            _global_security_manager = SecurityManager()
        return _global_security_manager

if __name__ == "__main__":
    # セキュリティマネージャーのテスト
    print("🔒 Security Manager Test")
    print("=" * 40)
    
    sm = get_security_manager()
    
    # 入力検証テスト
    test_data = {
        "username": "test_user",
        "description": "This is a <script>alert('xss')</script> test",
        "age": 25
    }
    
    try:
        sanitized = sm.validate_and_sanitize_input(test_data)
        print(f"✓ Input validation passed")
        print(f"  Sanitized description: {sanitized['description']}")
    except Exception as e:
        print(f"✗ Input validation failed: {e}")
    
    # API キー生成テスト
    api_key = sm.auth_manager.generate_api_key()
    print(f"✓ API key generated: {api_key[:8]}...")
    
    # セキュリティレポート
    report = sm.get_security_report()
    print(f"✓ Security report generated")
    print(f"  Active sessions: {report['sessions']['active_count']}")
    print(f"  Audit log entries: {report['audit_log_entries']}")