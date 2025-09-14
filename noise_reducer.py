#!/usr/bin/env python3
"""
Noise Reducer - Audio denoising and enhancement without heavy dependencies
Pure Python implementation with spectral subtraction and filtering
"""

import math
import struct
from typing import List, Tuple, Dict, Optional, Any
from collections import deque

class NoiseReducer:
    """Lightweight noise reduction using spectral subtraction"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.frame_size = 512
        self.noise_profile = None
        
    def estimate_noise_profile(self, audio_data: bytes, 
                              duration_ms: int = 500) -> Dict[float, float]:
        """
        Estimate noise profile from beginning of audio
        Assumes first duration_ms contains only noise
        """
        # Convert bytes to samples
        samples = []
        for i in range(0, min(len(audio_data) - 1, 
                              int(self.sample_rate * duration_ms / 1000) * 2), 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Compute spectrum of noise
        noise_spectrum = self._compute_spectrum(samples)
        self.noise_profile = noise_spectrum
        
        return noise_spectrum
    
    def _compute_spectrum(self, samples: List[float]) -> Dict[float, float]:
        """Simple DFT for spectrum computation"""
        N = min(len(samples), self.frame_size)
        spectrum = {}
        
        for k in range(N // 2):
            real = 0
            imag = 0
            for n in range(N):
                angle = -2 * math.pi * k * n / N
                real += samples[n] * math.cos(angle)
                imag += samples[n] * math.sin(angle)
            
            freq = k * self.sample_rate / N
            magnitude = math.sqrt(real ** 2 + imag ** 2) / N
            spectrum[freq] = magnitude
        
        return spectrum
    
    def reduce_noise(self, audio_data: bytes, 
                    reduction_factor: float = 0.8,
                    noise_gate_threshold: float = 0.01) -> bytes:
        """
        Reduce noise using spectral subtraction
        reduction_factor: 0.0 (no reduction) to 1.0 (maximum reduction)
        """
        # Convert to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # If no noise profile, estimate from first 100ms
        if self.noise_profile is None:
            self.estimate_noise_profile(audio_data, 100)
        
        # Process in overlapping frames
        processed = []
        hop_size = self.frame_size // 2
        
        for start in range(0, len(samples) - self.frame_size, hop_size):
            frame = samples[start:start + self.frame_size]
            
            # Apply window
            windowed = [frame[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / (self.frame_size - 1)))
                       for i in range(len(frame))]
            
            # Compute spectrum
            frame_spectrum = self._compute_spectrum(windowed)
            
            # Spectral subtraction
            cleaned_spectrum = {}
            for freq, mag in frame_spectrum.items():
                noise_level = self.noise_profile.get(freq, 0) * reduction_factor
                cleaned_mag = max(0, mag - noise_level)
                
                # Noise gate
                if cleaned_mag < noise_gate_threshold:
                    cleaned_mag = 0
                
                cleaned_spectrum[freq] = cleaned_mag
            
            # Inverse transform (simplified)
            cleaned_frame = self._inverse_spectrum(cleaned_spectrum, self.frame_size)
            
            # Overlap-add
            if not processed:
                processed.extend(cleaned_frame)
            else:
                # Mix overlapping region
                overlap_start = len(processed) - hop_size
                for i in range(hop_size):
                    if overlap_start + i < len(processed):
                        processed[overlap_start + i] = (processed[overlap_start + i] + cleaned_frame[i]) / 2
                processed.extend(cleaned_frame[hop_size:])
        
        # Add remaining samples
        if len(samples) > len(processed):
            processed.extend(samples[len(processed):])
        
        # Convert back to bytes
        output = b''
        for sample in processed:
            # Clip to valid range
            sample = max(-1.0, min(1.0, sample))
            sample_int = int(sample * 32767)
            output += struct.pack('<h', sample_int)
        
        return output
    
    def _inverse_spectrum(self, spectrum: Dict[float, float], N: int) -> List[float]:
        """Simplified inverse DFT"""
        samples = []
        
        for n in range(N):
            sample = 0
            for freq, mag in spectrum.items():
                k = int(freq * N / self.sample_rate)
                if k < N // 2:
                    angle = 2 * math.pi * k * n / N
                    sample += mag * math.cos(angle)
            
            samples.append(sample * 2)  # Compensate for using only positive frequencies
        
        return samples


class AudioEnhancer:
    """Audio enhancement tools"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        
    def enhance_clarity(self, audio_data: bytes, 
                       clarity_factor: float = 1.5) -> bytes:
        """
        Enhance audio clarity by boosting speech frequencies
        clarity_factor: 1.0 (no change) to 2.0 (maximum enhancement)
        """
        # Convert to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Apply bandpass filter for speech frequencies (300-3400 Hz)
        filtered = self._bandpass_filter(samples, 300, 3400)
        
        # Mix with original (emphasize filtered frequencies)
        enhanced = []
        for i in range(len(samples)):
            if i < len(filtered):
                enhanced_sample = samples[i] + (filtered[i] - samples[i]) * (clarity_factor - 1)
            else:
                enhanced_sample = samples[i]
            
            enhanced.append(enhanced_sample)
        
        # Normalize
        max_val = max(abs(s) for s in enhanced) if enhanced else 1.0
        if max_val > 0:
            enhanced = [s / max_val * 0.95 for s in enhanced]
        
        # Convert to bytes
        output = b''
        for sample in enhanced:
            sample_int = int(sample * 32767)
            output += struct.pack('<h', sample_int)
        
        return output
    
    def _bandpass_filter(self, samples: List[float], 
                        low_freq: float, high_freq: float) -> List[float]:
        """Simple bandpass filter using moving average"""
        # Calculate filter parameters
        low_period = int(self.sample_rate / low_freq)
        high_period = int(self.sample_rate / high_freq)
        
        # High-pass filter (remove low frequencies)
        high_passed = []
        history = deque(maxlen=low_period)
        
        for sample in samples:
            history.append(sample)
            if len(history) == low_period:
                avg = sum(history) / len(history)
                high_passed.append(sample - avg)
            else:
                high_passed.append(sample)
        
        # Low-pass filter (remove high frequencies)
        filtered = []
        window = deque(maxlen=high_period)
        
        for sample in high_passed:
            window.append(sample)
            filtered.append(sum(window) / len(window))
        
        return filtered
    
    def remove_clicks(self, audio_data: bytes, 
                     threshold: float = 3.0) -> bytes:
        """
        Remove clicks and pops from audio
        threshold: sensitivity (lower = more aggressive)
        """
        # Convert to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Detect and interpolate clicks
        cleaned = samples.copy()
        window_size = 5
        
        for i in range(window_size, len(samples) - window_size):
            # Calculate local statistics
            window = samples[i-window_size:i] + samples[i+1:i+window_size+1]
            if window:
                mean = sum(window) / len(window)
                std = math.sqrt(sum((x - mean) ** 2 for x in window) / len(window))
                
                # Detect outlier
                if std > 0 and abs(samples[i] - mean) > threshold * std:
                    # Interpolate
                    cleaned[i] = mean
        
        # Convert to bytes
        output = b''
        for sample in cleaned:
            sample_int = int(sample * 32767)
            output += struct.pack('<h', sample_int)
        
        return output
    
    def apply_compressor(self, audio_data: bytes,
                        threshold: float = 0.7,
                        ratio: float = 4.0,
                        attack_ms: float = 5.0,
                        release_ms: float = 50.0) -> bytes:
        """
        Apply dynamic range compression
        threshold: 0.0 to 1.0 (level where compression starts)
        ratio: compression ratio (e.g., 4:1)
        """
        # Convert to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Calculate time constants
        attack_samples = int(self.sample_rate * attack_ms / 1000)
        release_samples = int(self.sample_rate * release_ms / 1000)
        
        # Apply compression
        compressed = []
        gain = 1.0
        
        for sample in samples:
            level = abs(sample)
            
            # Calculate target gain
            if level > threshold:
                target_gain = threshold + (level - threshold) / ratio
                target_gain = target_gain / level if level > 0 else 1.0
            else:
                target_gain = 1.0
            
            # Smooth gain changes
            if target_gain < gain:
                # Attack
                gain = gain - (gain - target_gain) / attack_samples
            else:
                # Release
                gain = gain + (target_gain - gain) / release_samples
            
            # Apply gain
            compressed.append(sample * gain)
        
        # Make-up gain (normalize)
        max_val = max(abs(s) for s in compressed) if compressed else 1.0
        if max_val > 0:
            makeup_gain = 0.95 / max_val
            compressed = [s * makeup_gain for s in compressed]
        
        # Convert to bytes
        output = b''
        for sample in compressed:
            sample_int = int(sample * 32767)
            output += struct.pack('<h', sample_int)
        
        return output
    
    def apply_limiter(self, audio_data: bytes,
                     ceiling: float = 0.95) -> bytes:
        """
        Apply brick-wall limiter to prevent clipping
        ceiling: maximum output level (0.0 to 1.0)
        """
        # Convert to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        
        # Apply limiting with look-ahead
        look_ahead = 10
        limited = []
        
        for i in range(len(samples)):
            # Look ahead for peaks
            peak = abs(samples[i])
            for j in range(1, min(look_ahead, len(samples) - i)):
                peak = max(peak, abs(samples[i + j]))
            
            # Calculate gain reduction
            if peak > ceiling:
                gain = ceiling / peak
            else:
                gain = 1.0
            
            # Apply gain with smoothing
            limited.append(samples[i] * gain)
        
        # Convert to bytes
        output = b''
        for sample in limited:
            sample_int = int(sample * 32767)
            output += struct.pack('<h', sample_int)
        
        return output


def process_audio_enhancement(input_file: str, output_file: str,
                             noise_reduction: float = 0.5,
                             clarity_enhancement: float = 1.2,
                             remove_clicks: bool = True,
                             apply_compression: bool = False) -> bool:
    """
    High-level function to enhance audio
    """
    try:
        import wave
        
        # Read input audio
        with wave.open(input_file, 'rb') as wav_in:
            params = wav_in.getparams()
            audio_data = wav_in.readframes(params.nframes)
            sample_rate = params.framerate
        
        # Create processors
        noise_reducer = NoiseReducer(sample_rate)
        enhancer = AudioEnhancer(sample_rate)
        
        # Apply processing chain
        processed = audio_data
        
        # 1. Noise reduction
        if noise_reduction > 0:
            print(f"Applying noise reduction ({noise_reduction:.0%})...")
            processed = noise_reducer.reduce_noise(processed, noise_reduction)
        
        # 2. Click removal
        if remove_clicks:
            print("Removing clicks and pops...")
            processed = enhancer.remove_clicks(processed)
        
        # 3. Clarity enhancement
        if clarity_enhancement > 1.0:
            print(f"Enhancing clarity ({clarity_enhancement:.1f}x)...")
            processed = enhancer.enhance_clarity(processed, clarity_enhancement)
        
        # 4. Compression
        if apply_compression:
            print("Applying compression...")
            processed = enhancer.apply_compressor(processed)
        
        # 5. Final limiting
        print("Applying final limiter...")
        processed = enhancer.apply_limiter(processed)
        
        # Write output
        with wave.open(output_file, 'wb') as wav_out:
            wav_out.setparams(params)
            wav_out.writeframes(processed)
        
        print(f"Enhanced audio saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"Enhancement error: {e}")
        return False


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python noise_reducer.py <input.wav> <output.wav> [options]")
        print("Options:")
        print("  --noise-reduction=0.0-1.0  Noise reduction amount (default: 0.5)")
        print("  --clarity=1.0-2.0         Clarity enhancement (default: 1.2)")
        print("  --no-click-removal        Disable click removal")
        print("  --compress                Apply compression")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Parse options
    noise_reduction = 0.5
    clarity = 1.2
    remove_clicks = True
    compress = False
    
    for arg in sys.argv[3:]:
        if arg.startswith('--noise-reduction='):
            noise_reduction = float(arg.split('=')[1])
        elif arg.startswith('--clarity='):
            clarity = float(arg.split('=')[1])
        elif arg == '--no-click-removal':
            remove_clicks = False
        elif arg == '--compress':
            compress = True
    
    # Process audio
    success = process_audio_enhancement(
        input_file, output_file,
        noise_reduction, clarity,
        remove_clicks, compress
    )
    
    sys.exit(0 if success else 1)