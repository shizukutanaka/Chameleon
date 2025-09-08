"""
Chameleon Voice Processor

Lightweight, practical audio processing framework with clean architecture design.
"""

__version__ = "2.0.0"
__author__ = "Chameleon Team"
__license__ = "MIT"
__description__ = "Lightweight voice processing framework"

# Import core components for easy access
try:
    from .types import (
        AudioData, AudioInfo, AudioConstants, AudioSettings, ProcessingSettings, 
        FileSettings, ChameleonError, AudioProcessingError, FileOperationError,
        ValidationError, ConfigurationError, LogLevel, ProcessingMode
    )
    from .core import (
        generate_sine_wave, 
        write_wav_file, 
        read_wav_file, 
        get_system_capabilities,
        load_config,
        normalize_audio,
        trim_silence,
        mix_audio,
        generate_chord,
        create_silence,
        concatenate_audio,
        adjust_volume,
        detect_audio_properties,
        get_audio_summary,
        is_valid_audio_file,
        get_file_size,
        loop_audio,
        calculate_rms,
        mono_to_stereo,
        stereo_to_mono
    )
    
    # Import advanced features if available
    try:
        from .audio_formats import (
            convert_audio_file,
            get_audio_info,
            get_supported_formats,
            check_conversion_capability
        )
        from .batch_processor import (
            BatchProcessor,
            batch_generate_tones,
            batch_convert_files,
            batch_analyze_files
        )
        from .profiles import (
            get_profile_manager,
            list_profiles,
            get_profile,
            set_active_profile
        )
        from .logger import (
            configure_logging,
            get_logger,
            LogLevel
        )
        from .effects import (
            apply_fade_in,
            apply_fade_out,
            apply_echo,
            apply_simple_reverb,
            change_speed,
            apply_amplification,
            apply_low_pass_filter,
            apply_compressor,
            chain_effects
        )
        ADVANCED_FEATURES = True
    except ImportError:
        ADVANCED_FEATURES = False
    
    base_exports = [
        # Core functions
        'generate_sine_wave',
        'write_wav_file',
        'read_wav_file', 
        'get_system_capabilities',
        'load_config',
        'generate_chord',
        'normalize_audio',
        'trim_silence',
        'mix_audio',
        'create_silence',
        'concatenate_audio',
        'adjust_volume',
        'detect_audio_properties',
        'get_audio_summary',
        'is_valid_audio_file',
        'get_file_size',
        'loop_audio',
        'calculate_rms',
        'mono_to_stereo',
        'stereo_to_mono',
        # Types and constants
        'AudioData',
        'AudioInfo', 
        'AudioConstants',
        'AudioSettings',
        'ProcessingSettings',
        'FileSettings',
        'ChameleonError',
        'AudioProcessingError',
        'FileOperationError',
        'ValidationError',
        'ConfigurationError',
        'LogLevel',
        'ProcessingMode',
        # Package metadata
        '__version__',
        '__author__',
        '__license__',
        '__description__'
    ]
    
    if ADVANCED_FEATURES:
        advanced_exports = [
            'convert_audio_file',
            'get_audio_info',
            'get_supported_formats',
            'check_conversion_capability',
            'BatchProcessor',
            'batch_convert_files',
            'batch_analyze_files',
            'get_profile_manager',
            'list_profiles', 
            'get_profile',
            'set_active_profile',
            'configure_logging',
            'get_logger',
            'LogLevel'
        ]
        __all__ = base_exports + advanced_exports
    else:
        __all__ = base_exports
except ImportError:
    # Handle case where dependencies are not available
    __all__ = [
        '__version__',
        '__author__',
        '__license__',
        '__description__'
    ]


def main():
    """Main CLI entry point."""
    from .cli import main as cli_main
    return cli_main()

if __name__ == "__main__":
    main()