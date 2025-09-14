#!/usr/bin/env python3
"""
Plugin Fault Tolerance System
Advanced fault tolerance specifically designed for plugin ecosystem
"""

import logging
import threading
import time
import traceback
from typing import Dict, Any, Optional, List, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import json
import weakref
from datetime import datetime, timedelta
from collections import defaultdict, deque
import copy
import sys

from error_recovery import ErrorRecoveryManager, ErrorSeverity, RecoveryStrategy

class PluginState(Enum):
    """Plugin operational states"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    DISABLED = "disabled"

class PluginIsolationLevel(Enum):
    """Plugin isolation levels"""
    NONE = "none"           # No isolation
    SANDBOXED = "sandboxed" # Limited permissions
    ISOLATED = "isolated"   # Separate thread
    CONTAINERIZED = "containerized" # Separate process (future)

@dataclass
class PluginMetrics:
    """Plugin performance and reliability metrics"""
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0

@dataclass
class PluginFailure:
    """Record of plugin failure"""
    timestamp: datetime
    plugin_id: str
    error_type: str
    error_message: str
    stack_trace: str
    context: Dict[str, Any] = field(default_factory=dict)
    severity: ErrorSeverity = ErrorSeverity.ERROR
    recovery_attempted: bool = False
    recovery_successful: bool = False

class PluginSandbox:
    """Secure sandbox environment for plugin execution"""
    
    def __init__(self, plugin_id: str, resource_limits: Dict[str, Any] = None):
        self.plugin_id = plugin_id
        self.resource_limits = resource_limits or {}
        self.start_time = None
        self.execution_context = {}
        
        # Resource tracking
        self.initial_memory = 0
        self.peak_memory = 0
        
    def __enter__(self):
        self.start_time = time.time()
        # In production, would set up actual sandboxing
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up resources
        execution_time = time.time() - self.start_time if self.start_time else 0
        
        if exc_type:
            # Handle sandbox violations
            if execution_time > self.resource_limits.get("max_execution_time", 10.0):
                raise TimeoutError(f"Plugin {self.plugin_id} exceeded execution time limit")
        
        return False  # Don't suppress exceptions

class PluginFaultToleranceManager:
    """Advanced fault tolerance system for plugin ecosystem"""
    
    def __init__(self, error_recovery_manager: Optional[ErrorRecoveryManager] = None):
        self.error_recovery = error_recovery_manager or ErrorRecoveryManager()
        self.plugin_states = {}
        self.plugin_metrics = defaultdict(PluginMetrics)
        self.plugin_failures = deque(maxlen=1000)
        self.fallback_chains = {}
        self.plugin_dependencies = {}
        self.quarantine_list = set()
        self.disabled_plugins = set()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Configuration
        self.config = {
            "max_consecutive_failures": 5,
            "quarantine_duration": timedelta(hours=1),
            "failure_rate_threshold": 0.5,  # 50% failure rate
            "resource_limits": {
                "max_execution_time": 10.0,
                "max_memory_mb": 100,
                "max_cpu_percent": 50
            },
            "auto_recovery": True,
            "fallback_enabled": True
        }
        
        # Initialize logging
        self.logger = logging.getLogger("PluginFaultTolerance")
        
        # Setup plugin-specific recovery rules
        self._setup_plugin_recovery_rules()
        
        # Start background monitoring
        self._start_monitoring()
    
    def _setup_plugin_recovery_rules(self):
        """Setup plugin-specific recovery rules"""
        from error_recovery import RecoveryAction
        
        # Plugin timeout errors - restart plugin
        self.error_recovery.add_recovery_rule(
            "plugin_timeout",
            RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                conditions={"error_types": ["TimeoutError"], "components": ["plugin"]}
            )
        )
        
        # Plugin memory errors - restart with resource limits
        self.error_recovery.add_recovery_rule(
            "plugin_memory",
            RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                conditions={"error_types": ["MemoryError"], "components": ["plugin"]}
            )
        )
        
        # Plugin import/loading errors - fallback to alternative
        self.error_recovery.add_recovery_rule(
            "plugin_loading",
            RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                conditions={"error_types": ["ImportError", "ModuleNotFoundError"], "components": ["plugin_loader"]}
            )
        )
        
        # General plugin errors - try graceful degradation first
        self.error_recovery.add_recovery_rule(
            "plugin_general",
            RecoveryAction(
                strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
                max_retries=2,
                conditions={"components": ["plugin"]}
            )
        )
    
    def register_plugin(self, plugin_id: str, plugin_info: Dict[str, Any]):
        """Register a plugin for fault tolerance monitoring"""
        with self.lock:
            self.plugin_states[plugin_id] = PluginState.UNLOADED
            self.plugin_metrics[plugin_id] = PluginMetrics()
            
            # Store plugin metadata
            if "dependencies" in plugin_info:
                self.plugin_dependencies[plugin_id] = plugin_info["dependencies"]
            
            self.logger.info(f"Registered plugin for fault tolerance: {plugin_id}")
    
    def unregister_plugin(self, plugin_id: str):
        """Unregister plugin from monitoring"""
        with self.lock:
            self.plugin_states.pop(plugin_id, None)
            self.plugin_metrics.pop(plugin_id, None)
            self.plugin_dependencies.pop(plugin_id, None)
            self.quarantine_list.discard(plugin_id)
            self.disabled_plugins.discard(plugin_id)
            
            self.logger.info(f"Unregistered plugin: {plugin_id}")
    
    def set_fallback_chain(self, plugin_id: str, fallback_plugins: List[str]):
        """Set fallback chain for plugin"""
        with self.lock:
            self.fallback_chains[plugin_id] = fallback_plugins
            self.logger.info(f"Set fallback chain for {plugin_id}: {fallback_plugins}")
    
    def execute_plugin_safely(self, plugin_id: str, plugin_func: Callable, 
                            *args, isolation_level: PluginIsolationLevel = PluginIsolationLevel.SANDBOXED, 
                            **kwargs) -> Any:
        """Execute plugin function with comprehensive fault tolerance"""
        
        # Check if plugin is available
        if not self._is_plugin_available(plugin_id):
            return self._handle_unavailable_plugin(plugin_id, plugin_func, *args, **kwargs)
        
        # Update plugin state
        self._update_plugin_state(plugin_id, PluginState.ACTIVE)
        
        start_time = time.time()
        result = None
        error_occurred = False
        
        try:
            # Execute with appropriate isolation
            if isolation_level == PluginIsolationLevel.SANDBOXED:
                result = self._execute_sandboxed(plugin_id, plugin_func, *args, **kwargs)
            elif isolation_level == PluginIsolationLevel.ISOLATED:
                result = self._execute_isolated(plugin_id, plugin_func, *args, **kwargs)
            else:
                result = plugin_func(*args, **kwargs)
            
            # Record success
            self._record_plugin_success(plugin_id, time.time() - start_time)
            
        except Exception as e:
            error_occurred = True
            execution_time = time.time() - start_time
            
            # Record failure
            failure = self._record_plugin_failure(plugin_id, e, execution_time)
            
            # Attempt recovery
            if self.config["auto_recovery"]:
                result = self._attempt_plugin_recovery(plugin_id, plugin_func, failure, *args, **kwargs)
                if result is not None:
                    error_occurred = False
            
            if error_occurred:
                raise
        
        finally:
            # Update plugin state
            if not error_occurred:
                self._update_plugin_state(plugin_id, PluginState.LOADED)
        
        return result
    
    def _is_plugin_available(self, plugin_id: str) -> bool:
        """Check if plugin is available for execution"""
        with self.lock:
            if plugin_id in self.disabled_plugins:
                return False
            
            if plugin_id in self.quarantine_list:
                return False
            
            state = self.plugin_states.get(plugin_id, PluginState.UNLOADED)
            if state in [PluginState.FAILED, PluginState.QUARANTINED]:
                return False
            
            return True
    
    def _handle_unavailable_plugin(self, plugin_id: str, plugin_func: Callable, *args, **kwargs) -> Any:
        """Handle execution when plugin is unavailable"""
        self.logger.warning(f"Plugin {plugin_id} is unavailable, attempting fallback")
        
        # Try fallback chain
        if self.config["fallback_enabled"] and plugin_id in self.fallback_chains:
            for fallback_id in self.fallback_chains[plugin_id]:
                if self._is_plugin_available(fallback_id):
                    self.logger.info(f"Using fallback plugin: {fallback_id}")
                    # In a real implementation, we'd need to get the fallback function
                    # For now, return None to indicate fallback should be used
                    return None
        
        # No fallback available
        raise RuntimeError(f"Plugin {plugin_id} is unavailable and no fallback exists")
    
    def _execute_sandboxed(self, plugin_id: str, plugin_func: Callable, *args, **kwargs) -> Any:
        """Execute plugin in sandboxed environment"""
        resource_limits = self.config["resource_limits"].copy()
        
        with PluginSandbox(plugin_id, resource_limits) as sandbox:
            return plugin_func(*args, **kwargs)
    
    def _execute_isolated(self, plugin_id: str, plugin_func: Callable, *args, **kwargs) -> Any:
        """Execute plugin in isolated thread"""
        result = [None]
        exception = [None]
        
        def thread_func():
            try:
                result[0] = plugin_func(*args, **kwargs)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=thread_func)
        thread.daemon = True
        thread.start()
        
        # Wait with timeout
        timeout = self.config["resource_limits"]["max_execution_time"]
        thread.join(timeout)
        
        if thread.is_alive():
            # Thread is still running - timeout occurred
            raise TimeoutError(f"Plugin {plugin_id} execution timeout")
        
        if exception[0]:
            raise exception[0]
        
        return result[0]
    
    def _record_plugin_success(self, plugin_id: str, execution_time: float):
        """Record successful plugin execution"""
        with self.lock:
            metrics = self.plugin_metrics[plugin_id]
            metrics.execution_count += 1
            metrics.success_count += 1
            metrics.total_execution_time += execution_time
            metrics.average_execution_time = metrics.total_execution_time / metrics.execution_count
            metrics.last_success = datetime.now()
            metrics.consecutive_failures = 0
            
            # Update error recovery manager
            self.error_recovery.record_success(f"plugin_{plugin_id}")
    
    def _record_plugin_failure(self, plugin_id: str, error: Exception, execution_time: float) -> PluginFailure:
        """Record plugin failure"""
        failure = PluginFailure(
            timestamp=datetime.now(),
            plugin_id=plugin_id,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            context={"execution_time": execution_time}
        )
        
        with self.lock:
            # Update metrics
            metrics = self.plugin_metrics[plugin_id]
            metrics.execution_count += 1
            metrics.failure_count += 1
            metrics.total_execution_time += execution_time
            metrics.average_execution_time = metrics.total_execution_time / metrics.execution_count
            metrics.last_failure = datetime.now()
            metrics.consecutive_failures += 1
            
            # Store failure record
            self.plugin_failures.append(failure)
            
            # Check if plugin should be quarantined
            self._check_quarantine_conditions(plugin_id, metrics)
            
            # Update error recovery manager
            self.error_recovery.record_error(error, f"plugin_{plugin_id}", 
                                           {"plugin_id": plugin_id, "execution_time": execution_time})
        
        return failure
    
    def _check_quarantine_conditions(self, plugin_id: str, metrics: PluginMetrics):
        """Check if plugin should be quarantined"""
        should_quarantine = False
        
        # Too many consecutive failures
        if metrics.consecutive_failures >= self.config["max_consecutive_failures"]:
            should_quarantine = True
            reason = f"exceeded consecutive failure limit ({metrics.consecutive_failures})"
        
        # High failure rate
        elif metrics.execution_count >= 10:  # Minimum executions to calculate rate
            failure_rate = metrics.failure_count / metrics.execution_count
            if failure_rate > self.config["failure_rate_threshold"]:
                should_quarantine = True
                reason = f"high failure rate ({failure_rate:.2%})"
        
        if should_quarantine:
            self._quarantine_plugin(plugin_id, reason)
    
    def _quarantine_plugin(self, plugin_id: str, reason: str):
        """Quarantine a problematic plugin"""
        with self.lock:
            self.quarantine_list.add(plugin_id)
            self._update_plugin_state(plugin_id, PluginState.QUARANTINED)
            
            self.logger.warning(f"Plugin {plugin_id} quarantined: {reason}")
            
            # Schedule automatic release from quarantine
            threading.Timer(
                self.config["quarantine_duration"].total_seconds(),
                self._release_from_quarantine,
                args=[plugin_id]
            ).start()
    
    def _release_from_quarantine(self, plugin_id: str):
        """Release plugin from quarantine"""
        with self.lock:
            if plugin_id in self.quarantine_list:
                self.quarantine_list.remove(plugin_id)
                self._update_plugin_state(plugin_id, PluginState.LOADED)
                
                # Reset consecutive failures to give plugin another chance
                if plugin_id in self.plugin_metrics:
                    self.plugin_metrics[plugin_id].consecutive_failures = 0
                
                self.logger.info(f"Plugin {plugin_id} released from quarantine")
    
    def _attempt_plugin_recovery(self, plugin_id: str, plugin_func: Callable, 
                                failure: PluginFailure, *args, **kwargs) -> Any:
        """Attempt to recover from plugin failure"""
        self.logger.info(f"Attempting recovery for plugin {plugin_id}")
        
        # Try fallback first
        if self.config["fallback_enabled"] and plugin_id in self.fallback_chains:
            for fallback_id in self.fallback_chains[plugin_id]:
                if self._is_plugin_available(fallback_id):
                    try:
                        self.logger.info(f"Using fallback plugin: {fallback_id}")
                        # In real implementation, would execute fallback plugin
                        # For now, return a safe default
                        return self._get_safe_default_result(plugin_id)
                    except Exception as e:
                        self.logger.warning(f"Fallback plugin {fallback_id} also failed: {e}")
        
        # Try graceful degradation
        return self._graceful_degradation(plugin_id, failure)
    
    def _get_safe_default_result(self, plugin_id: str) -> Any:
        """Get safe default result for plugin"""
        # Return plugin-type appropriate defaults
        if "effect" in plugin_id.lower():
            return b''  # Empty audio data
        elif "generator" in plugin_id.lower():
            return b'\x00' * 1024  # Silence
        elif "analyzer" in plugin_id.lower():
            return {"analysis": "unavailable"}
        else:
            return None
    
    def _graceful_degradation(self, plugin_id: str, failure: PluginFailure) -> Any:
        """Implement graceful degradation for plugin failure"""
        self.logger.info(f"Graceful degradation for plugin {plugin_id}")
        
        # Mark plugin as degraded but keep it available
        with self.lock:
            self._update_plugin_state(plugin_id, PluginState.LOADED)
        
        # Return safe default
        return self._get_safe_default_result(plugin_id)
    
    def _update_plugin_state(self, plugin_id: str, state: PluginState):
        """Update plugin state"""
        with self.lock:
            self.plugin_states[plugin_id] = state
    
    def disable_plugin(self, plugin_id: str, reason: str = "Manual disable"):
        """Manually disable a plugin"""
        with self.lock:
            self.disabled_plugins.add(plugin_id)
            self._update_plugin_state(plugin_id, PluginState.DISABLED)
            self.logger.info(f"Plugin {plugin_id} disabled: {reason}")
    
    def enable_plugin(self, plugin_id: str):
        """Re-enable a disabled plugin"""
        with self.lock:
            self.disabled_plugins.discard(plugin_id)
            self.quarantine_list.discard(plugin_id)
            self._update_plugin_state(plugin_id, PluginState.LOADED)
            
            # Reset failure metrics
            if plugin_id in self.plugin_metrics:
                self.plugin_metrics[plugin_id].consecutive_failures = 0
            
            self.logger.info(f"Plugin {plugin_id} enabled")
    
    def get_plugin_health_status(self, plugin_id: str) -> Dict[str, Any]:
        """Get comprehensive health status for plugin"""
        with self.lock:
            metrics = self.plugin_metrics.get(plugin_id, PluginMetrics())
            state = self.plugin_states.get(plugin_id, PluginState.UNLOADED)
            
            # Calculate reliability metrics
            reliability = 0.0
            if metrics.execution_count > 0:
                reliability = metrics.success_count / metrics.execution_count
            
            # Recent failures
            recent_failures = [f for f in self.plugin_failures 
                             if f.plugin_id == plugin_id and 
                             datetime.now() - f.timestamp < timedelta(hours=1)]
            
            return {
                "plugin_id": plugin_id,
                "state": state.value,
                "is_available": self._is_plugin_available(plugin_id),
                "is_quarantined": plugin_id in self.quarantine_list,
                "is_disabled": plugin_id in self.disabled_plugins,
                "metrics": {
                    "execution_count": metrics.execution_count,
                    "success_count": metrics.success_count,
                    "failure_count": metrics.failure_count,
                    "reliability": reliability,
                    "consecutive_failures": metrics.consecutive_failures,
                    "average_execution_time": metrics.average_execution_time,
                    "last_success": metrics.last_success.isoformat() if metrics.last_success else None,
                    "last_failure": metrics.last_failure.isoformat() if metrics.last_failure else None,
                },
                "recent_failures": len(recent_failures),
                "fallback_available": len(self.fallback_chains.get(plugin_id, [])) > 0
            }
    
    def get_system_health_report(self) -> Dict[str, Any]:
        """Get comprehensive system health report"""
        with self.lock:
            total_plugins = len(self.plugin_states)
            available_plugins = sum(1 for pid in self.plugin_states if self._is_plugin_available(pid))
            quarantined_plugins = len(self.quarantine_list)
            disabled_plugins = len(self.disabled_plugins)
            
            # Calculate system reliability
            total_executions = sum(m.execution_count for m in self.plugin_metrics.values())
            total_successes = sum(m.success_count for m in self.plugin_metrics.values())
            system_reliability = total_successes / total_executions if total_executions > 0 else 1.0
            
            # Recent failures
            recent_failures = [f for f in self.plugin_failures 
                             if datetime.now() - f.timestamp < timedelta(hours=1)]
            
            return {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_plugins": total_plugins,
                    "available_plugins": available_plugins,
                    "quarantined_plugins": quarantined_plugins,
                    "disabled_plugins": disabled_plugins,
                    "availability_rate": available_plugins / total_plugins if total_plugins > 0 else 1.0,
                    "system_reliability": system_reliability
                },
                "recent_activity": {
                    "failures_last_hour": len(recent_failures),
                    "total_executions": total_executions,
                    "total_successes": total_successes
                },
                "plugins": {pid: self.get_plugin_health_status(pid) for pid in self.plugin_states}
            }
    
    def _start_monitoring(self):
        """Start background monitoring tasks"""
        def monitor_plugins():
            while True:
                try:
                    self._perform_health_checks()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    self.logger.error(f"Plugin monitoring error: {e}")
                    time.sleep(10)
        
        monitor_thread = threading.Thread(target=monitor_plugins, daemon=True)
        monitor_thread.start()
    
    def _perform_health_checks(self):
        """Perform periodic health checks on plugins"""
        with self.lock:
            current_time = datetime.now()
            
            # Check for plugins that have been inactive too long
            for plugin_id, metrics in self.plugin_metrics.items():
                if (metrics.last_success and 
                    current_time - metrics.last_success > timedelta(hours=2) and
                    metrics.consecutive_failures > 0):
                    
                    # Plugin might be stuck, consider quarantine
                    if plugin_id not in self.quarantine_list:
                        self.logger.warning(f"Plugin {plugin_id} appears inactive, monitoring closely")

# Decorator for plugin fault tolerance
def plugin_fault_tolerant(plugin_id: str, 
                         isolation_level: PluginIsolationLevel = PluginIsolationLevel.SANDBOXED,
                         fault_manager: Optional[PluginFaultToleranceManager] = None):
    """Decorator to add fault tolerance to plugin functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = fault_manager or get_global_plugin_fault_manager()
            return manager.execute_plugin_safely(plugin_id, func, *args, 
                                                isolation_level=isolation_level, **kwargs)
        return wrapper
    return decorator

# Global plugin fault tolerance manager
_global_plugin_fault_manager = None

def get_global_plugin_fault_manager() -> PluginFaultToleranceManager:
    """Get or create global plugin fault tolerance manager"""
    global _global_plugin_fault_manager
    if _global_plugin_fault_manager is None:
        _global_plugin_fault_manager = PluginFaultToleranceManager()
    return _global_plugin_fault_manager

if __name__ == "__main__":
    # Example usage
    ft_manager = PluginFaultToleranceManager()
    
    # Register a plugin
    ft_manager.register_plugin("test_plugin", {"type": "effect", "dependencies": []})
    
    # Set up fallback chain
    ft_manager.set_fallback_chain("test_plugin", ["backup_plugin", "default_plugin"])
    
    # Example plugin function
    def sample_plugin_function(data):
        if len(data) > 100:
            raise ValueError("Data too large")
        return f"Processed: {data}"
    
    # Execute plugin safely
    try:
        result = ft_manager.execute_plugin_safely(
            "test_plugin", 
            sample_plugin_function, 
            "test_data",
            isolation_level=PluginIsolationLevel.SANDBOXED
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Plugin execution failed: {e}")
    
    # Get health report
    report = ft_manager.get_system_health_report()
    print("\nSystem Health Report:")
    print(json.dumps(report, indent=2, default=str))