"""
Chameleon Audio Processing
Simple, reliable audio processing tools
"""

# Version removed for simplicity
__author__ = "Chameleon Team"
__license__ = "MIT"

# Import core functionality if available
try:
    from .core import (
        generate_sine_wave,
        write_wav_file,
        read_wav_file,
        apply_volume,
        get_system_capabilities,
        benchmark_generation,
        load_config,
        AudioError,
        # Constants
        SAMPLE_RATE_44K,
        CHANNELS_MONO,
        SAMPLE_WIDTH_16,
        PCM_MAX,
        PCM_MIN,
        PCM_SCALE,
        FREQ_MIN,
        FREQ_MAX,
        VOLUME_MAX,
        AMPLITUDE_DEFAULT,
        TEST_DURATION
    )
    
    from .audio_analyzer import (
        AudioAnalyzer,
        analyze_file,
        generate_report
    )
    
    from .batch_processor import BatchProcessor
    
    from .utils import (
        format_duration,
        format_size,
        ensure_dir,
        safe_filename,
        get_file_info,
        validate_audio_file_path,
        list_audio_files,
        SimpleTimer,
        log_error,
        handle_error,
        SUPPORTED_AUDIO_FORMATS,
        is_audio_file,
        validate_audio_file_path_extended
    )
    
    CORE_AVAILABLE = True
    
    __all__ = [
        # Core functions
        'generate_sine_wave',
        'write_wav_file',
        'read_wav_file',
        'apply_volume',
        'get_system_capabilities',
        'benchmark_generation',
        'load_config',
        'AudioError',
        # Constants
        'SAMPLE_RATE_44K',
        'CHANNELS_MONO',
        'SAMPLE_WIDTH_16',
        'PCM_MAX',
        'PCM_MIN',
        'PCM_SCALE',
        'FREQ_MIN',
        'FREQ_MAX',
        'VOLUME_MAX',
        'AMPLITUDE_DEFAULT',
        'TEST_DURATION',
        # Analyzer
        'AudioAnalyzer',
        'analyze_file',
        'generate_report',
        # Batch processing
        'BatchProcessor',
        # Utils
        'format_duration',
        'format_size',
        'ensure_dir',
        'safe_filename',
        'list_audio_files',
        'SimpleTimer',
        'log_error',
        'handle_error',
        'SUPPORTED_AUDIO_FORMATS',
        'is_audio_file',
        'validate_audio_file_path_extended',
        # Metadata
        '__author__',
        '__license__'
    ]
    
except ImportError:
    # Minimal exports if core not available
    CORE_AVAILABLE = False
    __all__ = [
        '__author__',
        '__license__'
    ]

# Entry point moved to chameleon.py to avoid duplication