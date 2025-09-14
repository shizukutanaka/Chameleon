#!/usr/bin/env python3
"""
Robust Error Handler - 包括的エラー処理システム
すべてのモジュールで使用する統一エラーハンドラー
"""

import logging
import traceback
import functools
import sys
import threading
from typing import Dict, Any, Optional, List, Callable, Union, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

class ErrorSeverity(Enum):
    """エラー重要度"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"

class ErrorCategory(Enum):
    """エラーカテゴリ"""
    SYSTEM = "system"
    NETWORK = "network"
    IO = "io"
    VALIDATION = "validation"
    PERMISSION = "permission"
    RESOURCE = "resource"
    LOGIC = "logic"
    DEPENDENCY = "dependency"
    USER_INPUT = "user_input"

@dataclass
class ErrorContext:
    """エラーコンテキスト情報"""
    component: str
    function: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ErrorRecord:
    """エラー記録"""
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    error_type: str
    message: str
    stack_trace: str
    context: ErrorContext
    handled: bool = False
    recovery_attempted: bool = False
    recovery_successful: bool = False

class RobustErrorHandler:
    """包括的エラーハンドラー"""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = self._setup_logger()
        self.error_history = []
        self.error_counts = {}
        self.lock = threading.RLock()
        
        # エラー処理設定
        self.config = {
            "log_to_file": True,
            "log_to_console": True,
            "include_stack_trace": True,
            "max_error_history": 10000,
            "auto_recovery": True,
            "notify_on_critical": True
        }
    
    def _setup_logger(self) -> logging.Logger:
        """ロガーのセットアップ"""
        logger = logging.getLogger(f"ErrorHandler.{self.component_name}")
        
        if not logger.handlers:
            # コンソールハンドラー
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # ファイルハンドラー（可能な場合）
            try:
                file_handler = logging.FileHandler(
                    f"chameleon_{self.component_name}_errors.log"
                )
                file_formatter = logging.Formatter(
                    '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except (OSError, PermissionError):
                # ファイルハンドラーが作成できない場合は無視
                pass
            
            logger.setLevel(logging.DEBUG)
        
        return logger
    
    def handle_error(self, 
                    error: Exception,
                    context: ErrorContext,
                    severity: ErrorSeverity = ErrorSeverity.ERROR,
                    category: ErrorCategory = ErrorCategory.LOGIC,
                    recovery_action: Optional[Callable] = None) -> ErrorRecord:
        """エラーを処理"""
        
        error_record = ErrorRecord(
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            error_type=type(error).__name__,
            message=str(error),
            stack_trace=traceback.format_exc(),
            context=context
        )
        
        # エラー履歴に追加
        with self.lock:
            self.error_history.append(error_record)
            if len(self.error_history) > self.config["max_error_history"]:
                self.error_history = self.error_history[-self.config["max_error_history"]//2:]
            
            # エラー統計更新
            error_key = f"{error_record.error_type}:{error_record.category.value}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # ログ出力
        self._log_error(error_record)
        
        # 自動復旧の試行
        if recovery_action and self.config["auto_recovery"]:
            try:
                recovery_action()
                error_record.recovery_attempted = True
                error_record.recovery_successful = True
                self.logger.info(f"Auto-recovery successful for {error_record.error_type}")
            except Exception as recovery_error:
                error_record.recovery_attempted = True
                error_record.recovery_successful = False
                self.logger.error(f"Auto-recovery failed: {recovery_error}")
        
        # クリティカルエラーの通知
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL] and self.config["notify_on_critical"]:
            self._notify_critical_error(error_record)
        
        error_record.handled = True
        return error_record
    
    def _log_error(self, record: ErrorRecord):
        """エラーログ出力"""
        log_message = self._format_error_message(record)
        
        if record.severity == ErrorSeverity.DEBUG:
            self.logger.debug(log_message)
        elif record.severity == ErrorSeverity.INFO:
            self.logger.info(log_message)
        elif record.severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        elif record.severity == ErrorSeverity.ERROR:
            self.logger.error(log_message)
        elif record.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            self.logger.critical(log_message)
    
    def _format_error_message(self, record: ErrorRecord) -> str:
        """エラーメッセージフォーマット"""
        context = record.context
        message_parts = [
            f"[{record.severity.value.upper()}] {record.error_type}: {record.message}",
            f"Component: {context.component}",
            f"Function: {context.function}",
            f"Category: {record.category.value}"
        ]
        
        if context.user_id:
            message_parts.append(f"User: {context.user_id}")
        
        if context.request_id:
            message_parts.append(f"Request: {context.request_id}")
        
        if context.additional_info:
            message_parts.append(f"Info: {json.dumps(context.additional_info)}")
        
        if self.config["include_stack_trace"] and record.stack_trace:
            message_parts.append(f"Stack trace:\n{record.stack_trace}")
        
        return " | ".join(message_parts)
    
    def _notify_critical_error(self, record: ErrorRecord):
        """クリティカルエラー通知"""
        # 実際の本番環境では、Slack、メール、PagerDutyなどに通知
        self.logger.critical("🚨 CRITICAL ERROR NOTIFICATION 🚨")
        self.logger.critical(f"Component: {self.component_name}")
        self.logger.critical(f"Error: {record.error_type} - {record.message}")
        self.logger.critical(f"Time: {record.timestamp.isoformat()}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """エラー統計取得"""
        with self.lock:
            recent_errors = [e for e in self.error_history 
                           if (datetime.now() - e.timestamp).total_seconds() < 3600]  # 1時間以内
            
            return {
                "total_errors": len(self.error_history),
                "recent_errors_1h": len(recent_errors),
                "error_counts_by_type": dict(self.error_counts),
                "severity_distribution": {
                    severity.value: len([e for e in recent_errors if e.severity == severity])
                    for severity in ErrorSeverity
                },
                "category_distribution": {
                    category.value: len([e for e in recent_errors if e.category == category])
                    for category in ErrorCategory
                },
                "recovery_success_rate": self._calculate_recovery_success_rate()
            }
    
    def _calculate_recovery_success_rate(self) -> float:
        """復旧成功率計算"""
        with self.lock:
            attempted_recoveries = [e for e in self.error_history if e.recovery_attempted]
            if not attempted_recoveries:
                return 0.0
            
            successful = len([e for e in attempted_recoveries if e.recovery_successful])
            return (successful / len(attempted_recoveries)) * 100
    
    def clear_error_history(self):
        """エラー履歴クリア"""
        with self.lock:
            self.error_history.clear()
            self.error_counts.clear()
        self.logger.info("Error history cleared")

def with_error_handling(
    component: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    category: ErrorCategory = ErrorCategory.LOGIC,
    recovery_action: Optional[Callable] = None,
    reraise: bool = True,
    default_return=None
):
    """エラーハンドリングデコレーター"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            handler = get_error_handler(component)
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(
                    component=component,
                    function=func.__name__,
                    args=args,
                    kwargs=kwargs,
                    additional_info={
                        "module": func.__module__,
                        "qualname": func.__qualname__
                    }
                )
                
                handler.handle_error(e, context, severity, category, recovery_action)
                
                if reraise:
                    raise
                else:
                    return default_return
        
        return wrapper
    return decorator

def safe_execute(
    func: Callable,
    component: str,
    *args,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    category: ErrorCategory = ErrorCategory.LOGIC,
    recovery_action: Optional[Callable] = None,
    default_return=None,
    **kwargs
):
    """安全な関数実行"""
    handler = get_error_handler(component)
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        context = ErrorContext(
            component=component,
            function=func.__name__ if hasattr(func, '__name__') else 'anonymous',
            args=args,
            kwargs=kwargs
        )
        
        handler.handle_error(e, context, severity, category, recovery_action)
        return default_return

# グローバルエラーハンドラー管理
_error_handlers = {}
_error_handlers_lock = threading.RLock()

def get_error_handler(component: str) -> RobustErrorHandler:
    """コンポーネント用エラーハンドラー取得"""
    with _error_handlers_lock:
        if component not in _error_handlers:
            _error_handlers[component] = RobustErrorHandler(component)
        return _error_handlers[component]

def configure_error_handling(component: str, **config):
    """エラーハンドリング設定"""
    handler = get_error_handler(component)
    handler.config.update(config)

# 高レベルエラータイプのマッピング
ERROR_TYPE_MAPPING = {
    # ネットワーク関連
    ConnectionError: ErrorCategory.NETWORK,
    TimeoutError: ErrorCategory.NETWORK,
    OSError: ErrorCategory.SYSTEM,
    
    # IO関連
    FileNotFoundError: ErrorCategory.IO,
    PermissionError: ErrorCategory.PERMISSION,
    IOError: ErrorCategory.IO,
    
    # リソース関連
    MemoryError: ErrorCategory.RESOURCE,
    RecursionError: ErrorCategory.RESOURCE,
    
    # バリデーション関連
    ValueError: ErrorCategory.VALIDATION,
    TypeError: ErrorCategory.VALIDATION,
    KeyError: ErrorCategory.VALIDATION,
    IndexError: ErrorCategory.VALIDATION,
    
    # 依存関係
    ImportError: ErrorCategory.DEPENDENCY,
    ModuleNotFoundError: ErrorCategory.DEPENDENCY,
}

def get_error_category(error: Exception) -> ErrorCategory:
    """エラーからカテゴリを推定"""
    error_type = type(error)
    return ERROR_TYPE_MAPPING.get(error_type, ErrorCategory.LOGIC)

def get_error_severity(error: Exception) -> ErrorSeverity:
    """エラーから重要度を推定"""
    error_type = type(error)
    
    if error_type in [SystemExit, KeyboardInterrupt]:
        return ErrorSeverity.FATAL
    elif error_type in [MemoryError, OSError]:
        return ErrorSeverity.CRITICAL
    elif error_type in [ConnectionError, TimeoutError, ImportError]:
        return ErrorSeverity.ERROR
    elif error_type in [ValueError, TypeError]:
        return ErrorSeverity.WARNING
    else:
        return ErrorSeverity.ERROR

if __name__ == "__main__":
    # エラーハンドラーのテスト
    print("🛡️ Robust Error Handler Test")
    print("=" * 40)
    
    # テスト用コンポーネント
    handler = get_error_handler("test_component")
    
    # テスト1: 基本エラー処理
    @with_error_handling("test_component", reraise=False, default_return="fallback")
    def test_function_1():
        raise ValueError("Test error")
    
    result = test_function_1()
    print(f"Test 1 result: {result}")
    
    # テスト2: 復旧アクション付きエラー処理
    recovery_called = False
    
    def recovery_action():
        global recovery_called
        recovery_called = True
        print("Recovery action executed")
    
    @with_error_handling("test_component", recovery_action=recovery_action, reraise=False)
    def test_function_2():
        raise ConnectionError("Network error")
    
    test_function_2()
    print(f"Recovery called: {recovery_called}")
    
    # テスト3: 統計情報
    stats = handler.get_error_statistics()
    print(f"\nError Statistics:")
    print(f"  Total errors: {stats['total_errors']}")
    print(f"  Recent errors (1h): {stats['recent_errors_1h']}")
    print(f"  Recovery success rate: {stats['recovery_success_rate']:.1f}%")