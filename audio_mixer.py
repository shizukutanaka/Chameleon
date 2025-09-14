#!/usr/bin/env python3
"""
Audio Mixer - Multi-track mixing and audio composition
Pure Python implementation with professional mixing features
"""

import struct
import math
import wave
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

class PanLaw(Enum):
    """Panning law types"""
    LINEAR = "linear"
    CONSTANT_POWER = "constant_power"
    MINUS_3DB = "-3dB"
    MINUS_4_5DB = "-4.5dB"
    MINUS_6DB = "-6dB"

@dataclass
class Track:
    """Audio track with mixing parameters"""
    name: str
    audio_data: bytes
    sample_rate: int = 44100
    channels: int = 1
    volume: float = 1.0  # 0.0 to 2.0
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)
    mute: bool = False
    solo: bool = False
    fx_send: float = 0.0  # Effect send level
    eq_low: float = 0.0  # -12dB to +12dB
    eq_mid: float = 0.0
    eq_high: float = 0.0
    
    def get_samples(self) -> List[float]:
        """Convert audio bytes to samples"""
        samples = []
        for i in range(0, len(self.audio_data) - 1, 2):
            sample = struct.unpack('<h', self.audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        return samples
    
    def set_samples(self, samples: List[float]):
        """Convert samples to audio bytes"""
        self.audio_data = b''
        for sample in samples:
            sample = max(-1.0, min(1.0, sample))
            sample_int = int(sample * 32767)
            self.audio_data += struct.pack('<h', sample_int)

class AudioMixer:
    """Professional multi-track audio mixer"""
    
    def __init__(self, sample_rate: int = 44100, channels: int = 2):
        self.sample_rate = sample_rate
        self.output_channels = channels
        self.tracks: List[Track] = []
        self.master_volume = 1.0
        self.master_limiter = True
        self.pan_law = PanLaw.CONSTANT_POWER
        
        # Aux/effect buses
        self.aux_buses: Dict[str, float] = {
            'reverb': 0.0,
            'delay': 0.0,
            'chorus': 0.0
        }
        
        # Master EQ
        self.master_eq = {
            'low': 0.0,
            'mid': 0.0,
            'high': 0.0
        }
        
    def add_track(self, track: Track) -> int:
        """Add a track to the mixer"""
        self.tracks.append(track)
        return len(self.tracks) - 1
    
    def remove_track(self, index: int):
        """Remove a track from the mixer"""
        if 0 <= index < len(self.tracks):
            del self.tracks[index]
    
    def set_track_volume(self, index: int, volume: float):
        """Set track volume (0.0 to 2.0)"""
        if 0 <= index < len(self.tracks):
            self.tracks[index].volume = max(0.0, min(2.0, volume))
    
    def set_track_pan(self, index: int, pan: float):
        """Set track pan (-1.0 to 1.0)"""
        if 0 <= index < len(self.tracks):
            self.tracks[index].pan = max(-1.0, min(1.0, pan))
    
    def set_track_mute(self, index: int, mute: bool):
        """Set track mute state"""
        if 0 <= index < len(self.tracks):
            self.tracks[index].mute = mute
    
    def set_track_solo(self, index: int, solo: bool):
        """Set track solo state"""
        if 0 <= index < len(self.tracks):
            self.tracks[index].solo = solo
    
    def mix(self, output_length: Optional[int] = None) -> bytes:
        """Mix all tracks to stereo output"""
        if not self.tracks:
            return b''
        
        # Determine output length
        if output_length is None:
            output_length = max(len(track.audio_data) // 2 for track in self.tracks)
        
        # Initialize output buffers (stereo)
        left_channel = [0.0] * output_length
        right_channel = [0.0] * output_length
        
        # Check if any track is soloed
        has_solo = any(track.solo for track in self.tracks)
        
        # Mix each track
        for track in self.tracks:
            # Skip muted tracks (unless soloed)
            if track.mute and not track.solo:
                continue
            
            # Skip non-soloed tracks if any track is soloed
            if has_solo and not track.solo:
                continue
            
            # Get track samples
            samples = track.get_samples()
            
            # Apply track EQ
            samples = self._apply_eq(samples, track.eq_low, track.eq_mid, track.eq_high)
            
            # Calculate pan gains
            left_gain, right_gain = self._calculate_pan_gains(track.pan)
            
            # Mix into output channels
            for i, sample in enumerate(samples):
                if i >= output_length:
                    break
                
                # Apply volume and pan
                left_sample = sample * track.volume * left_gain
                right_sample = sample * track.volume * right_gain
                
                # Add to output
                left_channel[i] += left_sample
                right_channel[i] += right_sample
        
        # Apply master processing
        left_channel = self._apply_eq(left_channel, 
                                      self.master_eq['low'],
                                      self.master_eq['mid'],
                                      self.master_eq['high'])
        right_channel = self._apply_eq(right_channel,
                                       self.master_eq['low'],
                                       self.master_eq['mid'],
                                       self.master_eq['high'])
        
        # Apply master volume
        left_channel = [s * self.master_volume for s in left_channel]
        right_channel = [s * self.master_volume for s in right_channel]
        
        # Apply limiter if enabled
        if self.master_limiter:
            left_channel = self._apply_limiter(left_channel)
            right_channel = self._apply_limiter(right_channel)
        
        # Convert to interleaved stereo bytes
        output = b''
        for left, right in zip(left_channel, right_channel):
            # Clip to valid range
            left = max(-1.0, min(1.0, left))
            right = max(-1.0, min(1.0, right))
            
            # Convert to 16-bit
            left_int = int(left * 32767)
            right_int = int(right * 32767)
            
            # Interleave stereo
            output += struct.pack('<hh', left_int, right_int)
        
        return output
    
    def mix_down_mono(self) -> bytes:
        """Mix all tracks to mono output"""
        stereo_mix = self.mix()
        
        # Convert stereo to mono
        mono_samples = []
        for i in range(0, len(stereo_mix) - 3, 4):
            left = struct.unpack('<h', stereo_mix[i:i+2])[0] / 32768.0
            right = struct.unpack('<h', stereo_mix[i+2:i+4])[0] / 32768.0
            mono = (left + right) / 2
            mono_samples.append(mono)
        
        # Convert to bytes
        output = b''
        for sample in mono_samples:
            sample_int = int(sample * 32767)
            output += struct.pack('<h', sample_int)
        
        return output
    
    def _calculate_pan_gains(self, pan: float) -> Tuple[float, float]:
        """Calculate left and right gains based on pan position"""
        # Pan: -1.0 (full left) to 1.0 (full right)
        
        if self.pan_law == PanLaw.LINEAR:
            # Linear panning
            left_gain = min(1.0, 1.0 - pan)
            right_gain = min(1.0, 1.0 + pan)
            
        elif self.pan_law == PanLaw.CONSTANT_POWER:
            # Constant power panning (default)
            angle = (pan + 1.0) * math.pi / 4
            left_gain = math.cos(angle)
            right_gain = math.sin(angle)
            
        elif self.pan_law == PanLaw.MINUS_3DB:
            # -3dB center
            left_gain = math.sqrt(0.5 * (1.0 - pan))
            right_gain = math.sqrt(0.5 * (1.0 + pan))
            
        elif self.pan_law == PanLaw.MINUS_4_5DB:
            # -4.5dB center
            left_gain = math.pow(0.5 * (1.0 - pan), 0.75)
            right_gain = math.pow(0.5 * (1.0 + pan), 0.75)
            
        else:  # -6dB
            # -6dB center
            left_gain = 0.5 * (1.0 - pan)
            right_gain = 0.5 * (1.0 + pan)
        
        return left_gain, right_gain
    
    def _apply_eq(self, samples: List[float], low: float, mid: float, high: float) -> List[float]:
        """Apply 3-band EQ to samples"""
        if low == 0 and mid == 0 and high == 0:
            return samples
        
        # Simple 3-band EQ using filters
        # Low: < 250 Hz, Mid: 250-4000 Hz, High: > 4000 Hz
        
        # Convert dB to linear gain
        low_gain = math.pow(10, low / 20)
        mid_gain = math.pow(10, mid / 20)
        high_gain = math.pow(10, high / 20)
        
        # Apply simple filtering (very basic implementation)
        output = []
        history_low = 0
        history_high = 0
        
        for i, sample in enumerate(samples):
            # Low-pass for bass (simple one-pole filter)
            cutoff_low = 250 / self.sample_rate
            alpha_low = cutoff_low / (cutoff_low + 1)
            history_low = alpha_low * sample + (1 - alpha_low) * history_low
            low_component = history_low * low_gain
            
            # High-pass for treble
            cutoff_high = 4000 / self.sample_rate
            alpha_high = 1 / (cutoff_high + 1)
            history_high = alpha_high * (history_high + sample - samples[i-1] if i > 0 else sample)
            high_component = history_high * high_gain
            
            # Mid is what's left
            mid_component = (sample - history_low - history_high) * mid_gain
            
            # Combine
            eq_sample = low_component + mid_component + high_component
            output.append(eq_sample)
        
        return output
    
    def _apply_limiter(self, samples: List[float], ceiling: float = 0.95) -> List[float]:
        """Apply brick-wall limiter"""
        output = []
        look_ahead = 5
        
        for i, sample in enumerate(samples):
            # Look ahead for peaks
            peak = abs(sample)
            for j in range(1, min(look_ahead, len(samples) - i)):
                peak = max(peak, abs(samples[i + j]))
            
            # Calculate gain reduction
            if peak > ceiling:
                gain = ceiling / peak
            else:
                gain = 1.0
            
            output.append(sample * gain)
        
        return output
    
    def bounce_to_file(self, filename: str, stereo: bool = True):
        """Bounce mix to audio file"""
        # Mix tracks
        if stereo:
            mixed_audio = self.mix()
            channels = 2
        else:
            mixed_audio = self.mix_down_mono()
            channels = 1
        
        # Save to file
        with wave.open(filename, 'wb') as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            wav.writeframes(mixed_audio)
    
    def get_track_info(self) -> List[Dict[str, Any]]:
        """Get information about all tracks"""
        info = []
        for i, track in enumerate(self.tracks):
            info.append({
                'index': i,
                'name': track.name,
                'volume': track.volume,
                'pan': track.pan,
                'mute': track.mute,
                'solo': track.solo,
                'duration': len(track.audio_data) / (2 * track.sample_rate)
            })
        return info
    
    def apply_automation(self, track_index: int, parameter: str,
                        automation_points: List[Tuple[float, float]]):
        """Apply automation to track parameter"""
        if not 0 <= track_index < len(self.tracks):
            return
        
        track = self.tracks[track_index]
        samples = track.get_samples()
        
        # Create automation curve
        automated_samples = []
        samples_per_second = track.sample_rate
        
        for i, sample in enumerate(samples):
            time = i / samples_per_second
            
            # Find automation value at this time
            value = self._interpolate_automation(time, automation_points)
            
            # Apply automation based on parameter
            if parameter == 'volume':
                automated_samples.append(sample * value)
            elif parameter == 'pan':
                # This would need stereo processing
                automated_samples.append(sample)
            else:
                automated_samples.append(sample)
        
        track.set_samples(automated_samples)
    
    def _interpolate_automation(self, time: float, 
                               points: List[Tuple[float, float]]) -> float:
        """Interpolate automation value at given time"""
        if not points:
            return 1.0
        
        # Find surrounding points
        prev_point = (0.0, points[0][1])
        next_point = points[-1]
        
        for point in points:
            if point[0] <= time:
                prev_point = point
            if point[0] > time:
                next_point = point
                break
        
        # Linear interpolation
        if prev_point[0] == next_point[0]:
            return prev_point[1]
        
        t = (time - prev_point[0]) / (next_point[0] - prev_point[0])
        return prev_point[1] + t * (next_point[1] - prev_point[1])


def create_multitrack_mix(track_files: List[str], output_file: str,
                         mix_settings: Optional[Dict[str, Any]] = None):
    """High-level function to create multi-track mix"""
    
    # Create mixer
    mixer = AudioMixer()
    
    # Load tracks
    for i, track_file in enumerate(track_files):
        try:
            # Load audio file
            with wave.open(track_file, 'rb') as wav:
                params = wav.getparams()
                audio_data = wav.readframes(params.nframes)
                
                # Create track
                track = Track(
                    name=f"Track {i+1}",
                    audio_data=audio_data,
                    sample_rate=params.framerate,
                    channels=params.nchannels
                )
                
                # Apply settings if provided
                if mix_settings and f'track_{i}' in mix_settings:
                    settings = mix_settings[f'track_{i}']
                    track.volume = settings.get('volume', 1.0)
                    track.pan = settings.get('pan', 0.0)
                    track.mute = settings.get('mute', False)
                    track.solo = settings.get('solo', False)
                
                mixer.add_track(track)
                print(f"Added track: {track_file}")
                
        except Exception as e:
            print(f"Error loading {track_file}: {e}")
    
    # Apply master settings
    if mix_settings:
        mixer.master_volume = mix_settings.get('master_volume', 1.0)
        mixer.master_limiter = mix_settings.get('master_limiter', True)
    
    # Mix and save
    print(f"Mixing {len(mixer.tracks)} tracks...")
    mixer.bounce_to_file(output_file, stereo=True)
    print(f"Mix saved to: {output_file}")
    
    # Show track info
    print("\nTrack Information:")
    for info in mixer.get_track_info():
        print(f"  {info['name']}: Vol={info['volume']:.1f}, Pan={info['pan']:+.1f}, Duration={info['duration']:.1f}s")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python audio_mixer.py <output.wav> <track1.wav> [track2.wav] ...")
        sys.exit(1)
    
    output_file = sys.argv[1]
    track_files = sys.argv[2:]
    
    # Example mix settings
    mix_settings = {
        'master_volume': 0.9,
        'master_limiter': True,
        'track_0': {'volume': 1.0, 'pan': -0.3},
        'track_1': {'volume': 0.8, 'pan': 0.3},
    }
    
    create_multitrack_mix(track_files, output_file, mix_settings)