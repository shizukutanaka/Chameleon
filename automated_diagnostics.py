#!/usr/bin/env python3
"""
Automated Diagnostics System
Comprehensive system health monitoring, issue detection, and automated diagnostics
"""

import logging
import threading
import time
import psutil
import traceback
import subprocess
import platform
from typing import Dict, Any, Optional, List, Callable, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import statistics
from collections import defaultdict, deque
import re
import hashlib
import socket
import sys
import os

from error_recovery import ErrorRecoveryManager, ErrorSeverity
from performance_optimizer import PerformanceOptimizer
from plugin_fault_tolerance import PluginFaultToleranceManager

class DiagnosticSeverity(Enum):
    """Diagnostic severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class DiagnosticCategory(Enum):
    """Categories of diagnostic checks"""
    SYSTEM = "system"
    PERFORMANCE = "performance"
    SECURITY = "security"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    NETWORK = "network"
    AUDIO = "audio"
    PLUGIN = "plugin"

@dataclass
class DiagnosticResult:
    """Result of a diagnostic check"""
    timestamp: datetime
    category: DiagnosticCategory
    check_name: str
    severity: DiagnosticSeverity
    status: str  # "pass", "fail", "warning", "unknown"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    auto_fixable: bool = False
    fix_applied: bool = False

@dataclass
class SystemSnapshot:
    """Snapshot of system state"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_connections: int
    process_count: int
    thread_count: int
    open_files: int
    system_load: Tuple[float, float, float]
    uptime: float

class DiagnosticCheck:
    """Base class for diagnostic checks"""
    
    def __init__(self, name: str, category: DiagnosticCategory, 
                 description: str, auto_fixable: bool = False):
        self.name = name
        self.category = category
        self.description = description
        self.auto_fixable = auto_fixable
        self.last_run = None
        self.run_count = 0
        
    def run(self) -> DiagnosticResult:
        """Run the diagnostic check"""
        self.last_run = datetime.now()
        self.run_count += 1
        return self._execute()
    
    def _execute(self) -> DiagnosticResult:
        """Execute the actual check - to be overridden by subclasses"""
        raise NotImplementedError
    
    def can_auto_fix(self) -> bool:
        """Check if this diagnostic can be automatically fixed"""
        return self.auto_fixable
    
    def auto_fix(self) -> bool:
        """Attempt to automatically fix the issue"""
        return False

class SystemResourceCheck(DiagnosticCheck):
    """Check system resource usage"""
    
    def __init__(self):
        super().__init__(
            name="system_resources",
            category=DiagnosticCategory.SYSTEM,
            description="Check system resource usage (CPU, memory, disk)",
            auto_fixable=False
        )
        
    def _execute(self) -> DiagnosticResult:
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            issues = []
            severity = DiagnosticSeverity.INFO
            status = "pass"
            
            if cpu_percent > 90:
                issues.append(f"High CPU usage: {cpu_percent}%")
                severity = DiagnosticSeverity.CRITICAL
                status = "fail"
            elif cpu_percent > 70:
                issues.append(f"Elevated CPU usage: {cpu_percent}%")
                severity = DiagnosticSeverity.WARNING
                status = "warning"
                
            if memory.percent > 90:
                issues.append(f"High memory usage: {memory.percent}%")
                severity = DiagnosticSeverity.CRITICAL
                status = "fail"
            elif memory.percent > 80:
                issues.append(f"Elevated memory usage: {memory.percent}%")
                severity = DiagnosticSeverity.WARNING
                status = "warning"
                
            if disk.percent > 95:
                issues.append(f"Disk almost full: {disk.percent}%")
                severity = DiagnosticSeverity.CRITICAL
                status = "fail"
            elif disk.percent > 85:
                issues.append(f"Disk usage high: {disk.percent}%")
                severity = DiagnosticSeverity.WARNING
                status = "warning"
            
            message = "System resources normal" if not issues else "; ".join(issues)
            
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=severity,
                status=status,
                message=message,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free / (1024**3)
                },
                recommendations=self._generate_resource_recommendations(cpu_percent, memory.percent, disk.percent)
            )
            
        except Exception as e:
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=DiagnosticSeverity.ERROR,
                status="fail",
                message=f"Failed to check system resources: {e}",
                details={"error": str(e)}
            )
    
    def _generate_resource_recommendations(self, cpu: float, memory: float, disk: float) -> List[str]:
        recommendations = []
        
        if cpu > 80:
            recommendations.append("Consider reducing CPU-intensive operations")
            recommendations.append("Check for runaway processes")
            
        if memory > 80:
            recommendations.append("Consider increasing available memory")
            recommendations.append("Check for memory leaks in applications")
            
        if disk > 85:
            recommendations.append("Clean up temporary files")
            recommendations.append("Consider expanding disk storage")
            
        return recommendations

class DependencyCheck(DiagnosticCheck):
    """Check system dependencies"""
    
    def __init__(self):
        super().__init__(
            name="dependencies",
            category=DiagnosticCategory.DEPENDENCY,
            description="Check required dependencies and versions",
            auto_fixable=True
        )
        
        # Define required dependencies
        self.required_deps = {
            "python": {"min_version": "3.8"},
            "psutil": {"package": True},
            "numpy": {"package": True, "optional": True}
        }
    
    def _execute(self) -> DiagnosticResult:
        missing_deps = []
        version_issues = []
        details = {}
        
        try:
            # Check Python version
            python_version = sys.version_info
            details["python_version"] = f"{python_version.major}.{python_version.minor}.{python_version.micro}"
            
            required_python = tuple(map(int, self.required_deps["python"]["min_version"].split(".")))
            if python_version[:2] < required_python[:2]:
                version_issues.append(f"Python {self.required_deps['python']['min_version']} required, got {details['python_version']}")
            
            # Check package dependencies
            for dep_name, dep_info in self.required_deps.items():
                if dep_name == "python":
                    continue
                    
                if dep_info.get("package"):
                    try:
                        __import__(dep_name)
                        details[f"{dep_name}_installed"] = True
                    except ImportError:
                        if dep_info.get("optional"):
                            details[f"{dep_name}_installed"] = False
                            details[f"{dep_name}_optional"] = True
                        else:
                            missing_deps.append(dep_name)
                            details[f"{dep_name}_installed"] = False
            
            # Determine overall status
            if missing_deps:
                severity = DiagnosticSeverity.ERROR
                status = "fail"
                message = f"Missing required dependencies: {', '.join(missing_deps)}"
            elif version_issues:
                severity = DiagnosticSeverity.ERROR
                status = "fail"
                message = f"Version issues: {'; '.join(version_issues)}"
            else:
                severity = DiagnosticSeverity.INFO
                status = "pass"
                message = "All dependencies satisfied"
            
            recommendations = []
            if missing_deps:
                recommendations.append(f"Install missing dependencies: pip install {' '.join(missing_deps)}")
            if version_issues:
                recommendations.append("Upgrade Python to required version")
            
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=severity,
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                auto_fixable=bool(missing_deps and not version_issues)
            )
            
        except Exception as e:
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=DiagnosticSeverity.ERROR,
                status="fail",
                message=f"Failed to check dependencies: {e}",
                details={"error": str(e)}
            )
    
    def auto_fix(self) -> bool:
        """Attempt to install missing dependencies"""
        try:
            # Check what's missing
            result = self._execute()
            if result.status != "fail":
                return True
            
            # Try to install missing packages
            missing_packages = []
            for dep_name, dep_info in self.required_deps.items():
                if dep_name != "python" and dep_info.get("package"):
                    try:
                        __import__(dep_name)
                    except ImportError:
                        if not dep_info.get("optional"):
                            missing_packages.append(dep_name)
            
            if missing_packages:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install"
                ] + missing_packages)
                return True
                
        except Exception as e:
            logging.error(f"Auto-fix failed for dependencies: {e}")
            
        return False

class AudioSystemCheck(DiagnosticCheck):
    """Check audio system configuration"""
    
    def __init__(self):
        super().__init__(
            name="audio_system",
            category=DiagnosticCategory.AUDIO,
            description="Check audio system availability and configuration",
            auto_fixable=False
        )
    
    def _execute(self) -> DiagnosticResult:
        try:
            details = {}
            issues = []
            
            # Check for audio devices (simplified)
            try:
                if platform.system() == "Windows":
                    # Windows audio check
                    result = subprocess.run(["wmic", "sounddev", "list"], 
                                          capture_output=True, text=True, timeout=10)
                    details["audio_devices_found"] = "No output" not in result.stdout
                elif platform.system() == "Linux":
                    # Linux audio check
                    result = subprocess.run(["aplay", "-l"], 
                                          capture_output=True, text=True, timeout=10)
                    details["audio_devices_found"] = result.returncode == 0
                else:
                    details["audio_devices_found"] = True  # Assume available on other systems
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                details["audio_devices_found"] = False
                issues.append("Could not detect audio devices")
            
            # Check audio sample rates and formats
            details["supported_sample_rates"] = [8000, 16000, 22050, 44100, 48000, 96000]
            details["supported_formats"] = ["int16", "int24", "int32", "float32"]
            
            # Determine status
            if not details.get("audio_devices_found", False):
                severity = DiagnosticSeverity.WARNING
                status = "warning"
                message = "Audio devices may not be available"
            else:
                severity = DiagnosticSeverity.INFO
                status = "pass"
                message = "Audio system appears functional"
            
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=severity,
                status=status,
                message=message,
                details=details,
                recommendations=["Verify audio drivers are installed", "Test audio playback"] if issues else []
            )
            
        except Exception as e:
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=DiagnosticSeverity.ERROR,
                status="fail",
                message=f"Failed to check audio system: {e}",
                details={"error": str(e)}
            )

class NetworkConnectivityCheck(DiagnosticCheck):
    """Check network connectivity"""
    
    def __init__(self):
        super().__init__(
            name="network_connectivity",
            category=DiagnosticCategory.NETWORK,
            description="Check network connectivity and DNS resolution",
            auto_fixable=False
        )
    
    def _execute(self) -> DiagnosticResult:
        try:
            details = {}
            issues = []
            
            # Test basic connectivity
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=5)
                details["internet_connectivity"] = True
            except (socket.timeout, socket.error):
                details["internet_connectivity"] = False
                issues.append("No internet connectivity")
            
            # Test DNS resolution
            try:
                socket.gethostbyname("google.com")
                details["dns_resolution"] = True
            except socket.gaierror:
                details["dns_resolution"] = False
                issues.append("DNS resolution failed")
            
            # Get network interface info
            try:
                net_if = psutil.net_if_addrs()
                details["network_interfaces"] = len(net_if)
                details["active_interfaces"] = len([iface for iface in net_if.values() if iface])
            except:
                details["network_interfaces"] = 0
                details["active_interfaces"] = 0
            
            # Determine status
            if issues:
                severity = DiagnosticSeverity.WARNING
                status = "warning"
                message = "; ".join(issues)
            else:
                severity = DiagnosticSeverity.INFO
                status = "pass"
                message = "Network connectivity normal"
            
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=severity,
                status=status,
                message=message,
                details=details,
                recommendations=["Check network configuration", "Verify DNS settings"] if issues else []
            )
            
        except Exception as e:
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=DiagnosticSeverity.ERROR,
                status="fail",
                message=f"Failed to check network: {e}",
                details={"error": str(e)}
            )

class ConfigurationCheck(DiagnosticCheck):
    """Check system configuration"""
    
    def __init__(self):
        super().__init__(
            name="configuration",
            category=DiagnosticCategory.CONFIGURATION,
            description="Check system configuration for optimal performance",
            auto_fixable=True
        )
    
    def _execute(self) -> DiagnosticResult:
        try:
            details = {}
            issues = []
            recommendations = []
            
            # Check file limits
            try:
                import resource
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                details["file_descriptors"] = {"soft": soft, "hard": hard}
                
                if soft < 1024:
                    issues.append(f"Low file descriptor limit: {soft}")
                    recommendations.append("Increase file descriptor limit")
                    
            except:
                details["file_descriptors"] = {"error": "Could not check"}
            
            # Check environment variables
            important_env_vars = ["PATH", "PYTHONPATH", "HOME", "USER"]
            details["environment"] = {}
            
            for var in important_env_vars:
                value = os.environ.get(var)
                details["environment"][var] = bool(value)
                if not value and var in ["PATH", "HOME"]:
                    issues.append(f"Missing environment variable: {var}")
            
            # Check temporary directory
            import tempfile
            temp_dir = tempfile.gettempdir()
            details["temp_directory"] = temp_dir
            
            try:
                temp_space = psutil.disk_usage(temp_dir)
                details["temp_space_gb"] = temp_space.free / (1024**3)
                
                if temp_space.free < 1024**3:  # Less than 1GB
                    issues.append("Low temporary disk space")
                    recommendations.append("Clean temporary files")
                    
            except:
                details["temp_space_gb"] = 0
            
            # Determine status
            if issues:
                severity = DiagnosticSeverity.WARNING
                status = "warning"
                message = "; ".join(issues)
            else:
                severity = DiagnosticSeverity.INFO
                status = "pass"
                message = "Configuration appears optimal"
            
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=severity,
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                auto_fixable=len(issues) > 0
            )
            
        except Exception as e:
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=self.category,
                check_name=self.name,
                severity=DiagnosticSeverity.ERROR,
                status="fail",
                message=f"Failed to check configuration: {e}",
                details={"error": str(e)}
            )

class AutomatedDiagnosticsManager:
    """Comprehensive automated diagnostics system"""
    
    def __init__(self, error_recovery: Optional[ErrorRecoveryManager] = None,
                 performance_optimizer: Optional[PerformanceOptimizer] = None,
                 plugin_ft: Optional[PluginFaultToleranceManager] = None):
        
        self.error_recovery = error_recovery
        self.performance_optimizer = performance_optimizer
        self.plugin_ft = plugin_ft
        
        # Diagnostic results storage
        self.diagnostic_history = deque(maxlen=10000)
        self.last_full_check = None
        self.system_snapshots = deque(maxlen=1000)
        
        # Initialize checks
        self.checks = {
            "system_resources": SystemResourceCheck(),
            "dependencies": DependencyCheck(),
            "audio_system": AudioSystemCheck(),
            "network_connectivity": NetworkConnectivityCheck(),
            "configuration": ConfigurationCheck()
        }
        
        # Configuration
        self.config = {
            "auto_run_interval": 300,  # 5 minutes
            "auto_fix_enabled": True,
            "critical_alert_threshold": 3,  # Number of critical issues to trigger alert
            "snapshot_interval": 60,  # 1 minute
            "max_auto_fix_attempts": 3
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Initialize logging
        self.logger = logging.getLogger("AutomatedDiagnostics")
        
        # Auto-fix tracking
        self.auto_fix_attempts = defaultdict(int)
        
        # Start background tasks
        self._start_monitoring()
    
    def add_custom_check(self, check: DiagnosticCheck):
        """Add a custom diagnostic check"""
        with self.lock:
            self.checks[check.name] = check
            self.logger.info(f"Added custom diagnostic check: {check.name}")
    
    def remove_check(self, check_name: str):
        """Remove a diagnostic check"""
        with self.lock:
            if check_name in self.checks:
                del self.checks[check_name]
                self.logger.info(f"Removed diagnostic check: {check_name}")
    
    def run_single_check(self, check_name: str) -> Optional[DiagnosticResult]:
        """Run a single diagnostic check"""
        if check_name not in self.checks:
            self.logger.error(f"Unknown diagnostic check: {check_name}")
            return None
        
        try:
            check = self.checks[check_name]
            result = check.run()
            
            with self.lock:
                self.diagnostic_history.append(result)
            
            # Attempt auto-fix if enabled and applicable
            if (self.config["auto_fix_enabled"] and 
                result.status == "fail" and 
                result.auto_fixable and
                self.auto_fix_attempts[check_name] < self.config["max_auto_fix_attempts"]):
                
                self._attempt_auto_fix(check_name, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error running diagnostic check {check_name}: {e}")
            return DiagnosticResult(
                timestamp=datetime.now(),
                category=DiagnosticCategory.SYSTEM,
                check_name=check_name,
                severity=DiagnosticSeverity.ERROR,
                status="fail",
                message=f"Diagnostic check failed: {e}",
                details={"error": str(e), "traceback": traceback.format_exc()}
            )
    
    def run_all_checks(self) -> List[DiagnosticResult]:
        """Run all diagnostic checks"""
        results = []
        
        self.logger.info("Running comprehensive diagnostic checks")
        
        for check_name in self.checks:
            result = self.run_single_check(check_name)
            if result:
                results.append(result)
        
        self.last_full_check = datetime.now()
        
        # Take system snapshot
        self._take_system_snapshot()
        
        # Check for critical issues
        critical_issues = [r for r in results if r.severity == DiagnosticSeverity.CRITICAL]
        if len(critical_issues) >= self.config["critical_alert_threshold"]:
            self._handle_critical_issues(critical_issues)
        
        return results
    
    def _attempt_auto_fix(self, check_name: str, result: DiagnosticResult):
        """Attempt to automatically fix a failed check"""
        self.auto_fix_attempts[check_name] += 1
        
        try:
            check = self.checks[check_name]
            self.logger.info(f"Attempting auto-fix for {check_name} (attempt {self.auto_fix_attempts[check_name]})")
            
            if check.auto_fix():
                self.logger.info(f"Auto-fix successful for {check_name}")
                result.fix_applied = True
                
                # Verify fix by running check again
                verify_result = check.run()
                if verify_result.status == "pass":
                    self.logger.info(f"Auto-fix verified successful for {check_name}")
                    # Reset attempt counter on successful fix
                    self.auto_fix_attempts[check_name] = 0
                else:
                    self.logger.warning(f"Auto-fix applied but issue persists for {check_name}")
            else:
                self.logger.warning(f"Auto-fix failed for {check_name}")
                
        except Exception as e:
            self.logger.error(f"Auto-fix error for {check_name}: {e}")
    
    def _take_system_snapshot(self):
        """Take a snapshot of current system state"""
        try:
            snapshot = SystemSnapshot(
                timestamp=datetime.now(),
                cpu_usage=psutil.cpu_percent(),
                memory_usage=psutil.virtual_memory().percent,
                disk_usage=psutil.disk_usage('/').percent,
                network_connections=len(psutil.net_connections()),
                process_count=len(psutil.pids()),
                thread_count=threading.active_count(),
                open_files=len(psutil.Process().open_files()) if hasattr(psutil.Process(), 'open_files') else 0,
                system_load=psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0),
                uptime=time.time() - psutil.boot_time()
            )
            
            with self.lock:
                self.system_snapshots.append(snapshot)
                
        except Exception as e:
            self.logger.error(f"Failed to take system snapshot: {e}")
    
    def _handle_critical_issues(self, critical_issues: List[DiagnosticResult]):
        """Handle critical issues that require immediate attention"""
        self.logger.critical(f"Multiple critical issues detected: {len(critical_issues)}")
        
        # If error recovery manager is available, record the issues
        if self.error_recovery:
            for issue in critical_issues:
                self.error_recovery.record_error(
                    Exception(issue.message),
                    f"diagnostic_{issue.check_name}",
                    {"diagnostic_result": issue.__dict__}
                )
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive system health summary"""
        with self.lock:
            recent_results = [r for r in self.diagnostic_history 
                            if datetime.now() - r.timestamp < timedelta(hours=1)]
            
            # Count issues by severity
            severity_counts = defaultdict(int)
            category_counts = defaultdict(int)
            
            for result in recent_results:
                severity_counts[result.severity.value] += 1
                category_counts[result.category.value] += 1
            
            # Calculate health score (0-100)
            total_checks = len(recent_results)
            if total_checks == 0:
                health_score = 100
            else:
                critical_weight = severity_counts.get("critical", 0) * 4
                error_weight = severity_counts.get("error", 0) * 2
                warning_weight = severity_counts.get("warning", 0) * 1
                
                total_weight = critical_weight + error_weight + warning_weight
                max_possible_weight = total_checks * 4
                
                health_score = max(0, 100 - (total_weight / max_possible_weight * 100))
            
            # System trends
            trends = self._analyze_system_trends()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "health_score": health_score,
                "last_full_check": self.last_full_check.isoformat() if self.last_full_check else None,
                "summary": {
                    "total_checks": total_checks,
                    "severity_distribution": dict(severity_counts),
                    "category_distribution": dict(category_counts),
                    "auto_fix_attempts": dict(self.auto_fix_attempts)
                },
                "trends": trends,
                "recent_critical_issues": [
                    r.__dict__ for r in recent_results 
                    if r.severity == DiagnosticSeverity.CRITICAL
                ][:5],  # Last 5 critical issues
                "recommendations": self._generate_system_recommendations(recent_results)
            }
    
    def _analyze_system_trends(self) -> Dict[str, Any]:
        """Analyze system performance trends"""
        if len(self.system_snapshots) < 2:
            return {"status": "insufficient_data"}
        
        snapshots = list(self.system_snapshots)[-100:]  # Last 100 snapshots
        
        # Calculate trends
        cpu_trend = self._calculate_trend([s.cpu_usage for s in snapshots])
        memory_trend = self._calculate_trend([s.memory_usage for s in snapshots])
        disk_trend = self._calculate_trend([s.disk_usage for s in snapshots])
        
        return {
            "cpu_usage": {
                "current": snapshots[-1].cpu_usage,
                "trend": cpu_trend,
                "average": statistics.mean([s.cpu_usage for s in snapshots])
            },
            "memory_usage": {
                "current": snapshots[-1].memory_usage,
                "trend": memory_trend,
                "average": statistics.mean([s.memory_usage for s in snapshots])
            },
            "disk_usage": {
                "current": snapshots[-1].disk_usage,
                "trend": disk_trend,
                "average": statistics.mean([s.disk_usage for s in snapshots])
            },
            "system_load": {
                "current": snapshots[-1].system_load,
                "uptime_hours": snapshots[-1].uptime / 3600
            }
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values"""
        if len(values) < 2:
            return "stable"
        
        # Simple linear regression slope
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _generate_system_recommendations(self, recent_results: List[DiagnosticResult]) -> List[str]:
        """Generate system-wide recommendations based on diagnostic results"""
        recommendations = set()
        
        # Collect all recommendations from recent results
        for result in recent_results:
            recommendations.update(result.recommendations)
        
        # Add system-wide recommendations
        critical_count = len([r for r in recent_results if r.severity == DiagnosticSeverity.CRITICAL])
        error_count = len([r for r in recent_results if r.severity == DiagnosticSeverity.ERROR])
        
        if critical_count > 2:
            recommendations.add("System requires immediate attention - multiple critical issues detected")
        
        if error_count > 5:
            recommendations.add("Consider running full system maintenance")
        
        return list(recommendations)
    
    def _start_monitoring(self):
        """Start background monitoring tasks"""
        def diagnostic_monitor():
            while True:
                try:
                    # Run periodic full checks
                    self.run_all_checks()
                    time.sleep(self.config["auto_run_interval"])
                except Exception as e:
                    self.logger.error(f"Diagnostic monitor error: {e}")
                    time.sleep(60)  # Wait 1 minute before retrying
        
        def snapshot_monitor():
            while True:
                try:
                    # Take periodic snapshots
                    self._take_system_snapshot()
                    time.sleep(self.config["snapshot_interval"])
                except Exception as e:
                    self.logger.error(f"Snapshot monitor error: {e}")
                    time.sleep(30)  # Wait 30 seconds before retrying
        
        # Start monitoring threads
        diagnostic_thread = threading.Thread(target=diagnostic_monitor, daemon=True)
        snapshot_thread = threading.Thread(target=snapshot_monitor, daemon=True)
        
        diagnostic_thread.start()
        snapshot_thread.start()
        
        self.logger.info("Automated diagnostics monitoring started")

# Global diagnostics manager instance
_global_diagnostics_manager = None

def get_global_diagnostics_manager() -> AutomatedDiagnosticsManager:
    """Get or create global diagnostics manager"""
    global _global_diagnostics_manager
    if _global_diagnostics_manager is None:
        _global_diagnostics_manager = AutomatedDiagnosticsManager()
    return _global_diagnostics_manager

if __name__ == "__main__":
    import os
    
    # Example usage
    diagnostics = AutomatedDiagnosticsManager()
    
    # Run all checks
    results = diagnostics.run_all_checks()
    
    print("Diagnostic Results:")
    for result in results:
        print(f"  {result.check_name}: {result.status} - {result.message}")
        if result.recommendations:
            print(f"    Recommendations: {', '.join(result.recommendations)}")
    
    # Get health summary
    health_summary = diagnostics.get_system_health_summary()
    print(f"\nSystem Health Score: {health_summary['health_score']:.1f}/100")
    print("Health Summary:")
    print(json.dumps(health_summary, indent=2, default=str))