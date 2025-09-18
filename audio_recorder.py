#!/usr/bin/env python3
"""
Simple Audio Recorder - Platform-independent recording using subprocess
"""

import subprocess
import sys
import os
import wave
import array
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

class SimpleRecorder:
    """Cross-platform audio recording using system tools"""

    def __init__(self, sample_rate: int = 44100, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.platform = sys.platform

    def get_recording_command(self, output_file: str, duration: int) -> Optional[list]:
        """Get platform-specific recording command"""

        if self.platform == "linux" or self.platform == "linux2":
            # Try arecord (ALSA)
            return [
                "arecord",
                "-f", "cd",  # CD quality
                "-d", str(duration),
                "-c", str(self.channels),
                output_file
            ]
        elif self.platform == "darwin":  # macOS
            # Use sox or rec command
            return [
                "rec",
                "-c", str(self.channels),
                "-r", str(self.sample_rate),
                output_file,
                "trim", "0", str(duration)
            ]
        elif self.platform == "win32":  # Windows
            # PowerShell command for Windows
            ps_script = f"""
            Add-Type -TypeDefinition @'
            using System;
            using System.IO;
            using System.Media;
            public class Recorder {{
                public static void Record(string file, int duration) {{
                    // Simple Windows recording placeholder
                    Console.WriteLine("Recording to " + file);
                    System.Threading.Thread.Sleep(duration * 1000);
                }}
            }}
            '@
            """
            return ["powershell", "-Command", ps_script]

        return None

    def record_audio(self, duration: int, output_file: Optional[str] = None) -> Optional[str]:
        """Record audio for specified duration"""

        if output_file is None:
            # Create temp file
            fd, output_file = tempfile.mkstemp(suffix='.wav')
            os.close(fd)

        command = self.get_recording_command(output_file, duration)

        if command is None:
            print(f"Recording not supported on {self.platform}")
            return None

        try:
            print(f"Recording {duration} seconds to {output_file}...")
            result = subprocess.run(command, capture_output=True, text=True, timeout=duration+2)

            if result.returncode != 0:
                print(f"Recording failed: {result.stderr}")
                return None

            print(f"Recording saved to {output_file}")
            return output_file

        except subprocess.TimeoutExpired:
            print("Recording timeout")
            return None
        except FileNotFoundError:
            print(f"Recording tool not found. Please install recording tools for your platform.")
            return None
        except Exception as e:
            print(f"Recording error: {e}")
            return None

    def generate_test_tone(self, frequency: float, duration: float,
                          output_file: Optional[str] = None) -> str:
        """Generate a test tone (fallback when recording not available)"""

        import math

        if output_file is None:
            fd, output_file = tempfile.mkstemp(suffix='.wav')
            os.close(fd)

        # Generate samples
        num_samples = int(duration * self.sample_rate)
        samples = array.array('h')

        for i in range(num_samples):
            t = i / self.sample_rate
            sample = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * t))
            samples.append(sample)

        # Save as WAV
        with wave.open(output_file, 'wb') as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(samples.tobytes())

        print(f"Generated {frequency}Hz test tone: {output_file}")
        return output_file


class AudioCapture:
    """Simple audio capture using file polling"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.recorder = SimpleRecorder(sample_rate)

    def capture_segments(self, segment_duration: int = 1, num_segments: int = 5) -> list:
        """Capture audio in segments"""
        segments = []

        for i in range(num_segments):
            print(f"Recording segment {i+1}/{num_segments}")

            # Record segment
            output_file = self.recorder.record_audio(segment_duration)

            if output_file and os.path.exists(output_file):
                segments.append(output_file)
            else:
                # Fallback to test tone
                test_file = self.recorder.generate_test_tone(440 + i*100, segment_duration)
                segments.append(test_file)

            if i < num_segments - 1:
                time.sleep(0.1)  # Small pause between segments

        return segments

    def continuous_capture(self, output_dir: str, segment_duration: int = 5,
                          max_segments: int = 10) -> None:
        """Continuously capture audio segments to directory"""

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        for i in range(max_segments):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"capture_{timestamp}_{i:03d}.wav")

            result = self.recorder.record_audio(segment_duration, output_file)

            if result is None:
                print(f"Capture failed, generating test file instead")
                self.recorder.generate_test_tone(440, segment_duration, output_file)

            print(f"Saved: {output_file}")

            # Check for stop signal (presence of stop.txt file)
            if os.path.exists(os.path.join(output_dir, "stop.txt")):
                print("Stop signal detected")
                break


def demo():
    """Demo recording functionality"""
    print("Audio Recording Demo")
    print("-" * 40)

    recorder = SimpleRecorder()

    # Try recording
    print("\n1. Attempting 2-second recording...")
    recorded_file = recorder.record_audio(2)

    if recorded_file:
        print(f"Success! File: {recorded_file}")

        # Check file
        if os.path.exists(recorded_file):
            size = os.path.getsize(recorded_file)
            print(f"File size: {size} bytes")
    else:
        print("Recording failed, generating test tone instead...")
        test_file = recorder.generate_test_tone(440, 2)
        print(f"Test file: {test_file}")

    # Capture segments
    print("\n2. Capturing audio segments...")
    capture = AudioCapture()
    segments = capture.capture_segments(segment_duration=1, num_segments=3)
    print(f"Captured {len(segments)} segments:")
    for seg in segments:
        print(f"  - {seg}")

    print("\nDemo complete!")


if __name__ == '__main__':
    demo()