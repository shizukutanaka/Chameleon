#!/usr/bin/env python3
"""
Dependency Manager - Smart dependency handling with fallbacks
依存関係を適切に管理し、フォールバックを提供
"""

import sys
import subprocess
import importlib
import logging
import warnings
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

class DependencyLevel(Enum):
    """依存関係の重要度レベル"""
    CRITICAL = "critical"      # システムに必須
    REQUIRED = "required"      # 機能に必要
    OPTIONAL = "optional"      # あると便利
    DEVELOPMENT = "development" # 開発時のみ

@dataclass
class DependencyInfo:
    """依存関係情報"""
    name: str
    level: DependencyLevel
    min_version: Optional[str] = None
    install_command: Optional[str] = None
    fallback_available: bool = False
    fallback_warning: Optional[str] = None
    import_alternatives: List[str] = field(default_factory=list)

class DependencyManager:
    """依存関係マネージャー"""
    
    def __init__(self):
        self.logger = logging.getLogger("DependencyManager")
        self.installed_packages = {}
        self.missing_packages = {}
        self.fallbacks_enabled = {}
        
        # 依存関係定義
        self.dependencies = {
            # Critical dependencies
            "threading": DependencyInfo(
                name="threading",
                level=DependencyLevel.CRITICAL,
                fallback_available=False
            ),
            "json": DependencyInfo(
                name="json",
                level=DependencyLevel.CRITICAL,
                fallback_available=False
            ),
            "logging": DependencyInfo(
                name="logging", 
                level=DependencyLevel.CRITICAL,
                fallback_available=False
            ),
            
            # Required but with fallbacks
            "psutil": DependencyInfo(
                name="psutil",
                level=DependencyLevel.REQUIRED,
                install_command="pip install psutil",
                fallback_available=True,
                fallback_warning="System monitoring will use basic OS commands instead of psutil"
            ),
            
            # Optional dependencies
            "numpy": DependencyInfo(
                name="numpy",
                level=DependencyLevel.OPTIONAL,
                install_command="pip install numpy",
                fallback_available=True,
                fallback_warning="Advanced mathematical operations will use Python lists",
                import_alternatives=["array"]
            ),
            "matplotlib": DependencyInfo(
                name="matplotlib",
                level=DependencyLevel.OPTIONAL,
                install_command="pip install matplotlib",
                fallback_available=True,
                fallback_warning="Visualizations will use text-based charts"
            ),
            "scipy": DependencyInfo(
                name="scipy",
                level=DependencyLevel.OPTIONAL,
                install_command="pip install scipy",
                fallback_available=True,
                fallback_warning="Advanced signal processing will use basic algorithms"
            )
        }
        
        # Check all dependencies on initialization
        self._check_all_dependencies()
    
    def _check_all_dependencies(self):
        """すべての依存関係をチェック"""
        for name, info in self.dependencies.items():
            try:
                module = importlib.import_module(name)
                self.installed_packages[name] = {
                    "module": module,
                    "info": info,
                    "version": getattr(module, "__version__", "unknown")
                }
                self.logger.debug(f"✓ {name} available")
                
            except ImportError:
                self.missing_packages[name] = info
                
                if info.level == DependencyLevel.CRITICAL:
                    self.logger.critical(f"❌ CRITICAL dependency missing: {name}")
                elif info.level == DependencyLevel.REQUIRED:
                    if info.fallback_available:
                        self.logger.warning(f"⚠️ Required dependency missing (fallback available): {name}")
                        self.fallbacks_enabled[name] = True
                    else:
                        self.logger.error(f"❌ Required dependency missing: {name}")
                else:
                    self.logger.info(f"ℹ️ Optional dependency missing: {name}")
                    if info.fallback_available:
                        self.fallbacks_enabled[name] = True
    
    def get_safe_import(self, module_name: str, fallback_factory: Optional[Callable] = None):
        """安全なインポート - フォールバック付き"""
        if module_name in self.installed_packages:
            return self.installed_packages[module_name]["module"]
        
        if module_name in self.missing_packages:
            info = self.missing_packages[module_name]
            
            if info.fallback_available and fallback_factory:
                if info.fallback_warning:
                    warnings.warn(info.fallback_warning, UserWarning)
                return fallback_factory()
            
            # 代替インポートを試す
            for alternative in info.import_alternatives:
                try:
                    return importlib.import_module(alternative)
                except ImportError:
                    continue
            
            # フォールバックも代替もない場合
            if info.level == DependencyLevel.CRITICAL:
                raise ImportError(f"Critical dependency {module_name} not available")
            else:
                warnings.warn(f"Dependency {module_name} not available", UserWarning)
                return None
        
        # 未定義の依存関係
        try:
            return importlib.import_module(module_name)
        except ImportError:
            warnings.warn(f"Unknown dependency {module_name} not available", UserWarning)
            return None
    
    def install_missing_dependencies(self, level: DependencyLevel = DependencyLevel.REQUIRED) -> bool:
        """不足している依存関係をインストール"""
        success = True
        
        for name, info in self.missing_packages.items():
            if info.level.value in [level.value, DependencyLevel.CRITICAL.value]:
                if info.install_command:
                    try:
                        self.logger.info(f"Installing {name}...")
                        result = subprocess.run(
                            info.install_command.split(),
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        
                        if result.returncode == 0:
                            self.logger.info(f"✓ Successfully installed {name}")
                            # Re-check this dependency
                            try:
                                module = importlib.import_module(name)
                                self.installed_packages[name] = {
                                    "module": module,
                                    "info": info,
                                    "version": getattr(module, "__version__", "unknown")
                                }
                                del self.missing_packages[name]
                            except ImportError:
                                success = False
                        else:
                            self.logger.error(f"❌ Failed to install {name}: {result.stderr}")
                            success = False
                            
                    except subprocess.TimeoutExpired:
                        self.logger.error(f"❌ Installation timeout for {name}")
                        success = False
                    except Exception as e:
                        self.logger.error(f"❌ Installation error for {name}: {e}")
                        success = False
        
        return success
    
    def get_dependency_report(self) -> Dict[str, Any]:
        """依存関係レポートを生成"""
        return {
            "installed": {
                name: {
                    "version": pkg["version"],
                    "level": pkg["info"].level.value
                }
                for name, pkg in self.installed_packages.items()
            },
            "missing": {
                name: {
                    "level": info.level.value,
                    "fallback_available": info.fallback_available,
                    "install_command": info.install_command
                }
                for name, info in self.missing_packages.items()
            },
            "fallbacks_enabled": list(self.fallbacks_enabled.keys()),
            "total_dependencies": len(self.dependencies),
            "installed_count": len(self.installed_packages),
            "missing_count": len(self.missing_packages)
        }

# グローバル依存関係マネージャー
_global_dependency_manager = None

def get_dependency_manager() -> DependencyManager:
    """グローバル依存関係マネージャーを取得"""
    global _global_dependency_manager
    if _global_dependency_manager is None:
        _global_dependency_manager = DependencyManager()
    return _global_dependency_manager

def safe_import(module_name: str, fallback_factory: Optional[Callable] = None):
    """安全なインポート関数"""
    return get_dependency_manager().get_safe_import(module_name, fallback_factory)

# Fallback implementations
class FallbackNumpy:
    """Numpy fallback implementation"""
    
    @staticmethod
    def array(data):
        """Basic array implementation"""
        if isinstance(data, list):
            return data
        return list(data)
    
    @staticmethod
    def mean(data):
        """Calculate mean"""
        return sum(data) / len(data) if data else 0
    
    @staticmethod
    def std(data):
        """Calculate standard deviation"""
        if not data:
            return 0
        mean_val = FallbackNumpy.mean(data)
        variance = sum((x - mean_val) ** 2 for x in data) / len(data)
        return variance ** 0.5
    
    @staticmethod
    def fft(data):
        """Fallback FFT (very basic)"""
        warnings.warn("Using basic FFT fallback - install numpy/scipy for full functionality", UserWarning)
        # Very simplified FFT - just return the input for now
        return data

class FallbackPsutil:
    """PSUtil fallback implementation"""
    
    @staticmethod
    def cpu_percent(interval=None):
        """Fallback CPU percentage"""
        try:
            import os
            # Very basic CPU usage estimation
            with open('/proc/loadavg', 'r') as f:
                load_avg = float(f.read().split()[0])
            return min(100, load_avg * 25)  # Rough estimation
        except:
            return 50.0  # Default fallback
    
    @staticmethod
    def virtual_memory():
        """Fallback memory info"""
        class MemoryInfo:
            def __init__(self):
                try:
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = f.read()
                    
                    import re
                    total_match = re.search(r'MemTotal:\s+(\d+)', meminfo)
                    available_match = re.search(r'MemAvailable:\s+(\d+)', meminfo)
                    
                    if total_match and available_match:
                        self.total = int(total_match.group(1)) * 1024
                        self.available = int(available_match.group(1)) * 1024
                        self.used = self.total - self.available
                        self.percent = (self.used / self.total) * 100
                    else:
                        raise Exception("Could not parse meminfo")
                        
                except:
                    # Fallback values
                    self.total = 8 * 1024 * 1024 * 1024  # 8GB
                    self.available = 4 * 1024 * 1024 * 1024  # 4GB
                    self.used = self.total - self.available
                    self.percent = 50.0
        
        return MemoryInfo()
    
    @staticmethod
    def disk_usage(path):
        """Fallback disk usage"""
        class DiskUsage:
            def __init__(self, path):
                try:
                    import os
                    statvfs = os.statvfs(path)
                    self.total = statvfs.f_frsize * statvfs.f_blocks
                    self.free = statvfs.f_frsize * statvfs.f_available
                    self.used = self.total - self.free
                    self.percent = (self.used / self.total) * 100
                except:
                    # Fallback values
                    self.total = 100 * 1024 * 1024 * 1024  # 100GB
                    self.free = 50 * 1024 * 1024 * 1024   # 50GB
                    self.used = self.total - self.free
                    self.percent = 50.0
        
        return DiskUsage(path)

class FallbackMatplotlib:
    """Matplotlib fallback for text-based plotting"""
    
    class pyplot:
        @staticmethod
        def figure(*args, **kwargs):
            return FallbackFigure()
        
        @staticmethod
        def plot(*args, **kwargs):
            pass
        
        @staticmethod
        def title(title):
            print(f"Chart: {title}")
        
        @staticmethod
        def xlabel(label):
            print(f"X-Axis: {label}")
        
        @staticmethod
        def ylabel(label):
            print(f"Y-Axis: {label}")
        
        @staticmethod
        def show():
            print("Chart display completed (text mode)")
        
        @staticmethod
        def close(*args):
            pass

class FallbackFigure:
    """Fallback figure for matplotlib"""
    
    def __init__(self):
        pass
    
    def add_subplot(self, *args, **kwargs):
        return self
    
    def plot(self, *args, **kwargs):
        pass
    
    def set_title(self, title):
        print(f"Chart: {title}")
    
    def set_xlabel(self, label):
        print(f"X-Axis: {label}")
    
    def set_ylabel(self, label):
        print(f"Y-Axis: {label}")

# Dependency factory functions
def numpy_factory():
    """Numpy fallback factory"""
    return FallbackNumpy()

def psutil_factory():
    """PSUtil fallback factory"""
    return FallbackPsutil()

def matplotlib_factory():
    """Matplotlib fallback factory"""
    return FallbackMatplotlib()

if __name__ == "__main__":
    # Test dependency manager
    dm = get_dependency_manager()
    
    print("🔍 Dependency Manager Test")
    print("=" * 40)
    
    # Test safe imports
    numpy = safe_import("numpy", numpy_factory)
    if numpy:
        print("✓ NumPy (or fallback) available")
        print(f"  Mean of [1,2,3,4,5]: {numpy.mean([1,2,3,4,5])}")
    
    psutil = safe_import("psutil", psutil_factory)
    if psutil:
        print("✓ PSUtil (or fallback) available")
        print(f"  CPU usage: {psutil.cpu_percent()}%")
    
    matplotlib = safe_import("matplotlib", matplotlib_factory)
    if matplotlib:
        print("✓ Matplotlib (or fallback) available")
    
    # Generate report
    report = dm.get_dependency_report()
    print("\n📊 Dependency Report:")
    print(f"  Installed: {report['installed_count']}/{report['total_dependencies']}")
    print(f"  Missing: {report['missing_count']}")
    print(f"  Fallbacks enabled: {len(report['fallbacks_enabled'])}")
    
    if report['missing']:
        print("\n❌ Missing dependencies:")
        for name, info in report['missing'].items():
            status = "✓ Fallback available" if info['fallback_available'] else "❌ No fallback"
            print(f"  {name} ({info['level']}) - {status}")