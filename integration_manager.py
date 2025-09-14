#!/usr/bin/env python3
"""
Integration Manager - システム統合管理
すべてのコンポーネントの統合、相互運用性、一貫性を保証
"""

import logging
import threading
import time
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import weakref
import inspect

# Import all major system components
try:
    from dependency_manager import get_dependency_manager, DependencyManager
    from robust_error_handler import get_error_handler, RobustErrorHandler
    from security_manager import get_security_manager, SecurityManager
    from performance_enhancer import get_performance_enhancer, PerformanceEnhancer
    from code_quality_manager import get_code_quality_manager, CodeQualityManager
    
    # Audio processing components
    from audio_processor import AudioProcessor
    from cloud_processor import get_global_cloud_processor, CloudProcessor
    
    # Monitoring and diagnostics
    from automated_diagnostics import get_global_diagnostics_manager
    from visualization_dashboard import get_global_visualization_dashboard
    
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Some components not available for integration: {e}")
    COMPONENTS_AVAILABLE = False

class IntegrationStatus(Enum):
    """統合ステータス"""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"

class ComponentType(Enum):
    """コンポーネントタイプ"""
    CORE = "core"
    PROCESSING = "processing"
    MONITORING = "monitoring"
    SECURITY = "security"
    UI = "ui"
    STORAGE = "storage"
    NETWORK = "network"

@dataclass
class ComponentInfo:
    """コンポーネント情報"""
    name: str
    component_type: ComponentType
    instance: Any
    status: IntegrationStatus = IntegrationStatus.NOT_INITIALIZED
    dependencies: Set[str] = field(default_factory=set)
    health_check: Optional[Callable] = None
    last_health_check: Optional[datetime] = None
    error_count: int = 0
    restart_count: int = 0

@dataclass
class SystemHealth:
    """システムヘルス情報"""
    overall_status: IntegrationStatus
    component_count: int
    healthy_components: int
    degraded_components: int
    failed_components: int
    last_check: datetime
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

class ComponentRegistry:
    """コンポーネントレジストリ"""
    
    def __init__(self):
        self.components: Dict[str, ComponentInfo] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger("ComponentRegistry")
    
    def register_component(self, info: ComponentInfo):
        """コンポーネント登録"""
        with self.lock:
            self.components[info.name] = info
            self.dependency_graph[info.name] = info.dependencies.copy()
            self.logger.info(f"Registered component: {info.name} ({info.component_type.value})")
    
    def unregister_component(self, name: str):
        """コンポーネント登録解除"""
        with self.lock:
            if name in self.components:
                del self.components[name]
                del self.dependency_graph[name]
                
                # 他のコンポーネントの依存関係からも削除
                for comp_deps in self.dependency_graph.values():
                    comp_deps.discard(name)
                
                self.logger.info(f"Unregistered component: {name}")
    
    def get_component(self, name: str) -> Optional[ComponentInfo]:
        """コンポーネント取得"""
        with self.lock:
            return self.components.get(name)
    
    def get_initialization_order(self) -> List[str]:
        """初期化順序を取得（トポロジカルソート）"""
        with self.lock:
            visited = set()
            temp_visited = set()
            order = []
            
            def visit(node: str):
                if node in temp_visited:
                    raise ValueError(f"Circular dependency detected involving {node}")
                if node in visited:
                    return
                
                temp_visited.add(node)
                
                for dependency in self.dependency_graph.get(node, set()):
                    if dependency in self.components:
                        visit(dependency)
                
                temp_visited.remove(node)
                visited.add(node)
                order.append(node)
            
            for component in self.components:
                if component not in visited:
                    visit(component)
            
            return order
    
    def get_components_by_type(self, component_type: ComponentType) -> List[ComponentInfo]:
        """タイプ別コンポーネント取得"""
        with self.lock:
            return [comp for comp in self.components.values() 
                   if comp.component_type == component_type]

class HealthMonitor:
    """ヘルスモニター"""
    
    def __init__(self, registry: ComponentRegistry):
        self.registry = registry
        self.logger = logging.getLogger("HealthMonitor")
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # 30秒間隔
        
    def start_monitoring(self):
        """ヘルスモニタリング開始"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Health monitoring started")
    
    def stop_monitoring(self):
        """ヘルスモニタリング停止"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Health monitoring stopped")
    
    def _monitor_loop(self):
        """モニタリングループ"""
        while self.monitoring:
            try:
                self.check_all_components()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                time.sleep(self.check_interval * 2)  # エラー時は間隔を倍に
    
    def check_all_components(self) -> SystemHealth:
        """全コンポーネントヘルスチェック"""
        with self.registry.lock:
            issues = []
            recommendations = []
            healthy_count = 0
            degraded_count = 0
            failed_count = 0
            
            for name, component in self.registry.components.items():
                try:
                    status = self.check_component_health(component)
                    component.status = status
                    component.last_health_check = datetime.now()
                    
                    if status == IntegrationStatus.HEALTHY:
                        healthy_count += 1
                    elif status == IntegrationStatus.DEGRADED:
                        degraded_count += 1
                        issues.append(f"Component {name} is degraded")
                    elif status == IntegrationStatus.FAILED:
                        failed_count += 1
                        issues.append(f"Component {name} has failed")
                        recommendations.append(f"Restart or reinitialize {name}")
                
                except Exception as e:
                    component.status = IntegrationStatus.FAILED
                    component.error_count += 1
                    failed_count += 1
                    issues.append(f"Health check failed for {name}: {e}")
                    self.logger.error(f"Health check error for {name}: {e}")
            
            # 全体ステータス決定
            total_components = len(self.registry.components)
            if failed_count > total_components * 0.5:
                overall_status = IntegrationStatus.FAILED
            elif degraded_count > 0 or failed_count > 0:
                overall_status = IntegrationStatus.DEGRADED
            else:
                overall_status = IntegrationStatus.HEALTHY
            
            return SystemHealth(
                overall_status=overall_status,
                component_count=total_components,
                healthy_components=healthy_count,
                degraded_components=degraded_count,
                failed_components=failed_count,
                last_check=datetime.now(),
                issues=issues,
                recommendations=recommendations
            )
    
    def check_component_health(self, component: ComponentInfo) -> IntegrationStatus:
        """個別コンポーネントヘルスチェック"""
        if component.health_check:
            try:
                result = component.health_check()
                return IntegrationStatus.HEALTHY if result else IntegrationStatus.DEGRADED
            except Exception as e:
                self.logger.error(f"Health check failed for {component.name}: {e}")
                return IntegrationStatus.FAILED
        
        # デフォルトヘルスチェック
        if hasattr(component.instance, 'get_status'):
            try:
                status = component.instance.get_status()
                return IntegrationStatus.HEALTHY if status else IntegrationStatus.DEGRADED
            except Exception:
                return IntegrationStatus.FAILED
        
        # インスタンスが生きているかチェック
        if component.instance is None:
            return IntegrationStatus.FAILED
        
        return IntegrationStatus.HEALTHY

class IntegrationManager:
    """統合管理システム"""
    
    def __init__(self):
        self.logger = logging.getLogger("IntegrationManager")
        self.registry = ComponentRegistry()
        self.health_monitor = HealthMonitor(self.registry)
        self.initialized = False
        self.startup_time = None
        self.config = {
            'auto_restart_failed_components': True,
            'max_restart_attempts': 3,
            'health_check_interval': 30,
            'dependency_timeout': 60
        }
        
        # システムイベント履歴
        self.events = deque(maxlen=1000)
        
    def initialize_system(self) -> bool:
        """システム全体初期化"""
        if self.initialized:
            self.logger.warning("System already initialized")
            return True
        
        self.logger.info("Starting system initialization...")
        self.startup_time = datetime.now()
        
        try:
            # コンポーネント自動発見と登録
            self._discover_and_register_components()
            
            # 初期化順序決定
            init_order = self.registry.get_initialization_order()
            self.logger.info(f"Initialization order: {init_order}")
            
            # コンポーネント初期化
            for component_name in init_order:
                success = self._initialize_component(component_name)
                if not success:
                    self.logger.error(f"Failed to initialize {component_name}")
                    return False
            
            # ヘルスモニタリング開始
            self.health_monitor.start_monitoring()
            
            # 初期ヘルスチェック
            health = self.health_monitor.check_all_components()
            
            self.initialized = True
            self.logger.info(f"System initialization completed. Status: {health.overall_status.value}")
            
            self._record_event("SYSTEM_INITIALIZED", {
                "startup_time": (datetime.now() - self.startup_time).total_seconds(),
                "component_count": health.component_count,
                "status": health.overall_status.value
            })
            
            return health.overall_status in [IntegrationStatus.HEALTHY, IntegrationStatus.DEGRADED]
            
        except Exception as e:
            self.logger.error(f"System initialization failed: {e}")
            self._record_event("SYSTEM_INIT_FAILED", {"error": str(e)})
            return False
    
    def _discover_and_register_components(self):
        """コンポーネント自動発見と登録"""
        if not COMPONENTS_AVAILABLE:
            self.logger.warning("Limited components available for integration")
            return
        
        # Core components
        try:
            dep_manager = get_dependency_manager()
            self.registry.register_component(ComponentInfo(
                name="dependency_manager",
                component_type=ComponentType.CORE,
                instance=dep_manager,
                health_check=lambda: True
            ))
        except Exception as e:
            self.logger.error(f"Failed to register dependency manager: {e}")
        
        try:
            error_handler = get_error_handler("system")
            self.registry.register_component(ComponentInfo(
                name="error_handler",
                component_type=ComponentType.CORE,
                instance=error_handler,
                health_check=lambda: True
            ))
        except Exception as e:
            self.logger.error(f"Failed to register error handler: {e}")
        
        # Security components
        try:
            security_manager = get_security_manager()
            self.registry.register_component(ComponentInfo(
                name="security_manager",
                component_type=ComponentType.SECURITY,
                instance=security_manager,
                dependencies={"error_handler"},
                health_check=lambda: security_manager.auth_manager is not None
            ))
        except Exception as e:
            self.logger.error(f"Failed to register security manager: {e}")
        
        # Performance components
        try:
            perf_enhancer = get_performance_enhancer()
            self.registry.register_component(ComponentInfo(
                name="performance_enhancer",
                component_type=ComponentType.MONITORING,
                instance=perf_enhancer,
                dependencies={"error_handler"},
                health_check=lambda: True
            ))
        except Exception as e:
            self.logger.error(f"Failed to register performance enhancer: {e}")
        
        # Quality components
        try:
            quality_manager = get_code_quality_manager()
            self.registry.register_component(ComponentInfo(
                name="code_quality_manager",
                component_type=ComponentType.MONITORING,
                instance=quality_manager,
                health_check=lambda: True
            ))
        except Exception as e:
            self.logger.error(f"Failed to register code quality manager: {e}")
        
        # Processing components
        try:
            cloud_processor = get_global_cloud_processor()
            self.registry.register_component(ComponentInfo(
                name="cloud_processor",
                component_type=ComponentType.PROCESSING,
                instance=cloud_processor,
                dependencies={"error_handler", "security_manager"},
                health_check=lambda: cloud_processor.get_system_status()["system_health"] != "critical"
            ))
        except Exception as e:
            self.logger.error(f"Failed to register cloud processor: {e}")
        
        # Audio processing
        try:
            audio_processor = AudioProcessor()
            self.registry.register_component(ComponentInfo(
                name="audio_processor",
                component_type=ComponentType.PROCESSING,
                instance=audio_processor,
                dependencies={"error_handler"},
                health_check=lambda: True
            ))
        except Exception as e:
            self.logger.error(f"Failed to register audio processor: {e}")
        
        # Monitoring components
        try:
            diagnostics_manager = get_global_diagnostics_manager()
            self.registry.register_component(ComponentInfo(
                name="diagnostics_manager",
                component_type=ComponentType.MONITORING,
                instance=diagnostics_manager,
                dependencies={"error_handler", "performance_enhancer"},
                health_check=lambda: True
            ))
        except Exception as e:
            self.logger.error(f"Failed to register diagnostics manager: {e}")
        
        # UI components
        try:
            dashboard = get_global_visualization_dashboard()
            self.registry.register_component(ComponentInfo(
                name="visualization_dashboard",
                component_type=ComponentType.UI,
                instance=dashboard,
                dependencies={"diagnostics_manager", "cloud_processor"},
                health_check=lambda: True
            ))
        except Exception as e:
            self.logger.error(f"Failed to register visualization dashboard: {e}")
    
    def _initialize_component(self, component_name: str) -> bool:
        """個別コンポーネント初期化"""
        component = self.registry.get_component(component_name)
        if not component:
            self.logger.error(f"Component not found: {component_name}")
            return False
        
        try:
            component.status = IntegrationStatus.INITIALIZING
            
            # 依存関係チェック
            for dep_name in component.dependencies:
                dep_component = self.registry.get_component(dep_name)
                if not dep_component or dep_component.status != IntegrationStatus.HEALTHY:
                    self.logger.error(f"Dependency {dep_name} not ready for {component_name}")
                    component.status = IntegrationStatus.FAILED
                    return False
            
            # 初期化実行
            if hasattr(component.instance, 'initialize'):
                component.instance.initialize()
            elif hasattr(component.instance, 'start'):
                component.instance.start()
            
            component.status = IntegrationStatus.HEALTHY
            self.logger.info(f"Component {component_name} initialized successfully")
            
            self._record_event("COMPONENT_INITIALIZED", {
                "component": component_name,
                "type": component.component_type.value
            })
            
            return True
            
        except Exception as e:
            component.status = IntegrationStatus.FAILED
            component.error_count += 1
            self.logger.error(f"Failed to initialize {component_name}: {e}")
            
            self._record_event("COMPONENT_INIT_FAILED", {
                "component": component_name,
                "error": str(e)
            })
            
            return False
    
    def restart_component(self, component_name: str) -> bool:
        """コンポーネント再起動"""
        component = self.registry.get_component(component_name)
        if not component:
            return False
        
        if component.restart_count >= self.config['max_restart_attempts']:
            self.logger.error(f"Max restart attempts exceeded for {component_name}")
            return False
        
        try:
            # 停止
            if hasattr(component.instance, 'stop'):
                component.instance.stop()
            elif hasattr(component.instance, 'shutdown'):
                component.instance.shutdown()
            
            # 再初期化
            success = self._initialize_component(component_name)
            if success:
                component.restart_count += 1
                self._record_event("COMPONENT_RESTARTED", {
                    "component": component_name,
                    "restart_count": component.restart_count
                })
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to restart {component_name}: {e}")
            return False
    
    def shutdown_system(self):
        """システム終了"""
        self.logger.info("Shutting down system...")
        
        # ヘルスモニタリング停止
        self.health_monitor.stop_monitoring()
        
        # 逆順でコンポーネント停止
        init_order = self.registry.get_initialization_order()
        for component_name in reversed(init_order):
            self._shutdown_component(component_name)
        
        self.initialized = False
        self._record_event("SYSTEM_SHUTDOWN", {
            "uptime": (datetime.now() - self.startup_time).total_seconds() if self.startup_time else 0
        })
        
        self.logger.info("System shutdown completed")
    
    def _shutdown_component(self, component_name: str):
        """個別コンポーネント停止"""
        component = self.registry.get_component(component_name)
        if not component:
            return
        
        try:
            if hasattr(component.instance, 'stop'):
                component.instance.stop()
            elif hasattr(component.instance, 'shutdown'):
                component.instance.shutdown()
            
            component.status = IntegrationStatus.NOT_INITIALIZED
            self.logger.info(f"Component {component_name} stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping {component_name}: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """システムステータス取得"""
        health = self.health_monitor.check_all_components()
        
        component_details = {}
        for name, component in self.registry.components.items():
            component_details[name] = {
                'type': component.component_type.value,
                'status': component.status.value,
                'error_count': component.error_count,
                'restart_count': component.restart_count,
                'last_health_check': component.last_health_check.isoformat() if component.last_health_check else None,
                'dependencies': list(component.dependencies)
            }
        
        return {
            'initialized': self.initialized,
            'startup_time': self.startup_time.isoformat() if self.startup_time else None,
            'uptime_seconds': (datetime.now() - self.startup_time).total_seconds() if self.startup_time else 0,
            'overall_health': health.__dict__,
            'components': component_details,
            'recent_events': list(self.events)[-10:]  # 最新10件
        }
    
    def get_integration_report(self) -> Dict[str, Any]:
        """統合レポート生成"""
        status = self.get_system_status()
        
        # 依存関係グラフ分析
        dependency_analysis = self._analyze_dependencies()
        
        # パフォーマンスメトリクス
        performance_metrics = self._collect_performance_metrics()
        
        return {
            'system_status': status,
            'dependency_analysis': dependency_analysis,
            'performance_metrics': performance_metrics,
            'recommendations': self._generate_integration_recommendations(status)
        }
    
    def _analyze_dependencies(self) -> Dict[str, Any]:
        """依存関係分析"""
        total_components = len(self.registry.components)
        circular_deps = []
        
        try:
            self.registry.get_initialization_order()
        except ValueError as e:
            if "Circular dependency" in str(e):
                circular_deps.append(str(e))
        
        return {
            'total_components': total_components,
            'circular_dependencies': circular_deps,
            'dependency_depth': self._calculate_dependency_depth()
        }
    
    def _calculate_dependency_depth(self) -> int:
        """依存関係の深さ計算"""
        max_depth = 0
        
        def get_depth(component_name: str, visited: Set[str] = None) -> int:
            if visited is None:
                visited = set()
            
            if component_name in visited:
                return 0
            
            visited.add(component_name)
            component = self.registry.get_component(component_name)
            
            if not component or not component.dependencies:
                return 1
            
            max_dep_depth = 0
            for dep in component.dependencies:
                dep_depth = get_depth(dep, visited.copy())
                max_dep_depth = max(max_dep_depth, dep_depth)
            
            return max_dep_depth + 1
        
        for component_name in self.registry.components:
            depth = get_depth(component_name)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _collect_performance_metrics(self) -> Dict[str, Any]:
        """パフォーマンスメトリクス収集"""
        metrics = {
            'memory_usage': {},
            'response_times': {},
            'error_rates': {}
        }
        
        for name, component in self.registry.components.items():
            try:
                if hasattr(component.instance, 'get_performance_metrics'):
                    component_metrics = component.instance.get_performance_metrics()
                    metrics['memory_usage'][name] = component_metrics.get('memory_usage', 0)
                    metrics['response_times'][name] = component_metrics.get('avg_response_time', 0)
                
                error_rate = component.error_count / max(1, component.error_count + 100)  # 仮の成功数
                metrics['error_rates'][name] = error_rate
                
            except Exception as e:
                self.logger.error(f"Failed to collect metrics for {name}: {e}")
        
        return metrics
    
    def _generate_integration_recommendations(self, status: Dict[str, Any]) -> List[str]:
        """統合改善推奨事項生成"""
        recommendations = []
        
        health = status['overall_health']
        
        if health['failed_components'] > 0:
            recommendations.append("Investigate and fix failed components")
        
        if health['degraded_components'] > 0:
            recommendations.append("Monitor and optimize degraded components")
        
        # 高エラー率コンポーネント
        for name, component in status['components'].items():
            if component['error_count'] > 5:
                recommendations.append(f"Component {name} has high error count - investigate")
            
            if component['restart_count'] > 2:
                recommendations.append(f"Component {name} requires frequent restarts - check stability")
        
        return recommendations
    
    def _record_event(self, event_type: str, details: Dict[str, Any]):
        """イベント記録"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'details': details
        }
        self.events.append(event)

# Global integration manager
_global_integration_manager = None

def get_integration_manager() -> IntegrationManager:
    """グローバル統合マネージャー取得"""
    global _global_integration_manager
    if _global_integration_manager is None:
        _global_integration_manager = IntegrationManager()
    return _global_integration_manager

def initialize_chameleon_system() -> bool:
    """Chameleonシステム全体初期化"""
    manager = get_integration_manager()
    return manager.initialize_system()

def shutdown_chameleon_system():
    """Chameleonシステム全体終了"""
    manager = get_integration_manager()
    manager.shutdown_system()

def get_system_health() -> SystemHealth:
    """システムヘルス取得"""
    manager = get_integration_manager()
    return manager.health_monitor.check_all_components()

if __name__ == "__main__":
    # 統合システムのテスト
    print("🔗 Integration Manager Test")
    print("=" * 40)
    
    # システム初期化
    success = initialize_chameleon_system()
    print(f"System initialization: {'SUCCESS' if success else 'FAILED'}")
    
    if success:
        # システムステータス取得
        manager = get_integration_manager()
        status = manager.get_system_status()
        
        print(f"Components initialized: {len(status['components'])}")
        print(f"Overall health: {status['overall_health']['overall_status']}")
        print(f"Healthy components: {status['overall_health']['healthy_components']}")
        
        # 統合レポート
        report = manager.get_integration_report()
        print(f"Dependency depth: {report['dependency_analysis']['dependency_depth']}")
        
        if report['recommendations']:
            print("Recommendations:")
            for rec in report['recommendations'][:3]:
                print(f"  • {rec}")
        
        # システム終了
        print("\nShutting down system...")
        shutdown_chameleon_system()
    
    print("Integration test completed")