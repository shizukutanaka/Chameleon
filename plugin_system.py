"""
🔌 Chameleon Plugin Architecture v3.0
Advanced plugin system for extensible audio processing capabilities
"""

import os
import sys
import json
import importlib
import inspect
import threading
import ast
import queue
import contextlib
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Type, Union
from dataclasses import dataclass, field
from pathlib import Path
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor
import logging

try:
    import resource  # type: ignore
except ImportError:  # pragma: no cover - platform specific
    resource = None

from security_validator import SecurityValidator, SecurityConfig, SecurityError

@dataclass
class PluginMetadata:
    """Plugin metadata and information"""
    name: str
    version: str
    author: str
    description: str
    category: str  # "effect", "analyzer", "generator", "utility"
    tags: List[str] = field(default_factory=list)
    website: Optional[str] = None
    license: str = "MIT"
    dependencies: List[str] = field(default_factory=list)
    min_chameleon_version: str = "3.0.0"
    parameters: Dict[str, Dict] = field(default_factory=dict)
    enabled: bool = True

@dataclass
class PluginConfig:
    """Plugin system configuration"""
    plugin_directories: List[str] = field(default_factory=lambda: ["plugins", "~/.chameleon/plugins"])
    auto_discover: bool = True
    sandbox_mode: bool = True
    max_execution_time: float = 30.0
    max_memory_mb: int = 512
    allow_network: bool = False
    cache_plugins: bool = True

class PluginInterface(ABC):
    """Base interface for all Chameleon plugins"""

    def __init__(self):
        self.metadata: Optional[PluginMetadata] = None
        self.config: Dict[str, Any] = {}
        self.logger = logging.getLogger(f"plugin.{self.__class__.__name__}")

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin with configuration"""
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup resources when plugin is unloaded"""
        pass

    def validate_input(self, audio_data: Any, **kwargs) -> bool:
        """Validate input data before processing"""
        return True

    def get_parameters(self) -> Dict[str, Dict]:
        """Get plugin parameter definitions"""
        return self.metadata.parameters if self.metadata else {}

class AudioEffectPlugin(PluginInterface):
    """Base class for audio effect plugins"""

    @abstractmethod
    def process_audio(self, audio_data: List[float], sample_rate: int, **params) -> List[float]:
        """Process audio data and return modified audio"""
        pass

    def process_realtime(self, audio_chunk: List[float], sample_rate: int, **params) -> List[float]:
        """Process audio in real-time (default: use process_audio)"""
        return self.process_audio(audio_chunk, sample_rate, **params)

class AudioAnalyzerPlugin(PluginInterface):
    """Base class for audio analyzer plugins"""

    @abstractmethod
    def analyze_audio(self, audio_data: List[float], sample_rate: int, **params) -> Dict[str, Any]:
        """Analyze audio and return analysis results"""
        pass

class AudioGeneratorPlugin(PluginInterface):
    """Base class for audio generator plugins"""

    @abstractmethod
    def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
        """Generate audio data"""
        pass

class UtilityPlugin(PluginInterface):
    """Base class for utility plugins"""

    @abstractmethod
    def execute(self, **params) -> Any:
        """Execute utility function"""
        pass

class PluginSandbox:
    """Security sandbox for plugin execution"""

    def __init__(self, config: PluginConfig):
        self.config = config
        self.restricted_modules = {
            'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests',
            'ftplib', 'smtplib', 'telnetlib', 'xmlrpc'
        }
        self.logger = logging.getLogger("plugin_sandbox")

    @contextlib.contextmanager
    def _apply_memory_limit(self):
        """Apply soft memory limits on POSIX systems when available."""

        if resource is None or not self.config.max_memory_mb:
            yield
            return

        limit_bytes = int(self.config.max_memory_mb) * 1024 * 1024

        try:
            soft_before, hard_before = resource.getrlimit(resource.RLIMIT_AS)
        except (ValueError, AttributeError, OSError):  # pragma: no cover - platform dependent
            yield
            return

        target_limit = limit_bytes
        if hard_before != resource.RLIM_INFINITY:
            target_limit = min(target_limit, hard_before)

        if target_limit <= 0:
            yield
            return

        try:
            resource.setrlimit(resource.RLIMIT_AS, (target_limit, target_limit))
        except (ValueError, resource.error, OSError) as exc:  # pragma: no cover - platform dependent
            self.logger.warning("Failed to apply memory limit: %s", exc)
            yield
            return

        try:
            yield
        finally:
            try:
                resource.setrlimit(resource.RLIMIT_AS, (soft_before, hard_before))
            except Exception:  # pragma: no cover - best effort rollback
                self.logger.warning("Unable to restore memory limit after sandbox execution")

    def is_safe_import(self, module_name: str) -> bool:
        """Check if module import is safe"""
        if not self.config.sandbox_mode:
            return True

        for restricted in self.restricted_modules:
            if module_name.startswith(restricted):
                return False

        return True

    def execute_with_limits(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with resource limits"""
        if not self.config.sandbox_mode:
            return func(*args, **kwargs)

        max_time = max(0.0, float(self.config.max_execution_time))

        if os.name != 'nt':
            try:
                import signal
            except ImportError:  # pragma: no cover - extremely rare
                signal = None
        else:
            signal = None

        if signal is not None and hasattr(signal, 'SIGALRM') and max_time > 0:
            previous_handler = signal.getsignal(signal.SIGALRM)

            def timeout_handler(signum, frame):  # pragma: no cover - requires timing
                raise TimeoutError("Plugin execution timed out")

            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(max_time))
                with self._apply_memory_limit():
                    return func(*args, **kwargs)
            finally:
                try:
                    signal.alarm(0)
                finally:
                    signal.signal(signal.SIGALRM, previous_handler)

        result_queue: "queue.Queue[tuple[bool, Any]]" = queue.Queue()

        def target():
            try:
                with self._apply_memory_limit():
                    value = func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - passed through
                result_queue.put((False, exc))
            else:
                result_queue.put((True, value))

        worker = threading.Thread(target=target, name="plugin-sandbox-exec", daemon=True)
        worker.start()

        if max_time > 0:
            worker.join(max_time)
        else:
            worker.join()

        if worker.is_alive():
            self.logger.error(
                "Plugin execution exceeded timeout of %.2f seconds; continuing with failure", max_time
            )
            raise TimeoutError("Plugin execution timed out")

        try:
            success, payload = result_queue.get_nowait()
        except queue.Empty:
            raise RuntimeError("Plugin execution completed without returning a result")

        if success:
            return payload

        raise payload

class PluginLoader:
    """Plugin loading and management system"""

    _FILE_VALIDATOR = SecurityValidator(
        SecurityConfig(allowed_extensions={'.py'})
    )
    _NAME_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
    _SEMVER_PATTERN = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:[-+][A-Za-z0-9.-]+)?$')

    def __init__(self, config: PluginConfig):
        self.config = config
        self.plugins: Dict[str, PluginInterface] = {}
        self.plugin_cache: Dict[str, Dict] = {}
        self.sandbox = PluginSandbox(config)
        self.logger = logging.getLogger("plugin_loader")

    def _resolve_directory(self, directory: str) -> Optional[Path]:
        """Resolve and validate a plugin directory path."""
        expanded = Path(directory).expanduser()
        try:
            resolved = expanded.resolve(strict=False)
        except Exception as exc:
            self.logger.warning(f"Unable to resolve plugin directory {directory}: {exc}")
            return None

        if not resolved.is_absolute():
            resolved = resolved.parent.resolve(strict=False) / resolved.name

        if os.name == 'posix':
            try:
                resolved.mkdir(parents=True, exist_ok=True)
                os.chmod(resolved, 0o750)
            except PermissionError:
                self.logger.warning(f"Insufficient permissions to secure directory {resolved}")
        else:
            resolved.mkdir(parents=True, exist_ok=True)

        return resolved

    def discover_plugins(self) -> List[str]:
        """Discover all available plugins"""
        plugin_files = []

        for directory in self.config.plugin_directories:
            resolved_dir = self._resolve_directory(directory)
            if not resolved_dir or not resolved_dir.exists():
                continue

            for candidate in resolved_dir.glob("*.py"):
                if self._is_safe_plugin_file(candidate):
                    plugin_files.append(candidate)

            for item in resolved_dir.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    init_file = item / "__init__.py"
                    if self._is_safe_plugin_file(init_file):
                        plugin_files.append(init_file)

        return [str(f) for f in plugin_files]

    def load_plugin(self, plugin_path: str) -> Optional[PluginInterface]:
        """Load a single plugin from file"""
        load_started = time.monotonic()

        try:
            validated_path = self._validate_plugin_path(plugin_path)

            # Calculate plugin hash for caching
            plugin_hash = self._calculate_file_hash(validated_path)

            # Check cache
            if self.config.cache_plugins and plugin_hash in self.plugin_cache:
                cached_info = self.plugin_cache[plugin_hash]
                if cached_info.get("valid", False):
                    self.logger.info(f"Loading cached plugin: {cached_info['name']}")

            # Load module
            spec = importlib.util.spec_from_file_location("plugin_module", str(validated_path))
            module = importlib.util.module_from_spec(spec)

            # Security check for imports
            if self.config.sandbox_mode:
                self._check_module_safety(validated_path)

            spec.loader.exec_module(module)

            # Find plugin classes
            plugin_classes = []
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, PluginInterface) and
                    obj != PluginInterface and
                    not inspect.isabstract(obj)):
                    plugin_classes.append(obj)

            if not plugin_classes:
                self.logger.warning(f"No valid plugin classes found in {plugin_path}")
                return None

            # Instantiate first valid plugin class
            plugin_class = plugin_classes[0]
            plugin_instance = plugin_class()

            # Get metadata
            metadata = plugin_instance.get_metadata()
            plugin_instance.metadata = metadata

            # Validate plugin
            if not self._validate_plugin(plugin_instance):
                return None

            # Initialize plugin
            if not plugin_instance.initialize({}):
                self.logger.error(f"Failed to initialize plugin: {metadata.name}")
                return None

            # Cache plugin info
            if self.config.cache_plugins:
                self.plugin_cache[plugin_hash] = {
                    "name": metadata.name,
                    "version": metadata.version,
                    "valid": True,
                    "loaded_time": time.time()
                }

            self.plugins[metadata.name] = plugin_instance
            load_duration = time.monotonic() - load_started
            self.logger.info(
                "Successfully loaded plugin '%s' v%s (hash=%s, %.3fs)",
                metadata.name,
                metadata.version,
                plugin_hash,
                load_duration
            )

            return plugin_instance

        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_path}: {e}")
            return None

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash of plugin file for caching"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _check_module_safety(self, plugin_path: Path):
        """Check if plugin uses safe imports"""
        try:
            with open(plugin_path, 'r', encoding='utf-8') as f:
                parsed = ast.parse(f.read(), filename=str(plugin_path))
        except SyntaxError as exc:
            raise SecurityError(f"Plugin contains invalid syntax: {exc}") from exc

        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if not self.sandbox.is_safe_import(module_name):
                        raise SecurityError(f"Unsafe import detected: {module_name}")
            elif isinstance(node, ast.ImportFrom):
                module_name = (node.module or '').split('.')[0]
                if module_name and not self.sandbox.is_safe_import(module_name):
                    raise SecurityError(f"Unsafe import detected: {module_name}")

    def _validate_plugin_path(self, plugin_path: str) -> Path:
        try:
            return self._FILE_VALIDATOR.validate_file_path(plugin_path, operation='read')
        except SecurityError as exc:
            raise SecurityError(f"Plugin path rejected: {exc}") from exc

    def _is_safe_plugin_file(self, path: Path) -> bool:
        try:
            self._FILE_VALIDATOR.validate_file_path(str(path), operation='read')
            return True
        except SecurityError as exc:
            self.logger.warning(f"Skipping unsafe plugin file {path}: {exc}")
            return False

    def _validate_plugin(self, plugin: PluginInterface) -> bool:
        """Validate plugin metadata and interface"""
        metadata = plugin.metadata
        if not metadata:
            return False

        # Required fields
        required_fields = ['name', 'version', 'author', 'description', 'category']
        for field in required_fields:
            if not getattr(metadata, field):
                self.logger.error(f"Plugin missing required field: {field}")
                return False

        if not self._NAME_PATTERN.match(metadata.name):
            self.logger.error("Plugin name contains prohibited characters: %s", metadata.name)
            return False

        if len(metadata.description) > 500:
            self.logger.error("Plugin description exceeds 500 characters for %s", metadata.name)
            return False

        if not self._SEMVER_PATTERN.match(metadata.version):
            self.logger.error("Plugin version is not semver compliant: %s", metadata.version)
            return False

        # Valid category
        valid_categories = ['effect', 'analyzer', 'generator', 'utility']
        if metadata.category not in valid_categories:
            self.logger.error(f"Invalid plugin category: {metadata.category}")
            return False

        if metadata.website:
            website = metadata.website.strip()
            if not website.lower().startswith('https://'):
                self.logger.error("Plugin website must use HTTPS: %s", website)
                return False
            if len(website) > 2083:
                self.logger.error("Plugin website URL too long: %s", website)
                return False

        return True

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin"""
        if plugin_name in self.plugins:
            try:
                self.plugins[plugin_name].cleanup()
                del self.plugins[plugin_name]
                self.logger.info(f"Unloaded plugin: {plugin_name}")
                return True
            except Exception as e:
                self.logger.error(f"Error unloading plugin {plugin_name}: {e}")
        return False

    def get_plugins_by_category(self, category: str) -> List[PluginInterface]:
        """Get all plugins of a specific category"""
        return [p for p in self.plugins.values()
                if p.metadata and p.metadata.category == category]

    def reload_plugin(self, plugin_name: str, plugin_path: str) -> bool:
        """Reload a plugin"""
        if plugin_name in self.plugins:
            self.unload_plugin(plugin_name)

        plugin = self.load_plugin(plugin_path)
        return plugin is not None

class PluginManager:
    """Main plugin management system"""

    def __init__(self, config: Optional[PluginConfig] = None):
        self.config = config or PluginConfig()
        self.loader = PluginLoader(self.config)
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.logger = logging.getLogger("plugin_manager")
        self._plugin_registry: Dict[str, str] = {}  # name -> path mapping

    def initialize(self):
        """Initialize the plugin system"""
        self.logger.info("Initializing plugin system...")

        # Create plugin directories if they don't exist
        for directory in self.config.plugin_directories:
            dir_path = Path(directory).expanduser()
            dir_path.mkdir(parents=True, exist_ok=True)

        # Auto-discover plugins if enabled
        if self.config.auto_discover:
            self.discover_and_load_all()

    def discover_and_load_all(self):
        """Discover and load all available plugins"""
        plugin_files = self.loader.discover_plugins()
        self.logger.info(f"Discovered {len(plugin_files)} potential plugins")

        loaded_count = 0
        for plugin_file in plugin_files:
            plugin = self.loader.load_plugin(plugin_file)
            if plugin:
                self._plugin_registry[plugin.metadata.name] = plugin_file
                loaded_count += 1

        self.logger.info(f"Successfully loaded {loaded_count} plugins")

    def get_plugin(self, name: str) -> Optional[PluginInterface]:
        """Get a plugin by name"""
        return self.loader.plugins.get(name)

    def list_plugins(self) -> Dict[str, PluginMetadata]:
        """List all loaded plugins with their metadata"""
        return {name: plugin.metadata
                for name, plugin in self.loader.plugins.items()
                if plugin.metadata}

    def execute_plugin(self, plugin_name: str, operation: str, **params) -> Any:
        """Execute a plugin operation safely"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin not found: {plugin_name}")

        if not plugin.metadata.enabled:
            raise RuntimeError(f"Plugin is disabled: {plugin_name}")

        # Get the operation method
        if hasattr(plugin, operation):
            method = getattr(plugin, operation)
            return self.loader.sandbox.execute_with_limits(method, **params)
        else:
            raise AttributeError(f"Plugin {plugin_name} has no method: {operation}")

    def install_plugin(self, plugin_source: str, plugin_name: Optional[str] = None) -> bool:
        """Install a plugin from source"""
        # This would implement plugin installation from various sources
        # For now, just load from local file
        if Path(plugin_source).exists():
            plugin = self.loader.load_plugin(plugin_source)
            if plugin:
                name = plugin.metadata.name
                self._plugin_registry[name] = plugin_source
                self.logger.info(f"Installed plugin: {name}")
                return True
        return False

    def create_plugin_template(self, plugin_name: str, category: str, output_dir: str = "plugins"):
        """Create a plugin template for development"""
        template = self._generate_plugin_template(plugin_name, category)

        output_path = Path(output_dir) / f"{plugin_name.lower()}_plugin.py"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(template)

        self.logger.info(f"Created plugin template: {output_path}")
        return str(output_path)

    def _generate_plugin_template(self, name: str, category: str) -> str:
        """Generate plugin template code"""
        if category == "effect":
            base_class = "AudioEffectPlugin"
            main_method = """def process_audio(self, audio_data: List[float], sample_rate: int, **params) -> List[float]:
        \"\"\"Process audio data\"\"\"
        # TODO: Implement your audio effect here
        # Example: simple gain
        gain = params.get('gain', 1.0)
        return [sample * gain for sample in audio_data]"""

        elif category == "analyzer":
            base_class = "AudioAnalyzerPlugin"
            main_method = """def analyze_audio(self, audio_data: List[float], sample_rate: int, **params) -> Dict[str, Any]:
        \"\"\"Analyze audio data\"\"\"
        # TODO: Implement your audio analysis here
        # Example: simple peak detection
        peak = max(abs(sample) for sample in audio_data) if audio_data else 0.0
        return {"peak_level": peak, "sample_count": len(audio_data)}"""

        elif category == "generator":
            base_class = "AudioGeneratorPlugin"
            main_method = """def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
        \"\"\"Generate audio data\"\"\"
        # TODO: Implement your audio generator here
        # Example: sine wave
        import math
        frequency = params.get('frequency', 440.0)
        samples = []
        for i in range(int(duration * sample_rate)):
            t = i / sample_rate
            sample = math.sin(2 * math.pi * frequency * t)
            samples.append(sample)
        return samples"""

        else:  # utility
            base_class = "UtilityPlugin"
            main_method = """def execute(self, **params) -> Any:
        \"\"\"Execute utility function\"\"\"
        # TODO: Implement your utility here
        return {"status": "success", "message": "Utility executed"}"""

        template = f'''"""
{name} Plugin for Chameleon Audio Processing System
Generated plugin template
"""

from typing import List, Dict, Any
from plugin_system import {base_class}, PluginMetadata

class {name}Plugin({base_class}):
    """
    {name} - A Chameleon audio processing plugin
    """

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="{name}",
            version="1.0.0",
            author="Plugin Developer",
            description="Description of {name} plugin",
            category="{category}",
            tags=["{category}", "audio"],
            parameters={{
                "gain": {{
                    "type": "float",
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "description": "Gain level"
                }}
            }}
        )

    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin"""
        self.logger.info(f"Initializing {{self.get_metadata().name}} plugin")
        # TODO: Add initialization code here
        return True

    def cleanup(self):
        """Cleanup plugin resources"""
        self.logger.info(f"Cleaning up {{self.get_metadata().name}} plugin")
        # TODO: Add cleanup code here
        pass

    {main_method}

# Plugin entry point
def create_plugin():
    return {name}Plugin()
'''
        return template

    def shutdown(self):
        """Shutdown the plugin system"""
        self.logger.info("Shutting down plugin system...")

        # Unload all plugins
        plugin_names = list(self.loader.plugins.keys())
        for name in plugin_names:
            self.loader.unload_plugin(name)

        # Shutdown executor
        self.executor.shutdown(wait=True)

# SecurityError is imported from security_validator (single canonical type).

def demo_plugin_system():
    """Demonstrate plugin system capabilities"""
    print("🔌 Chameleon Plugin System Demo")
    print("=" * 50)

    # Initialize plugin manager
    config = PluginConfig(
        plugin_directories=["plugins", "demo_plugins"],
        sandbox_mode=True,
        auto_discover=True
    )

    manager = PluginManager(config)
    manager.initialize()

    # Create demo plugin directory
    demo_dir = Path("demo_plugins")
    demo_dir.mkdir(exist_ok=True)

    # Create sample plugins
    print("\n1. 🛠️ Creating sample plugins...")

    # Simple gain effect plugin
    gain_template = manager._generate_plugin_template("SimpleGain", "effect")
    with open(demo_dir / "simple_gain.py", 'w') as f:
        f.write(gain_template)

    # Peak analyzer plugin
    analyzer_template = manager._generate_plugin_template("PeakAnalyzer", "analyzer")
    with open(demo_dir / "peak_analyzer.py", 'w') as f:
        f.write(analyzer_template)

    print("   ✅ Created SimpleGain effect plugin")
    print("   ✅ Created PeakAnalyzer analyzer plugin")

    # Load plugins
    print("\n2. 🔄 Loading plugins...")
    manager.discover_and_load_all()

    # List loaded plugins
    print("\n3. 📋 Loaded plugins:")
    plugins = manager.list_plugins()
    for name, metadata in plugins.items():
        print(f"   • {name} v{metadata.version} ({metadata.category})")
        print(f"     {metadata.description}")

    # Test plugin execution (would need actual audio data)
    print("\n4. ⚡ Plugin execution capabilities ready")
    print("   Plugins can process audio, analyze content, and generate sounds")
    print("   Sandbox security enabled for safe execution")

    # Plugin development helper
    print("\n5. 🎯 Plugin development:")
    template_path = manager.create_plugin_template("MyCustomEffect", "effect")
    print(f"   ✅ Created development template: {template_path}")

    # Cleanup
    manager.shutdown()

    print("\n🎉 Plugin system demo completed!")
    print("   Ready for custom plugin development and execution")

    return True

if __name__ == "__main__":
    demo_plugin_system()