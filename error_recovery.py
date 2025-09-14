#!/usr/bin/env python3
"""
Advanced Error Recovery System
Provides intelligent error handling, recovery mechanisms, and fault tolerance
"""

import logging
import traceback
import time
import threading
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict, deque

class ErrorSeverity(Enum):
    """Error severity levels"""
    TRACE = "trace"
    DEBUG = "debug" 
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"

class RecoveryStrategy(Enum):
    """Recovery strategy types"""
    RETRY = "retry"
    FALLBACK = "fallback"
    RESTART = "restart"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    CIRCUIT_BREAKER = "circuit_breaker"
    IGNORE = "ignore"
    ESCALATE = "escalate"

@dataclass
class ErrorRecord:
    """Record of an error occurrence"""
    timestamp: datetime
    error_type: str
    error_message: str
    severity: ErrorSeverity
    component: str
    stack_trace: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_strategy: Optional[RecoveryStrategy] = None

@dataclass
class RecoveryAction:
    """Definition of a recovery action"""
    strategy: RecoveryStrategy
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    fallback_action: Optional[Callable] = None
    escalation_action: Optional[Callable] = None
    conditions: Dict[str, Any] = field(default_factory=dict)

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, blocking requests
    HALF_OPEN = "half_open" # Testing if service recovered

@dataclass
class CircuitBreaker:
    """Circuit breaker for service protection"""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    success_threshold: int = 3  # Consecutive successes needed to close

class ErrorRecoveryManager:
    """Comprehensive error recovery and fault tolerance system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.error_history = deque(maxlen=10000)
        self.recovery_rules = {}
        self.circuit_breakers = {}
        self.component_health = defaultdict(lambda: {"status": "healthy", "last_check": datetime.now()})
        self.recovery_stats = defaultdict(int)
        self.lock = threading.RLock()
        
        # Initialize logging
        self.logger = logging.getLogger("ErrorRecovery")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize default recovery rules
        self._setup_default_rules()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load error recovery configuration"""
        default_config = {
            "retry_delays": [1, 2, 4, 8, 16],
            "max_error_history": 10000,
            "health_check_interval": 30,
            "circuit_breaker_defaults": {
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "success_threshold": 3
            },
            "escalation_thresholds": {
                "error_rate_per_minute": 10,
                "critical_errors_per_hour": 5
            }
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                self.logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return default_config
    
    def _setup_default_rules(self):
        """Setup default recovery rules for common scenarios"""
        
        # Network/IO errors - retry with exponential backoff
        self.add_recovery_rule(
            "network_error",
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                max_retries=5,
                retry_delay=2.0,
                conditions={"error_types": ["ConnectionError", "TimeoutError", "RequestException"]}
            )
        )
        
        # Audio processing errors - graceful degradation
        self.add_recovery_rule(
            "audio_processing_error", 
            RecoveryAction(
                strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
                max_retries=2,
                conditions={"components": ["audio_processor", "effects_chain"]}
            )
        )
        
        # Plugin errors - fallback to default
        self.add_recovery_rule(
            "plugin_error",
            RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                max_retries=1,
                conditions={"components": ["plugin_manager", "plugin"]}
            )
        )
        
        # Memory errors - restart component
        self.add_recovery_rule(
            "memory_error",
            RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                conditions={"error_types": ["MemoryError", "OutOfMemoryError"]}
            )
        )
        
        # Critical system errors - escalate
        self.add_recovery_rule(
            "critical_error",
            RecoveryAction(
                strategy=RecoveryStrategy.ESCALATE,
                conditions={"severity": [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]}
            )
        )
    
    def add_recovery_rule(self, rule_name: str, action: RecoveryAction):
        """Add a recovery rule"""
        with self.lock:
            self.recovery_rules[rule_name] = action
            self.logger.info(f"Added recovery rule: {rule_name}")
    
    def remove_recovery_rule(self, rule_name: str):
        """Remove a recovery rule"""
        with self.lock:
            if rule_name in self.recovery_rules:
                del self.recovery_rules[rule_name]
                self.logger.info(f"Removed recovery rule: {rule_name}")
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            cb_config = self.config["circuit_breaker_defaults"]
            self.circuit_breakers[service_name] = CircuitBreaker(
                failure_threshold=cb_config["failure_threshold"],
                recovery_timeout=cb_config["recovery_timeout"],
                success_threshold=cb_config["success_threshold"]
            )
        return self.circuit_breakers[service_name]
    
    def record_error(self, error: Exception, component: str, context: Dict[str, Any] = None) -> ErrorRecord:
        """Record an error occurrence"""
        error_record = ErrorRecord(
            timestamp=datetime.now(),
            error_type=type(error).__name__,
            error_message=str(error),
            severity=self._classify_error_severity(error),
            component=component,
            stack_trace=traceback.format_exc(),
            context=context or {}
        )
        
        with self.lock:
            self.error_history.append(error_record)
        
        self.logger.error(f"Error recorded: {error_record.error_type} in {component}: {error_record.error_message}")
        
        # Update circuit breaker
        self._update_circuit_breaker(component, success=False)
        
        # Trigger recovery if applicable
        self._attempt_recovery(error_record)
        
        return error_record
    
    def record_success(self, component: str):
        """Record successful operation for circuit breaker"""
        self._update_circuit_breaker(component, success=True)
    
    def _classify_error_severity(self, error: Exception) -> ErrorSeverity:
        """Classify error severity based on type and context"""
        error_type = type(error).__name__
        
        # Critical system errors
        if error_type in ["SystemExit", "KeyboardInterrupt", "SystemError"]:
            return ErrorSeverity.FATAL
        
        # Memory and resource errors
        if error_type in ["MemoryError", "OSError", "IOError"]:
            return ErrorSeverity.CRITICAL
        
        # Runtime errors
        if error_type in ["RuntimeError", "ValueError", "TypeError"]:
            return ErrorSeverity.ERROR
        
        # Network and connection errors
        if "Connection" in error_type or "Timeout" in error_type:
            return ErrorSeverity.WARNING
        
        return ErrorSeverity.ERROR
    
    def _update_circuit_breaker(self, service_name: str, success: bool):
        """Update circuit breaker state"""
        cb = self.get_circuit_breaker(service_name)
        
        if success:
            if cb.state == CircuitBreakerState.HALF_OPEN:
                cb.failure_count = 0
                if cb.failure_count <= -cb.success_threshold:  # Track consecutive successes
                    cb.state = CircuitBreakerState.CLOSED
                    self.logger.info(f"Circuit breaker CLOSED for {service_name}")
            elif cb.state == CircuitBreakerState.CLOSED:
                cb.failure_count = max(0, cb.failure_count - 1)
        else:
            cb.failure_count += 1
            cb.last_failure_time = datetime.now()
            
            if cb.state == CircuitBreakerState.CLOSED and cb.failure_count >= cb.failure_threshold:
                cb.state = CircuitBreakerState.OPEN
                self.logger.warning(f"Circuit breaker OPENED for {service_name}")
            elif cb.state == CircuitBreakerState.HALF_OPEN:
                cb.state = CircuitBreakerState.OPEN
                self.logger.warning(f"Circuit breaker OPENED again for {service_name}")
    
    def _attempt_recovery(self, error_record: ErrorRecord):
        """Attempt to recover from error using defined rules"""
        matching_rules = self._find_matching_rules(error_record)
        
        for rule_name, action in matching_rules:
            self.logger.info(f"Attempting recovery using rule: {rule_name}")
            
            success = self._execute_recovery_action(action, error_record)
            
            error_record.recovery_attempted = True
            error_record.recovery_successful = success
            error_record.recovery_strategy = action.strategy
            
            self.recovery_stats[f"{rule_name}_{action.strategy.value}"] += 1
            
            if success:
                self.recovery_stats["successful_recoveries"] += 1
                self.logger.info(f"Recovery successful using {rule_name}")
                break
            else:
                self.recovery_stats["failed_recoveries"] += 1
                self.logger.warning(f"Recovery failed using {rule_name}")
    
    def _find_matching_rules(self, error_record: ErrorRecord) -> List[Tuple[str, RecoveryAction]]:
        """Find recovery rules that match the error"""
        matching_rules = []
        
        for rule_name, action in self.recovery_rules.items():
            if self._rule_matches_error(action, error_record):
                matching_rules.append((rule_name, action))
        
        # Sort by strategy priority (retry first, escalate last)
        strategy_priority = {
            RecoveryStrategy.RETRY: 1,
            RecoveryStrategy.FALLBACK: 2,
            RecoveryStrategy.GRACEFUL_DEGRADATION: 3,
            RecoveryStrategy.CIRCUIT_BREAKER: 4,
            RecoveryStrategy.RESTART: 5,
            RecoveryStrategy.IGNORE: 6,
            RecoveryStrategy.ESCALATE: 7
        }
        
        matching_rules.sort(key=lambda x: strategy_priority.get(x[1].strategy, 99))
        return matching_rules
    
    def _rule_matches_error(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Check if recovery rule matches the error"""
        conditions = action.conditions
        
        # Check error types
        if "error_types" in conditions:
            if error_record.error_type not in conditions["error_types"]:
                return False
        
        # Check components
        if "components" in conditions:
            if error_record.component not in conditions["components"]:
                return False
        
        # Check severity
        if "severity" in conditions:
            if error_record.severity not in conditions["severity"]:
                return False
        
        return True
    
    def _execute_recovery_action(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Execute a recovery action"""
        try:
            if action.strategy == RecoveryStrategy.RETRY:
                return self._retry_operation(action, error_record)
            elif action.strategy == RecoveryStrategy.FALLBACK:
                return self._execute_fallback(action, error_record)
            elif action.strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
                return self._graceful_degradation(action, error_record)
            elif action.strategy == RecoveryStrategy.RESTART:
                return self._restart_component(action, error_record)
            elif action.strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                return self._handle_circuit_breaker(action, error_record)
            elif action.strategy == RecoveryStrategy.ESCALATE:
                return self._escalate_error(action, error_record)
            elif action.strategy == RecoveryStrategy.IGNORE:
                return True
            
        except Exception as recovery_error:
            self.logger.error(f"Recovery action failed: {recovery_error}")
            return False
        
        return False
    
    def _retry_operation(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Implement retry recovery strategy"""
        delays = self.config["retry_delays"][:action.max_retries]
        
        for attempt in range(action.max_retries):
            if attempt > 0:
                delay = delays[min(attempt - 1, len(delays) - 1)]
                self.logger.info(f"Retry attempt {attempt + 1} after {delay}s delay")
                time.sleep(delay)
            
            # Here we would re-execute the failed operation
            # For now, simulate success based on error type
            if self._simulate_retry_success(error_record):
                return True
        
        return False
    
    def _execute_fallback(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Execute fallback action"""
        if action.fallback_action:
            try:
                result = action.fallback_action(error_record)
                return bool(result)
            except Exception as e:
                self.logger.error(f"Fallback action failed: {e}")
        
        # Default fallback behavior
        self.logger.info(f"Using default fallback for {error_record.component}")
        return True
    
    def _graceful_degradation(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Implement graceful degradation"""
        self.logger.info(f"Graceful degradation for {error_record.component}")
        
        # Update component health status
        with self.lock:
            self.component_health[error_record.component]["status"] = "degraded"
            self.component_health[error_record.component]["last_check"] = datetime.now()
        
        return True
    
    def _restart_component(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Restart component"""
        self.logger.info(f"Restarting component: {error_record.component}")
        
        # Simulate component restart
        with self.lock:
            self.component_health[error_record.component]["status"] = "restarting"
            self.component_health[error_record.component]["last_check"] = datetime.now()
        
        # In real implementation, this would restart the actual component
        time.sleep(2)  # Simulate restart time
        
        with self.lock:
            self.component_health[error_record.component]["status"] = "healthy"
            self.component_health[error_record.component]["last_check"] = datetime.now()
        
        return True
    
    def _handle_circuit_breaker(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Handle circuit breaker logic"""
        cb = self.get_circuit_breaker(error_record.component)
        
        if cb.state == CircuitBreakerState.OPEN:
            # Check if we should transition to half-open
            if (cb.last_failure_time and 
                datetime.now() - cb.last_failure_time > timedelta(seconds=cb.recovery_timeout)):
                cb.state = CircuitBreakerState.HALF_OPEN
                self.logger.info(f"Circuit breaker HALF-OPEN for {error_record.component}")
                return True
            else:
                self.logger.warning(f"Circuit breaker OPEN - blocking request for {error_record.component}")
                return False
        
        return True
    
    def _escalate_error(self, action: RecoveryAction, error_record: ErrorRecord) -> bool:
        """Escalate error to higher-level handler"""
        self.logger.critical(f"Escalating error: {error_record.error_type} in {error_record.component}")
        
        if action.escalation_action:
            try:
                action.escalation_action(error_record)
                return True
            except Exception as e:
                self.logger.error(f"Escalation action failed: {e}")
        
        # Default escalation - just log and continue
        return True
    
    def _simulate_retry_success(self, error_record: ErrorRecord) -> bool:
        """Simulate retry success based on error type"""
        # Network errors have 70% success rate on retry
        if "Connection" in error_record.error_type or "Timeout" in error_record.error_type:
            return hash(error_record.timestamp) % 10 < 7
        
        # Other errors have 50% success rate
        return hash(error_record.timestamp) % 10 < 5
    
    def _start_background_tasks(self):
        """Start background monitoring tasks"""
        def health_monitor():
            while True:
                try:
                    self._perform_health_checks()
                    time.sleep(self.config["health_check_interval"])
                except Exception as e:
                    self.logger.error(f"Health monitor error: {e}")
                    time.sleep(10)
        
        monitor_thread = threading.Thread(target=health_monitor, daemon=True)
        monitor_thread.start()
    
    def _perform_health_checks(self):
        """Perform periodic health checks"""
        current_time = datetime.now()
        
        with self.lock:
            for component, health_info in self.component_health.items():
                # Check if component needs health update
                time_since_check = current_time - health_info["last_check"]
                if time_since_check > timedelta(minutes=5):
                    # Component hasn't been checked recently
                    if health_info["status"] == "degraded":
                        # Try to restore degraded components
                        health_info["status"] = "healthy"
                        health_info["last_check"] = current_time
                        self.logger.info(f"Component {component} restored to healthy")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics"""
        with self.lock:
            recent_errors = [e for e in self.error_history 
                           if datetime.now() - e.timestamp < timedelta(hours=1)]
            
            error_by_type = defaultdict(int)
            error_by_component = defaultdict(int)
            error_by_severity = defaultdict(int)
            
            for error in recent_errors:
                error_by_type[error.error_type] += 1
                error_by_component[error.component] += 1
                error_by_severity[error.severity.value] += 1
            
            return {
                "total_errors": len(self.error_history),
                "recent_errors_1h": len(recent_errors),
                "error_by_type": dict(error_by_type),
                "error_by_component": dict(error_by_component),
                "error_by_severity": dict(error_by_severity),
                "recovery_stats": dict(self.recovery_stats),
                "circuit_breaker_states": {
                    name: cb.state.value for name, cb in self.circuit_breakers.items()
                },
                "component_health": dict(self.component_health)
            }
    
    def get_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        stats = self.get_error_statistics()
        current_time = datetime.now()
        
        # Calculate error rates
        recent_errors = stats["recent_errors_1h"]
        error_rate = recent_errors / 60  # per minute
        
        # Determine overall health status
        health_status = "healthy"
        if error_rate > self.config["escalation_thresholds"]["error_rate_per_minute"]:
            health_status = "degraded"
        
        critical_errors = stats["error_by_severity"].get("critical", 0) + stats["error_by_severity"].get("fatal", 0)
        if critical_errors > self.config["escalation_thresholds"]["critical_errors_per_hour"]:
            health_status = "critical"
        
        return {
            "timestamp": current_time.isoformat(),
            "overall_health": health_status,
            "error_rate_per_minute": error_rate,
            "critical_errors_1h": critical_errors,
            "statistics": stats,
            "recommendations": self._generate_recommendations(stats)
        }
    
    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on error patterns"""
        recommendations = []
        
        # High error rate recommendations
        if stats["recent_errors_1h"] > 10:
            recommendations.append("High error rate detected. Consider reviewing recent changes.")
        
        # Component-specific recommendations
        for component, count in stats["error_by_component"].items():
            if count > 5:
                recommendations.append(f"Component '{component}' has high error rate. Consider investigation.")
        
        # Circuit breaker recommendations
        open_breakers = [name for name, state in stats["circuit_breaker_states"].items() if state == "open"]
        if open_breakers:
            recommendations.append(f"Circuit breakers open for: {', '.join(open_breakers)}")
        
        return recommendations

# Decorator for automatic error handling
def with_error_recovery(component: str, recovery_manager: Optional[ErrorRecoveryManager] = None):
    """Decorator to add automatic error recovery to functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = recovery_manager or _get_global_recovery_manager()
            try:
                result = func(*args, **kwargs)
                manager.record_success(component)
                return result
            except Exception as e:
                manager.record_error(e, component, {"function": func.__name__, "args": args, "kwargs": kwargs})
                raise
        return wrapper
    return decorator

# Global recovery manager instance
_global_recovery_manager = None

def get_global_recovery_manager() -> ErrorRecoveryManager:
    """Get or create global recovery manager"""
    global _global_recovery_manager
    if _global_recovery_manager is None:
        _global_recovery_manager = ErrorRecoveryManager()
    return _global_recovery_manager

def _get_global_recovery_manager() -> ErrorRecoveryManager:
    """Internal function to get global recovery manager"""
    return get_global_recovery_manager()

if __name__ == "__main__":
    # Example usage
    recovery_manager = ErrorRecoveryManager()
    
    # Simulate some errors
    try:
        raise ConnectionError("Network connection failed")
    except Exception as e:
        recovery_manager.record_error(e, "network_client")
    
    try:
        raise MemoryError("Out of memory")
    except Exception as e:
        recovery_manager.record_error(e, "audio_processor")
    
    # Get health report
    report = recovery_manager.get_health_report()
    print("Health Report:")
    print(json.dumps(report, indent=2, default=str))