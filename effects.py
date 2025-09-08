#!/usr/bin/env python3
"""
Chameleon Audio Effects - Practical audio processing effects
Lightweight and efficient implementations for real-world use
"""

import math
import struct
from typing import Optional, Tuple, Union

try:
    from .types import AudioData, get_fallback_logger
    from .logger import get_logger
    logger = get_logger()
except ImportError:
    try:
        from types import AudioData, get_fallback_logger
        logger = get_fallback_logger(__name__)
    except ImportError:
        # Complete fallback
        from typing import Tuple
        import logging
        AudioData = Tuple[bytes, int, int, int]
        logger = logging.getLogger(__name__)

def apply_fade_in(audio_data: AudioData, fade_duration: float = 0.1) -> Optional[AudioData]:
    """Apply fade-in effect to audio data"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        fade_samples = int(fade_duration * sample_rate * channels)
        if fade_samples <= 0 or fade_samples >= len(data) // 2:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        
        for i in range(min(fade_samples, len(samples))):
            fade_factor = i / fade_samples
            samples[i] = int(samples[i] * fade_factor)
        
        modified_data = struct.pack('<' + 'h' * len(samples), *samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Fade-in effect failed: {e}")
        return None

def apply_fade_out(audio_data: AudioData, fade_duration: float = 0.1) -> Optional[AudioData]:
    """Apply fade-out effect to audio data"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        fade_samples = int(fade_duration * sample_rate * channels)
        if fade_samples <= 0 or fade_samples >= len(data) // 2:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        total_samples = len(samples)
        start_fade = total_samples - fade_samples
        
        for i in range(start_fade, total_samples):
            fade_factor = (total_samples - i) / fade_samples
            samples[i] = int(samples[i] * fade_factor)
        
        modified_data = struct.pack('<' + 'h' * len(samples), *samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Fade-out effect failed: {e}")
        return None

def apply_echo(audio_data: AudioData, delay_ms: float = 200, decay: float = 0.4) -> Optional[AudioData]:
    """Apply echo effect with specified delay and decay"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        if delay_ms <= 0 or decay <= 0 or decay >= 1:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        delay_samples = int((delay_ms / 1000) * sample_rate * channels)
        
        if delay_samples <= 0 or delay_samples >= len(samples):
            return audio_data
            
        for i in range(delay_samples, len(samples)):
            echo_sample = int(samples[i - delay_samples] * decay)
            combined = samples[i] + echo_sample
            samples[i] = max(-32768, min(32767, combined))
        
        modified_data = struct.pack('<' + 'h' * len(samples), *samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Echo effect failed: {e}")
        return None

def apply_simple_reverb(audio_data: AudioData, room_size: float = 0.5, dampening: float = 0.7) -> Optional[AudioData]:
    """Apply simple reverb effect with multiple short delays"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        if room_size <= 0 or room_size > 1 or dampening <= 0 or dampening > 1:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        
        # Multiple delay lines for reverb simulation
        delays = [
            int(0.03 * sample_rate * room_size),  # 30ms base delay
            int(0.05 * sample_rate * room_size),  # 50ms
            int(0.08 * sample_rate * room_size),  # 80ms
        ]
        
        gains = [0.4, 0.3, 0.2]
        
        for delay_samples, gain in zip(delays, gains):
            if delay_samples <= 0 or delay_samples >= len(samples):
                continue
                
            for i in range(delay_samples, len(samples)):
                reverb_sample = int(samples[i - delay_samples] * gain * dampening)
                combined = samples[i] + reverb_sample
                samples[i] = max(-32768, min(32767, combined))
        
        modified_data = struct.pack('<' + 'h' * len(samples), *samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Reverb effect failed: {e}")
        return None

def change_speed(audio_data: AudioData, speed_factor: float = 1.0) -> Optional[AudioData]:
    """Change playback speed by sample skipping/interpolation"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        if speed_factor <= 0.1 or speed_factor > 4.0:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        
        if speed_factor == 1.0:
            return audio_data
            
        new_length = int(len(samples) / speed_factor)
        new_samples = []
        
        for i in range(new_length):
            source_index = int(i * speed_factor)
            if source_index < len(samples):
                new_samples.append(samples[source_index])
            else:
                new_samples.append(0)
        
        modified_data = struct.pack('<' + 'h' * len(new_samples), *new_samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Speed change failed: {e}")
        return None

def apply_amplification(audio_data: AudioData, amplification_db: float = 0.0) -> Optional[AudioData]:
    """Apply amplification in decibels"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        if amplification_db == 0.0:
            return audio_data
            
        # Convert dB to linear factor
        factor = pow(10, amplification_db / 20)
        
        if factor <= 0:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        
        for i in range(len(samples)):
            amplified = int(samples[i] * factor)
            samples[i] = max(-32768, min(32767, amplified))
        
        modified_data = struct.pack('<' + 'h' * len(samples), *samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Amplification failed: {e}")
        return None

def apply_low_pass_filter(audio_data: AudioData, cutoff_freq: float = 5000) -> Optional[AudioData]:
    """Simple low-pass filter using moving average"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        if cutoff_freq <= 0 or cutoff_freq >= sample_rate / 2:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        
        # Simple moving average filter
        window_size = max(1, int(sample_rate / cutoff_freq / 2))
        filtered_samples = []
        
        for i in range(len(samples)):
            start = max(0, i - window_size // 2)
            end = min(len(samples), i + window_size // 2 + 1)
            
            window_sum = sum(samples[start:end])
            window_count = end - start
            filtered_samples.append(int(window_sum / window_count))
        
        modified_data = struct.pack('<' + 'h' * len(filtered_samples), *filtered_samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Low-pass filter failed: {e}")
        return None

def apply_compressor(audio_data: AudioData, threshold_db: float = -20, ratio: float = 4.0) -> Optional[AudioData]:
    """Simple audio compressor"""
    try:
        data, sample_rate, channels, sample_width = audio_data
        if not data or sample_width != 2:
            return None
            
        if ratio <= 1.0:
            return audio_data
            
        samples = list(struct.unpack('<' + 'h' * (len(data) // 2), data))
        threshold = int(32768 * pow(10, threshold_db / 20))
        
        for i in range(len(samples)):
            sample_abs = abs(samples[i])
            
            if sample_abs > threshold:
                # Apply compression
                over_threshold = sample_abs - threshold
                compressed_over = over_threshold / ratio
                new_amplitude = threshold + compressed_over
                
                # Preserve sign
                if samples[i] >= 0:
                    samples[i] = int(new_amplitude)
                else:
                    samples[i] = int(-new_amplitude)
        
        modified_data = struct.pack('<' + 'h' * len(samples), *samples)
        return (modified_data, sample_rate, channels, sample_width)
        
    except Exception as e:
        logger.error(f"Compressor failed: {e}")
        return None

def chain_effects(audio_data: AudioData, effects_chain: list) -> Optional[AudioData]:
    """Apply multiple effects in sequence"""
    try:
        result = audio_data
        
        for effect_config in effects_chain:
            if not isinstance(effect_config, dict) or 'type' not in effect_config:
                continue
                
            effect_type = effect_config['type']
            params = effect_config.get('params', {})
            
            if effect_type == 'fade_in':
                result = apply_fade_in(result, **params)
            elif effect_type == 'fade_out':
                result = apply_fade_out(result, **params)
            elif effect_type == 'echo':
                result = apply_echo(result, **params)
            elif effect_type == 'reverb':
                result = apply_simple_reverb(result, **params)
            elif effect_type == 'speed':
                result = change_speed(result, **params)
            elif effect_type == 'amplify':
                result = apply_amplification(result, **params)
            elif effect_type == 'lowpass':
                result = apply_low_pass_filter(result, **params)
            elif effect_type == 'compress':
                result = apply_compressor(result, **params)
            
            if result is None:
                logger.error(f"Effect chain failed at {effect_type}")
                return None
        
        return result
        
    except Exception as e:
        logger.error(f"Effects chain failed: {e}")
        return None