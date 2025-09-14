#!/usr/bin/env python3
"""
Plugin System for Chameleon Audio
Simple plugin architecture for extensible audio processing
"""

import importlib
import inspect
import os
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional, Type
from abc import ABC, abstractmethod

import audio_utils


class AudioPlugin(ABC):
    """Base class for audio plugins"""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.parameters = {}
    
    @abstractmethod
    def process(self, audio_data: bytes, sample_rate: int = 44100, **kwargs) -> bytes:
        """Process audio data and return modified data"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get plugin parameters and their default values"""
        pass
    
    def set_parameter(self, name: str, value: Any):
        """Set a plugin parameter"""
        if name in self.get_parameters():
            self.parameters[name] = value
    
    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get a plugin parameter value"""
        return self.parameters.get(name, self.get_parameters().get(name, default))
    
    def enable(self):
        """Enable the plugin"""
        self.enabled = True
    
    def disable(self):
        """Disable the plugin"""
        self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled"""
        return self.enabled


class ReverbPlugin(AudioPlugin):
    """Simple reverb effect plugin"""
    
    def __init__(self):
        super().__init__("Reverb")
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'room_size': 0.5,
            'damping': 0.5,
            'wet_level': 0.3,
            'dry_level': 0.7
        }
    
    def process(self, audio_data: bytes, sample_rate: int = 44100, **kwargs) -> bytes:
        if not self.enabled:
            return audio_data
        
        samples = audio_utils.bytes_to_samples(audio_data)
        if not samples:
            return audio_data
        
        room_size = self.get_parameter('room_size', 0.5)
        wet_level = self.get_parameter('wet_level', 0.3)
        dry_level = self.get_parameter('dry_level', 0.7)
        
        # Simple reverb using delay lines
        delay_time = int(room_size * 0.05 * sample_rate)  # Up to 50ms delay
        delay_buffer = [0] * delay_time
        
        processed = []
        for i, sample in enumerate(samples):
            # Get delayed signal
            delayed = delay_buffer[i % delay_time] if delay_time > 0 else 0
            
            # Mix dry and wet signals
            output = int(sample * dry_level + delayed * wet_level)
            processed.append(audio_utils.clamp(output, -32768, 32767))
            
            # Update delay buffer
            if delay_time > 0:
                delay_buffer[i % delay_time] = int(sample * 0.5 + delayed * 0.3)
        
        return audio_utils.samples_to_bytes(processed)


class DistortionPlugin(AudioPlugin):
    """Distortion effect plugin"""
    
    def __init__(self):
        super().__init__("Distortion")
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'drive': 1.5,
            'tone': 0.5,
            'level': 0.8
        }
    
    def process(self, audio_data: bytes, sample_rate: int = 44100, **kwargs) -> bytes:
        if not self.enabled:
            return audio_data
        
        samples = audio_utils.bytes_to_samples(audio_data)
        if not samples:
            return audio_data
        
        drive = self.get_parameter('drive', 1.5)
        level = self.get_parameter('level', 0.8)
        
        processed = []
        for sample in samples:
            # Apply overdrive
            driven = sample * drive
            
            # Soft clipping distortion
            if driven > 16000:
                driven = 16000 + (driven - 16000) * 0.3
            elif driven < -16000:
                driven = -16000 + (driven + 16000) * 0.3
            
            # Apply output level
            output = int(driven * level)
            processed.append(audio_utils.clamp(output, -32768, 32767))
        
        return audio_utils.samples_to_bytes(processed)


class ChorusPlugin(AudioPlugin):
    """Chorus effect plugin"""
    
    def __init__(self):
        super().__init__("Chorus")
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'depth': 0.5,
            'rate': 2.0,
            'mix': 0.5
        }
    
    def process(self, audio_data: bytes, sample_rate: int = 44100, **kwargs) -> bytes:
        if not self.enabled:
            return audio_data
        
        samples = audio_utils.bytes_to_samples(audio_data)
        if not samples:
            return audio_data
        
        depth = self.get_parameter('depth', 0.5)
        rate = self.get_parameter('rate', 2.0)
        mix = self.get_parameter('mix', 0.5)
        
        # Simple chorus using modulated delay
        max_delay = int(0.020 * sample_rate)  # 20ms max delay
        delay_buffer = [0] * max_delay
        
        processed = []
        for i, sample in enumerate(samples):
            # Calculate modulated delay time
            lfo = audio_utils.fast_sin(2 * 3.14159 * rate * i / sample_rate)
            delay_samples = int(max_delay * 0.5 * (1 + depth * lfo))
            delay_samples = max(1, min(delay_samples, max_delay - 1))
            
            # Get delayed sample
            delayed = delay_buffer[i % delay_samples] if delay_samples > 0 else 0
            
            # Mix original and delayed
            output = int(sample * (1 - mix) + delayed * mix)
            processed.append(audio_utils.clamp(output, -32768, 32767))
            
            # Update delay buffer
            delay_buffer[i % max_delay] = sample
        
        return audio_utils.samples_to_bytes(processed)


class PluginManager:
    """Manage and coordinate audio plugins"""
    
    def __init__(self):
        self.plugins: Dict[str, AudioPlugin] = {}
        self.plugin_chain: List[str] = []
        
        # Load built-in plugins
        self._load_builtin_plugins()
    
    def _load_builtin_plugins(self):
        """Load built-in plugins"""
        builtin_plugins = [
            ReverbPlugin(),
            DistortionPlugin(),
            ChorusPlugin()
        ]
        
        for plugin in builtin_plugins:
            self.register_plugin(plugin)
    
    def register_plugin(self, plugin: AudioPlugin) -> bool:
        """Register a plugin"""
        if not isinstance(plugin, AudioPlugin):
            return False
        
        self.plugins[plugin.name] = plugin
        return True
    
    def unregister_plugin(self, name: str) -> bool:
        """Unregister a plugin"""
        if name in self.plugins:
            if name in self.plugin_chain:
                self.plugin_chain.remove(name)
            del self.plugins[name]
            return True
        return False
    
    def get_plugin(self, name: str) -> Optional[AudioPlugin]:
        """Get a plugin by name"""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all available plugins"""
        return list(self.plugins.keys())
    
    def add_to_chain(self, plugin_name: str) -> bool:
        """Add plugin to processing chain"""
        if plugin_name in self.plugins and plugin_name not in self.plugin_chain:
            self.plugin_chain.append(plugin_name)
            return True
        return False
    
    def remove_from_chain(self, plugin_name: str) -> bool:
        """Remove plugin from processing chain"""
        if plugin_name in self.plugin_chain:
            self.plugin_chain.remove(plugin_name)
            return True
        return False
    
    def clear_chain(self):
        """Clear the plugin processing chain"""
        self.plugin_chain.clear()
    
    def get_chain(self) -> List[str]:
        """Get current plugin chain"""
        return self.plugin_chain.copy()
    
    def process_chain(self, audio_data: bytes, sample_rate: int = 44100) -> bytes:
        """Process audio through the plugin chain"""
        processed_data = audio_data
        
        for plugin_name in self.plugin_chain:
            plugin = self.plugins.get(plugin_name)
            if plugin and plugin.is_enabled():
                try:
                    processed_data = plugin.process(processed_data, sample_rate)
                except Exception as e:
                    print(f"Plugin {plugin_name} failed: {e}")
                    # Continue with unprocessed data
                    continue
        
        return processed_data
    
    def set_plugin_parameter(self, plugin_name: str, param_name: str, value: Any) -> bool:
        """Set a parameter for a specific plugin"""
        plugin = self.plugins.get(plugin_name)
        if plugin:
            plugin.set_parameter(param_name, value)
            return True
        return False
    
    def get_plugin_parameters(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get parameters for a specific plugin"""
        plugin = self.plugins.get(plugin_name)
        if plugin:
            return plugin.get_parameters()
        return None
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin"""
        plugin = self.plugins.get(plugin_name)
        if plugin:
            plugin.enable()
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin"""
        plugin = self.plugins.get(plugin_name)
        if plugin:
            plugin.disable()
            return True
        return False
    
    def load_plugin_from_file(self, filepath: str) -> bool:
        """Load a plugin from a Python file (experimental)"""
        try:
            # This is a simplified plugin loader
            # In production, you'd want more security checks
            path = Path(filepath)
            if not path.exists() or path.suffix != '.py':
                return False
            
            # Import the module
            spec = importlib.util.spec_from_file_location("plugin_module", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Look for AudioPlugin subclasses
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, AudioPlugin) and 
                    obj != AudioPlugin and 
                    hasattr(obj, '__init__')):
                    
                    # Instantiate and register the plugin
                    plugin_instance = obj()
                    return self.register_plugin(plugin_instance)
            
            return False
            
        except Exception as e:
            print(f"Failed to load plugin from {filepath}: {e}")
            return False
    
    def save_chain_preset(self, name: str, filepath: str) -> bool:
        """Save current plugin chain as a preset"""
        try:
            preset = {
                'name': name,
                'chain': self.plugin_chain.copy(),
                'parameters': {}
            }
            
            # Save plugin parameters
            for plugin_name in self.plugin_chain:
                plugin = self.plugins.get(plugin_name)
                if plugin:
                    preset['parameters'][plugin_name] = plugin.parameters.copy()
            
            import json
            with open(filepath, 'w') as f:
                json.dump(preset, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Failed to save preset: {e}")
            return False
    
    def load_chain_preset(self, filepath: str) -> bool:
        """Load a plugin chain preset"""
        try:
            import json
            with open(filepath, 'r') as f:
                preset = json.load(f)
            
            # Clear current chain
            self.clear_chain()
            
            # Load chain
            for plugin_name in preset.get('chain', []):
                if plugin_name in self.plugins:
                    self.add_to_chain(plugin_name)
            
            # Load parameters
            parameters = preset.get('parameters', {})
            for plugin_name, params in parameters.items():
                plugin = self.plugins.get(plugin_name)
                if plugin:
                    for param_name, value in params.items():
                        plugin.set_parameter(param_name, value)
            
            return True
            
        except Exception as e:
            print(f"Failed to load preset: {e}")
            return False


# Global plugin manager instance
plugin_manager = PluginManager()


# Convenience functions
def process_with_plugins(audio_data: bytes, plugin_names: List[str], 
                        sample_rate: int = 44100) -> bytes:
    """Process audio with specific plugins"""
    manager = PluginManager()
    manager.clear_chain()
    
    for name in plugin_names:
        manager.add_to_chain(name)
    
    return manager.process_chain(audio_data, sample_rate)


def apply_reverb(audio_data: bytes, room_size: float = 0.5, 
                wet_level: float = 0.3) -> bytes:
    """Apply reverb effect to audio"""
    plugin = ReverbPlugin()
    plugin.set_parameter('room_size', room_size)
    plugin.set_parameter('wet_level', wet_level)
    return plugin.process(audio_data)


def apply_distortion(audio_data: bytes, drive: float = 1.5, 
                    level: float = 0.8) -> bytes:
    """Apply distortion effect to audio"""
    plugin = DistortionPlugin()
    plugin.set_parameter('drive', drive)
    plugin.set_parameter('level', level)
    return plugin.process(audio_data)


def apply_chorus(audio_data: bytes, depth: float = 0.5, 
                rate: float = 2.0, mix: float = 0.5) -> bytes:
    """Apply chorus effect to audio"""
    plugin = ChorusPlugin()
    plugin.set_parameter('depth', depth)
    plugin.set_parameter('rate', rate)
    plugin.set_parameter('mix', mix)
    return plugin.process(audio_data)