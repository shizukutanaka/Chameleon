#!/usr/bin/env python3
"""
Simple Voice Processor - Lightweight voice transformation
Pure Python implementation without heavy dependencies
"""

import array
import math
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from functools import lru_cache

@dataclass
class VoiceProfile:
    """Voice transformation profile"""
    pitch: float = 1.0        # 0.5-2.0
    speed: float = 1.0         # 0.5-2.0  
    formant: float = 1.0       # 0.5-2.0
    gender: float = 0.0        # -1.0 to 1.0

class VoiceProcessor:
    """Simple voice processor using basic algorithms"""
    
    # Voice presets for common transformations
    PRESETS = {
        'normal': VoiceProfile(1.0, 1.0, 1.0, 0.0),
        'male': VoiceProfile(0.85, 0.95, 0.9, -0.5),
        'female': VoiceProfile(1.2, 1.05, 1.1, 0.5),
        'child': VoiceProfile(1.5, 1.1, 1.3, 0.7),
        'robot': VoiceProfile(1.0, 1.0, 0.8, 0.0),
        'deep': VoiceProfile(0.7, 0.9, 0.8, -0.8),
        'cartoon': VoiceProfile(1.8, 1.2, 1.4, 0.8)
    }
    
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.profile = VoiceProfile()
        
        # Processing buffers
        self._buffer = [0] * chunk_size * 2
        self._window = self._create_hann_window(256)
        
        # Performance tracking
        self.chunks_processed = 0
        
    def _create_hann_window(self, size: int) -> List[float]:
        """Create Hann window for smooth processing"""
        return [0.5 - 0.5 * math.cos(2 * math.pi * i / (size - 1)) for i in range(size)]
    
    def _simple_pitch_shift(self, samples: List[int], pitch_factor: float) -> List[int]:
        """Simple pitch shifting using time-domain method"""
        if abs(pitch_factor - 1.0) < 0.01:
            return samples
            
        # Simple time-stretching approach
        output_length = int(len(samples) / pitch_factor)
        result = []
        
        for i in range(output_length):
            # Linear interpolation
            src_pos = i * pitch_factor
            src_idx = int(src_pos)
            frac = src_pos - src_idx
            
            if src_idx < len(samples) - 1:
                val = samples[src_idx] * (1 - frac) + samples[src_idx + 1] * frac
                result.append(int(val))
            elif src_idx < len(samples):
                result.append(samples[src_idx])
        
        return result
    
    def _simple_formant_shift(self, samples: List[int], formant_factor: float) -> List[int]:
        """Simple formant shifting using basic filtering"""
        if abs(formant_factor - 1.0) < 0.01:
            return samples
            
        # Simple frequency-dependent gain adjustment
        # Higher formant factor = brighter sound
        result = []
        prev = 0
        
        for sample in samples:
            # Basic high-pass/low-pass combination
            if formant_factor > 1.0:
                # Brighten - emphasize high frequencies
                high_pass = sample - prev * 0.8
                result.append(int(high_pass * formant_factor * 0.8 + sample * 0.2))
            else:
                # Darken - emphasize low frequencies  
                low_pass = prev * 0.7 + sample * 0.3
                result.append(int(low_pass))
            
            prev = sample
            
        return result
    
    def _apply_gender_shift(self, samples: List[int], gender: float) -> List[int]:
        """Apply gender-based voice characteristics"""
        if abs(gender) < 0.01:
            return samples
            
        # Gender affects both pitch and formant characteristics
        if gender > 0:  # More female
            # Slightly brighter, with subtle pitch variation
            result = []
            for i, sample in enumerate(samples):
                # Add subtle pitch modulation
                mod = math.sin(2 * math.pi * i / self.sample_rate * 2) * gender * 0.1
                modified = sample * (1.0 + mod)
                result.append(int(modified))
            return result
        else:  # More male
            # Slightly darker, more stable
            alpha = 0.7 + abs(gender) * 0.2
            result = []
            prev = 0
            
            for sample in samples:
                filtered = alpha * sample + (1 - alpha) * prev
                result.append(int(filtered))
                prev = filtered
                
            return result
    
    def load_preset(self, preset_name: str) -> bool:
        """Load a voice preset"""
        if preset_name in self.PRESETS:
            self.profile = self.PRESETS[preset_name]
            return True
        return False
    
    def get_preset_names(self) -> List[str]:
        """Get available preset names"""
        return list(self.PRESETS.keys())
    
    def set_profile(self, profile: VoiceProfile):
        """Set voice profile"""
        self.profile = profile
    
    def process_chunk(self, chunk: bytes) -> bytes:
        """Process audio chunk with current voice profile"""
        if not chunk:
            return chunk
            
        # Convert bytes to samples
        arr = array.array('h')
        arr.frombytes(chunk)
        samples = list(arr)
        
        if not samples:
            return chunk
            
        # Apply transformations in order
        result = samples
        
        # 1. Pitch shifting
        if abs(self.profile.pitch - 1.0) > 0.01:
            result = self._simple_pitch_shift(result, self.profile.pitch)
        
        # 2. Formant shifting  
        if abs(self.profile.formant - 1.0) > 0.01:
            result = self._simple_formant_shift(result, self.profile.formant)
        
        # 3. Gender adjustment
        if abs(self.profile.gender) > 0.01:
            result = self._apply_gender_shift(result, self.profile.gender)
        
        # 4. Speed adjustment (simple time stretching)
        if abs(self.profile.speed - 1.0) > 0.01:
            target_length = int(len(result) / self.profile.speed)
            if target_length > 0:
                speed_adjusted = []
                for i in range(target_length):
                    src_pos = i * self.profile.speed
                    src_idx = int(src_pos)
                    if src_idx < len(result):
                        speed_adjusted.append(result[src_idx])
                result = speed_adjusted
        
        # Convert back to bytes
        output_array = array.array('h', result[:len(samples)])  # Maintain original length
        self.chunks_processed += 1
        
        return output_array.tobytes()
    
    def process_realtime(self, samples: List[int]) -> List[int]:
        """Process samples for real-time use"""
        if not samples:
            return samples
            
        # Apply basic voice transformation
        result = samples
        
        if abs(self.profile.pitch - 1.0) > 0.01:
            result = self._simple_pitch_shift(result, self.profile.pitch)
            
        if abs(self.profile.formant - 1.0) > 0.01:
            result = self._simple_formant_shift(result, self.profile.formant)
            
        return result[:len(samples)]  # Maintain original length
    
    def analyze_voice(self, audio_data: bytes) -> Dict[str, float]:
        """Simple voice analysis"""
        if not audio_data:
            return {}
            
        # Convert to samples
        arr = array.array('h')
        arr.frombytes(audio_data)
        samples = list(arr)
        
        if not samples:
            return {}
        
        # Basic analysis
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        peak = max(abs(s) for s in samples)
        
        # Simple pitch estimation using zero crossings
        zero_crossings = 0
        for i in range(1, len(samples)):
            if (samples[i-1] >= 0) != (samples[i] >= 0):
                zero_crossings += 1
        
        # Estimate fundamental frequency
        if zero_crossings > 0:
            estimated_freq = (zero_crossings / 2) * self.sample_rate / len(samples)
        else:
            estimated_freq = 0
            
        return {
            'pitch_hz': estimated_freq,
            'energy': rms,
            'peak_amplitude': peak / 32767.0,
            'zero_crossings': zero_crossings
        }
    
    def batch_process(self, chunks: List[List[int]]) -> List[List[int]]:
        """Process multiple chunks"""
        results = []
        for chunk in chunks:
            processed = self.process_realtime(chunk)
            results.append(processed)
        return results
    
    def create_custom_preset(self, name: str, pitch: float, formant: float, 
                           speed: float, gender: float) -> bool:
        """Create custom preset with validation"""
        # Validate parameters
        if not (0.25 <= pitch <= 4.0):
            return False
        if not (0.25 <= formant <= 4.0):
            return False
        if not (0.25 <= speed <= 4.0):
            return False
        if not (-1.0 <= gender <= 1.0):
            return False
            
        # Create and store preset
        self.PRESETS[name] = VoiceProfile(pitch, formant, speed, gender)
        return True
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get processing performance statistics"""
        return {
            'chunks_processed': self.chunks_processed,
            'sample_rate': self.sample_rate,
            'chunk_size': self.chunk_size,
            'current_preset': self._get_current_preset_name(),
            'profile': {
                'pitch': self.profile.pitch,
                'formant': self.profile.formant,
                'speed': self.profile.speed,
                'gender': self.profile.gender
            }
        }
    
    def _get_current_preset_name(self) -> str:
        """Get name of current preset if it matches"""
        for name, preset in self.PRESETS.items():
            if (abs(preset.pitch - self.profile.pitch) < 0.01 and
                abs(preset.formant - self.profile.formant) < 0.01 and
                abs(preset.speed - self.profile.speed) < 0.01 and
                abs(preset.gender - self.profile.gender) < 0.01):
                return name
        return 'custom'