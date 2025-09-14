#!/usr/bin/env python3
"""
Chameleon Audio System - Advanced System Monitor
===============================================
Comprehensive system monitoring and health checking
"""

import os
import sys
import time
import json
import threading
import psutil
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import queue
import traceback
from collections import deque, defaultdict
import statistics


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SystemStatus(Enum):
    """Overall system status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class SystemAlert:
    """System alert/notification"""
    level: AlertLevel
    message: str
    component: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_usage_percent: float
    network_io: Dict[str, int]
    audio_processing_latency: float
    active_threads: int
    active_plugins: int
    error_rate: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class ComponentHealth:
    """Health status of a system component"""
    name: str
    status: SystemStatus
    last_check: float
    error_count: int
    performance_score: float
    alerts: List[SystemAlert] = field(default_factory=list)


class HealthChecker:
    """Health checking for system components"""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.thresholds = {
            'cpu_warning': 80.0,
            'cpu_critical': 95.0,
            'memory_warning': 85.0,
            'memory_critical': 95.0,
            'disk_warning': 90.0,
            'disk_critical': 98.0,
            'latency_warning': 50.0,  # ms
            'latency_critical': 100.0,  # ms
            'error_rate_warning': 0.05,  # 5%
            'error_rate_critical': 0.10   # 10%
        }
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """Register a health check function"""
        self.checks[name] = check_func
    
    def run_checks(self) -> Dict[str, ComponentHealth]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_func in self.checks.items():
            try:
                health = check_func()
                results[name] = health
            except Exception as e:
                results[name] = ComponentHealth(
                    name=name,
                    status=SystemStatus.CRITICAL,
                    last_check=time.time(),
                    error_count=1,
                    performance_score=0.0,
                    alerts=[SystemAlert(
                        level=AlertLevel.CRITICAL,
                        message=f"Health check failed: {str(e)}",
                        component=name
                    )]
                )
        
        return results
    
    def check_system_resources(self) -> ComponentHealth:
        """Check system resource usage"""
        alerts = []
        
        # CPU check
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > self.thresholds['cpu_critical']:
            alerts.append(SystemAlert(
                level=AlertLevel.CRITICAL,
                message=f"CPU usage critical: {cpu_percent:.1f}%",
                component="system_resources"
            ))
        elif cpu_percent > self.thresholds['cpu_warning']:
            alerts.append(SystemAlert(
                level=AlertLevel.WARNING,
                message=f"CPU usage high: {cpu_percent:.1f}%",
                component="system_resources"
            ))
        
        # Memory check
        memory = psutil.virtual_memory()
        if memory.percent > self.thresholds['memory_critical']:
            alerts.append(SystemAlert(
                level=AlertLevel.CRITICAL,
                message=f"Memory usage critical: {memory.percent:.1f}%",
                component="system_resources"
            ))
        elif memory.percent > self.thresholds['memory_warning']:
            alerts.append(SystemAlert(
                level=AlertLevel.WARNING,
                message=f"Memory usage high: {memory.percent:.1f}%",
                component="system_resources"
            ))
        
        # Disk check
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > self.thresholds['disk_critical']:
            alerts.append(SystemAlert(
                level=AlertLevel.CRITICAL,
                message=f"Disk usage critical: {disk_percent:.1f}%",
                component="system_resources"
            ))
        elif disk_percent > self.thresholds['disk_warning']:
            alerts.append(SystemAlert(
                level=AlertLevel.WARNING,
                message=f"Disk usage high: {disk_percent:.1f}%",
                component="system_resources"
            ))
        
        # Determine overall status
        if any(alert.level == AlertLevel.CRITICAL for alert in alerts):
            status = SystemStatus.CRITICAL
            score = 0.0
        elif any(alert.level == AlertLevel.ERROR for alert in alerts):
            status = SystemStatus.UNHEALTHY
            score = 0.3
        elif any(alert.level == AlertLevel.WARNING for alert in alerts):
            status = SystemStatus.DEGRADED
            score = 0.7
        else:
            status = SystemStatus.HEALTHY
            score = 1.0
        
        return ComponentHealth(
            name="system_resources",
            status=status,
            last_check=time.time(),
            error_count=len([a for a in alerts if a.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]]),
            performance_score=score,
            alerts=alerts
        )
    
    def check_audio_processing(self) -> ComponentHealth:
        """Check audio processing health"""
        alerts = []
        
        try:
            # Test basic audio processing
            import audio_processor
            processor = audio_processor.AudioProcessor()
            
            # Generate test signal
            test_signal = [0.5] * 1024  # Simple test signal
            
            # Measure processing time
            start_time = time.perf_counter()
            processed = processor.process_audio(test_signal, {})
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Check latency
            if latency_ms > self.thresholds['latency_critical']:
                alerts.append(SystemAlert(
                    level=AlertLevel.CRITICAL,
                    message=f"Audio processing latency critical: {latency_ms:.2f}ms",
                    component="audio_processing"
                ))
            elif latency_ms > self.thresholds['latency_warning']:
                alerts.append(SystemAlert(
                    level=AlertLevel.WARNING,
                    message=f"Audio processing latency high: {latency_ms:.2f}ms",
                    component="audio_processing"
                ))
            
            # Check if processing succeeded
            if not processed:
                alerts.append(SystemAlert(
                    level=AlertLevel.ERROR,
                    message="Audio processing returned no output",
                    component="audio_processing"
                ))
            
        except Exception as e:
            alerts.append(SystemAlert(
                level=AlertLevel.CRITICAL,
                message=f"Audio processing failed: {str(e)}",
                component="audio_processing"
            ))
        
        # Determine status
        if any(alert.level == AlertLevel.CRITICAL for alert in alerts):
            status = SystemStatus.CRITICAL
            score = 0.0
        elif any(alert.level == AlertLevel.ERROR for alert in alerts):
            status = SystemStatus.UNHEALTHY
            score = 0.3
        elif any(alert.level == AlertLevel.WARNING for alert in alerts):
            status = SystemStatus.DEGRADED
            score = 0.7
        else:
            status = SystemStatus.HEALTHY
            score = 1.0
        
        return ComponentHealth(
            name="audio_processing",
            status=status,
            last_check=time.time(),
            error_count=len([a for a in alerts if a.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]]),
            performance_score=score,
            alerts=alerts
        )


class SystemMonitor:
    """Advanced system monitoring and alerting"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.health_checker = HealthChecker()
        self.running = False
        self.monitor_thread = None
        
        # Metrics storage
        self.metrics_history = deque(maxlen=1000)  # Store last 1000 metrics
        self.alerts_queue = queue.Queue()
        
        # Performance tracking
        self.component_stats = defaultdict(list)
        self.error_counts = defaultdict(int)
        
        # Logging setup
        self.setup_logging()
        
        # Register default health checks
        self.health_checker.register_check("system_resources", 
                                          self.health_checker.check_system_resources)
        self.health_checker.register_check("audio_processing", 
                                          self.health_checker.check_audio_processing)
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load monitoring configuration"""
        default_config = {
            "monitoring_interval": 30,  # seconds
            "alert_retention": 86400,   # 24 hours
            "metrics_retention": 3600,  # 1 hour
            "log_level": "INFO",
            "alert_destinations": [],
            "performance_tracking": True,
            "auto_recovery": True
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file) as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")
        
        return default_config
    
    def setup_logging(self):
        """Setup logging for system monitor"""
        log_level = getattr(logging, self.config.get("log_level", "INFO"))
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('chameleon_monitor.log'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('ChameleonMonitor')
    
    def start_monitoring(self):
        """Start background monitoring"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("System monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Collect metrics
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Run health checks
                health_results = self.health_checker.run_checks()
                
                # Process alerts
                self._process_health_results(health_results)
                
                # Auto-recovery if enabled
                if self.config.get("auto_recovery", True):
                    self._attempt_auto_recovery(health_results)
                
                # Sleep until next check
                time.sleep(self.config.get("monitoring_interval", 30))
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                time.sleep(5)  # Short sleep on error
    
    def _collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            thread_count = process.num_threads()
            
            # Audio processing latency (simplified)
            audio_latency = self._measure_audio_latency()
            
            # Plugin count (simplified)
            active_plugins = 0
            try:
                from plugin_sdk import PluginManager
                mgr = PluginManager()
                active_plugins = len(mgr.active_plugins)
            except:
                pass
            
            # Error rate calculation
            error_rate = self._calculate_error_rate()
            
            return PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_mb=memory.used / (1024 * 1024),
                disk_usage_percent=(disk.used / disk.total) * 100,
                network_io={
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv
                },
                audio_processing_latency=audio_latency,
                active_threads=thread_count,
                active_plugins=active_plugins,
                error_rate=error_rate
            )
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")
            return PerformanceMetrics(0, 0, 0, 0, {}, 0, 0, 0, 1.0)
    
    def _measure_audio_latency(self) -> float:
        """Measure current audio processing latency"""
        try:
            import audio_processor
            processor = audio_processor.AudioProcessor()
            
            test_signal = [0.5] * 512
            start_time = time.perf_counter()
            processor.process_audio(test_signal, {})
            return (time.perf_counter() - start_time) * 1000
            
        except Exception:
            return 0.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate recent error rate"""
        # Simplified error rate calculation
        total_errors = sum(self.error_counts.values())
        total_operations = max(1, len(self.metrics_history) * 10)  # Estimated ops
        return total_errors / total_operations
    
    def _process_health_results(self, health_results: Dict[str, ComponentHealth]):
        """Process health check results and generate alerts"""
        for component_name, health in health_results.items():
            # Store component stats
            self.component_stats[component_name].append({
                'timestamp': health.last_check,
                'status': health.status.value,
                'score': health.performance_score,
                'errors': health.error_count
            })
            
            # Keep only recent stats
            cutoff_time = time.time() - self.config.get("metrics_retention", 3600)
            self.component_stats[component_name] = [
                stat for stat in self.component_stats[component_name]
                if stat['timestamp'] > cutoff_time
            ]
            
            # Queue alerts
            for alert in health.alerts:
                self.alerts_queue.put(alert)
                self.logger.log(
                    self._alert_level_to_log_level(alert.level),
                    f"[{alert.component}] {alert.message}"
                )
    
    def _alert_level_to_log_level(self, alert_level: AlertLevel) -> int:
        """Convert alert level to logging level"""
        mapping = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }
        return mapping.get(alert_level, logging.INFO)
    
    def _attempt_auto_recovery(self, health_results: Dict[str, ComponentHealth]):
        """Attempt automatic recovery for known issues"""
        for component_name, health in health_results.items():
            if health.status in [SystemStatus.UNHEALTHY, SystemStatus.CRITICAL]:
                self._try_component_recovery(component_name, health)
    
    def _try_component_recovery(self, component_name: str, health: ComponentHealth):
        """Try to recover a specific component"""
        recovery_actions = {
            'system_resources': self._recover_system_resources,
            'audio_processing': self._recover_audio_processing,
        }
        
        recovery_func = recovery_actions.get(component_name)
        if recovery_func:
            try:
                recovery_func(health)
                self.logger.info(f"Attempted recovery for {component_name}")
            except Exception as e:
                self.logger.error(f"Recovery failed for {component_name}: {e}")
    
    def _recover_system_resources(self, health: ComponentHealth):
        """Attempt to recover system resources"""
        import gc
        
        # Force garbage collection
        gc.collect()
        
        # Clear caches if available
        try:
            import audio_processor
            processor = audio_processor.AudioProcessor()
            if hasattr(processor, '_cache'):
                processor._cache.clear()
        except:
            pass
    
    def _recover_audio_processing(self, health: ComponentHealth):
        """Attempt to recover audio processing"""
        # Restart audio processing components if needed
        try:
            import audio_processor
            # Create fresh processor instance
            audio_processor.AudioProcessor()
        except Exception as e:
            self.logger.error(f"Audio processing recovery failed: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status summary"""
        health_results = self.health_checker.run_checks()
        current_metrics = self._collect_metrics()
        
        # Calculate overall status
        statuses = [health.status for health in health_results.values()]
        if SystemStatus.CRITICAL in statuses:
            overall_status = SystemStatus.CRITICAL
        elif SystemStatus.UNHEALTHY in statuses:
            overall_status = SystemStatus.UNHEALTHY
        elif SystemStatus.DEGRADED in statuses:
            overall_status = SystemStatus.DEGRADED
        else:
            overall_status = SystemStatus.HEALTHY
        
        # Get recent alerts
        recent_alerts = []
        try:
            while not self.alerts_queue.empty():
                alert = self.alerts_queue.get_nowait()
                if time.time() - alert.timestamp < 300:  # Last 5 minutes
                    recent_alerts.append({
                        'level': alert.level.value,
                        'message': alert.message,
                        'component': alert.component,
                        'timestamp': alert.timestamp
                    })
        except queue.Empty:
            pass
        
        return {
            'overall_status': overall_status.value,
            'timestamp': time.time(),
            'components': {
                name: {
                    'status': health.status.value,
                    'performance_score': health.performance_score,
                    'error_count': health.error_count,
                    'last_check': health.last_check
                }
                for name, health in health_results.items()
            },
            'current_metrics': {
                'cpu_percent': current_metrics.cpu_percent,
                'memory_percent': current_metrics.memory_percent,
                'memory_mb': current_metrics.memory_mb,
                'disk_usage_percent': current_metrics.disk_usage_percent,
                'audio_latency_ms': current_metrics.audio_processing_latency,
                'active_threads': current_metrics.active_threads,
                'active_plugins': current_metrics.active_plugins,
                'error_rate': current_metrics.error_rate
            },
            'recent_alerts': recent_alerts,
            'uptime': self._get_uptime()
        }
    
    def _get_uptime(self) -> float:
        """Get system uptime in seconds"""
        try:
            return time.time() - psutil.boot_time()
        except:
            return 0.0
    
    def get_historical_metrics(self, duration: int = 3600) -> List[Dict[str, Any]]:
        """Get historical metrics for specified duration (seconds)"""
        cutoff_time = time.time() - duration
        
        return [
            {
                'timestamp': metrics.timestamp,
                'cpu_percent': metrics.cpu_percent,
                'memory_percent': metrics.memory_percent,
                'memory_mb': metrics.memory_mb,
                'disk_usage_percent': metrics.disk_usage_percent,
                'audio_latency_ms': metrics.audio_processing_latency,
                'active_threads': metrics.active_threads,
                'active_plugins': metrics.active_plugins,
                'error_rate': metrics.error_rate
            }
            for metrics in self.metrics_history
            if metrics.timestamp > cutoff_time
        ]
    
    def generate_health_report(self) -> str:
        """Generate comprehensive health report"""
        status = self.get_system_status()
        
        report = []
        report.append("CHAMELEON AUDIO SYSTEM - HEALTH REPORT")
        report.append("=" * 50)
        report.append(f"Overall Status: {status['overall_status'].upper()}")
        report.append(f"Report Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"System Uptime: {status['uptime'] / 3600:.1f} hours")
        report.append("")
        
        # Current metrics
        metrics = status['current_metrics']
        report.append("Current Metrics:")
        report.append(f"  CPU Usage: {metrics['cpu_percent']:.1f}%")
        report.append(f"  Memory Usage: {metrics['memory_percent']:.1f}% ({metrics['memory_mb']:.0f} MB)")
        report.append(f"  Disk Usage: {metrics['disk_usage_percent']:.1f}%")
        report.append(f"  Audio Latency: {metrics['audio_latency_ms']:.2f}ms")
        report.append(f"  Active Threads: {metrics['active_threads']}")
        report.append(f"  Active Plugins: {metrics['active_plugins']}")
        report.append(f"  Error Rate: {metrics['error_rate']:.3f}")
        report.append("")
        
        # Component status
        report.append("Component Health:")
        for name, component in status['components'].items():
            status_icon = {
                'healthy': '✅',
                'degraded': '⚠️',
                'unhealthy': '❌',
                'critical': '🔥'
            }.get(component['status'], '❓')
            
            report.append(f"  {status_icon} {name}: {component['status']}")
            report.append(f"    Performance Score: {component['performance_score']:.2f}")
            report.append(f"    Error Count: {component['error_count']}")
        report.append("")
        
        # Recent alerts
        if status['recent_alerts']:
            report.append("Recent Alerts (Last 5 minutes):")
            for alert in status['recent_alerts'][-10:]:  # Last 10 alerts
                alert_icon = {
                    'info': 'ℹ️',
                    'warning': '⚠️',
                    'error': '❌',
                    'critical': '🔥'
                }.get(alert['level'], '❓')
                
                report.append(f"  {alert_icon} [{alert['component']}] {alert['message']}")
        else:
            report.append("No recent alerts")
        
        return "\n".join(report)


def demo_system_monitor():
    """Demonstrate system monitoring functionality"""
    print("=" * 60)
    print("CHAMELEON SYSTEM MONITOR DEMO")
    print("=" * 60)
    
    # Create monitor
    monitor = SystemMonitor()
    
    print("Starting monitoring...")
    monitor.start_monitoring()
    
    try:
        # Run for 30 seconds
        for i in range(6):
            time.sleep(5)
            
            print(f"\n--- Status Check {i+1} ---")
            status = monitor.get_system_status()
            
            print(f"Overall Status: {status['overall_status']}")
            print(f"CPU: {status['current_metrics']['cpu_percent']:.1f}%")
            print(f"Memory: {status['current_metrics']['memory_percent']:.1f}%")
            print(f"Audio Latency: {status['current_metrics']['audio_latency_ms']:.2f}ms")
            
            # Show any alerts
            if status['recent_alerts']:
                print("Recent Alerts:")
                for alert in status['recent_alerts'][-3:]:
                    print(f"  {alert['level']}: {alert['message']}")
        
        print("\n--- Final Health Report ---")
        print(monitor.generate_health_report())
        
    finally:
        monitor.stop_monitoring()
    
    print("\nSystem monitoring demo completed!")


if __name__ == "__main__":
    demo_system_monitor()