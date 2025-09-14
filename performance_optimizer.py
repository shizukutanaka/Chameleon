#!/usr/bin/env python3
"""
Performance Optimization and Monitoring System
Advanced performance analysis and automatic optimization
"""

import logging
import threading
import time
import traceback
from typing import Dict, Any, Optional, List, Callable, Tuple, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps, lru_cache
import json
import statistics
from datetime import datetime, timedelta
from collections import defaultdict, deque
import asyncio
import concurrent.futures

# Safe imports with fallbacks
try:
    from dependency_manager import safe_import, psutil_factory, numpy_factory
    psutil = safe_import("psutil", psutil_factory)
    np = safe_import("numpy", numpy_factory)
    PSUTIL_AVAILABLE = psutil is not None
    NUMPY_AVAILABLE = np is not None
except ImportError:
    # Fallback if dependency_manager is not available
    try:
        import psutil
        PSUTIL_AVAILABLE = True
    except ImportError:
        psutil = None
        PSUTIL_AVAILABLE = False
    
    try:
        import numpy as np
        NUMPY_AVAILABLE = True
    except ImportError:
        np = None
        NUMPY_AVAILABLE = False

class OptimizationStrategy(Enum):
    """Performance optimization strategies"""
    CACHING = "caching"
    PARALLEL_PROCESSING = "parallel_processing"
    RESOURCE_POOLING = "resource_pooling"
    LOAD_BALANCING = "load_balancing"
    ALGORITHM_SWITCHING = "algorithm_switching"
    MEMORY_OPTIMIZATION = "memory_optimization"
    CPU_OPTIMIZATION = "cpu_optimization"
    IO_OPTIMIZATION = "io_optimization"

class PerformanceMetric(Enum):
    """Performance metrics to track"""
    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    RESOURCE_UTILIZATION = "resource_utilization"

@dataclass
class PerformanceSample:
    """Single performance measurement"""
    timestamp: datetime
    component: str
    operation: str
    execution_time: float
    memory_before: float
    memory_after: float
    cpu_usage: float
    thread_count: int
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceProfile:
    """Performance profile for a component/operation"""
    component: str
    operation: str
    sample_count: int = 0
    avg_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    avg_memory_usage: float = 0.0
    avg_cpu_usage: float = 0.0
    throughput: float = 0.0
    last_updated: Optional[datetime] = None
    optimization_applied: List[OptimizationStrategy] = field(default_factory=list)

@dataclass
class OptimizationRecommendation:
    """Optimization recommendation"""
    component: str
    strategy: OptimizationStrategy
    priority: int  # 1-10, 10 being highest
    estimated_improvement: float  # Percentage improvement
    description: str
    implementation_cost: int  # 1-10, 10 being highest cost
    confidence: float  # 0-1, confidence in recommendation

class PerformanceAnalyzer:
    """Advanced performance analysis engine"""
    
    def __init__(self):
        self.samples = deque(maxlen=100000)
        self.profiles = {}
        self.baselines = {}
        self.lock = threading.RLock()
        
    def add_sample(self, sample: PerformanceSample):
        """Add performance sample and update profiles"""
        with self.lock:
            self.samples.append(sample)
            self._update_profile(sample)
    
    def _update_profile(self, sample: PerformanceSample):
        """Update performance profile with new sample"""
        key = f"{sample.component}::{sample.operation}"
        
        if key not in self.profiles:
            self.profiles[key] = PerformanceProfile(
                component=sample.component,
                operation=sample.operation
            )
        
        profile = self.profiles[key]
        profile.sample_count += 1
        
        # Update execution time statistics
        profile.avg_execution_time = (
            (profile.avg_execution_time * (profile.sample_count - 1) + sample.execution_time) / 
            profile.sample_count
        )
        profile.min_execution_time = min(profile.min_execution_time, sample.execution_time)
        profile.max_execution_time = max(profile.max_execution_time, sample.execution_time)
        
        # Update resource usage
        memory_delta = sample.memory_after - sample.memory_before
        profile.avg_memory_usage = (
            (profile.avg_memory_usage * (profile.sample_count - 1) + memory_delta) / 
            profile.sample_count
        )
        profile.avg_cpu_usage = (
            (profile.avg_cpu_usage * (profile.sample_count - 1) + sample.cpu_usage) / 
            profile.sample_count
        )
        
        # Calculate throughput (operations per second)
        if sample.execution_time > 0:
            current_throughput = 1.0 / sample.execution_time
            profile.throughput = (
                (profile.throughput * (profile.sample_count - 1) + current_throughput) / 
                profile.sample_count
            )
        
        profile.last_updated = datetime.now()
    
    def get_profile(self, component: str, operation: str) -> Optional[PerformanceProfile]:
        """Get performance profile for component/operation"""
        key = f"{component}::{operation}"
        return self.profiles.get(key)
    
    def analyze_trends(self, component: str, operation: str, 
                      time_window: timedelta = timedelta(hours=1)) -> Dict[str, Any]:
        """Analyze performance trends over time"""
        with self.lock:
            cutoff = datetime.now() - time_window
            relevant_samples = [
                s for s in self.samples 
                if (s.component == component and s.operation == operation and 
                    s.timestamp >= cutoff)
            ]
            
            if not relevant_samples:
                return {"status": "insufficient_data"}
            
            # Calculate trends
            times = [s.execution_time for s in relevant_samples]
            memory_usage = [s.memory_after - s.memory_before for s in relevant_samples]
            cpu_usage = [s.cpu_usage for s in relevant_samples]
            
            return {
                "sample_count": len(relevant_samples),
                "execution_time": {
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "stdev": statistics.stdev(times) if len(times) > 1 else 0,
                    "min": min(times),
                    "max": max(times)
                },
                "memory_usage": {
                    "mean": statistics.mean(memory_usage),
                    "median": statistics.median(memory_usage),
                    "stdev": statistics.stdev(memory_usage) if len(memory_usage) > 1 else 0
                },
                "cpu_usage": {
                    "mean": statistics.mean(cpu_usage),
                    "median": statistics.median(cpu_usage),
                    "stdev": statistics.stdev(cpu_usage) if len(cpu_usage) > 1 else 0
                }
            }
    
    def detect_performance_issues(self, component: str, operation: str) -> List[str]:
        """Detect performance issues based on analysis"""
        issues = []
        
        profile = self.get_profile(component, operation)
        if not profile or profile.sample_count < 10:
            return issues
        
        trends = self.analyze_trends(component, operation)
        if trends.get("status") == "insufficient_data":
            return issues
        
        exec_stats = trends["execution_time"]
        memory_stats = trends["memory_usage"]
        cpu_stats = trends["cpu_usage"]
        
        # Check for high variance in execution time
        if exec_stats["stdev"] > exec_stats["mean"] * 0.5:
            issues.append("High variance in execution time - inconsistent performance")
        
        # Check for high execution time
        if exec_stats["mean"] > 1.0:  # More than 1 second
            issues.append("High average execution time")
        
        # Check for memory growth
        if memory_stats["mean"] > 100 * 1024 * 1024:  # More than 100MB
            issues.append("High memory usage")
        
        # Check for high CPU usage
        if cpu_stats["mean"] > 80:  # More than 80% CPU
            issues.append("High CPU usage")
        
        return issues

class PerformanceOptimizer:
    """Automatic performance optimization system"""
    
    def __init__(self):
        self.analyzer = PerformanceAnalyzer()
        self.optimizations = {}
        self.optimization_history = deque(maxlen=1000)
        self.resource_pool = {}
        self.cache_layer = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger("PerformanceOptimizer")
        
        # Configuration
        self.config = {
            "auto_optimize": True,
            "optimization_threshold": 0.1,  # 10% performance degradation
            "cache_size_limit": 1000,
            "thread_pool_size": 4,
            "memory_limit_mb": 500,
            "cpu_limit_percent": 80
        }
        
        # Initialize thread pool
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config["thread_pool_size"]
        )
        
        # Start monitoring
        self._start_monitoring()
    
    def record_performance(self, component: str, operation: str, 
                          execution_time: float, memory_before: float, 
                          memory_after: float, cpu_usage: float, 
                          context: Dict[str, Any] = None) -> None:
        """Record performance measurement"""
        sample = PerformanceSample(
            timestamp=datetime.now(),
            component=component,
            operation=operation,
            execution_time=execution_time,
            memory_before=memory_before,
            memory_after=memory_after,
            cpu_usage=cpu_usage,
            thread_count=threading.active_count(),
            context=context or {}
        )
        
        self.analyzer.add_sample(sample)
        
        # Trigger optimization if enabled
        if self.config["auto_optimize"]:
            self._consider_optimization(component, operation)
    
    def _consider_optimization(self, component: str, operation: str):
        """Consider if optimization is needed"""
        profile = self.analyzer.get_profile(component, operation)
        if not profile or profile.sample_count < 20:
            return
        
        # Check if performance has degraded
        baseline_key = f"{component}::{operation}"
        if baseline_key in self.analyzer.baselines:
            baseline = self.analyzer.baselines[baseline_key]
            current_perf = profile.avg_execution_time
            degradation = (current_perf - baseline) / baseline
            
            if degradation > self.config["optimization_threshold"]:
                self._trigger_optimization(component, operation, degradation)
    
    def _trigger_optimization(self, component: str, operation: str, degradation: float):
        """Trigger optimization for component/operation"""
        recommendations = self.generate_recommendations(component, operation)
        
        for rec in recommendations:
            if rec.priority >= 7:  # High priority recommendations
                self._apply_optimization(rec)
    
    def generate_recommendations(self, component: str, operation: str) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations"""
        recommendations = []
        
        profile = self.analyzer.get_profile(component, operation)
        if not profile:
            return recommendations
        
        issues = self.analyzer.detect_performance_issues(component, operation)
        
        # Caching recommendation
        if profile.sample_count > 50 and "caching" not in [s.value for s in profile.optimization_applied]:
            recommendations.append(OptimizationRecommendation(
                component=component,
                strategy=OptimizationStrategy.CACHING,
                priority=8,
                estimated_improvement=30.0,
                description="Implement result caching to reduce redundant computations",
                implementation_cost=3,
                confidence=0.8
            ))
        
        # Parallel processing recommendation
        if ("High execution time" in issues and 
            profile.avg_execution_time > 0.5 and
            "parallel_processing" not in [s.value for s in profile.optimization_applied]):
            
            recommendations.append(OptimizationRecommendation(
                component=component,
                strategy=OptimizationStrategy.PARALLEL_PROCESSING,
                priority=7,
                estimated_improvement=40.0,
                description="Use parallel processing to utilize multiple CPU cores",
                implementation_cost=6,
                confidence=0.7
            ))
        
        # Memory optimization recommendation
        if "High memory usage" in issues:
            recommendations.append(OptimizationRecommendation(
                component=component,
                strategy=OptimizationStrategy.MEMORY_OPTIMIZATION,
                priority=6,
                estimated_improvement=25.0,
                description="Optimize memory usage through better data structures",
                implementation_cost=4,
                confidence=0.6
            ))
        
        # Algorithm switching recommendation
        if "High variance in execution time" in issues:
            recommendations.append(OptimizationRecommendation(
                component=component,
                strategy=OptimizationStrategy.ALGORITHM_SWITCHING,
                priority=5,
                estimated_improvement=20.0,
                description="Switch to more stable algorithm based on input characteristics",
                implementation_cost=8,
                confidence=0.5
            ))
        
        # Sort by priority and confidence
        recommendations.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
        return recommendations
    
    def _apply_optimization(self, recommendation: OptimizationRecommendation):
        """Apply optimization recommendation"""
        try:
            if recommendation.strategy == OptimizationStrategy.CACHING:
                self._apply_caching(recommendation.component)
            elif recommendation.strategy == OptimizationStrategy.PARALLEL_PROCESSING:
                self._apply_parallel_processing(recommendation.component)
            elif recommendation.strategy == OptimizationStrategy.MEMORY_OPTIMIZATION:
                self._apply_memory_optimization(recommendation.component)
            elif recommendation.strategy == OptimizationStrategy.RESOURCE_POOLING:
                self._apply_resource_pooling(recommendation.component)
            
            # Record optimization application
            self.optimization_history.append({
                "timestamp": datetime.now(),
                "recommendation": recommendation,
                "status": "applied"
            })
            
            # Update profile
            profile = self.analyzer.get_profile(recommendation.component, "*")
            if profile:
                profile.optimization_applied.append(recommendation.strategy)
            
            self.logger.info(f"Applied optimization: {recommendation.strategy.value} to {recommendation.component}")
            
        except Exception as e:
            self.logger.error(f"Failed to apply optimization {recommendation.strategy.value}: {e}")
            self.optimization_history.append({
                "timestamp": datetime.now(),
                "recommendation": recommendation,
                "status": "failed",
                "error": str(e)
            })
    
    def _apply_caching(self, component: str):
        """Apply caching optimization"""
        if component not in self.cache_layer:
            self.cache_layer[component] = {}
        
        # Create LRU cache for component
        cache_size = min(self.config["cache_size_limit"], 100)
        
        @lru_cache(maxsize=cache_size)
        def cached_wrapper(func, *args, **kwargs):
            return func(*args, **kwargs)
        
        self.cache_layer[component]["wrapper"] = cached_wrapper
    
    def _apply_parallel_processing(self, component: str):
        """Apply parallel processing optimization"""
        # Create component-specific thread pool
        if component not in self.resource_pool:
            self.resource_pool[component] = concurrent.futures.ThreadPoolExecutor(
                max_workers=min(4, self.config["thread_pool_size"])
            )
    
    def _apply_memory_optimization(self, component: str):
        """Apply memory optimization"""
        # Implement memory monitoring for component
        if component not in self.optimizations:
            self.optimizations[component] = {}
        
        self.optimizations[component]["memory_monitor"] = True
        self.optimizations[component]["memory_limit"] = self.config["memory_limit_mb"] * 1024 * 1024
    
    def _apply_resource_pooling(self, component: str):
        """Apply resource pooling optimization"""
        if component not in self.resource_pool:
            self.resource_pool[component] = {
                "pool": [],
                "max_size": 10,
                "current_size": 0
            }
    
    def get_cached_result(self, component: str, operation: str, key: str) -> Any:
        """Get cached result if available"""
        if (component in self.cache_layer and 
            operation in self.cache_layer[component]):
            return self.cache_layer[component][operation].get(key)
        return None
    
    def set_cached_result(self, component: str, operation: str, key: str, result: Any):
        """Cache result for future use"""
        if component not in self.cache_layer:
            self.cache_layer[component] = {}
        if operation not in self.cache_layer[component]:
            self.cache_layer[component][operation] = {}
        
        # Simple cache with size limit
        cache = self.cache_layer[component][operation]
        if len(cache) >= self.config["cache_size_limit"]:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(cache))
            del cache[oldest_key]
        
        cache[key] = result
    
    def get_thread_pool(self, component: str) -> concurrent.futures.ThreadPoolExecutor:
        """Get thread pool for component"""
        if component in self.resource_pool and isinstance(self.resource_pool[component], concurrent.futures.ThreadPoolExecutor):
            return self.resource_pool[component]
        return self.thread_pool
    
    def get_optimization_status(self, component: str) -> Dict[str, Any]:
        """Get optimization status for component"""
        profile = self.analyzer.get_profile(component, "*")
        trends = self.analyzer.analyze_trends(component, "*")
        issues = self.analyzer.detect_performance_issues(component, "*")
        recommendations = self.generate_recommendations(component, "*")
        
        return {
            "component": component,
            "profile": profile.__dict__ if profile else None,
            "trends": trends,
            "issues": issues,
            "recommendations": [rec.__dict__ for rec in recommendations],
            "applied_optimizations": self.optimizations.get(component, {}),
            "cache_stats": {
                "cached_operations": len(self.cache_layer.get(component, {})),
                "cache_size": sum(len(cache) for cache in self.cache_layer.get(component, {}).values())
            }
        }
    
    def get_system_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive system performance report"""
        with self.lock:
            # System resource usage
            system_stats = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": psutil.virtual_memory()._asdict(),
                "disk": psutil.disk_usage('/')._asdict(),
                "network": psutil.net_io_counters()._asdict()
            }
            
            # Component performance summary
            component_summary = {}
            for key, profile in self.analyzer.profiles.items():
                component = profile.component
                if component not in component_summary:
                    component_summary[component] = {
                        "operations": 0,
                        "avg_execution_time": 0,
                        "total_samples": 0,
                        "optimizations_applied": len(profile.optimization_applied)
                    }
                
                summary = component_summary[component]
                summary["operations"] += 1
                summary["total_samples"] += profile.sample_count
                summary["avg_execution_time"] = (
                    (summary["avg_execution_time"] * (summary["operations"] - 1) + 
                     profile.avg_execution_time) / summary["operations"]
                )
            
            # Optimization effectiveness
            optimization_stats = {
                "total_optimizations": len(self.optimization_history),
                "successful_optimizations": len([o for o in self.optimization_history 
                                                if o.get("status") == "applied"]),
                "failed_optimizations": len([o for o in self.optimization_history 
                                           if o.get("status") == "failed"])
            }
            
            return {
                "timestamp": datetime.now().isoformat(),
                "system_resources": system_stats,
                "component_performance": component_summary,
                "optimization_statistics": optimization_stats,
                "total_performance_samples": len(self.analyzer.samples),
                "cache_effectiveness": self._calculate_cache_effectiveness()
            }
    
    def _calculate_cache_effectiveness(self) -> Dict[str, float]:
        """Calculate cache hit rates and effectiveness"""
        total_cache_size = 0
        total_operations = 0
        
        for component, operations in self.cache_layer.items():
            for operation, cache in operations.items():
                if isinstance(cache, dict):
                    total_cache_size += len(cache)
                    # Estimate cache hits (simplified)
                    total_operations += len(cache) * 2  # Assume 2:1 hit ratio
        
        cache_hit_rate = 0.67 if total_operations > 0 else 0  # Simplified estimation
        
        return {
            "total_cached_items": total_cache_size,
            "estimated_hit_rate": cache_hit_rate,
            "estimated_operations_served": total_operations
        }
    
    def _start_monitoring(self):
        """Start background performance monitoring"""
        def monitor_system():
            while True:
                try:
                    # Perform system health checks
                    self._monitor_system_resources()
                    time.sleep(10)
                except Exception as e:
                    self.logger.error(f"System monitoring error: {e}")
                    time.sleep(30)
        
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()
    
    def _monitor_system_resources(self):
        """Monitor system resource usage"""
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        # Alert if system resources are high
        if cpu_percent > self.config["cpu_limit_percent"]:
            self.logger.warning(f"High CPU usage detected: {cpu_percent}%")
        
        if memory.percent > 90:
            self.logger.warning(f"High memory usage detected: {memory.percent}%")
            # Trigger cache cleanup
            self._cleanup_caches()
    
    def _cleanup_caches(self):
        """Clean up caches to free memory"""
        with self.lock:
            for component in self.cache_layer:
                for operation in self.cache_layer[component]:
                    cache = self.cache_layer[component][operation]
                    if isinstance(cache, dict) and len(cache) > 10:
                        # Keep only most recent 10 items
                        items = list(cache.items())
                        cache.clear()
                        cache.update(items[-10:])
            
            self.logger.info("Cache cleanup completed")

# Decorator for automatic performance monitoring
def monitor_performance(component: str, operation: str = None, 
                       optimizer: Optional[PerformanceOptimizer] = None):
    """Decorator to automatically monitor function performance"""
    def decorator(func):
        op_name = operation or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            perf_optimizer = optimizer or get_global_performance_optimizer()
            
            # Measure performance
            start_time = time.time()
            process = psutil.Process()
            memory_before = process.memory_info().rss
            cpu_before = process.cpu_percent()
            
            try:
                result = func(*args, **kwargs)
                
                # Record successful execution
                end_time = time.time()
                memory_after = process.memory_info().rss
                cpu_after = process.cpu_percent()
                
                perf_optimizer.record_performance(
                    component=component,
                    operation=op_name,
                    execution_time=end_time - start_time,
                    memory_before=memory_before,
                    memory_after=memory_after,
                    cpu_usage=(cpu_before + cpu_after) / 2,
                    context={"args_count": len(args), "kwargs_count": len(kwargs)}
                )
                
                return result
                
            except Exception as e:
                # Record failed execution
                end_time = time.time()
                memory_after = process.memory_info().rss
                cpu_after = process.cpu_percent()
                
                perf_optimizer.record_performance(
                    component=component,
                    operation=op_name,
                    execution_time=end_time - start_time,
                    memory_before=memory_before,
                    memory_after=memory_after,
                    cpu_usage=(cpu_before + cpu_after) / 2,
                    context={"error": str(e), "error_type": type(e).__name__}
                )
                
                raise
        
        return wrapper
    return decorator

# Global performance optimizer instance
_global_performance_optimizer = None

def get_global_performance_optimizer() -> PerformanceOptimizer:
    """Get or create global performance optimizer"""
    global _global_performance_optimizer
    if _global_performance_optimizer is None:
        _global_performance_optimizer = PerformanceOptimizer()
    return _global_performance_optimizer

if __name__ == "__main__":
    # Example usage
    optimizer = PerformanceOptimizer()
    
    # Example function with performance monitoring
    @monitor_performance("test_component", "test_operation")
    def sample_function(data_size: int):
        # Simulate work
        data = list(range(data_size))
        return sum(x * x for x in data)
    
    # Run some tests
    for i in range(10):
        result = sample_function(1000 * (i + 1))
        time.sleep(0.1)
    
    # Get performance report
    report = optimizer.get_system_performance_report()
    print("Performance Report:")
    print(json.dumps(report, indent=2, default=str))
    
    # Get optimization status
    status = optimizer.get_optimization_status("test_component")
    print("\nOptimization Status:")
    print(json.dumps(status, indent=2, default=str))