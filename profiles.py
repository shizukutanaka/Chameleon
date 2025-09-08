#!/usr/bin/env python3
"""
Configuration profiles and presets system for Chameleon.
Provides predefined and custom settings for different use cases.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

# Import types and logger
try:
    from .types import (
        AudioSettings, ProcessingSettings, FileSettings as OutputSettings,
        AudioConstants, get_fallback_logger
    )
    from .logger import get_logger
    logger = get_logger()
except ImportError:
    try:
        from types import (
            AudioSettings, ProcessingSettings, FileSettings as OutputSettings,
            AudioConstants, get_fallback_logger
        )
        logger = get_fallback_logger(__name__)
    except ImportError:
        # Complete fallback
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        
        @dataclass
        class AudioSettings:
            sample_rate: int = 44100
            channels: int = 1
            bit_depth: int = 16
            format: str = 'wav'
            quality: str = 'high'

        @dataclass
        class ProcessingSettings:
            max_workers: int = 4
            enable_cache: bool = True
            cache_size: int = 32
            fast_mode: bool = True
            parallel_processing: bool = True

        @dataclass  
        class OutputSettings:
            base_output_dir: str = './output'
            organize_by_date: bool = False
            organize_by_format: bool = True
            preserve_metadata: bool = True
            
        class AudioConstants:
            SAMPLE_RATE_44K = 44100
            QUALITY_HIGH = 'high'

@dataclass
class LoggingSettings:
    """Logging configuration settings"""
    level: str = 'INFO'
    file_enabled: bool = True
    console_colors: bool = True
    performance_logging: bool = True

@dataclass
class Profile:
    """Complete configuration profile"""
    name: str
    description: str
    audio: AudioSettings
    processing: ProcessingSettings
    output: OutputSettings
    logging: LoggingSettings
    created_at: str = None
    modified_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()

class ProfileManager:
    """Manages configuration profiles and presets"""
    
    def __init__(self, profiles_dir: str = None):
        self.profiles_dir = Path(profiles_dir or os.path.expanduser("~/.chameleon/profiles"))
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_profile: Optional[Profile] = None
        self.built_in_profiles = self._create_builtin_profiles()
        
        logger.info(f"Profile manager initialized with directory: {self.profiles_dir}")
    
    def _create_builtin_profiles(self) -> Dict[str, Profile]:
        """Create built-in profiles for common use cases"""
        profiles = {}
        
        # Podcast production profile
        profiles['podcast'] = Profile(
            name='podcast',
            description='Optimized for podcast and voice recording production',
            audio=AudioSettings(
                sample_rate=44100,
                channels=1,
                bit_depth=16,
                format='mp3',
                quality='high'
            ),
            processing=ProcessingSettings(
                max_workers=2,
                enable_cache=True,
                cache_size=64,
                fast_mode=True,
                parallel_processing=True
            ),
            output=OutputSettings(
                base_output_dir='./podcast_output',
                organize_by_date=True,
                organize_by_format=False,
                preserve_metadata=True
            ),
            logging=LoggingSettings(
                level='INFO',
                file_enabled=True,
                console_colors=True,
                performance_logging=True
            )
        )
        
        # Music production profile  
        profiles['music'] = Profile(
            name='music',
            description='High quality settings for music production and mastering',
            audio=AudioSettings(
                sample_rate=48000,
                channels=2,
                bit_depth=24,
                format='flac',
                quality='high'
            ),
            processing=ProcessingSettings(
                max_workers=8,
                enable_cache=True,
                cache_size=128,
                fast_mode=False,
                parallel_processing=True
            ),
            output=OutputSettings(
                base_output_dir='./music_output',
                organize_by_date=False,
                organize_by_format=True,
                preserve_metadata=True
            ),
            logging=LoggingSettings(
                level='DEBUG',
                file_enabled=True,
                console_colors=True,
                performance_logging=True
            )
        )
        
        # Game audio profile
        profiles['game'] = Profile(
            name='game',
            description='Optimized for game audio processing and sound effects',
            audio=AudioSettings(
                sample_rate=44100,
                channels=1,
                bit_depth=16,
                format='ogg',
                quality='medium'
            ),
            processing=ProcessingSettings(
                max_workers=6,
                enable_cache=True,
                cache_size=32,
                fast_mode=True,
                parallel_processing=True
            ),
            output=OutputSettings(
                base_output_dir='./game_audio',
                organize_by_date=False,
                organize_by_format=True,
                preserve_metadata=False
            ),
            logging=LoggingSettings(
                level='WARNING',
                file_enabled=False,
                console_colors=True,
                performance_logging=False
            )
        )
        
        # Quick processing profile
        profiles['quick'] = Profile(
            name='quick',
            description='Fast processing for quick tests and experiments',
            audio=AudioSettings(
                sample_rate=22050,
                channels=1,
                bit_depth=16,
                format='wav',
                quality='medium'
            ),
            processing=ProcessingSettings(
                max_workers=4,
                enable_cache=True,
                cache_size=16,
                fast_mode=True,
                parallel_processing=True
            ),
            output=OutputSettings(
                base_output_dir='./temp_output',
                organize_by_date=False,
                organize_by_format=False,
                preserve_metadata=False
            ),
            logging=LoggingSettings(
                level='ERROR',
                file_enabled=False,
                console_colors=False,
                performance_logging=False
            )
        )
        
        # Archive quality profile
        profiles['archive'] = Profile(
            name='archive',
            description='Maximum quality settings for archival and preservation',
            audio=AudioSettings(
                sample_rate=96000,
                channels=2,
                bit_depth=24,
                format='flac',
                quality='high'
            ),
            processing=ProcessingSettings(
                max_workers=2,
                enable_cache=False,
                cache_size=256,
                fast_mode=False,
                parallel_processing=False
            ),
            output=OutputSettings(
                base_output_dir='./archive',
                organize_by_date=True,
                organize_by_format=True,
                preserve_metadata=True
            ),
            logging=LoggingSettings(
                level='DEBUG',
                file_enabled=True,
                console_colors=True,
                performance_logging=True
            )
        )
        
        return profiles
    
    def list_profiles(self, include_builtin: bool = True, include_custom: bool = True) -> List[str]:
        """List available profiles"""
        profiles = []
        
        if include_builtin:
            profiles.extend(list(self.built_in_profiles.keys()))
        
        if include_custom:
            custom_profiles = self._list_custom_profiles()
            profiles.extend(custom_profiles)
        
        return sorted(set(profiles))
    
    def _list_custom_profiles(self) -> List[str]:
        """List custom user profiles"""
        profiles = []
        for profile_file in self.profiles_dir.glob("*.yaml"):
            profiles.append(profile_file.stem)
        for profile_file in self.profiles_dir.glob("*.json"):
            profiles.append(profile_file.stem)
        return profiles
    
    def get_profile(self, name: str) -> Optional[Profile]:
        """Get profile by name"""
        # Check built-in profiles first
        if name in self.built_in_profiles:
            return self.built_in_profiles[name]
        
        # Check custom profiles
        profile_path = self._get_profile_path(name)
        if profile_path and profile_path.exists():
            return self._load_profile_from_file(profile_path)
        
        logger.warning(f"Profile not found: {name}")
        return None
    
    def _get_profile_path(self, name: str) -> Optional[Path]:
        """Get file path for custom profile"""
        yaml_path = self.profiles_dir / f"{name}.yaml"
        json_path = self.profiles_dir / f"{name}.json"
        
        if yaml_path.exists():
            return yaml_path
        elif json_path.exists():
            return json_path
        
        return None
    
    def _load_profile_from_file(self, profile_path: Path) -> Optional[Profile]:
        """Load profile from file"""
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                if profile_path.suffix == '.yaml':
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Convert nested dictionaries to dataclass objects
            profile = Profile(
                name=data['name'],
                description=data['description'],
                audio=AudioSettings(**data['audio']),
                processing=ProcessingSettings(**data['processing']),
                output=OutputSettings(**data['output']),
                logging=LoggingSettings(**data['logging']),
                created_at=data.get('created_at'),
                modified_at=data.get('modified_at')
            )
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to load profile from {profile_path}: {e}")
            return None
    
    def save_profile(self, profile: Profile, format: str = 'yaml') -> bool:
        """Save custom profile to file"""
        try:
            # Update modification time
            profile.modified_at = datetime.now().isoformat()
            
            # Create file path
            extension = 'yaml' if format == 'yaml' else 'json'
            profile_path = self.profiles_dir / f"{profile.name}.{extension}"
            
            # Convert profile to dictionary
            profile_dict = asdict(profile)
            
            # Save to file
            with open(profile_path, 'w', encoding='utf-8') as f:
                if format == 'yaml':
                    yaml.safe_dump(profile_dict, f, default_flow_style=False, indent=2)
                else:
                    json.dump(profile_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Profile saved: {profile.name} -> {profile_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save profile {profile.name}: {e}")
            return False
    
    def delete_profile(self, name: str) -> bool:
        """Delete custom profile"""
        if name in self.built_in_profiles:
            logger.error(f"Cannot delete built-in profile: {name}")
            return False
        
        profile_path = self._get_profile_path(name)
        if profile_path and profile_path.exists():
            try:
                profile_path.unlink()
                logger.info(f"Profile deleted: {name}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete profile {name}: {e}")
                return False
        
        logger.warning(f"Profile file not found for deletion: {name}")
        return False
    
    def set_active_profile(self, name: str) -> bool:
        """Set the active profile"""
        profile = self.get_profile(name)
        if profile:
            self.current_profile = profile
            logger.info(f"Active profile set to: {name}")
            return True
        return False
    
    def get_active_profile(self) -> Optional[Profile]:
        """Get the currently active profile"""
        return self.current_profile
    
    def create_profile_from_template(self, name: str, description: str, 
                                   base_profile: str = 'podcast') -> Optional[Profile]:
        """Create a new profile based on an existing template"""
        template = self.get_profile(base_profile)
        if not template:
            logger.error(f"Base profile not found: {base_profile}")
            return None
        
        # Create new profile with updated name and description
        new_profile = Profile(
            name=name,
            description=description,
            audio=AudioSettings(**asdict(template.audio)),
            processing=ProcessingSettings(**asdict(template.processing)),
            output=OutputSettings(**asdict(template.output)),
            logging=LoggingSettings(**asdict(template.logging))
        )
        
        return new_profile
    
    def export_profile(self, name: str, export_path: str, format: str = 'yaml') -> bool:
        """Export profile to specified location"""
        profile = self.get_profile(name)
        if not profile:
            return False
        
        try:
            profile_dict = asdict(profile)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                if format == 'yaml':
                    yaml.safe_dump(profile_dict, f, default_flow_style=False, indent=2)
                else:
                    json.dump(profile_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Profile exported: {name} -> {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export profile {name}: {e}")
            return False
    
    def import_profile(self, import_path: str, new_name: str = None) -> bool:
        """Import profile from file"""
        try:
            import_path = Path(import_path)
            if not import_path.exists():
                logger.error(f"Import file not found: {import_path}")
                return False
            
            with open(import_path, 'r', encoding='utf-8') as f:
                if import_path.suffix == '.yaml':
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Create profile object
            profile = Profile(
                name=new_name or data['name'],
                description=data['description'],
                audio=AudioSettings(**data['audio']),
                processing=ProcessingSettings(**data['processing']),
                output=OutputSettings(**data['output']),
                logging=LoggingSettings(**data['logging'])
            )
            
            # Save as custom profile
            return self.save_profile(profile)
            
        except Exception as e:
            logger.error(f"Failed to import profile from {import_path}: {e}")
            return False
    
    def get_profile_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a profile"""
        profile = self.get_profile(name)
        if not profile:
            return None
        
        info = {
            'name': profile.name,
            'description': profile.description,
            'created_at': profile.created_at,
            'modified_at': profile.modified_at,
            'is_builtin': name in self.built_in_profiles,
            'settings': {
                'audio': asdict(profile.audio),
                'processing': asdict(profile.processing),
                'output': asdict(profile.output),
                'logging': asdict(profile.logging)
            }
        }
        
        return info

# Global profile manager instance
_profile_manager = None

def get_profile_manager() -> ProfileManager:
    """Get or create global profile manager"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager

def list_profiles(include_builtin: bool = True, include_custom: bool = True) -> List[str]:
    """Convenience function to list profiles"""
    return get_profile_manager().list_profiles(include_builtin, include_custom)

def get_profile(name: str) -> Optional[Profile]:
    """Convenience function to get profile"""
    return get_profile_manager().get_profile(name)

def set_active_profile(name: str) -> bool:
    """Convenience function to set active profile"""
    return get_profile_manager().set_active_profile(name)

def get_active_profile() -> Optional[Profile]:
    """Convenience function to get active profile"""
    return get_profile_manager().get_active_profile()

if __name__ == '__main__':
    # Test profile system
    print("Profile System Test")
    print("=" * 40)
    
    manager = ProfileManager('./test_profiles')
    
    # List built-in profiles
    profiles = manager.list_profiles()
    print(f"Available profiles: {profiles}")
    
    # Test profile retrieval
    podcast_profile = manager.get_profile('podcast')
    if podcast_profile:
        print(f"\nPodcast profile:")
        print(f"Description: {podcast_profile.description}")
        print(f"Audio settings: {asdict(podcast_profile.audio)}")
    
    # Test custom profile creation
    custom_profile = manager.create_profile_from_template(
        'my_custom', 
        'My custom audio profile', 
        'music'
    )
    
    if custom_profile:
        # Modify some settings
        custom_profile.audio.sample_rate = 48000
        custom_profile.processing.max_workers = 6
        
        # Save profile
        success = manager.save_profile(custom_profile)
        print(f"\nCustom profile saved: {success}")
        
        # Test profile info
        info = manager.get_profile_info('my_custom')
        if info:
            print(f"Custom profile info: {info['name']} - {info['description']}")
    
    print("\nProfile system test completed")