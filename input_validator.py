#!/usr/bin/env python3
"""
Chameleon Audio System - Input Validation & Sanitization Module

入力検証・サニタイゼーション機能
- ファイルパス検証
- 音声パラメータ検証
- ユーザ入力サニタイゼーション
- セキュリティ制約チェック
"""

import os
import re
import pathlib
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum

class ValidationLevel(Enum):
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    PARANOID = "paranoid"

class ValidationError(Exception):
    """入力検証エラー"""
    pass

class InputValidator:
    """入力検証・サニタイゼーションクラス"""
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        self.validation_level = validation_level
        
        # セキュリティ制約
        self.max_file_size = 500 * 1024 * 1024  # 500MB
        self.allowed_extensions = {
            '.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma', '.aiff'
        }
        self.forbidden_paths = {
            '/etc', '/proc', '/sys', '/dev', '/root', '/boot',
            'C:\\Windows', 'C:\\Program Files', 'C:\\System32'
        }
        
        # パラメータ制約
        self.param_limits = {
            'sample_rate': (8000, 192000),
            'bit_depth': (8, 32),
            'channels': (1, 8),
            'buffer_size': (64, 8192),
            'pitch': (0.25, 4.0),
            'speed': (0.25, 4.0),
            'formant': (0.25, 4.0),
            'volume': (0.0, 10.0),
            'gain': (-60.0, 20.0),
            'reverb': (0.0, 1.0),
            'delay': (0.0, 5.0),
            'duration': (0.1, 3600.0),
            'frequency': (20.0, 20000.0)
        }
        
    def validate_file_path(self, file_path: str, 
                          mode: str = 'read') -> str:
        """ファイルパス検証"""
        if not file_path or not isinstance(file_path, str):
            raise ValidationError("Invalid file path: must be non-empty string")
            
        # パス正規化
        try:
            normalized_path = os.path.normpath(os.path.abspath(file_path))
        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid file path: {e}")
            
        # パストラバーサル攻撃防止
        if '..' in file_path or '~' in file_path:
            if self.validation_level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
                raise ValidationError("Path traversal detected")
                
        # 禁止パスチェック
        for forbidden in self.forbidden_paths:
            if normalized_path.startswith(forbidden):
                raise ValidationError(f"Access to system path forbidden: {forbidden}")
                
        # 拡張子チェック
        if mode == 'read':
            ext = pathlib.Path(file_path).suffix.lower()
            if ext and ext not in self.allowed_extensions:
                raise ValidationError(f"Unsupported file extension: {ext}")
                
        # ファイル存在チェック
        if mode == 'read':
            if not os.path.exists(normalized_path):
                raise ValidationError(f"File not found: {file_path}")
                
            if not os.path.isfile(normalized_path):
                raise ValidationError(f"Path is not a file: {file_path}")
                
            # ファイルサイズチェック
            try:
                file_size = os.path.getsize(normalized_path)
                if file_size > self.max_file_size:
                    raise ValidationError(f"File too large: {file_size} bytes")
                    
                if file_size == 0:
                    raise ValidationError("Empty file not allowed")
                    
            except OSError as e:
                raise ValidationError(f"Cannot access file: {e}")
                
        # 書き込みモードの場合、親ディレクトリの確認
        elif mode == 'write':
            parent_dir = os.path.dirname(normalized_path)
            if not os.path.exists(parent_dir):
                if self.validation_level == ValidationLevel.PARANOID:
                    raise ValidationError(f"Parent directory does not exist: {parent_dir}")
                else:
                    # ディレクトリ作成試行
                    try:
                        os.makedirs(parent_dir, exist_ok=True)
                    except OSError as e:
                        raise ValidationError(f"Cannot create directory: {e}")
                        
            if not os.access(parent_dir, os.W_OK):
                raise ValidationError(f"No write permission: {parent_dir}")
                
        return normalized_path
        
    def validate_audio_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """音声パラメータ検証"""
        validated_params = {}
        
        for key, value in params.items():
            if key in self.param_limits:
                validated_params[key] = self._validate_numeric_param(
                    key, value, self.param_limits[key]
                )
            else:
                # 未知のパラメータは制限的に処理
                if self.validation_level == ValidationLevel.PARANOID:
                    raise ValidationError(f"Unknown parameter: {key}")
                else:
                    validated_params[key] = self._sanitize_value(value)
                    
        return validated_params
        
    def _validate_numeric_param(self, name: str, value: Any, 
                               limits: Tuple[float, float]) -> float:
        """数値パラメータ検証"""
        if not isinstance(value, (int, float)):
            try:
                value = float(value)
            except (ValueError, TypeError):
                raise ValidationError(f"Invalid {name}: must be numeric")
                
        min_val, max_val = limits
        if not (min_val <= value <= max_val):
            # 範囲外の場合はクランプ
            value = max(min_val, min(max_val, value))
            
        return float(value)
        
    def validate_string_input(self, input_str: str, 
                             max_length: int = 1000,
                             allow_special_chars: bool = False) -> str:
        """文字列入力検証"""
        if not isinstance(input_str, str):
            raise ValidationError("Input must be string")
            
        if len(input_str) > max_length:
            if self.validation_level == ValidationLevel.PARANOID:
                raise ValidationError(f"String too long: {len(input_str)} > {max_length}")
            else:
                input_str = input_str[:max_length]
                
        # 危険な文字の除去
        if not allow_special_chars:
            # 基本的な英数字、ハイフン、アンダースコア、スペースのみ許可
            pattern = r'[^a-zA-Z0-9\-_\s\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]'
            sanitized = re.sub(pattern, '', input_str)
            
            if sanitized != input_str and self.validation_level == ValidationLevel.STRICT:
                raise ValidationError("Invalid characters detected")
                
            input_str = sanitized
            
        return input_str.strip()
        
    def validate_preset_name(self, preset_name: str) -> str:
        """プリセット名検証"""
        valid_presets = {
            'normal', 'male', 'female', 'child', 'robot', 'deep', 'cartoon',
            'echo', 'reverb', 'chipmunk', 'alien', 'phone', 'radio'
        }
        
        preset_name = preset_name.lower().strip()
        
        if preset_name not in valid_presets:
            raise ValidationError(f"Invalid preset: {preset_name}")
            
        return preset_name
        
    def validate_format(self, format_name: str) -> str:
        """フォーマット名検証"""
        valid_formats = {
            'wav', 'mp3', 'flac', 'ogg', 'm4a', 'aac'
        }
        
        format_name = format_name.lower().strip()
        
        if format_name not in valid_formats:
            raise ValidationError(f"Unsupported format: {format_name}")
            
        return format_name
        
    def validate_network_params(self, host: str, port: int) -> Tuple[str, int]:
        """ネットワークパラメータ検証"""
        # ホスト名検証
        if not isinstance(host, str) or not host:
            raise ValidationError("Invalid host")
            
        # IPアドレスまたはホスト名の簡易チェック
        host = host.strip()
        if not re.match(r'^[a-zA-Z0-9\.\-]+$', host):
            raise ValidationError("Invalid host format")
            
        # localhostと内部IPのみ許可（セキュリティ）
        if self.validation_level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
            allowed_hosts = {'localhost', '127.0.0.1', '::1'}
            if host not in allowed_hosts and not host.startswith('192.168.') and not host.startswith('10.'):
                raise ValidationError(f"Host not allowed: {host}")
                
        # ポート番号検証
        if not isinstance(port, int):
            try:
                port = int(port)
            except (ValueError, TypeError):
                raise ValidationError("Invalid port: must be integer")
                
        if not (1024 <= port <= 65535):
            raise ValidationError(f"Invalid port: {port} (must be 1024-65535)")
            
        return host, port
        
    def _sanitize_value(self, value: Any) -> Any:
        """値のサニタイゼーション"""
        if isinstance(value, str):
            return self.validate_string_input(value, allow_special_chars=True)
        elif isinstance(value, (int, float)):
            # 数値の範囲制限
            if abs(value) > 1e6:  # 過大な値の制限
                return 1e6 if value > 0 else -1e6
            return value
        elif isinstance(value, bool):
            return value
        elif isinstance(value, (list, tuple)):
            return [self._sanitize_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        else:
            # 不明な型は文字列化
            return str(value)
            
    def validate_command_args(self, args: List[str]) -> List[str]:
        """コマンドライン引数検証"""
        validated_args = []
        
        for arg in args:
            if not isinstance(arg, str):
                continue
                
            # 危険なコマンドインジェクションパターンをチェック
            dangerous_patterns = [
                r'[;&|`$()]', r'\.\./', r'~/', r'/etc', r'/proc'
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, arg):
                    if self.validation_level == ValidationLevel.PARANOID:
                        raise ValidationError(f"Dangerous pattern in argument: {pattern}")
                    else:
                        # パターンを除去
                        arg = re.sub(pattern, '', arg)
                        
            validated_args.append(arg)
            
        return validated_args

# グローバルバリデータインスタンス
_global_validator = None

def get_validator(level: ValidationLevel = ValidationLevel.STANDARD) -> InputValidator:
    """グローバルバリデータ取得"""
    global _global_validator
    if _global_validator is None or _global_validator.validation_level != level:
        _global_validator = InputValidator(level)
    return _global_validator

def validate_file_path(file_path: str, mode: str = 'read') -> str:
    """ファイルパス検証（便利関数）"""
    return get_validator().validate_file_path(file_path, mode)

def validate_audio_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """音声パラメータ検証（便利関数）"""
    return get_validator().validate_audio_params(params)

def validate_preset_name(preset_name: str) -> str:
    """プリセット名検証（便利関数）"""
    return get_validator().validate_preset_name(preset_name)

if __name__ == "__main__":
    # テスト用
    validator = InputValidator(ValidationLevel.STANDARD)
    
    try:
        # ファイルパステスト
        test_path = validate_file_path("test.wav", "write")
        print(f"Valid path: {test_path}")
        
        # パラメータテスト
        test_params = {"pitch": 1.5, "reverb": 0.7, "duration": 30.0}
        validated = validate_audio_params(test_params)
        print(f"Valid params: {validated}")
        
        # プリセットテスト
        preset = validate_preset_name("robot")
        print(f"Valid preset: {preset}")
        
    except ValidationError as e:
        print(f"Validation error: {e}")