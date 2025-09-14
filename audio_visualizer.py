#!/usr/bin/env python3
"""
Audio Visualizer - Terminal-based audio visualization
ASCII art visualization without heavy dependencies
"""

import math
import struct
import time
import sys
import os
from typing import List, Tuple, Dict, Optional, Any
from collections import deque
from dataclasses import dataclass

@dataclass
class VisualizationConfig:
    """Configuration for audio visualization"""
    width: int = 80
    height: int = 20
    fps: int = 30
    color: bool = True
    style: str = 'waveform'  # waveform, spectrum, spectrogram, level
    
class AudioVisualizer:
    """Terminal-based audio visualizer"""
    
    def __init__(self, config: Optional[VisualizationConfig] = None):
        self.config = config or VisualizationConfig()
        self.sample_rate = 44100
        
        # Visualization buffers
        self.waveform_buffer = deque(maxlen=self.config.width)
        self.spectrum_buffer = deque(maxlen=self.config.width)
        self.spectrogram_buffer = deque(maxlen=self.config.height)
        self.level_history = deque(maxlen=self.config.width)
        
        # Initialize with zeros
        for _ in range(self.config.width):
            self.waveform_buffer.append(0)
            self.spectrum_buffer.append(0)
            self.level_history.append(0)
        
        # Color codes
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'reset': '\033[0m',
            'bold': '\033[1m'
        }
    
    def visualize_waveform(self, audio_data: bytes) -> str:
        """Create waveform visualization"""
        # Convert bytes to samples
        samples = self._bytes_to_samples(audio_data)
        
        # Downsample to display width
        step = max(1, len(samples) // self.config.width)
        
        # Update buffer with new samples
        for i in range(0, len(samples), step):
            if i < len(samples):
                self.waveform_buffer.append(samples[i])
        
        # Create visualization
        lines = []
        
        # Create amplitude map
        mid = self.config.height // 2
        for y in range(self.config.height):
            line = ""
            for x in range(self.config.width):
                sample = self.waveform_buffer[x]
                amplitude = int(sample * mid)
                
                # Determine character based on position
                if y == mid:
                    if abs(amplitude) < 1:
                        char = "─"
                    else:
                        char = "┼"
                elif y == mid - amplitude:
                    char = "█"
                elif (amplitude > 0 and mid - amplitude < y < mid) or \
                     (amplitude < 0 and mid < y < mid - amplitude):
                    char = "│"
                else:
                    char = " "
                
                # Add color based on amplitude
                if self.config.color and char != " ":
                    if abs(sample) > 0.8:
                        line += self.colors['red'] + char + self.colors['reset']
                    elif abs(sample) > 0.5:
                        line += self.colors['yellow'] + char + self.colors['reset']
                    else:
                        line += self.colors['green'] + char + self.colors['reset']
                else:
                    line += char
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def visualize_spectrum(self, audio_data: bytes) -> str:
        """Create frequency spectrum visualization"""
        # Compute spectrum
        spectrum = self._compute_spectrum(audio_data)
        
        # Group frequencies into bands
        num_bands = self.config.width
        bands = self._group_spectrum_bands(spectrum, num_bands)
        
        # Update buffer
        self.spectrum_buffer = deque(bands, maxlen=self.config.width)
        
        # Create bar chart visualization
        lines = []
        max_height = self.config.height
        
        for y in range(max_height):
            line = ""
            for x in range(len(bands)):
                level = bands[x]
                bar_height = int(level * max_height)
                
                if max_height - y <= bar_height:
                    # Determine character and color
                    if y == 0:
                        char = "▁"
                    elif y < max_height // 4:
                        char = "▄"
                    elif y < max_height // 2:
                        char = "█"
                    else:
                        char = "█"
                    
                    # Color based on frequency range
                    if self.config.color:
                        if x < num_bands // 4:  # Bass
                            line += self.colors['blue'] + char + self.colors['reset']
                        elif x < num_bands // 2:  # Mid
                            line += self.colors['green'] + char + self.colors['reset']
                        elif x < 3 * num_bands // 4:  # High-mid
                            line += self.colors['yellow'] + char + self.colors['reset']
                        else:  # Treble
                            line += self.colors['magenta'] + char + self.colors['reset']
                    else:
                        line += char
                else:
                    line += " "
            
            lines.append(line)
        
        # Add frequency labels
        lines.append("─" * self.config.width)
        labels = "20Hz" + " " * (self.config.width // 2 - 8) + "10kHz" + " " * (self.config.width // 2 - 5) + "20kHz"
        lines.append(labels[:self.config.width])
        
        return "\n".join(lines)
    
    def visualize_spectrogram(self, audio_data: bytes) -> str:
        """Create spectrogram visualization (waterfall)"""
        # Compute spectrum for current frame
        spectrum = self._compute_spectrum(audio_data)
        bands = self._group_spectrum_bands(spectrum, self.config.width)
        
        # Add to spectrogram buffer (newest at top)
        self.spectrogram_buffer.appendleft(bands)
        
        # Create visualization
        lines = []
        intensity_chars = " ░▒▓█"
        
        for y in range(min(len(self.spectrogram_buffer), self.config.height)):
            line = ""
            row = self.spectrogram_buffer[y]
            
            for x in range(len(row)):
                # Map intensity to character
                intensity = row[x]
                char_index = int(intensity * (len(intensity_chars) - 1))
                char = intensity_chars[char_index]
                
                # Add color based on intensity
                if self.config.color and char != " ":
                    if intensity > 0.8:
                        line += self.colors['red'] + char + self.colors['reset']
                    elif intensity > 0.5:
                        line += self.colors['yellow'] + char + self.colors['reset']
                    elif intensity > 0.2:
                        line += self.colors['green'] + char + self.colors['reset']
                    else:
                        line += self.colors['blue'] + char + self.colors['reset']
                else:
                    line += char
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def visualize_levels(self, audio_data: bytes) -> str:
        """Create level meter visualization"""
        # Calculate levels
        rms = self._calculate_rms(audio_data)
        peak = self._calculate_peak(audio_data)
        
        # Update history
        self.level_history.append(rms)
        
        # Create visualization
        lines = []
        
        # Peak meter
        peak_width = int(peak * self.config.width)
        peak_bar = "█" * peak_width + "░" * (self.config.width - peak_width)
        
        # RMS meter
        rms_width = int(rms * self.config.width)
        rms_bar = "█" * rms_width + "░" * (self.config.width - rms_width)
        
        # History graph
        history_height = self.config.height - 6
        for y in range(history_height):
            line = ""
            threshold = 1.0 - (y / history_height)
            
            for x in range(len(self.level_history)):
                if self.level_history[x] >= threshold:
                    char = "█"
                else:
                    char = " "
                
                # Color coding
                if self.config.color and char == "█":
                    if self.level_history[x] > 0.9:
                        line += self.colors['red'] + char + self.colors['reset']
                    elif self.level_history[x] > 0.7:
                        line += self.colors['yellow'] + char + self.colors['reset']
                    else:
                        line += self.colors['green'] + char + self.colors['reset']
                else:
                    line += char
            
            lines.append(line)
        
        # Add meters
        lines.append("─" * self.config.width)
        
        # Peak meter with color
        if self.config.color:
            if peak > 0.9:
                color = self.colors['red']
            elif peak > 0.7:
                color = self.colors['yellow']
            else:
                color = self.colors['green']
            lines.append(f"PEAK: {color}[{peak_bar}]{self.colors['reset']} {peak:.1%}")
        else:
            lines.append(f"PEAK: [{peak_bar}] {peak:.1%}")
        
        # RMS meter with color
        if self.config.color:
            if rms > 0.9:
                color = self.colors['red']
            elif rms > 0.7:
                color = self.colors['yellow']
            else:
                color = self.colors['green']
            lines.append(f"RMS:  {color}[{rms_bar}]{self.colors['reset']} {rms:.1%}")
        else:
            lines.append(f"RMS:  [{rms_bar}] {rms:.1%}")
        
        # Add dB scale
        lines.append("─" * self.config.width)
        db_peak = 20 * math.log10(max(peak, 0.0001))
        db_rms = 20 * math.log10(max(rms, 0.0001))
        lines.append(f"Peak: {db_peak:+.1f} dB  |  RMS: {db_rms:+.1f} dB")
        
        return "\n".join(lines)
    
    def visualize_combined(self, audio_data: bytes) -> str:
        """Create combined visualization with multiple views"""
        lines = []
        
        # Header
        lines.append("╔" + "═" * (self.config.width - 2) + "╗")
        lines.append("║" + " CHAMELEON AUDIO VISUALIZER ".center(self.config.width - 2) + "║")
        lines.append("╠" + "═" * (self.config.width - 2) + "╣")
        
        # Mini waveform (top 1/3)
        mini_height = self.config.height // 3
        waveform_config = VisualizationConfig(
            width=self.config.width - 4,
            height=mini_height,
            color=self.config.color,
            style='waveform'
        )
        mini_viz = AudioVisualizer(waveform_config)
        mini_viz.waveform_buffer = self.waveform_buffer
        waveform = mini_viz.visualize_waveform(audio_data)
        
        for line in waveform.split('\n'):
            lines.append("║ " + line.ljust(self.config.width - 4) + " ║")
        
        lines.append("╠" + "═" * (self.config.width - 2) + "╣")
        
        # Spectrum (middle 1/3)
        spectrum_config = VisualizationConfig(
            width=self.config.width - 4,
            height=mini_height,
            color=self.config.color,
            style='spectrum'
        )
        spectrum_viz = AudioVisualizer(spectrum_config)
        spectrum = spectrum_viz.visualize_spectrum(audio_data)
        
        for line in spectrum.split('\n')[:mini_height]:
            lines.append("║ " + line.ljust(self.config.width - 4) + " ║")
        
        lines.append("╠" + "═" * (self.config.width - 2) + "╣")
        
        # Level meters (bottom)
        rms = self._calculate_rms(audio_data)
        peak = self._calculate_peak(audio_data)
        
        # Create compact meters
        meter_width = (self.config.width - 20) // 2
        rms_bar = "█" * int(rms * meter_width) + "░" * (meter_width - int(rms * meter_width))
        peak_bar = "█" * int(peak * meter_width) + "░" * (meter_width - int(peak * meter_width))
        
        lines.append(f"║ RMS:  [{rms_bar}] {rms:4.1%} ║")
        lines.append(f"║ PEAK: [{peak_bar}] {peak:4.1%} ║")
        
        # Footer
        lines.append("╚" + "═" * (self.config.width - 2) + "╝")
        
        return "\n".join(lines)
    
    def _bytes_to_samples(self, audio_data: bytes) -> List[float]:
        """Convert audio bytes to normalized samples"""
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
            samples.append(sample)
        return samples
    
    def _compute_spectrum(self, audio_data: bytes) -> Dict[float, float]:
        """Simple spectrum computation"""
        samples = self._bytes_to_samples(audio_data)
        
        # Simple DFT for visualization (not accurate but fast)
        spectrum = {}
        N = min(len(samples), 512)
        
        for k in range(N // 2):
            freq = k * self.sample_rate / N
            
            # Skip very high frequencies for visualization
            if freq > 20000:
                break
            
            # Compute magnitude for this frequency
            real = sum(samples[n] * math.cos(2 * math.pi * k * n / N) 
                      for n in range(min(N, len(samples))))
            imag = sum(samples[n] * math.sin(2 * math.pi * k * n / N)
                      for n in range(min(N, len(samples))))
            
            magnitude = math.sqrt(real ** 2 + imag ** 2) / N
            spectrum[freq] = magnitude
        
        return spectrum
    
    def _group_spectrum_bands(self, spectrum: Dict[float, float], 
                             num_bands: int) -> List[float]:
        """Group spectrum into frequency bands"""
        bands = [0.0] * num_bands
        
        # Logarithmic frequency scale
        min_freq = 20
        max_freq = 20000
        
        for i in range(num_bands):
            # Calculate frequency range for this band
            freq_low = min_freq * (max_freq / min_freq) ** (i / num_bands)
            freq_high = min_freq * (max_freq / min_freq) ** ((i + 1) / num_bands)
            
            # Sum magnitudes in this range
            band_sum = 0
            count = 0
            
            for freq, mag in spectrum.items():
                if freq_low <= freq < freq_high:
                    band_sum += mag
                    count += 1
            
            if count > 0:
                bands[i] = min(1.0, band_sum / count * 10)  # Scale for visibility
        
        return bands
    
    def _calculate_rms(self, audio_data: bytes) -> float:
        """Calculate RMS level"""
        samples = self._bytes_to_samples(audio_data)
        if not samples:
            return 0.0
        
        rms = math.sqrt(sum(s ** 2 for s in samples) / len(samples))
        return min(1.0, rms)
    
    def _calculate_peak(self, audio_data: bytes) -> float:
        """Calculate peak level"""
        samples = self._bytes_to_samples(audio_data)
        if not samples:
            return 0.0
        
        peak = max(abs(s) for s in samples)
        return min(1.0, peak)
    
    def animate(self, audio_stream, duration: Optional[float] = None):
        """Animate visualization with audio stream"""
        start_time = time.time()
        
        try:
            while True:
                if duration and (time.time() - start_time) > duration:
                    break
                
                # Get audio chunk
                audio_chunk = audio_stream.read(1024)
                
                # Clear screen
                os.system('cls' if sys.platform == 'win32' else 'clear')
                
                # Generate visualization
                if self.config.style == 'waveform':
                    viz = self.visualize_waveform(audio_chunk)
                elif self.config.style == 'spectrum':
                    viz = self.visualize_spectrum(audio_chunk)
                elif self.config.style == 'spectrogram':
                    viz = self.visualize_spectrogram(audio_chunk)
                elif self.config.style == 'level':
                    viz = self.visualize_levels(audio_chunk)
                elif self.config.style == 'combined':
                    viz = self.visualize_combined(audio_chunk)
                else:
                    viz = self.visualize_waveform(audio_chunk)
                
                # Display
                print(viz)
                
                # Frame rate control
                time.sleep(1.0 / self.config.fps)
                
        except KeyboardInterrupt:
            print("\nVisualization stopped.")


def visualize_audio_file(filename: str, style: str = 'combined', 
                         duration: Optional[float] = None):
    """Visualize audio from file"""
    import wave
    
    try:
        # Open audio file
        with wave.open(filename, 'rb') as wav:
            sample_rate = wav.getframerate()
            num_frames = wav.getnframes()
            
            # Create visualizer
            config = VisualizationConfig(
                width=min(120, os.get_terminal_size().columns),
                height=min(30, os.get_terminal_size().lines - 5),
                style=style,
                color=True
            )
            visualizer = AudioVisualizer(config)
            visualizer.sample_rate = sample_rate
            
            # Process in chunks
            chunk_size = 1024
            frame_count = 0
            
            print(f"Visualizing: {filename}")
            print(f"Style: {style}")
            print("Press Ctrl+C to stop\n")
            time.sleep(2)
            
            while frame_count < num_frames:
                # Read chunk
                chunk_frames = min(chunk_size, num_frames - frame_count)
                audio_data = wav.readframes(chunk_frames)
                
                if not audio_data:
                    break
                
                # Clear screen
                os.system('cls' if sys.platform == 'win32' else 'clear')
                
                # Generate and display visualization
                if style == 'waveform':
                    viz = visualizer.visualize_waveform(audio_data)
                elif style == 'spectrum':
                    viz = visualizer.visualize_spectrum(audio_data)
                elif style == 'spectrogram':
                    viz = visualizer.visualize_spectrogram(audio_data)
                elif style == 'level':
                    viz = visualizer.visualize_levels(audio_data)
                else:  # combined
                    viz = visualizer.visualize_combined(audio_data)
                
                print(viz)
                
                # Progress
                progress = frame_count / num_frames
                print(f"\nProgress: {progress:.1%} | {frame_count/sample_rate:.1f}s / {num_frames/sample_rate:.1f}s")
                
                frame_count += chunk_frames
                
                # Control playback speed
                time.sleep(chunk_frames / sample_rate)
                
                if duration and frame_count / sample_rate > duration:
                    break
            
            print("\nVisualization complete!")
            
    except KeyboardInterrupt:
        print("\nVisualization stopped.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python audio_visualizer.py <audio_file> [style]")
        print("Styles: waveform, spectrum, spectrogram, level, combined")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    style = sys.argv[2] if len(sys.argv) > 2 else 'combined'
    
    visualize_audio_file(audio_file, style)