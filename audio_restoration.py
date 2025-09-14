#!/usr/bin/env python3
"""
Audio Restoration - Professional audio repair and restoration tools
Advanced algorithms for fixing damaged, degraded, or corrupted audio
"""

import math
import struct
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass
from collections import deque
import wave

@dataclass
class RestorationProfile:
    """Audio restoration profile with specific settings"""
    name: str
    description: str
    algorithms: List[str]
    parameters: Dict[str, Any]

class AudioRestoration:
    """Professional audio restoration toolkit"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        
        # Built-in restoration profiles
        self.profiles = {
            'vinyl_restoration': RestorationProfile(
                name='Vinyl Record Restoration',
                description='Remove pops, clicks, and surface noise from vinyl recordings',
                algorithms=['declicking', 'denoising', 'dehissing', 'wow_flutter_correction'],
                parameters={
                    'click_threshold': 3.0,
                    'noise_reduction': 0.6,
                    'hiss_reduction': 0.4,
                    'wow_flutter_strength': 0.3
                }
            ),
            'tape_restoration': RestorationProfile(
                name='Tape Restoration',
                description='Restore analog tape recordings',
                algorithms=['dropout_repair', 'wow_flutter_correction', 'denoising', 'azimuth_correction'],
                parameters={
                    'dropout_threshold': 0.1,
                    'wow_flutter_strength': 0.5,
                    'noise_reduction': 0.4,
                    'azimuth_correction': True
                }
            ),
            'digital_repair': RestorationProfile(
                name='Digital Audio Repair',
                description='Fix digital audio artifacts and corruption',
                algorithms=['digital_clip_repair', 'interpolation_repair', 'dc_removal'],
                parameters={
                    'clip_threshold': 0.95,
                    'interpolation_method': 'cubic',
                    'dc_removal_cutoff': 5.0
                }
            ),
            'broadcast_cleanup': RestorationProfile(
                name='Broadcast Cleanup',
                description='Clean up broadcast recordings',
                algorithms=['declicking', 'denoising', 'level_correction', 'stereo_enhancement'],
                parameters={
                    'click_threshold': 2.5,
                    'noise_reduction': 0.3,
                    'level_target': 0.8,
                    'stereo_width': 1.2
                }
            )
        }
    
    def restore_audio(self, audio_data: bytes, 
                     profile: str = 'digital_repair') -> bytes:
        """Main restoration function using specified profile"""
        
        if profile not in self.profiles:
            print(f"Unknown restoration profile: {profile}")
            return audio_data
        
        restoration_profile = self.profiles[profile]
        
        # Convert to samples for processing
        samples = self._bytes_to_samples(audio_data)
        
        print(f"Applying restoration profile: {restoration_profile.name}")
        
        # Apply restoration algorithms in sequence
        for algorithm in restoration_profile.algorithms:
            print(f"  Applying: {algorithm}")
            samples = self._apply_algorithm(samples, algorithm, restoration_profile.parameters)
        
        # Convert back to bytes
        return self._samples_to_bytes(samples)
    
    def _apply_algorithm(self, samples: List[float], 
                        algorithm: str, parameters: Dict[str, Any]) -> List[float]:
        """Apply specific restoration algorithm"""
        
        if algorithm == 'declicking':
            return self._remove_clicks_and_pops(samples, parameters.get('click_threshold', 3.0))
        elif algorithm == 'denoising':
            return self._spectral_noise_reduction(samples, parameters.get('noise_reduction', 0.5))
        elif algorithm == 'dehissing':
            return self._remove_hiss(samples, parameters.get('hiss_reduction', 0.3))
        elif algorithm == 'dropout_repair':
            return self._repair_dropouts(samples, parameters.get('dropout_threshold', 0.1))
        elif algorithm == 'wow_flutter_correction':
            return self._correct_wow_flutter(samples, parameters.get('wow_flutter_strength', 0.3))
        elif algorithm == 'digital_clip_repair':
            return self._repair_digital_clipping(samples, parameters.get('clip_threshold', 0.95))
        elif algorithm == 'interpolation_repair':
            return self._interpolation_repair(samples, parameters.get('interpolation_method', 'cubic'))
        elif algorithm == 'dc_removal':
            return self._remove_dc_offset(samples, parameters.get('dc_removal_cutoff', 5.0))
        elif algorithm == 'level_correction':
            return self._correct_levels(samples, parameters.get('level_target', 0.8))
        elif algorithm == 'stereo_enhancement':
            return self._enhance_stereo(samples, parameters.get('stereo_width', 1.2))
        elif algorithm == 'azimuth_correction':
            return self._correct_azimuth(samples)
        else:
            print(f"Unknown algorithm: {algorithm}")
            return samples
    
    def _remove_clicks_and_pops(self, samples: List[float], threshold: float) -> List[float]:
        """Remove clicks and pops using median filtering and interpolation"""
        restored = samples.copy()
        window_size = 5
        
        # Detect clicks
        for i in range(window_size, len(samples) - window_size):
            # Calculate local statistics
            window = samples[i-window_size:i] + samples[i+1:i+window_size+1]
            if window:
                median = sorted(window)[len(window)//2]
                mad = sum(abs(x - median) for x in window) / len(window)  # Mean Absolute Deviation
                
                # Detect outlier (click)
                if mad > 0 and abs(samples[i] - median) > threshold * mad:
                    # Interpolate using surrounding samples
                    restored[i] = (samples[i-1] + samples[i+1]) / 2
        
        return restored
    
    def _spectral_noise_reduction(self, samples: List[float], reduction: float) -> List[float]:
        """Spectral noise reduction using Wiener filtering approach"""
        # Simple implementation - estimate noise from quiet periods
        frame_size = 512
        hop_size = frame_size // 2
        
        # Estimate noise floor from quietest 10% of frames
        frame_energies = []
        for i in range(0, len(samples) - frame_size, hop_size):
            frame = samples[i:i + frame_size]
            energy = sum(s ** 2 for s in frame) / len(frame)
            frame_energies.append((energy, i))
        
        # Sort by energy and take quietest frames for noise estimation
        frame_energies.sort()
        quiet_frames = frame_energies[:len(frame_energies)//10]
        
        # Calculate noise threshold
        noise_threshold = sum(energy for energy, _ in quiet_frames) / len(quiet_frames)
        noise_threshold *= (1 + reduction)
        
        # Apply noise reduction
        restored = []
        for i in range(0, len(samples) - frame_size, hop_size):
            frame = samples[i:i + frame_size]
            frame_energy = sum(s ** 2 for s in frame) / len(frame)
            
            if frame_energy < noise_threshold:
                # Reduce amplitude in noisy frames
                gain = max(0.1, 1 - reduction)
                frame = [s * gain for s in frame]
            
            # Overlap-add
            if not restored:
                restored.extend(frame)
            else:
                # Mix overlapping region
                overlap_start = len(restored) - hop_size
                for j in range(hop_size):
                    if overlap_start + j < len(restored):
                        restored[overlap_start + j] = (restored[overlap_start + j] + frame[j]) / 2
                restored.extend(frame[hop_size:])
        
        return restored
    
    def _remove_hiss(self, samples: List[float], reduction: float) -> List[float]:
        """Remove high-frequency hiss using adaptive filtering"""
        # Simple high-frequency noise reduction
        # Apply low-pass filter with adaptive cutoff
        
        restored = []
        history = deque(maxlen=3)
        alpha = 0.3 * (1 - reduction)  # Filter strength based on reduction amount
        
        for sample in samples:
            history.append(sample)
            
            if len(history) >= 3:
                # Simple low-pass filter
                filtered = history[1] * (1 - alpha) + (history[0] + history[2]) * alpha / 2
                restored.append(filtered)
            else:
                restored.append(sample)
        
        return restored
    
    def _repair_dropouts(self, samples: List[float], threshold: float) -> List[float]:
        """Repair audio dropouts (silent or very quiet sections)"""
        restored = samples.copy()
        min_dropout_length = int(self.sample_rate * 0.01)  # 10ms minimum
        max_dropout_length = int(self.sample_rate * 0.1)   # 100ms maximum
        
        i = 0
        while i < len(samples):
            # Detect start of dropout
            if abs(samples[i]) < threshold:
                dropout_start = i
                
                # Find end of dropout
                while i < len(samples) and abs(samples[i]) < threshold:
                    i += 1
                dropout_end = i
                
                dropout_length = dropout_end - dropout_start
                
                # Only repair dropouts within reasonable length
                if min_dropout_length <= dropout_length <= max_dropout_length:
                    # Interpolate across dropout
                    if dropout_start > 0 and dropout_end < len(samples):
                        start_value = samples[dropout_start - 1]
                        end_value = samples[dropout_end]
                        
                        for j in range(dropout_start, dropout_end):
                            t = (j - dropout_start) / dropout_length
                            # Cubic interpolation for smoother result
                            restored[j] = start_value * (1 - t) + end_value * t
            else:
                i += 1
        
        return restored
    
    def _correct_wow_flutter(self, samples: List[float], strength: float) -> List[float]:
        """Correct wow and flutter (pitch variations) using pitch tracking"""
        # Simplified wow/flutter correction
        # In a real implementation, this would use sophisticated pitch tracking
        
        # Apply subtle pitch stabilization
        window_size = int(self.sample_rate * 0.1)  # 100ms windows
        restored = samples.copy()
        
        for i in range(0, len(samples) - window_size, window_size // 2):
            window = samples[i:i + window_size]
            
            # Estimate local pitch variation (very simplified)
            # Apply gentle smoothing to reduce rapid pitch changes
            smoothed_window = []
            for j, sample in enumerate(window):
                if j > 0 and j < len(window) - 1:
                    # Gentle smoothing
                    smoothed = (window[j-1] * 0.25 + sample * 0.5 + window[j+1] * 0.25)
                    smoothed_window.append(sample * (1 - strength) + smoothed * strength)
                else:
                    smoothed_window.append(sample)
            
            # Copy back to restored array
            for j, smoothed_sample in enumerate(smoothed_window):
                if i + j < len(restored):
                    restored[i + j] = smoothed_sample
        
        return restored
    
    def _repair_digital_clipping(self, samples: List[float], threshold: float) -> List[float]:
        """Repair digital clipping artifacts"""
        restored = samples.copy()
        
        for i in range(1, len(samples) - 1):
            # Detect clipping
            if abs(samples[i]) >= threshold:
                # Look for clipped regions
                clip_start = i
                while i < len(samples) - 1 and abs(samples[i]) >= threshold:
                    i += 1
                clip_end = i
                
                # Interpolate clipped region
                if clip_start > 0 and clip_end < len(samples):
                    start_value = samples[clip_start - 1]
                    end_value = samples[clip_end]
                    
                    # Use cubic spline interpolation for natural reconstruction
                    for j in range(clip_start, clip_end):
                        t = (j - clip_start) / max(1, clip_end - clip_start)
                        # Cubic interpolation
                        interpolated = start_value + (end_value - start_value) * t
                        # Limit to prevent re-clipping
                        restored[j] = max(-threshold, min(threshold, interpolated))
        
        return restored
    
    def _interpolation_repair(self, samples: List[float], method: str) -> List[float]:
        """General interpolation repair for missing samples"""
        restored = samples.copy()
        
        # Find zero-valued samples that might be missing/corrupted
        for i in range(1, len(samples) - 1):
            if samples[i] == 0 and samples[i-1] != 0 and samples[i+1] != 0:
                if method == 'linear':
                    restored[i] = (samples[i-1] + samples[i+1]) / 2
                elif method == 'cubic':
                    # Cubic interpolation using 4 points
                    if i >= 2 and i < len(samples) - 2:
                        # Catmull-Rom spline interpolation
                        p0, p1, p2, p3 = samples[i-2], samples[i-1], samples[i+1], samples[i+2]
                        restored[i] = 0.5 * (p1 + p2)  # Simplified cubic
                    else:
                        restored[i] = (samples[i-1] + samples[i+1]) / 2
        
        return restored
    
    def _remove_dc_offset(self, samples: List[float], cutoff_hz: float) -> List[float]:
        """Remove DC offset using high-pass filter"""
        # Simple high-pass filter to remove DC component
        cutoff = cutoff_hz / self.sample_rate
        alpha = cutoff / (cutoff + 1)
        
        restored = []
        prev_input = 0
        prev_output = 0
        
        for sample in samples:
            # High-pass filter: y[n] = alpha * (y[n-1] + x[n] - x[n-1])
            output = alpha * (prev_output + sample - prev_input)
            restored.append(output)
            
            prev_input = sample
            prev_output = output
        
        return restored
    
    def _correct_levels(self, samples: List[float], target_level: float) -> List[float]:
        """Correct audio levels to target"""
        if not samples:
            return samples
        
        # Calculate current RMS level
        rms = math.sqrt(sum(s ** 2 for s in samples) / len(samples))
        
        if rms > 0:
            # Calculate gain to reach target level
            gain = target_level / rms
            # Limit gain to prevent excessive amplification
            gain = min(gain, 3.0)
            
            return [s * gain for s in samples]
        
        return samples
    
    def _enhance_stereo(self, samples: List[float], width: float) -> List[float]:
        """Enhance stereo width (assumes interleaved stereo)"""
        if len(samples) % 2 != 0:
            return samples  # Not stereo
        
        enhanced = []
        
        for i in range(0, len(samples), 2):
            left = samples[i]
            right = samples[i + 1]
            
            # Calculate mid and side signals
            mid = (left + right) / 2
            side = (left - right) / 2
            
            # Enhance stereo width
            enhanced_side = side * width
            
            # Reconstruct stereo
            new_left = mid + enhanced_side
            new_right = mid - enhanced_side
            
            # Prevent clipping
            new_left = max(-1.0, min(1.0, new_left))
            new_right = max(-1.0, min(1.0, new_right))
            
            enhanced.extend([new_left, new_right])
        
        return enhanced
    
    def _correct_azimuth(self, samples: List[float]) -> List[float]:
        """Correct azimuth errors in stereo recordings"""
        # Simplified azimuth correction for stereo
        if len(samples) % 2 != 0:
            return samples
        
        corrected = []
        delay_compensation = 2  # samples delay compensation
        
        for i in range(0, len(samples), 2):
            left = samples[i]
            
            # Apply slight delay compensation to right channel
            if i + 2 + delay_compensation < len(samples):
                right = samples[i + 1 + delay_compensation]
            else:
                right = samples[i + 1]
            
            corrected.extend([left, right])
        
        return corrected
    
    def _bytes_to_samples(self, audio_data: bytes) -> List[float]:
        """Convert audio bytes to normalized float samples"""
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        return samples
    
    def _samples_to_bytes(self, samples: List[float]) -> bytes:
        """Convert float samples to audio bytes"""
        audio_data = b''
        for sample in samples:
            # Clip and convert to 16-bit
            sample = max(-1.0, min(1.0, sample))
            sample_int = int(sample * 32767)
            audio_data += struct.pack('<h', sample_int)
        return audio_data
    
    def analyze_audio_problems(self, audio_data: bytes) -> Dict[str, Any]:
        """Analyze audio for common problems"""
        samples = self._bytes_to_samples(audio_data)
        
        analysis = {
            'clipping_detected': False,
            'clipping_percentage': 0.0,
            'dc_offset': 0.0,
            'noise_level': 0.0,
            'dropouts_detected': 0,
            'dynamic_range': 0.0,
            'recommendations': []
        }
        
        if not samples:
            return analysis
        
        # Check for clipping
        clipped_samples = sum(1 for s in samples if abs(s) >= 0.95)
        analysis['clipping_percentage'] = clipped_samples / len(samples) * 100
        analysis['clipping_detected'] = analysis['clipping_percentage'] > 0.1
        
        # Calculate DC offset
        analysis['dc_offset'] = sum(samples) / len(samples)
        
        # Estimate noise level (RMS of quietest 10%)
        sorted_samples = sorted(samples, key=abs)
        quiet_samples = sorted_samples[:len(sorted_samples)//10]
        analysis['noise_level'] = math.sqrt(sum(s ** 2 for s in quiet_samples) / len(quiet_samples))
        
        # Check for dropouts
        dropout_count = 0
        consecutive_zeros = 0
        for sample in samples:
            if abs(sample) < 0.001:
                consecutive_zeros += 1
            else:
                if consecutive_zeros > self.sample_rate * 0.01:  # >10ms of silence
                    dropout_count += 1
                consecutive_zeros = 0
        analysis['dropouts_detected'] = dropout_count
        
        # Calculate dynamic range
        peak = max(abs(s) for s in samples)
        rms = math.sqrt(sum(s ** 2 for s in samples) / len(samples))
        if rms > 0:
            analysis['dynamic_range'] = 20 * math.log10(peak / rms)
        
        # Generate recommendations
        if analysis['clipping_detected']:
            analysis['recommendations'].append('Digital clipping repair recommended')
        
        if abs(analysis['dc_offset']) > 0.01:
            analysis['recommendations'].append('DC offset removal recommended')
        
        if analysis['noise_level'] > 0.05:
            analysis['recommendations'].append('Noise reduction recommended')
        
        if analysis['dropouts_detected'] > 0:
            analysis['recommendations'].append('Dropout repair recommended')
        
        if analysis['dynamic_range'] < 6:
            analysis['recommendations'].append('Audio appears over-compressed')
        
        return analysis
    
    def create_custom_profile(self, name: str, description: str, 
                            algorithms: List[str], parameters: Dict[str, Any]) -> bool:
        """Create a custom restoration profile"""
        self.profiles[name] = RestorationProfile(
            name=name,
            description=description,
            algorithms=algorithms,
            parameters=parameters
        )
        return True
    
    def list_profiles(self) -> List[str]:
        """List available restoration profiles"""
        return list(self.profiles.keys())
    
    def get_profile_info(self, profile_name: str) -> Optional[RestorationProfile]:
        """Get information about a restoration profile"""
        return self.profiles.get(profile_name)


def restore_audio_file(input_file: str, output_file: str, 
                      profile: str = 'digital_repair') -> bool:
    """High-level function to restore an audio file"""
    try:
        # Load audio
        with wave.open(input_file, 'rb') as wav_in:
            params = wav_in.getparams()
            audio_data = wav_in.readframes(params.nframes)
            sample_rate = params.framerate
        
        # Create restoration engine
        restorer = AudioRestoration(sample_rate)
        
        # Analyze problems first
        print("Analyzing audio problems...")
        analysis = restorer.analyze_audio_problems(audio_data)
        
        print("Audio Analysis Results:")
        print(f"  Clipping: {analysis['clipping_percentage']:.1f}%")
        print(f"  DC Offset: {analysis['dc_offset']:.4f}")
        print(f"  Noise Level: {analysis['noise_level']:.4f}")
        print(f"  Dropouts: {analysis['dropouts_detected']}")
        print(f"  Dynamic Range: {analysis['dynamic_range']:.1f} dB")
        
        if analysis['recommendations']:
            print("  Recommendations:")
            for rec in analysis['recommendations']:
                print(f"    - {rec}")
        
        # Apply restoration
        print(f"\nApplying restoration profile: {profile}")
        restored_data = restorer.restore_audio(audio_data, profile)
        
        # Save restored audio
        with wave.open(output_file, 'wb') as wav_out:
            wav_out.setparams(params)
            wav_out.writeframes(restored_data)
        
        print(f"Restored audio saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"Restoration error: {e}")
        return False


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python audio_restoration.py restore <input.wav> <output.wav> [profile]")
        print("  python audio_restoration.py analyze <input.wav>")
        print("  python audio_restoration.py profiles")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "restore":
        if len(sys.argv) < 4:
            print("Usage: python audio_restoration.py restore <input.wav> <output.wav> [profile]")
            sys.exit(1)
        
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        profile = sys.argv[4] if len(sys.argv) > 4 else 'digital_repair'
        
        success = restore_audio_file(input_file, output_file, profile)
        print("Restoration completed!" if success else "Restoration failed!")
    
    elif command == "analyze":
        if len(sys.argv) != 3:
            print("Usage: python audio_restoration.py analyze <input.wav>")
            sys.exit(1)
        
        input_file = sys.argv[2]
        
        try:
            with wave.open(input_file, 'rb') as wav:
                audio_data = wav.readframes(wav.getnframes())
                sample_rate = wav.getframerate()
            
            restorer = AudioRestoration(sample_rate)
            analysis = restorer.analyze_audio_problems(audio_data)
            
            print(f"Audio Analysis Report: {input_file}")
            print("=" * 50)
            print(f"Clipping: {analysis['clipping_percentage']:.1f}%")
            print(f"DC Offset: {analysis['dc_offset']:.4f}")
            print(f"Noise Level: {analysis['noise_level']:.4f}")
            print(f"Dropouts Detected: {analysis['dropouts_detected']}")
            print(f"Dynamic Range: {analysis['dynamic_range']:.1f} dB")
            
            if analysis['recommendations']:
                print("\nRecommendations:")
                for rec in analysis['recommendations']:
                    print(f"  - {rec}")
            else:
                print("\nNo major problems detected.")
        
        except Exception as e:
            print(f"Analysis error: {e}")
    
    elif command == "profiles":
        restorer = AudioRestoration()
        profiles = restorer.list_profiles()
        
        print("Available restoration profiles:")
        for profile_name in profiles:
            info = restorer.get_profile_info(profile_name)
            print(f"\n  {profile_name}:")
            print(f"    Description: {info.description}")
            print(f"    Algorithms: {', '.join(info.algorithms)}")
    
    else:
        print(f"Unknown command: {command}")