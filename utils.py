#!/usr/bin/env python3
"""
Practical utility functions for Chameleon audio processing.
Frequently used operations and helper functions.
"""

import os
import sys
import time
import math
import struct
import tempfile
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from dataclasses import dataclass

# Import core modules
try:
    from .core import AudioData, generate_sine_wave, write_wav_file, read_wav_file, generate_chord
    from .logger import get_logger
    from .validation import AudioValidator, FileValidator, DataValidator
    logger = get_logger()
except ImportError:
    # Fallback for standalone usage
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    AudioData = Tuple[bytes, int, int, int]

@dataclass
class AudioFileInfo:
    """Enhanced audio file information"""
    filepath: str
    format: str
    sample_rate: int
    channels: int
    duration: float
    bit_depth: int
    file_size_mb: float
    is_valid: bool
    estimated_quality: str

class AudioMixer:
    """Practical audio mixing utilities"""
    
    @staticmethod
    def crossfade(audio1: AudioData, audio2: AudioData, 
                 crossfade_duration: float = 0.5) -> Optional[AudioData]:
        """Create smooth crossfade between two audio clips"""
        try:
            data1, sr1, ch1, sw1 = audio1
            data2, sr2, ch2, sw2 = audio2
            
            # Validate compatibility
            if sr1 != sr2 or ch1 != ch2 or sw1 != sw2:
                logger.error("Audio parameters don't match for crossfade")
                return None
            
            if sw1 != 2:  # Only support 16-bit for now
                logger.error("Only 16-bit audio supported for crossfade")
                return None
            
            samples1 = list(struct.unpack('<' + 'h' * (len(data1) // 2), data1))
            samples2 = list(struct.unpack('<' + 'h' * (len(data2) // 2), data2))
            
            # Calculate crossfade samples
            crossfade_samples = int(crossfade_duration * sr1)
            
            if len(samples1) < crossfade_samples or len(samples2) < crossfade_samples:
                logger.error("Audio clips too short for requested crossfade duration")
                return None
            
            # Create crossfaded section
            fade_section = []
            for i in range(crossfade_samples):
                # Linear crossfade
                ratio = i / crossfade_samples
                sample1_idx = len(samples1) - crossfade_samples + i
                sample2_idx = i
                
                mixed_sample = int(samples1[sample1_idx] * (1 - ratio) + 
                                 samples2[sample2_idx] * ratio)
                fade_section.append(max(-32768, min(32767, mixed_sample)))
            
            # Combine: audio1 (without fade-out) + crossfade + audio2 (without fade-in)
            result_samples = (samples1[:-crossfade_samples] + 
                            fade_section + 
                            samples2[crossfade_samples:])
            
            result_data = struct.pack('<' + 'h' * len(result_samples), *result_samples)
            
            return (result_data, sr1, ch1, sw1)
            
        except Exception as e:
            logger.error(f"Crossfade operation failed: {e}")
            return None
    
    @staticmethod
    def create_silence(duration: float, sample_rate: int = 44100, 
                      channels: int = 1) -> AudioData:
        """Generate silence of specified duration"""
        frames = int(duration * sample_rate)
        silence_data = bytes(frames * channels * 2)  # 16-bit = 2 bytes
        return (silence_data, sample_rate, channels, 2)
    
    @staticmethod
    def loop_audio(audio_data: AudioData, loop_count: int) -> Optional[AudioData]:
        """Loop audio data specified number of times"""
        try:
            if loop_count <= 0:
                return None
            
            if loop_count == 1:
                return audio_data
            
            data, sample_rate, channels, sample_width = audio_data
            
            # Simply repeat the data
            looped_data = data * loop_count
            
            return (looped_data, sample_rate, channels, sample_width)
            
        except Exception as e:
            logger.error(f"Audio looping failed: {e}")
            return None

class AudioAnalyzer:
    """Practical audio analysis utilities"""
    
    @staticmethod
    def detect_silence_periods(audio_data: AudioData, 
                              threshold: float = 0.01,
                              min_silence_duration: float = 0.1) -> List[Tuple[float, float]]:
        """Detect periods of silence in audio"""
        try:
            data, sample_rate, channels, sample_width = audio_data
            
            if sample_width != 2:
                logger.error("Only 16-bit audio supported for silence detection")
                return []
            
            samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            
            # Convert threshold to absolute value
            threshold_abs = int(threshold * 32767)
            min_samples = int(min_silence_duration * sample_rate)
            
            silence_periods = []
            in_silence = False
            silence_start = 0
            
            for i, sample in enumerate(samples):
                is_silent = abs(sample) < threshold_abs
                
                if is_silent and not in_silence:
                    # Start of silence
                    silence_start = i
                    in_silence = True
                elif not is_silent and in_silence:
                    # End of silence
                    silence_length = i - silence_start
                    if silence_length >= min_samples:
                        start_time = silence_start / sample_rate
                        end_time = i / sample_rate
                        silence_periods.append((start_time, end_time))
                    in_silence = False
            
            # Handle silence at end
            if in_silence:
                silence_length = len(samples) - silence_start
                if silence_length >= min_samples:
                    start_time = silence_start / sample_rate
                    end_time = len(samples) / sample_rate
                    silence_periods.append((start_time, end_time))
            
            return silence_periods
            
        except Exception as e:
            logger.error(f"Silence detection failed: {e}")
            return []
    
    @staticmethod
    def calculate_rms(audio_data: AudioData) -> Optional[float]:
        """Calculate RMS (Root Mean Square) level of audio"""
        try:
            data, sample_rate, channels, sample_width = audio_data
            
            if sample_width != 2:
                return None
            
            samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            
            if not samples:
                return 0.0
            
            # Calculate RMS
            sum_squares = sum(sample * sample for sample in samples)
            rms = math.sqrt(sum_squares / len(samples))
            
            # Normalize to 0-1 range
            return rms / 32767.0
            
        except Exception as e:
            logger.error(f"RMS calculation failed: {e}")
            return None
    
    @staticmethod
    def find_audio_peaks(audio_data: AudioData, 
                        num_peaks: int = 10) -> List[Tuple[float, float]]:
        """Find audio peaks (time, amplitude)"""
        try:
            data, sample_rate, channels, sample_width = audio_data
            
            if sample_width != 2:
                return []
            
            samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            
            # Find local maxima
            peaks = []
            window_size = sample_rate // 10  # 100ms window
            
            for i in range(window_size, len(samples) - window_size, window_size):
                window = samples[i - window_size:i + window_size]
                max_value = max(abs(s) for s in window)
                max_idx = i - window_size + window.index(max_value)
                
                time_position = max_idx / sample_rate
                amplitude = max_value / 32767.0
                peaks.append((time_position, amplitude))
            
            # Sort by amplitude and return top N
            peaks.sort(key=lambda x: x[1], reverse=True)
            return peaks[:num_peaks]
            
        except Exception as e:
            logger.error(f"Peak detection failed: {e}")
            return []

class AudioConverter:
    """Practical audio conversion utilities"""
    
    @staticmethod
    def change_sample_rate(audio_data: AudioData, 
                          new_sample_rate: int,
                          quality: str = 'medium') -> Optional[AudioData]:
        """Simple sample rate conversion using linear interpolation"""
        try:
            data, old_sample_rate, channels, sample_width = audio_data
            
            if old_sample_rate == new_sample_rate:
                return audio_data
            
            if sample_width != 2:
                logger.error("Only 16-bit audio supported for sample rate conversion")
                return None
            
            old_samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            
            # Calculate conversion ratio
            ratio = new_sample_rate / old_sample_rate
            new_length = int(len(old_samples) * ratio)
            
            new_samples = []
            for i in range(new_length):
                # Linear interpolation
                old_index = i / ratio
                old_index_int = int(old_index)
                fraction = old_index - old_index_int
                
                if old_index_int < len(old_samples) - 1:
                    sample1 = old_samples[old_index_int]
                    sample2 = old_samples[old_index_int + 1]
                    interpolated = int(sample1 + (sample2 - sample1) * fraction)
                else:
                    interpolated = old_samples[-1] if old_samples else 0
                
                new_samples.append(max(-32768, min(32767, interpolated)))
            
            new_data = struct.pack('<' + 'h' * len(new_samples), *new_samples)
            
            return (new_data, new_sample_rate, channels, sample_width)
            
        except Exception as e:
            logger.error(f"Sample rate conversion failed: {e}")
            return None
    
    @staticmethod
    def mono_to_stereo(audio_data: AudioData) -> Optional[AudioData]:
        """Convert mono audio to stereo by duplicating channel"""
        try:
            data, sample_rate, channels, sample_width = audio_data
            
            if channels != 1:
                logger.warning("Audio is not mono")
                return audio_data
            
            if sample_width != 2:
                logger.error("Only 16-bit audio supported")
                return None
            
            mono_samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            
            # Duplicate each sample for stereo
            stereo_samples = []
            for sample in mono_samples:
                stereo_samples.extend([sample, sample])
            
            stereo_data = struct.pack('<' + 'h' * len(stereo_samples), *stereo_samples)
            
            return (stereo_data, sample_rate, 2, sample_width)
            
        except Exception as e:
            logger.error(f"Mono to stereo conversion failed: {e}")
            return None
    
    @staticmethod
    def stereo_to_mono(audio_data: AudioData) -> Optional[AudioData]:
        """Convert stereo audio to mono by mixing channels"""
        try:
            data, sample_rate, channels, sample_width = audio_data
            
            if channels != 2:
                logger.warning("Audio is not stereo")
                return audio_data
            
            if sample_width != 2:
                logger.error("Only 16-bit audio supported")
                return None
            
            stereo_samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            
            # Mix stereo to mono by averaging
            mono_samples = []
            for i in range(0, len(stereo_samples), 2):
                left = stereo_samples[i]
                right = stereo_samples[i + 1] if i + 1 < len(stereo_samples) else 0
                mixed = int((left + right) / 2)
                mono_samples.append(max(-32768, min(32767, mixed)))
            
            mono_data = struct.pack('<' + 'h' * len(mono_samples), *mono_samples)
            
            return (mono_data, sample_rate, 1, sample_width)
            
        except Exception as e:
            logger.error(f"Stereo to mono conversion failed: {e}")
            return None

class ToneGenerator:
    """Practical tone and signal generation utilities"""
    
    @staticmethod
    # generate_chord is now imported from core module for consistency
    # Use: from chameleon.core import generate_chord
    
    @staticmethod
    def generate_sweep(start_freq: float, end_freq: float, duration: float = 1.0,
                      sample_rate: int = 44100) -> Optional[AudioData]:
        """Generate frequency sweep (chirp)"""
        try:
            frames = int(duration * sample_rate)
            amplitude = 32767.0 * 0.5
            
            samples = []
            phase = 0.0
            
            for i in range(frames):
                # Linear frequency sweep
                progress = i / frames
                current_freq = start_freq + (end_freq - start_freq) * progress
                
                # Generate sample
                sample = int(amplitude * math.sin(phase))
                samples.append(max(-32768, min(32767, sample)))
                
                # Update phase
                phase += 2.0 * math.pi * current_freq / sample_rate
                if phase > 2.0 * math.pi:
                    phase -= 2.0 * math.pi
            
            sweep_data = struct.pack('<' + 'h' * len(samples), *samples)
            
            return (sweep_data, sample_rate, 1, 2)
            
        except Exception as e:
            logger.error(f"Frequency sweep generation failed: {e}")
            return None
    
    @staticmethod
    def generate_noise(duration: float = 1.0, sample_rate: int = 44100,
                      noise_type: str = 'white', amplitude: float = 0.1) -> Optional[AudioData]:
        """Generate different types of noise"""
        try:
            import random
            
            frames = int(duration * sample_rate)
            max_amplitude = int(32767.0 * amplitude)
            
            samples = []
            
            if noise_type == 'white':
                # White noise - equal power at all frequencies
                for _ in range(frames):
                    sample = random.randint(-max_amplitude, max_amplitude)
                    samples.append(sample)
            
            elif noise_type == 'pink':
                # Simple pink noise approximation
                prev_samples = [0.0] * 7
                for _ in range(frames):
                    white = random.uniform(-1, 1)
                    prev_samples[0] = 0.99886 * prev_samples[0] + white * 0.0555179
                    prev_samples[1] = 0.99332 * prev_samples[1] + white * 0.0750759
                    prev_samples[2] = 0.96900 * prev_samples[2] + white * 0.1538520
                    prev_samples[3] = 0.86650 * prev_samples[3] + white * 0.3104856
                    prev_samples[4] = 0.55000 * prev_samples[4] + white * 0.5329522
                    prev_samples[5] = -0.7616 * prev_samples[5] - white * 0.0168980
                    
                    pink = (sum(prev_samples) + white * 0.5362) * 0.11
                    sample = int(pink * max_amplitude)
                    samples.append(max(-32768, min(32767, sample)))
            
            else:
                logger.error(f"Unknown noise type: {noise_type}")
                return None
            
            noise_data = struct.pack('<' + 'h' * len(samples), *samples)
            
            return (noise_data, sample_rate, 1, 2)
            
        except Exception as e:
            logger.error(f"Noise generation failed: {e}")
            return None

def get_audio_file_info(filepath: str) -> Optional[AudioFileInfo]:
    """Get comprehensive audio file information"""
    try:
        if not os.path.exists(filepath):
            return None
        
        result = read_wav_file(filepath)
        if not result:
            return AudioFileInfo(
                filepath=filepath,
                format='unknown',
                sample_rate=0,
                channels=0,
                duration=0.0,
                bit_depth=0,
                file_size_mb=os.path.getsize(filepath) / (1024 * 1024),
                is_valid=False,
                estimated_quality='unknown'
            )
        
        audio_data, info = result
        data, sample_rate, channels, sample_width = audio_data
        
        duration = len(data) / (sample_rate * channels * sample_width)
        bit_depth = sample_width * 8
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        # Estimate quality based on parameters
        if sample_rate >= 48000 and bit_depth >= 24:
            quality = 'high'
        elif sample_rate >= 44100 and bit_depth >= 16:
            quality = 'standard'
        else:
            quality = 'basic'
        
        return AudioFileInfo(
            filepath=filepath,
            format=Path(filepath).suffix.lower().lstrip('.'),
            sample_rate=sample_rate,
            channels=channels,
            duration=duration,
            bit_depth=bit_depth,
            file_size_mb=file_size_mb,
            is_valid=True,
            estimated_quality=quality
        )
        
    except Exception as e:
        logger.error(f"Failed to get audio file info: {e}")
        return None

def create_test_tone_sequence(base_frequency: float = 440.0, 
                             interval_cents: int = 100,
                             num_tones: int = 12,
                             tone_duration: float = 0.5,
                             gap_duration: float = 0.1) -> Optional[AudioData]:
    """Create a sequence of test tones for audio system testing"""
    try:
        tone_clips = []
        
        # Generate silence gap
        gap = AudioMixer.create_silence(gap_duration)
        
        # Generate sequence of tones
        for i in range(num_tones):
            # Calculate frequency using equal temperament
            frequency = base_frequency * (2.0 ** (i * interval_cents / 1200.0))
            
            # Generate tone
            tone = generate_sine_wave(frequency, tone_duration, 44100)
            if tone:
                tone_clips.append(tone)
                if i < num_tones - 1:  # Don't add gap after last tone
                    tone_clips.append(gap)
        
        if not tone_clips:
            return None
        
        # Concatenate all clips
        result = tone_clips[0]
        
        for clip in tone_clips[1:]:
            # Simple concatenation
            data1, sr1, ch1, sw1 = result
            data2, sr2, ch2, sw2 = clip
            
            if sr1 == sr2 and ch1 == ch2 and sw1 == sw2:
                combined_data = data1 + data2
                result = (combined_data, sr1, ch1, sw1)
        
        return result
        
    except Exception as e:
        logger.error(f"Test tone sequence generation failed: {e}")
        return None

if __name__ == '__main__':
    # Test utility functions
    print("Audio Utilities Test")
    print("=" * 40)
    
    # Test tone generation
    print("Testing chord generation...")
    chord = ToneGenerator.generate_chord([261.63, 329.63, 392.00], 1.0)  # C major chord
    if chord:
        success = write_wav_file('test_chord.wav', chord)
        print(f"Chord generated: {'Success' if success else 'Failed'}")
    
    # Test frequency sweep
    print("Testing frequency sweep...")
    sweep = ToneGenerator.generate_sweep(220, 880, 2.0)
    if sweep:
        success = write_wav_file('test_sweep.wav', sweep)
        print(f"Sweep generated: {'Success' if success else 'Failed'}")
    
    # Test noise generation
    print("Testing noise generation...")
    noise = ToneGenerator.generate_noise(1.0, noise_type='white', amplitude=0.05)
    if noise:
        success = write_wav_file('test_noise.wav', noise)
        print(f"Noise generated: {'Success' if success else 'Failed'}")
    
    # Test analysis
    if chord:
        print("Testing audio analysis...")
        rms = AudioAnalyzer.calculate_rms(chord)
        print(f"Chord RMS level: {rms:.4f}" if rms else "RMS calculation failed")
        
        peaks = AudioAnalyzer.find_audio_peaks(chord, 5)
        print(f"Found {len(peaks)} peaks")
    
    print("Audio utilities test completed")