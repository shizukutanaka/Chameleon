#!/usr/bin/env python3
"""
Advanced performance optimization module for Chameleon Audio Processing Framework.
Implements production-grade performance monitoring, optimization, and resource management.
"""

import os
import gc
import time
import threading
import multiprocessing
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable, Tuple
from functools import wraps

try:
    from .types import get_fallback_logger
    logger = get_fallback_logger('chameleon.performance')
except ImportError:
    import logging
    logger = logging.getLogger('chameleon.performance')

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    thread_count: int = 0
    file_descriptors: int = 0
    execution_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            'cpu_percent': self.cpu_percent,
            'memory_mb': self.memory_mb,
            'memory_percent': self.memory_percent,
            'disk_io_read_mb': self.disk_io_read_mb,
            'disk_io_write_mb': self.disk_io_write_mb,
            'network_sent_mb': self.network_sent_mb,
            'network_recv_mb': self.network_recv_mb,
            'thread_count': self.thread_count,
            'file_descriptors': self.file_descriptors,
            'execution_time_ms': self.execution_time_ms,
            'cache_hit_rate': self.cache_hit_rate
        }

class PerformanceMonitor:
    """Real-time performance monitoring system"""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.metrics_history = deque(maxlen=history_size)
        self.start_time = time.time()
        self.last_disk_io = None
        self.last_network_io = None
        self.monitoring = False
        self.monitor_thread = None
        self.lock = threading.Lock()
    
    def start_monitoring(self, interval: float = 1.0):
        """Start continuous performance monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Performance monitoring started with {interval}s interval")
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Performance monitoring stopped")
    
    def _monitor_loop(self, interval: float):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                metrics = self.collect_metrics()
                with self.lock:
                    self.metrics_history.append(metrics)
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                time.sleep(interval)
    
    def collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""
        metrics = PerformanceMetrics()
        
        if not PSUTIL_AVAILABLE:
            return metrics
        
        try:
            process = psutil.Process()
            
            # CPU and Memory
            metrics.cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            metrics.memory_mb = memory_info.rss / (1024 * 1024)
            metrics.memory_percent = process.memory_percent()
            
            # Thread and file descriptor count
            metrics.thread_count = process.num_threads()
            try:
                metrics.file_descriptors = process.num_fds()
            except (AttributeError, psutil.AccessDenied):
                metrics.file_descriptors = 0
            
            # Disk I/O
            try:
                disk_io = process.io_counters()
                if self.last_disk_io:
                    read_diff = disk_io.read_bytes - self.last_disk_io.read_bytes
                    write_diff = disk_io.write_bytes - self.last_disk_io.write_bytes
                    metrics.disk_io_read_mb = read_diff / (1024 * 1024)
                    metrics.disk_io_write_mb = write_diff / (1024 * 1024)
                self.last_disk_io = disk_io
            except (AttributeError, psutil.AccessDenied):
                pass
            
            # Network I/O (system-wide)
            try:
                net_io = psutil.net_io_counters()
                if self.last_network_io:
                    sent_diff = net_io.bytes_sent - self.last_network_io.bytes_sent
                    recv_diff = net_io.bytes_recv - self.last_network_io.bytes_recv
                    metrics.network_sent_mb = sent_diff / (1024 * 1024)
                    metrics.network_recv_mb = recv_diff / (1024 * 1024)
                self.last_network_io = net_io
            except (AttributeError, psutil.AccessDenied):
                pass
            
        except Exception as e:
            logger.warning(f"Error collecting metrics: {e}")
        
        return metrics
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        return self.collect_metrics()
    
    def get_average_metrics(self, window_size: int = 60) -> PerformanceMetrics:
        """Get average metrics over specified window"""
        with self.lock:
            recent_metrics = list(self.metrics_history)[-window_size:]
        
        if not recent_metrics:
            return PerformanceMetrics()
        
        avg_metrics = PerformanceMetrics()
        
        # Calculate averages
        avg_metrics.cpu_percent = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_metrics.memory_mb = sum(m.memory_mb for m in recent_metrics) / len(recent_metrics)
        avg_metrics.memory_percent = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        avg_metrics.thread_count = sum(m.thread_count for m in recent_metrics) / len(recent_metrics)
        avg_metrics.file_descriptors = sum(m.file_descriptors for m in recent_metrics) / len(recent_metrics)
        
        return avg_metrics
    
    def get_peak_metrics(self) -> PerformanceMetrics:
        """Get peak metrics from history"""
        with self.lock:
            all_metrics = list(self.metrics_history)
        
        if not all_metrics:
            return PerformanceMetrics()
        
        peak_metrics = PerformanceMetrics()
        peak_metrics.cpu_percent = max(m.cpu_percent for m in all_metrics)
        peak_metrics.memory_mb = max(m.memory_mb for m in all_metrics)
        peak_metrics.memory_percent = max(m.memory_percent for m in all_metrics)
        peak_metrics.thread_count = max(m.thread_count for m in all_metrics)
        peak_metrics.file_descriptors = max(m.file_descriptors for m in all_metrics)
        
        return peak_metrics

class PerformanceCache:
    """High-performance caching system"""
    
    def __init__(self, max_size: int = 1000, ttl: float = 3600):
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        self.cache = {}
        self.access_times = {}
        self.hit_count = 0
        self.miss_count = 0
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self.lock:
            if key in self.cache:
                # Check TTL
                if time.time() - self.access_times[key] < self.ttl:
                    self.access_times[key] = time.time()
                    self.hit_count += 1
                    return self.cache[key]
                else:
                    # Expired
                    del self.cache[key]
                    del self.access_times[key]
            
            self.miss_count += 1
            return None
    
    def put(self, key: str, value: Any):
        """Put value in cache"""
        with self.lock:
            # Evict if at max size
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_lru()
            
            self.cache[key] = value
            self.access_times[key] = time.time()
    
    def _evict_lru(self):
        """Evict least recently used item"""
        if not self.access_times:
            return
        
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[lru_key]
        del self.access_times[lru_key]
    
    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.hit_count = 0
            self.miss_count = 0
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': self.get_hit_rate(),
            'ttl': self.ttl
        }

class ResourceManager:
    """System resource management"""
    
    def __init__(self):
        self.cpu_count = multiprocessing.cpu_count()
        self.memory_total_gb = 0
        self.resource_limits = {}
        self._detect_system_resources()
    
    def _detect_system_resources(self):
        """Detect system resources"""
        if PSUTIL_AVAILABLE:
            try:
                virtual_memory = psutil.virtual_memory()
                self.memory_total_gb = virtual_memory.total / (1024 ** 3)
            except Exception as e:
                logger.warning(f"Could not detect system memory: {e}")
        
        logger.info(f"System resources detected: {self.cpu_count} CPUs, {self.memory_total_gb:.1f}GB RAM")
    
    def set_resource_limits(self, cpu_percent: float = 80.0, memory_percent: float = 80.0):
        """Set resource usage limits"""
        self.resource_limits = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent
        }
        logger.info(f"Resource limits set: CPU {cpu_percent}%, Memory {memory_percent}%")
    
    def check_resource_limits(self) -> Tuple[bool, str]:
        """Check if resource usage is within limits"""
        if not self.resource_limits or not PSUTIL_AVAILABLE:
            return True, "Resource monitoring not available"
        
        try:
            # Check CPU usage
            cpu_usage = psutil.cpu_percent(interval=0.1)
            if cpu_usage > self.resource_limits['cpu_percent']:
                return False, f"CPU usage {cpu_usage:.1f}% exceeds limit {self.resource_limits['cpu_percent']}%"
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > self.resource_limits['memory_percent']:
                return False, f"Memory usage {memory.percent:.1f}% exceeds limit {self.resource_limits['memory_percent']}%"
            
            return True, "Resource usage within limits"
            
        except Exception as e:
            logger.warning(f"Resource limit check failed: {e}")
            return True, "Resource check failed"
    
    def optimize_for_performance(self):
        """Apply performance optimizations"""
        try:
            # Enable garbage collection optimization
            gc.set_threshold(700, 10, 10)
            
            # Set higher thread count for I/O operations
            if hasattr(os, 'cpu_count'):
                optimal_workers = min(self.cpu_count * 2, 32)
                logger.info(f"Optimal worker count set to: {optimal_workers}")
                
        except Exception as e:
            logger.warning(f"Performance optimization failed: {e}")

class PerformanceProfiler:
    """Function performance profiling"""
    
    def __init__(self):
        self.profiles = defaultdict(list)
        self.active_profiles = {}
        self.lock = threading.Lock()
    
    @contextmanager
    def profile(self, operation_name: str):
        """Context manager for profiling operations"""
        start_time = time.time()
        start_memory = 0
        
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                start_memory = process.memory_info().rss
            except Exception:
                pass
        
        try:
            yield
        finally:
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000  # ms
            
            end_memory = 0
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process()
                    end_memory = process.memory_info().rss
                except Exception:
                    pass
            
            memory_delta = (end_memory - start_memory) / (1024 * 1024)  # MB
            
            with self.lock:
                self.profiles[operation_name].append({
                    'execution_time_ms': execution_time,
                    'memory_delta_mb': memory_delta,
                    'timestamp': time.time()
                })
    
    def get_profile_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get profiling statistics for operation"""
        with self.lock:
            if operation_name not in self.profiles:
                return {}
            
            measurements = self.profiles[operation_name]
            if not measurements:
                return {}
            
            execution_times = [m['execution_time_ms'] for m in measurements]
            memory_deltas = [m['memory_delta_mb'] for m in measurements]
            
            return {
                'operation': operation_name,
                'count': len(measurements),
                'avg_execution_time_ms': sum(execution_times) / len(execution_times),
                'min_execution_time_ms': min(execution_times),
                'max_execution_time_ms': max(execution_times),
                'avg_memory_delta_mb': sum(memory_deltas) / len(memory_deltas) if memory_deltas else 0,
                'total_execution_time_ms': sum(execution_times)
            }
    
    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get all profiling statistics"""
        with self.lock:
            return {name: self.get_profile_stats(name) for name in self.profiles.keys()}
    
    def clear_profiles(self):
        """Clear all profiling data"""
        with self.lock:
            self.profiles.clear()

def performance_monitor(operation_name: str = None):
    """Decorator for monitoring function performance"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with profiler.profile(op_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

def memory_efficient(func: Callable) -> Callable:
    """Decorator for memory-efficient operations"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Force garbage collection before operation
        gc.collect()
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Force garbage collection after operation
            gc.collect()
    
    return wrapper

# Global performance instances
monitor = PerformanceMonitor()
cache = PerformanceCache()
resource_manager = ResourceManager()
profiler = PerformanceProfiler()

def initialize_performance():
    """Initialize performance subsystem"""
    logger.info("Performance subsystem initialized")
    
    # Set default resource limits
    resource_manager.set_resource_limits()
    
    # Apply performance optimizations
    resource_manager.optimize_for_performance()

def get_system_performance_report() -> Dict[str, Any]:
    """Get comprehensive system performance report"""
    current_metrics = monitor.get_current_metrics()
    average_metrics = monitor.get_average_metrics()
    peak_metrics = monitor.get_peak_metrics()
    cache_stats = cache.get_stats()
    profile_stats = profiler.get_all_profiles()
    
    # Resource limits check
    within_limits, limits_message = resource_manager.check_resource_limits()
    
    return {
        'timestamp': time.time(),
        'current_metrics': current_metrics.to_dict(),
        'average_metrics': average_metrics.to_dict(),
        'peak_metrics': peak_metrics.to_dict(),
        'cache_stats': cache_stats,
        'profile_stats': profile_stats,
        'resource_limits': {
            'within_limits': within_limits,
            'message': limits_message,
            'limits': resource_manager.resource_limits
        },
        'system_info': {
            'cpu_count': resource_manager.cpu_count,
            'memory_total_gb': resource_manager.memory_total_gb,
            'psutil_available': PSUTIL_AVAILABLE
        }
    }

# Initialize on import
initialize_performance()