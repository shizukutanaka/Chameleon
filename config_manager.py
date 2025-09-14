#!/usr/bin/env python3
"""
Configuration Management System
Simple configuration system for Chameleon Audio
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List


class Config:
    """Simple configuration manager"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._get_default_config_path()
        self.settings = self._load_defaults()
        self.load()
    
    def _get_default_config_path(self) -> str:
        """Get default config file path"""
        # Try user config directory first
        if os.name == 'nt':  # Windows
            config_dir = os.path.expandvars('%APPDATA%/Chameleon')
        else:  # Unix-like
            config_dir = os.path.expanduser('~/.config/chameleon')
        
        Path(config_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(config_dir, 'config.json')
    
    def _load_defaults(self) -> Dict[str, Any]:
        """Load default configuration"""
        return {
            'audio': {
                'sample_rate': 44100,
                'channels': 1,
                'bit_depth': 16,
                'buffer_size': 1024,
                'default_format': 'wav'
            },
            'processing': {
                'cache_enabled': True,
                'max_cache_size': 100,
                'real_time_factor_limit': 0.5,
                'max_latency_ms': 10.0,
                'error_recovery': True
            },
            'voice': {
                'default_preset': 'normal',
                'pitch_range': [0.5, 2.0],
                'formant_range': [0.5, 2.0],
                'speed_range': [0.5, 2.0],
                'gender_range': [-1.0, 1.0]
            },
            'effects': {
                'reverb_enabled': True,
                'delay_enabled': True,
                'chorus_enabled': False,
                'distortion_enabled': False,
                'default_reverb': 0.3,
                'default_delay': 0.1
            },
            'performance': {
                'optimization_level': 'balanced',  # performance, balanced, quality
                'threading_enabled': True,
                'benchmark_on_startup': False,
                'profile_performance': False
            },
            'ui': {
                'verbose': False,
                'progress_bars': True,
                'color_output': True
            }
        }
    
    def load(self) -> bool:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    self._merge_config(loaded)
                return True
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
        return False
    
    def save(self) -> bool:
        """Save configuration to file"""
        try:
            # Create directory if it doesn't exist
            config_dir = os.path.dirname(self.config_file)
            Path(config_dir).mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Warning: Could not save config: {e}")
            return False
    
    def _merge_config(self, loaded: Dict[str, Any]):
        """Merge loaded config with defaults"""
        for section, values in loaded.items():
            if section in self.settings:
                if isinstance(values, dict) and isinstance(self.settings[section], dict):
                    self.settings[section].update(values)
                else:
                    self.settings[section] = values
            else:
                self.settings[section] = values
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.settings.get(section, {}).get(key, default)
    
    def set(self, section: str, key: str, value: Any):
        """Set configuration value"""
        if section not in self.settings:
            self.settings[section] = {}
        self.settings[section][key] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self.settings.get(section, {})
    
    def set_section(self, section: str, values: Dict[str, Any]):
        """Set entire configuration section"""
        self.settings[section] = values
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.settings = self._load_defaults()
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Validate audio settings
        sample_rate = self.get('audio', 'sample_rate')
        if sample_rate not in [8000, 16000, 22050, 44100, 48000, 96000]:
            issues.append(f"Invalid sample rate: {sample_rate}")
        
        # Validate processing settings
        rtf_limit = self.get('processing', 'real_time_factor_limit')
        if rtf_limit <= 0 or rtf_limit > 1.0:
            issues.append(f"Invalid RTF limit: {rtf_limit}")
        
        # Validate voice ranges
        pitch_range = self.get('voice', 'pitch_range')
        if not (0.1 <= pitch_range[0] <= pitch_range[1] <= 5.0):
            issues.append(f"Invalid pitch range: {pitch_range}")
        
        return issues
    
    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio-specific configuration"""
        return self.get_section('audio')
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing-specific configuration"""
        return self.get_section('processing')
    
    def print_config(self):
        """Print current configuration"""
        print("Current Configuration:")
        print("=" * 50)
        for section, values in self.settings.items():
            print(f"\n[{section}]")
            if isinstance(values, dict):
                for key, value in values.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  {values}")


# Global config instance
_config_instance = None

def get_config() -> Config:
    """Get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def save_config() -> bool:
    """Save global configuration"""
    return get_config().save()


# Convenience functions for common settings
def get_sample_rate() -> int:
    """Get configured sample rate"""
    return get_config().get('audio', 'sample_rate', 44100)


def get_buffer_size() -> int:
    """Get configured buffer size"""
    return get_config().get('audio', 'buffer_size', 1024)


def is_cache_enabled() -> bool:
    """Check if caching is enabled"""
    return get_config().get('processing', 'cache_enabled', True)


def get_max_latency() -> float:
    """Get maximum allowed latency in milliseconds"""
    return get_config().get('processing', 'max_latency_ms', 10.0)


def is_verbose() -> bool:
    """Check if verbose output is enabled"""
    return get_config().get('ui', 'verbose', False)