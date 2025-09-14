#!/usr/bin/env python3
"""
Chameleon Audio System - Plugin SDK and Extension Framework
===========================================================
Comprehensive plugin system for audio processing extensions
"""

import os
import sys
import json
import importlib
import importlib.util
import inspect
import time
import threading
import traceback
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Type, Union
from dataclasses import dataclass, field
from enum import Enum
import tempfile
import shutil
import hashlib


class PluginType(Enum):
    """Types of plugins"""
    AUDIO_PROCESSOR = "audio_processor"
    EFFECT = "effect"
    ANALYZER = "analyzer"
    GENERATOR = "generator"
    FILTER = "filter"
    CODEC = "codec"
    VISUALIZATION = "visualization"
    UTILITY = "utility"
    INSTRUMENT = "instrument"
    MIXER = "mixer"


class PluginCategory(Enum):
    """Plugin categories"""
    DYNAMICS = "dynamics"
    EQ = "eq"
    REVERB = "reverb"
    DELAY = "delay"
    MODULATION = "modulation"
    DISTORTION = "distortion"
    SYNTHESIS = "synthesis"
    ANALYSIS = "analysis"
    UTILITY = "utility"
    EXPERIMENTAL = "experimental"


@dataclass
class PluginInfo:
    """Plugin metadata"""
    name: str
    version: str
    author: str
    description: str
    plugin_type: PluginType
    category: PluginCategory
    tags: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    website: str = ""
    license: str = ""
    min_chameleon_version: str = "1.0.0"
    max_chameleon_version: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)


@dataclass
class PluginContext:
    """Runtime context for plugins"""
    sample_rate: int
    channels: int
    chunk_size: int
    bit_depth: int
    host_info: Dict[str, Any]
    settings: Dict[str, Any] = field(default_factory=dict)
    user_data: Dict[str, Any] = field(default_factory=dict)


class PluginInterface(ABC):
    """Base interface for all plugins"""
    
    def __init__(self):
        self.info: Optional[PluginInfo] = None
        self.context: Optional[PluginContext] = None
        self.enabled = True
        self.parameters = {}
        self.state = {}
    
    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Get plugin information"""
        pass
    
    @abstractmethod
    def initialize(self, context: PluginContext) -> bool:
        """Initialize plugin with context"""
        pass
    
    @abstractmethod
    def process(self, audio_data: Any, **kwargs) -> Any:
        """Process audio data"""
        pass
    
    def set_parameter(self, name: str, value: Any) -> bool:
        """Set plugin parameter"""
        if name in self.get_info().parameters:
            self.parameters[name] = value
            return True
        return False
    
    def get_parameter(self, name: str) -> Any:
        """Get plugin parameter"""
        return self.parameters.get(name)
    
    def save_state(self) -> Dict[str, Any]:
        """Save plugin state"""
        return {
            'parameters': self.parameters.copy(),
            'state': self.state.copy(),
            'enabled': self.enabled
        }
    
    def load_state(self, state: Dict[str, Any]) -> bool:
        """Load plugin state"""
        try:
            self.parameters = state.get('parameters', {})
            self.state = state.get('state', {})
            self.enabled = state.get('enabled', True)
            return True
        except Exception:
            return False
    
    def cleanup(self):
        """Cleanup plugin resources"""
        pass


class AudioProcessorPlugin(PluginInterface):
    """Base class for audio processor plugins"""
    
    @abstractmethod
    def process_audio(self, samples: List[float], sample_rate: int) -> List[float]:
        """Process audio samples"""
        pass
    
    def process(self, audio_data: Any, **kwargs) -> Any:
        """Implementation of base process method"""
        if isinstance(audio_data, list):
            sample_rate = kwargs.get('sample_rate', 44100)
            return self.process_audio(audio_data, sample_rate)
        return audio_data


class EffectPlugin(PluginInterface):
    """Base class for audio effect plugins"""
    
    @abstractmethod
    def apply_effect(self, samples: List[float], **params) -> List[float]:
        """Apply effect to audio samples"""
        pass
    
    def process(self, audio_data: Any, **kwargs) -> Any:
        """Implementation of base process method"""
        if isinstance(audio_data, list):
            return self.apply_effect(audio_data, **kwargs)
        return audio_data


class AnalyzerPlugin(PluginInterface):
    """Base class for audio analyzer plugins"""
    
    @abstractmethod
    def analyze_audio(self, samples: List[float], sample_rate: int) -> Dict[str, Any]:
        """Analyze audio and return metrics"""
        pass
    
    def process(self, audio_data: Any, **kwargs) -> Any:
        """Implementation of base process method"""
        if isinstance(audio_data, list):
            sample_rate = kwargs.get('sample_rate', 44100)
            return self.analyze_audio(audio_data, sample_rate)
        return {}


class GeneratorPlugin(PluginInterface):
    """Base class for audio generator plugins"""
    
    @abstractmethod
    def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
        """Generate audio samples"""
        pass
    
    def process(self, audio_data: Any, **kwargs) -> Any:
        """Implementation of base process method"""
        duration = kwargs.pop('duration', 1.0)
        sample_rate = kwargs.pop('sample_rate', 44100)
        return self.generate_audio(duration, sample_rate, **kwargs)


class PluginValidator:
    """Validates plugin implementations"""
    
    @staticmethod
    def validate_plugin_class(plugin_class: Type[PluginInterface]) -> List[str]:
        """Validate plugin class implementation"""
        errors = []
        
        # Check if class inherits from PluginInterface
        if not issubclass(plugin_class, PluginInterface):
            errors.append("Plugin must inherit from PluginInterface")
        
        # Check required methods
        required_methods = ['get_info', 'initialize', 'process']
        for method in required_methods:
            if not hasattr(plugin_class, method):
                errors.append(f"Missing required method: {method}")
        
        # Check method signatures
        try:
            instance = plugin_class()
            
            # Test get_info
            info = instance.get_info()
            if not isinstance(info, PluginInfo):
                errors.append("get_info() must return PluginInfo instance")
            
        except Exception as e:
            errors.append(f"Error creating plugin instance: {str(e)}")
        
        return errors
    
    @staticmethod
    def validate_plugin_info(info: PluginInfo) -> List[str]:
        """Validate plugin metadata"""
        errors = []
        
        # Check required fields
        required_fields = ['name', 'version', 'author', 'description', 'plugin_type']
        for field in required_fields:
            if not getattr(info, field, None):
                errors.append(f"Missing required field: {field}")
        
        # Validate plugin type
        if not isinstance(info.plugin_type, PluginType):
            errors.append("plugin_type must be a PluginType enum")
        
        # Validate category
        if not isinstance(info.category, PluginCategory):
            errors.append("category must be a PluginCategory enum")
        
        # Validate version format
        if info.version and not info.version.replace('.', '').replace('-', '').isalnum():
            errors.append("Invalid version format")
        
        return errors


class PluginManager:
    """Core plugin management system"""
    
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(exist_ok=True)
        
        # Plugin registry
        self.loaded_plugins: Dict[str, PluginInterface] = {}
        self.plugin_classes: Dict[str, Type[PluginInterface]] = {}
        self.plugin_infos: Dict[str, PluginInfo] = {}
        
        # Plugin chains for different categories
        self.effect_chains: Dict[str, List[str]] = {}
        self.processor_chains: Dict[str, List[str]] = {}
        
        # Plugin state management
        self.plugin_states: Dict[str, Dict[str, Any]] = {}
        self.active_plugins: List[str] = []
        
        # Safety and sandboxing
        self.safe_mode = True
        self.allowed_imports = {
            'math', 'random', 'time', 'json', 'typing',
            'collections', 'itertools', 'functools'
        }
        
        # Performance tracking
        self.plugin_performance: Dict[str, Dict[str, float]] = {}
        
        # Load built-in plugins
        self._load_builtin_plugins()
    
    def _load_builtin_plugins(self):
        """Load built-in example plugins"""
        # Create built-in plugin examples
        self._create_builtin_examples()
    
    def _create_builtin_examples(self):
        """Create example plugins for demonstration"""
        
        # Simple Gain Plugin
        class SimpleGainPlugin(EffectPlugin):
            def get_info(self) -> PluginInfo:
                return PluginInfo(
                    name="Simple Gain",
                    version="1.0.0",
                    author="Chameleon Audio",
                    description="Basic gain/volume control",
                    plugin_type=PluginType.EFFECT,
                    category=PluginCategory.DYNAMICS,
                    tags=["gain", "volume", "basic"],
                    parameters={
                        "gain": {"type": "float", "min": 0.0, "max": 4.0, "default": 1.0},
                        "enabled": {"type": "bool", "default": True}
                    }
                )
            
            def initialize(self, context: PluginContext) -> bool:
                self.context = context
                self.parameters = {"gain": 1.0, "enabled": True}
                return True
            
            def apply_effect(self, samples: List[float], **params) -> List[float]:
                if not self.parameters.get("enabled", True):
                    return samples
                
                gain = self.parameters.get("gain", 1.0)
                return [sample * gain for sample in samples]
        
        # Simple Low-pass Filter Plugin
        class SimpleLowpassPlugin(EffectPlugin):
            def get_info(self) -> PluginInfo:
                return PluginInfo(
                    name="Simple Lowpass",
                    version="1.0.0",
                    author="Chameleon Audio",
                    description="Basic low-pass filter",
                    plugin_type=PluginType.FILTER,
                    category=PluginCategory.EQ,
                    tags=["filter", "lowpass", "eq"],
                    parameters={
                        "cutoff": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.5},
                        "enabled": {"type": "bool", "default": True}
                    }
                )
            
            def initialize(self, context: PluginContext) -> bool:
                self.context = context
                self.parameters = {"cutoff": 0.5, "enabled": True}
                self.state = {"prev_sample": 0.0}
                return True
            
            def apply_effect(self, samples: List[float], **params) -> List[float]:
                if not self.parameters.get("enabled", True):
                    return samples
                
                cutoff = self.parameters.get("cutoff", 0.5)
                prev = self.state.get("prev_sample", 0.0)
                
                result = []
                for sample in samples:
                    filtered = cutoff * sample + (1 - cutoff) * prev
                    result.append(filtered)
                    prev = filtered
                
                self.state["prev_sample"] = prev
                return result
        
        # Sine Wave Generator Plugin
        class SineGeneratorPlugin(GeneratorPlugin):
            def get_info(self) -> PluginInfo:
                return PluginInfo(
                    name="Sine Generator",
                    version="1.0.0",
                    author="Chameleon Audio",
                    description="Simple sine wave generator",
                    plugin_type=PluginType.GENERATOR,
                    category=PluginCategory.SYNTHESIS,
                    tags=["generator", "sine", "oscillator"],
                    parameters={
                        "frequency": {"type": "float", "min": 20.0, "max": 20000.0, "default": 440.0},
                        "amplitude": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.5}
                    }
                )
            
            def initialize(self, context: PluginContext) -> bool:
                self.context = context
                self.parameters = {"frequency": 440.0, "amplitude": 0.5}
                self.state = {"phase": 0.0}
                return True
            
            def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
                import math
                
                frequency = self.parameters.get("frequency", 440.0)
                amplitude = self.parameters.get("amplitude", 0.5)
                phase = self.state.get("phase", 0.0)
                
                samples = []
                for i in range(int(duration * sample_rate)):
                    sample = amplitude * math.sin(phase)
                    samples.append(sample)
                    phase += 2 * math.pi * frequency / sample_rate
                
                # Keep phase in reasonable range
                self.state["phase"] = phase % (2 * math.pi)
                return samples
        
        # Spectrum Analyzer Plugin
        class SpectrumAnalyzerPlugin(AnalyzerPlugin):
            def get_info(self) -> PluginInfo:
                return PluginInfo(
                    name="Spectrum Analyzer",
                    version="1.0.0",
                    author="Chameleon Audio",
                    description="Basic spectrum analysis",
                    plugin_type=PluginType.ANALYZER,
                    category=PluginCategory.ANALYSIS,
                    tags=["analyzer", "spectrum", "fft"],
                    parameters={
                        "fft_size": {"type": "int", "min": 64, "max": 8192, "default": 1024}
                    }
                )
            
            def initialize(self, context: PluginContext) -> bool:
                self.context = context
                self.parameters = {"fft_size": 1024}
                return True
            
            def analyze_audio(self, samples: List[float], sample_rate: int) -> Dict[str, Any]:
                # Simple spectral analysis
                if not samples:
                    return {}
                
                # Calculate RMS
                rms = (sum(s**2 for s in samples) / len(samples)) ** 0.5
                
                # Calculate peak
                peak = max(abs(s) for s in samples)
                
                # Simple frequency analysis
                zero_crossings = 0
                for i in range(1, len(samples)):
                    if (samples[i-1] >= 0) != (samples[i] >= 0):
                        zero_crossings += 1
                
                dominant_freq = (zero_crossings * sample_rate) / (2 * len(samples))
                
                return {
                    "rms": rms,
                    "peak": peak,
                    "dominant_frequency": dominant_freq,
                    "zero_crossings": zero_crossings,
                    "sample_count": len(samples)
                }
        
        # Register built-in plugins
        builtin_plugins = [
            SimpleGainPlugin,
            SimpleLowpassPlugin,
            SineGeneratorPlugin,
            SpectrumAnalyzerPlugin
        ]
        
        for plugin_class in builtin_plugins:
            try:
                plugin_name = plugin_class().get_info().name
                self.plugin_classes[plugin_name] = plugin_class
                
                # Create instance and store info
                instance = plugin_class()
                self.plugin_infos[plugin_name] = instance.get_info()
                
            except Exception as e:
                print(f"Failed to register built-in plugin {plugin_class.__name__}: {e}")
    
    def load_plugin_from_file(self, file_path: str) -> bool:
        """Load plugin from Python file"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"Plugin file not found: {file_path}")
            
            # Load module
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module spec from {file_path}")
            
            module = importlib.util.module_from_spec(spec)
            
            # Security check in safe mode
            if self.safe_mode:
                self._validate_plugin_security(file_path)
            
            # Load the module
            spec.loader.exec_module(module)
            
            # Find plugin classes
            plugin_classes = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, PluginInterface) and 
                    obj != PluginInterface):
                    plugin_classes.append(obj)
            
            if not plugin_classes:
                raise ValueError("No plugin classes found in file")
            
            # Validate and register plugins
            for plugin_class in plugin_classes:
                errors = PluginValidator.validate_plugin_class(plugin_class)
                if errors:
                    raise ValueError(f"Plugin validation failed: {', '.join(errors)}")
                
                # Create instance and validate info
                instance = plugin_class()
                info = instance.get_info()
                
                info_errors = PluginValidator.validate_plugin_info(info)
                if info_errors:
                    raise ValueError(f"Plugin info validation failed: {', '.join(info_errors)}")
                
                # Register plugin
                self.plugin_classes[info.name] = plugin_class
                self.plugin_infos[info.name] = info
                
                print(f"Loaded plugin: {info.name} v{info.version}")
            
            return True
            
        except Exception as e:
            print(f"Failed to load plugin from {file_path}: {e}")
            return False
    
    def _validate_plugin_security(self, file_path: Path):
        """Basic security validation for plugins"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for dangerous operations
        dangerous_patterns = [
            'import os', 'import subprocess', 'import sys',
            'exec(', 'eval(', '__import__',
            'open(', 'file(', 'input(',
            'socket', 'urllib', 'requests'
        ]
        
        for pattern in dangerous_patterns:
            if pattern in content:
                raise SecurityError(f"Potentially unsafe operation detected: {pattern}")
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load and instantiate a plugin"""
        try:
            if plugin_name in self.loaded_plugins:
                return True  # Already loaded
            
            if plugin_name not in self.plugin_classes:
                raise ValueError(f"Plugin class not found: {plugin_name}")
            
            # Create plugin instance
            plugin_class = self.plugin_classes[plugin_name]
            plugin_instance = plugin_class()
            
            # Create context
            context = PluginContext(
                sample_rate=44100,
                channels=1,
                chunk_size=1024,
                bit_depth=16,
                host_info={
                    "name": "Chameleon Audio System",
                    "version": "2.0.0",
                    "api_version": "1.0.0"
                }
            )
            
            # Initialize plugin
            if not plugin_instance.initialize(context):
                raise RuntimeError(f"Plugin initialization failed: {plugin_name}")
            
            # Store plugin
            self.loaded_plugins[plugin_name] = plugin_instance
            
            # Load saved state if available
            if plugin_name in self.plugin_states:
                plugin_instance.load_state(self.plugin_states[plugin_name])
            
            print(f"Plugin loaded: {plugin_name}")
            return True
            
        except Exception as e:
            print(f"Failed to load plugin {plugin_name}: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin"""
        try:
            if plugin_name in self.loaded_plugins:
                plugin = self.loaded_plugins[plugin_name]
                
                # Save state
                self.plugin_states[plugin_name] = plugin.save_state()
                
                # Cleanup
                plugin.cleanup()
                
                # Remove from loaded plugins
                del self.loaded_plugins[plugin_name]
                
                # Remove from active plugins
                if plugin_name in self.active_plugins:
                    self.active_plugins.remove(plugin_name)
                
                print(f"Plugin unloaded: {plugin_name}")
            
            return True
            
        except Exception as e:
            print(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    def process_through_plugins(self, audio_data: Any, plugin_chain: List[str] = None, **kwargs) -> Any:
        """Process audio through a chain of plugins"""
        if plugin_chain is None:
            plugin_chain = self.active_plugins
        
        result = audio_data
        
        for plugin_name in plugin_chain:
            if plugin_name not in self.loaded_plugins:
                print(f"Warning: Plugin not loaded: {plugin_name}")
                continue
            
            plugin = self.loaded_plugins[plugin_name]
            
            if not plugin.enabled:
                continue
            
            try:
                start_time = time.perf_counter()
                result = plugin.process(result, **kwargs)
                duration = time.perf_counter() - start_time
                
                # Track performance
                if plugin_name not in self.plugin_performance:
                    self.plugin_performance[plugin_name] = {"total_time": 0, "call_count": 0}
                
                self.plugin_performance[plugin_name]["total_time"] += duration
                self.plugin_performance[plugin_name]["call_count"] += 1
                
            except Exception as e:
                print(f"Error in plugin {plugin_name}: {e}")
                # Continue with next plugin in chain
                continue
        
        return result
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[str]:
        """Get plugins of specific type"""
        return [name for name, info in self.plugin_infos.items() 
                if info.plugin_type == plugin_type]
    
    def get_plugins_by_category(self, category: PluginCategory) -> List[str]:
        """Get plugins of specific category"""
        return [name for name, info in self.plugin_infos.items() 
                if info.category == category]
    
    def create_effect_chain(self, chain_name: str, plugins: List[str]) -> bool:
        """Create named effect chain"""
        try:
            # Validate all plugins exist
            for plugin_name in plugins:
                if plugin_name not in self.plugin_infos:
                    raise ValueError(f"Plugin not found: {plugin_name}")
            
            self.effect_chains[chain_name] = plugins.copy()
            return True
            
        except Exception as e:
            print(f"Failed to create effect chain {chain_name}: {e}")
            return False
    
    def apply_effect_chain(self, audio_data: Any, chain_name: str, **kwargs) -> Any:
        """Apply named effect chain"""
        if chain_name not in self.effect_chains:
            print(f"Effect chain not found: {chain_name}")
            return audio_data
        
        return self.process_through_plugins(audio_data, self.effect_chains[chain_name], **kwargs)
    
    def set_plugin_parameter(self, plugin_name: str, param_name: str, value: Any) -> bool:
        """Set plugin parameter"""
        if plugin_name not in self.loaded_plugins:
            return False
        
        return self.loaded_plugins[plugin_name].set_parameter(param_name, value)
    
    def get_plugin_parameter(self, plugin_name: str, param_name: str) -> Any:
        """Get plugin parameter"""
        if plugin_name not in self.loaded_plugins:
            return None
        
        return self.loaded_plugins[plugin_name].get_parameter(param_name)
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable plugin"""
        if plugin_name in self.loaded_plugins:
            self.loaded_plugins[plugin_name].enabled = True
            if plugin_name not in self.active_plugins:
                self.active_plugins.append(plugin_name)
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable plugin"""
        if plugin_name in self.loaded_plugins:
            self.loaded_plugins[plugin_name].enabled = False
            if plugin_name in self.active_plugins:
                self.active_plugins.remove(plugin_name)
            return True
        return False
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get plugin information"""
        return self.plugin_infos.get(plugin_name)
    
    def list_plugins(self) -> Dict[str, Dict[str, Any]]:
        """List all available plugins"""
        plugins = {}
        
        for name, info in self.plugin_infos.items():
            plugins[name] = {
                "info": info,
                "loaded": name in self.loaded_plugins,
                "active": name in self.active_plugins,
                "enabled": self.loaded_plugins[name].enabled if name in self.loaded_plugins else False
            }
        
        return plugins
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get plugin performance statistics"""
        stats = {}
        
        for plugin_name, perf_data in self.plugin_performance.items():
            if perf_data["call_count"] > 0:
                avg_time = perf_data["total_time"] / perf_data["call_count"]
                stats[plugin_name] = {
                    "total_time": perf_data["total_time"],
                    "call_count": perf_data["call_count"],
                    "average_time": avg_time,
                    "calls_per_second": 1.0 / avg_time if avg_time > 0 else 0
                }
        
        return stats
    
    def save_plugin_configuration(self, file_path: str) -> bool:
        """Save current plugin configuration"""
        try:
            config = {
                "active_plugins": self.active_plugins.copy(),
                "effect_chains": self.effect_chains.copy(),
                "plugin_states": {}
            }
            
            # Save states of loaded plugins
            for plugin_name, plugin in self.loaded_plugins.items():
                config["plugin_states"][plugin_name] = plugin.save_state()
            
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Failed to save plugin configuration: {e}")
            return False
    
    def load_plugin_configuration(self, file_path: str) -> bool:
        """Load plugin configuration"""
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            
            # Load plugin states
            self.plugin_states.update(config.get("plugin_states", {}))
            
            # Load effect chains
            self.effect_chains.update(config.get("effect_chains", {}))
            
            # Load active plugins
            for plugin_name in config.get("active_plugins", []):
                if self.load_plugin(plugin_name):
                    self.enable_plugin(plugin_name)
            
            return True
            
        except Exception as e:
            print(f"Failed to load plugin configuration: {e}")
            return False


class PluginDeveloperKit:
    """Development tools for plugin creators"""
    
    def __init__(self):
        self.template_dir = Path("plugin_templates")
        self.template_dir.mkdir(exist_ok=True)
        
        self._create_templates()
    
    def _create_templates(self):
        """Create plugin templates"""
        
        # Effect Plugin Template
        effect_template = '''#!/usr/bin/env python3
"""
{plugin_name} - Audio Effect Plugin
Generated by Chameleon Plugin SDK
"""

from plugin_sdk import EffectPlugin, PluginInfo, PluginType, PluginCategory, PluginContext
from typing import List


class {class_name}(EffectPlugin):
    """Custom audio effect plugin"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="{plugin_name}",
            version="1.0.0",
            author="Your Name",
            description="Description of your effect",
            plugin_type=PluginType.EFFECT,
            category=PluginCategory.UTILITY,
            tags=["{plugin_name.lower()}", "effect"],
            parameters={{
                "intensity": {{"type": "float", "min": 0.0, "max": 1.0, "default": 0.5}},
                "enabled": {{"type": "bool", "default": True}}
            }}
        )
    
    def initialize(self, context: PluginContext) -> bool:
        self.context = context
        self.parameters = {{"intensity": 0.5, "enabled": True}}
        self.state = {{}}
        return True
    
    def apply_effect(self, samples: List[float], **params) -> List[float]:
        if not self.parameters.get("enabled", True):
            return samples
        
        intensity = self.parameters.get("intensity", 0.5)
        
        # TODO: Implement your effect here
        # Example: simple gain
        result = []
        for sample in samples:
            processed = sample * (1.0 + intensity)
            result.append(processed)
        
        return result


# Plugin instance for loading
plugin_instance = {class_name}()
'''
        
        # Generator Plugin Template
        generator_template = '''#!/usr/bin/env python3
"""
{plugin_name} - Audio Generator Plugin
Generated by Chameleon Plugin SDK
"""

from plugin_sdk import GeneratorPlugin, PluginInfo, PluginType, PluginCategory, PluginContext
from typing import List
import math


class {class_name}(GeneratorPlugin):
    """Custom audio generator plugin"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="{plugin_name}",
            version="1.0.0",
            author="Your Name",
            description="Description of your generator",
            plugin_type=PluginType.GENERATOR,
            category=PluginCategory.SYNTHESIS,
            tags=["{plugin_name.lower()}", "generator"],
            parameters={{
                "frequency": {{"type": "float", "min": 20.0, "max": 20000.0, "default": 440.0}},
                "amplitude": {{"type": "float", "min": 0.0, "max": 1.0, "default": 0.5}}
            }}
        )
    
    def initialize(self, context: PluginContext) -> bool:
        self.context = context
        self.parameters = {{"frequency": 440.0, "amplitude": 0.5}}
        self.state = {{"phase": 0.0}}
        return True
    
    def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
        frequency = self.parameters.get("frequency", 440.0)
        amplitude = self.parameters.get("amplitude", 0.5)
        phase = self.state.get("phase", 0.0)
        
        samples = []
        for i in range(int(duration * sample_rate)):
            # TODO: Implement your generator here
            # Example: sine wave
            sample = amplitude * math.sin(phase)
            samples.append(sample)
            phase += 2 * math.pi * frequency / sample_rate
        
        # Keep phase in reasonable range
        self.state["phase"] = phase % (2 * math.pi)
        return samples


# Plugin instance for loading
plugin_instance = {class_name}()
'''
        
        # Save templates
        with open(self.template_dir / "effect_template.py", 'w') as f:
            f.write(effect_template)
        
        with open(self.template_dir / "generator_template.py", 'w') as f:
            f.write(generator_template)
    
    def create_plugin_project(self, plugin_name: str, plugin_type: str, output_dir: str = None) -> bool:
        """Create new plugin project from template"""
        try:
            if output_dir is None:
                output_dir = f"plugin_{plugin_name.lower().replace(' ', '_')}"
            
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            class_name = ''.join(word.capitalize() for word in plugin_name.split())
            
            # Select template
            if plugin_type.lower() == "effect":
                template_file = self.template_dir / "effect_template.py"
            elif plugin_type.lower() == "generator":
                template_file = self.template_dir / "generator_template.py"
            else:
                raise ValueError(f"Unknown plugin type: {plugin_type}")
            
            # Read template
            with open(template_file, 'r') as f:
                template_content = f.read()
            
            # Replace placeholders
            plugin_code = template_content.format(
                plugin_name=plugin_name,
                class_name=class_name
            )
            
            # Write plugin file
            plugin_file = output_path / f"{plugin_name.lower().replace(' ', '_')}_plugin.py"
            with open(plugin_file, 'w') as f:
                f.write(plugin_code)
            
            # Create plugin info file
            info_file = output_path / "plugin_info.json"
            info_data = {
                "name": plugin_name,
                "version": "1.0.0",
                "author": "Your Name",
                "description": f"{plugin_name} plugin",
                "type": plugin_type,
                "main_file": plugin_file.name
            }
            
            with open(info_file, 'w') as f:
                json.dump(info_data, f, indent=2)
            
            # Create README
            readme_file = output_path / "README.md"
            readme_content = f"""# {plugin_name} Plugin

## Description
{plugin_name} audio plugin for Chameleon Audio System.

## Installation
1. Copy the plugin file to your Chameleon plugins directory
2. Load the plugin using the plugin manager

## Usage
```python
from plugin_sdk import PluginManager

manager = PluginManager()
manager.load_plugin_from_file("{plugin_file.name}")
manager.load_plugin("{plugin_name}")
```

## Parameters
- intensity: Effect intensity (0.0 - 1.0)
- enabled: Enable/disable plugin

## Development
This plugin was generated using the Chameleon Plugin SDK.
"""
            
            with open(readme_file, 'w') as f:
                f.write(readme_content)
            
            print(f"Plugin project created: {output_path}")
            print(f"Main file: {plugin_file}")
            print(f"Edit the TODO sections to implement your plugin logic")
            
            return True
            
        except Exception as e:
            print(f"Failed to create plugin project: {e}")
            return False
    
    def validate_plugin_project(self, project_dir: str) -> List[str]:
        """Validate plugin project"""
        issues = []
        project_path = Path(project_dir)
        
        if not project_path.exists():
            issues.append("Project directory does not exist")
            return issues
        
        # Check for required files
        plugin_files = list(project_path.glob("*_plugin.py"))
        if not plugin_files:
            issues.append("No plugin Python files found")
        
        info_file = project_path / "plugin_info.json"
        if not info_file.exists():
            issues.append("plugin_info.json not found")
        
        # Validate plugin files
        for plugin_file in plugin_files:
            try:
                # Basic syntax check
                with open(plugin_file, 'r') as f:
                    content = f.read()
                
                compile(content, str(plugin_file), 'exec')
                
                # Check for required classes
                if 'class ' not in content:
                    issues.append(f"{plugin_file.name}: No classes found")
                
                if 'PluginInterface' not in content:
                    issues.append(f"{plugin_file.name}: Does not inherit from PluginInterface")
                
            except SyntaxError as e:
                issues.append(f"{plugin_file.name}: Syntax error at line {e.lineno}")
            except Exception as e:
                issues.append(f"{plugin_file.name}: {str(e)}")
        
        return issues


class SecurityError(Exception):
    """Plugin security error"""
    pass


# Example usage and testing
def demo_plugin_system():
    """Demonstrate plugin system functionality"""
    print("=" * 60)
    print("CHAMELEON PLUGIN SYSTEM DEMO")
    print("=" * 60)
    
    # Create plugin manager
    manager = PluginManager()
    
    # List available plugins
    print("\nAvailable plugins:")
    plugins = manager.list_plugins()
    for name, details in plugins.items():
        info = details["info"]
        print(f"  • {name} v{info.version} ({info.plugin_type.value})")
        print(f"    {info.description}")
        print(f"    Categories: {info.category.value}")
    
    # Load some plugins
    print("\nLoading plugins...")
    manager.load_plugin("Simple Gain")
    manager.load_plugin("Simple Lowpass")
    manager.load_plugin("Sine Generator")
    
    # Enable plugins in chain
    manager.enable_plugin("Simple Gain")
    manager.enable_plugin("Simple Lowpass")
    
    # Set parameters
    manager.set_plugin_parameter("Simple Gain", "gain", 1.5)
    manager.set_plugin_parameter("Simple Lowpass", "cutoff", 0.3)
    
    # Generate test audio
    print("\nGenerating test audio...")
    test_audio = manager.process_through_plugins(
        None, 
        ["Sine Generator"], 
        duration=0.1, 
        sample_rate=44100
    )
    
    if test_audio:
        print(f"Generated {len(test_audio)} samples")
        
        # Process through effect chain
        print("Processing through effect chain...")
        processed = manager.process_through_plugins(test_audio)
        
        print(f"Processed {len(processed)} samples")
    
    # Show performance stats
    print("\nPerformance statistics:")
    stats = manager.get_performance_stats()
    for plugin_name, perf in stats.items():
        print(f"  {plugin_name}: {perf['call_count']} calls, "
              f"avg {perf['average_time']*1000:.2f}ms")
    
    # Create effect chain
    print("\nCreating effect chain...")
    manager.create_effect_chain("my_chain", ["Simple Gain", "Simple Lowpass"])
    
    # Test analyzer
    print("\nRunning spectrum analysis...")
    if test_audio:
        analysis = manager.process_through_plugins(
            test_audio, 
            ["Spectrum Analyzer"], 
            sample_rate=44100
        )
        print(f"Analysis results: {analysis}")
    
    print("\nPlugin system demo completed!")


if __name__ == "__main__":
    demo_plugin_system()