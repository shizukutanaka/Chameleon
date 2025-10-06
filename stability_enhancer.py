#!/usr/bin/env python3
"""
Stability Enhancement Module for Chameleon Audio System
Provides error recovery, graceful degradation, and resource management
"""

import os
import sys
import time
import logging
import traceback
import functools
import signal
import resource
import gc
from pathlib import Path
from typing import Optional, Callable, Any, Dict, List, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import threading

logger = logging.getLogger("chameleon.stability")


@dataclass
class ResourceLimits:
    """Resource limit configuration"""
    max_memory_mb: int = 1024  # 1 GB
    max_cpu_seconds: int = 300  # 5 minutes
    max_file_size_mb: int = 500
    max_open_files: int = 100


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self._lock:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half_open"
                else:
                    raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)

            with self._lock:
                if self.state == "half_open":
                    self._reset()

            return result

        except self.expected_exception as e:
            with self._lock:
                self._record_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _record_failure(self) -> None:
        """Record a failure and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def _reset(self) -> None:
        """Reset circuit breaker"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        logger.info("Circuit breaker reset")


class RetryPolicy:
    """Retry policy with exponential backoff"""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_attempts} attempts failed")

        raise last_exception


class ResourceManager:
    """Manage system resources to prevent exhaustion"""

    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self._open_files: List[Any] = []
        self._lock = threading.Lock()

    def set_resource_limits(self) -> None:
        """Set system resource limits"""
        if not hasattr(resource, 'RLIMIT_AS'):
            logger.warning("Resource limits not available on this platform")
            return

        try:
            # Set memory limit
            memory_bytes = self.limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

            # Set CPU time limit
            cpu_seconds = self.limits.max_cpu_seconds
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))

            # Set file descriptor limit
            max_files = self.limits.max_open_files
            resource.setrlimit(resource.RLIMIT_NOFILE, (max_files, max_files))

            logger.info(f"Resource limits set: {self.limits.max_memory_mb}MB RAM, "
                       f"{cpu_seconds}s CPU, {max_files} files")

        except Exception as e:
            logger.warning(f"Could not set resource limits: {e}")

    @contextmanager
    def managed_file(self, path: Path, mode: str = 'rb'):
        """Context manager for file handles with tracking"""
        with self._lock:
            if len(self._open_files) >= self.limits.max_open_files:
                raise RuntimeError("Too many open files")

        file_handle = open(path, mode)

        try:
            with self._lock:
                self._open_files.append(file_handle)

            yield file_handle

        finally:
            with self._lock:
                if file_handle in self._open_files:
                    self._open_files.remove(file_handle)
            file_handle.close()

    def cleanup(self) -> None:
        """Clean up open resources"""
        with self._lock:
            for f in self._open_files:
                try:
                    f.close()
                except Exception as e:
                    logger.warning(f"Error closing file: {e}")
            self._open_files.clear()

        gc.collect()


class GracefulShutdownHandler:
    """Handle graceful shutdown on signals"""

    def __init__(self, cleanup_func: Optional[Callable] = None):
        self.cleanup_func = cleanup_func
        self._shutdown_requested = False

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        if self._shutdown_requested:
            logger.warning("Forced shutdown")
            sys.exit(1)

        self._shutdown_requested = True
        logger.info(f"Shutdown requested (signal {signum})")

        if self.cleanup_func:
            try:
                self.cleanup_func()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

        sys.exit(0)

    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown was requested"""
        return self._shutdown_requested


class ErrorRecovery:
    """Error recovery strategies"""

    @staticmethod
    def safe_execute(
        func: Callable,
        fallback_value: Any = None,
        log_errors: bool = True
    ) -> Any:
        """Execute function with fallback on error"""
        try:
            return func()
        except Exception as e:
            if log_errors:
                logger.error(f"Error in {func.__name__}: {e}")
                logger.debug(traceback.format_exc())
            return fallback_value

    @staticmethod
    def with_timeout(timeout_seconds: int):
        """Decorator to enforce timeout on function execution"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Simple timeout using signal (Unix only)
                if hasattr(signal, 'SIGALRM'):
                    def timeout_handler(signum, frame):
                        raise TimeoutError(f"Function {func.__name__} timed out")

                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(timeout_seconds)

                    try:
                        result = func(*args, **kwargs)
                    finally:
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, old_handler)

                    return result
                else:
                    # Fallback for Windows - no timeout
                    logger.warning("Timeout not supported on this platform")
                    return func(*args, **kwargs)

            return wrapper
        return decorator


def create_recovery_checkpoint(
    state: Dict[str, Any],
    checkpoint_dir: Optional[Path] = None
) -> Path:
    """Create recovery checkpoint"""
    import json

    checkpoint_dir = checkpoint_dir or Path.home() / ".chameleon" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    timestamp = int(time.time())
    checkpoint_file = checkpoint_dir / f"checkpoint_{timestamp}.json"

    with open(checkpoint_file, 'w') as f:
        json.dump(state, f, indent=2)

    logger.info(f"Checkpoint created: {checkpoint_file}")
    return checkpoint_file


def restore_from_checkpoint(checkpoint_file: Path) -> Dict[str, Any]:
    """Restore state from checkpoint"""
    import json

    with open(checkpoint_file, 'r') as f:
        state = json.load(f)

    logger.info(f"Restored from checkpoint: {checkpoint_file}")
    return state


def validate_system_health() -> Tuple[bool, List[str]]:
    """Validate system health and return issues"""
    issues = []

    # Check available memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            issues.append(f"Low memory: {mem.percent}% used")
    except ImportError:
        pass

    # Check disk space
    try:
        import shutil
        usage = shutil.disk_usage("/")
        percent_used = (usage.used / usage.total) * 100
        if percent_used > 90:
            issues.append(f"Low disk space: {percent_used:.1f}% used")
    except Exception as e:
        issues.append(f"Could not check disk space: {e}")

    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(f"Python version {sys.version} is too old (require 3.8+)")

    return len(issues) == 0, issues


if __name__ == "__main__":
    print("Testing Stability Enhancer...")

    # Test circuit breaker
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)

    def failing_func():
        raise ValueError("Test error")

    for i in range(5):
        try:
            breaker.call(failing_func)
        except Exception as e:
            print(f"Attempt {i + 1}: {e}")

    # Test retry policy
    retry = RetryPolicy(max_attempts=3, base_delay=0.1)

    attempt_count = 0
    def sometimes_fails():
        global attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise ValueError("Temporary failure")
        return "Success"

    result = retry.execute(sometimes_fails)
    print(f"Retry result: {result}")

    # Test resource manager
    resource_mgr = ResourceManager()
    resource_mgr.set_resource_limits()

    # Test safe execute
    result = ErrorRecovery.safe_execute(
        lambda: 1 / 0,
        fallback_value="Error occurred"
    )
    print(f"Safe execute result: {result}")

    # Test system health
    healthy, issues = validate_system_health()
    print(f"System healthy: {healthy}")
    if issues:
        print(f"Issues: {issues}")

    # Test checkpoint
    state = {"progress": 50, "files_processed": 10}
    checkpoint_file = create_recovery_checkpoint(state)
    restored_state = restore_from_checkpoint(checkpoint_file)
    print(f"Checkpoint restored: {restored_state}")

    print("Stability enhancer tests completed")
