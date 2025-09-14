#!/usr/bin/env python3
"""
Performance monitoring and optimization utilities
Optimized for real-time audio processing
"""

import time
import threading
import gc
from typing import Dict, List, Optional
from collections import deque

# Safe import of psutil (optional dependency)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class Performance:
    """Performance monitoring and optimization with system monitoring"""
    
    def __init__(self, max_history: int = 1000):
        self.metrics = {}
        self.start_times = {}
        self.lock = threading.Lock()
        self.max_history = max_history
        self.system_metrics = deque(maxlen=100)
        self._last_gc_time = time.time()
        self._gc_interval = 30.0  # Force GC every 30 seconds
        
    def start_timer(self, name: str):
        """Start a named timer"""
        with self.lock:
            self.start_times[name] = time.perf_counter()
    
    def end_timer(self, name: str) -> float:
        """End a named timer and return elapsed time"""
        with self.lock:
            if name in self.start_times:
                elapsed = time.perf_counter() - self.start_times[name]
                del self.start_times[name]
                
                if name not in self.metrics:
                    self.metrics[name] = deque(maxlen=self.max_history)
                self.metrics[name].append(elapsed)
                
                # Auto garbage collection for memory management
                current_time = time.time()
                if current_time - self._last_gc_time > self._gc_interval:
                    gc.collect()
                    self._last_gc_time = current_time
                
                return elapsed
        return 0.0
    
    def get_average(self, name: str) -> float:
        """Get average time for a named operation"""
        with self.lock:
            if name in self.metrics and self.metrics[name]:
                return sum(self.metrics[name]) / len(self.metrics[name])
        return 0.0
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics"""
        with self.lock:
            stats = {}
            for name, times in self.metrics.items():
                if times:
                    stats[name] = {
                        'average': sum(times) / len(times),
                        'min': min(times),
                        'max': max(times),
                        'count': len(times)
                    }
            return stats
    
    def reset(self):
        """Reset all metrics"""
        with self.lock:
            self.metrics.clear()
            self.start_times.clear()
    
    def measure(self, func):
        """Decorator to measure function execution time"""
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            
            with self.lock:
                name = func.__name__
                if name not in self.metrics:
                    self.metrics[name] = deque(maxlen=self.max_history)
                self.metrics[name].append(elapsed)
            
            return result
        return wrapper
    
    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system performance metrics"""
        if not HAS_PSUTIL:
            return {'error': 'psutil not available'}
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.01)
            memory = psutil.virtual_memory()
            
            metrics = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / (1024 * 1024),
                'memory_used_mb': memory.used / (1024 * 1024)
            }
            
            self.system_metrics.append(metrics)
            return metrics
        except Exception as e:
            return {'error': str(e)}
    
    def get_real_time_factor(self, processing_time: float, audio_duration: float) -> float:
        """Calculate real-time factor for audio processing"""
        if audio_duration <= 0:
            return float('inf')
        return processing_time / audio_duration
    
    def optimize_memory(self):
        """Force garbage collection and clear old metrics"""
        gc.collect()
        with self.lock:
            # Keep only recent data to manage memory
            for name in list(self.metrics.keys()):
                if len(self.metrics[name]) > self.max_history:
                    # Convert to deque if it's still a list
                    if isinstance(self.metrics[name], list):
                        self.metrics[name] = deque(self.metrics[name][-self.max_history:], maxlen=self.max_history)
    
    def get_performance_report(self) -> Dict[str, any]:
        """Get comprehensive performance report"""
        stats = self.get_stats()
        system = self.get_system_metrics()
        
        report = {
            'timing_stats': stats,
            'system_metrics': system,
            'memory_optimized': len(self.system_metrics),
            'tracked_operations': len(self.metrics)
        }
        
        # Calculate real-time factors for audio operations
        audio_ops = ['process_chunk', 'process_audio', 'voice_process']
        for op in audio_ops:
            if op in stats:
                # Estimate audio duration (assume 1024 samples at 44100 Hz)
                estimated_duration = 1024 / 44100
                rtf = self.get_real_time_factor(stats[op]['average'], estimated_duration)
                report[f'{op}_rtf'] = rtf
        
        return report

# Global performance instance
performance_monitor = Performance()