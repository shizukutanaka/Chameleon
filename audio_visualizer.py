#!/usr/bin/env python3
"""
Audio Visualizer - Text-based audio visualization
"""

import array
import math
from typing import List, Tuple, Optional

from chameleon import AudioProcessor
from audio_analyzer import AudioAnalyzer


class TextVisualizer:
    """Text-based audio visualization without external dependencies"""

    def __init__(self, width: int = 80, height: int = 20):
        self.width = width
        self.height = height
        self.chars = [' ', '░', '▒', '▓', '█']

    def draw_waveform(self, samples: array.array, title: str = "Waveform") -> List[str]:
        """Draw waveform using text characters"""
        if not samples:
            return [f"{title}: No data"]

        lines = [f"{title} ({len(samples)} samples)"]
        lines.append("=" * self.width)

        # Downsample for display
        step = max(1, len(samples) // self.width)
        display_samples = []

        for i in range(0, len(samples), step):
            chunk = samples[i:i+step]
            if chunk:
                # Use RMS for better representation
                rms = math.sqrt(sum(s*s for s in chunk) / len(chunk))
                display_samples.append(rms)

        if not display_samples:
            return lines + ["No data to display"]

        # Normalize to display height
        max_val = max(display_samples) if display_samples else 1
        scale = (self.height - 1) / max_val if max_val > 0 else 1

        # Create display grid
        grid = [[' ' for _ in range(self.width)] for _ in range(self.height)]

        for x, sample in enumerate(display_samples[:self.width]):
            height_pos = int(sample * scale)
            height_pos = min(height_pos, self.height - 1)

            # Fill from bottom up
            for y in range(height_pos + 1):
                if y < self.height:
                    char_idx = min(4, int(sample * scale * 4 / (self.height - 1)))
                    grid[self.height - 1 - y][x] = self.chars[char_idx]

        # Convert grid to lines
        for row in grid:
            lines.append(''.join(row))

        lines.append("=" * self.width)
        lines.append(f"Peak: {max(display_samples):.0f}, Samples: {len(samples)}")

        return lines

    def draw_spectrum(self, samples: array.array, title: str = "Spectrum") -> List[str]:
        """Draw frequency spectrum using text"""
        if not samples:
            return [f"{title}: No data"]

        analyzer = AudioAnalyzer()
        bands = analyzer.get_spectrum_bands(samples, self.width // 4)

        lines = [f"{title} (Frequency Bands)"]
        lines.append("=" * self.width)

        if not bands:
            return lines + ["No spectrum data"]

        # Normalize bands
        max_band = max(bands) if bands else 1
        scale = (self.height - 1) / max_band if max_band > 0 else 1

        # Create bar chart
        for i in range(self.height - 1, -1, -1):
            line = ""
            for band_val in bands:
                bar_height = int(band_val * scale)
                if bar_height >= i:
                    char_idx = min(4, int((bar_height - i) * 4))
                    line += self.chars[char_idx] * 3 + " "
                else:
                    line += "    "
            lines.append(line[:self.width])

        lines.append("=" * self.width)

        # Add frequency labels
        freq_labels = ""
        for i in range(len(bands)):
            if i % 4 == 0:
                freq = int(22050 * (i + 1) / len(bands))  # Approximate frequency
                freq_labels += f"{freq:>3} ".ljust(4)
        lines.append(freq_labels[:self.width])

        return lines

    def draw_levels(self, samples: array.array, title: str = "Levels") -> List[str]:
        """Draw level meters"""
        if not samples:
            return [f"{title}: No data"]

        analyzer = AudioAnalyzer()

        # Calculate levels
        rms = analyzer.get_rms(samples)
        peak = analyzer.get_peak(samples)

        # Convert to dB
        processor = AudioProcessor()
        rms_db = processor.linear_to_db(rms / 32767) if rms > 0 else -60
        peak_db = processor.linear_to_db(peak / 32767) if peak > 0 else -60

        lines = [f"{title}"]
        lines.append("=" * self.width)

        # RMS meter
        rms_level = max(0, (rms_db + 60) / 60)  # Normalize -60dB to 0dB range
        rms_chars = int(rms_level * (self.width - 10))
        rms_meter = "RMS:  [" + "█" * rms_chars + " " * (self.width - 10 - rms_chars) + f"] {rms_db:5.1f}dB"
        lines.append(rms_meter[:self.width])

        # Peak meter
        peak_level = max(0, (peak_db + 60) / 60)
        peak_chars = int(peak_level * (self.width - 10))

        # Color coding with characters
        meter_chars = []
        for i in range(self.width - 10):
            if i < peak_chars:
                if i / (self.width - 10) > 0.8:  # Red zone
                    meter_chars.append("█")
                elif i / (self.width - 10) > 0.6:  # Yellow zone
                    meter_chars.append("▓")
                else:  # Green zone
                    meter_chars.append("▒")
            else:
                meter_chars.append(" ")

        peak_meter = "Peak: [" + "".join(meter_chars) + f"] {peak_db:5.1f}dB"
        lines.append(peak_meter[:self.width])

        lines.append("=" * self.width)

        # Add additional info
        zero_crossings = analyzer.get_zero_crossings(samples)
        zcr = zero_crossings / len(samples) if len(samples) > 0 else 0
        lines.append(f"Zero crossings: {zero_crossings} ({zcr:.4f} rate)")

        return lines

    def draw_voice_activity(self, samples: array.array, window_size: int = 4096) -> List[str]:
        """Visualize voice activity detection"""
        processor = AudioProcessor()
        segments = processor.detect_voice_activity(samples, window_size)

        lines = ["Voice Activity Detection"]
        lines.append("=" * self.width)

        if not segments:
            lines.append("No voice activity detected")
            return lines

        # Create timeline
        duration = len(samples) / 44100  # Assume 44.1kHz
        scale = self.width / duration if duration > 0 else 1

        timeline = [' '] * self.width

        for start, end in segments:
            start_pos = int((start / 44100) * scale)
            end_pos = int((end / 44100) * scale)
            start_pos = max(0, min(start_pos, self.width - 1))
            end_pos = max(0, min(end_pos, self.width - 1))

            for i in range(start_pos, end_pos + 1):
                if i < len(timeline):
                    timeline[i] = '█'

        lines.append("Timeline: " + "".join(timeline))
        lines.append(f"Duration: {duration:.2f}s")
        lines.append(f"Voice segments: {len(segments)}")

        # Show segment details
        for i, (start, end) in enumerate(segments[:5]):  # Show first 5
            start_time = start / 44100
            end_time = end / 44100
            lines.append(f"  Segment {i+1}: {start_time:.2f}s - {end_time:.2f}s")

        return lines


class AudioReport:
    """Generate comprehensive text-based audio reports"""

    def __init__(self):
        self.visualizer = TextVisualizer()
        self.processor = AudioProcessor()
        self.analyzer = AudioAnalyzer()

    def generate_report(self, filepath: str) -> List[str]:
        """Generate complete audio analysis report"""

        lines = [f"Audio Analysis Report: {filepath}"]
        lines.append("=" * 80)

        try:
            # Load file
            samples, info = self.processor.load_wav(filepath)
            if not samples:
                return lines + ["Error: Could not load audio file"]

            # File information
            lines.append("FILE INFORMATION:")
            lines.append(f"  Format: {info.get('format', 'unknown')}")
            lines.append(f"  Duration: {info.get('duration', 0):.2f} seconds")
            lines.append(f"  Sample Rate: {info.get('sample_rate', 0)} Hz")
            lines.append(f"  Channels: {info.get('channels', 0)}")
            lines.append(f"  Size: {info.get('size_bytes', 0)} bytes")
            lines.append("")

            # Basic statistics
            stats = self.processor.get_statistics(samples)
            lines.append("AUDIO STATISTICS:")
            lines.append(f"  RMS Level: {stats.get('rms', 0):.2f}")
            lines.append(f"  Peak Level: {stats.get('peak', 0)}")
            lines.append(f"  Dynamic Range: {stats.get('dynamic_range', 0):.2f}")
            lines.append(f"  Zero Crossings: {stats.get('zero_crossings', 0)}")
            lines.append(f"  Estimated Frequency: {stats.get('estimated_frequency', 0):.2f} Hz")
            lines.append("")

            # Visualizations (use smaller samples for performance)
            display_samples = samples[:44100]  # First second

            # Waveform
            lines.extend(self.visualizer.draw_waveform(display_samples, "WAVEFORM (first second)"))
            lines.append("")

            # Spectrum
            lines.extend(self.visualizer.draw_spectrum(display_samples, "FREQUENCY SPECTRUM"))
            lines.append("")

            # Levels
            lines.extend(self.visualizer.draw_levels(display_samples, "LEVEL METERS"))
            lines.append("")

            # Voice activity
            lines.extend(self.visualizer.draw_voice_activity(samples, "VOICE ACTIVITY"))
            lines.append("")

            # Metadata if available
            if 'metadata' in info and info['metadata']:
                lines.append("METADATA:")
                for key, value in info['metadata'].items():
                    lines.append(f"  {key.title()}: {value}")
                lines.append("")

        except Exception as e:
            lines.append(f"Error generating report: {e}")

        lines.append("=" * 80)
        lines.append("Report complete")

        return lines

    def save_report(self, filepath: str, output_path: str) -> bool:
        """Save report to text file"""
        try:
            report = self.generate_report(filepath)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report))
            print(f"Report saved to: {output_path}")
            return True
        except Exception as e:
            print(f"Error saving report: {e}")
            return False


def demo():
    """Demo visualization features"""
    print("Audio Visualizer Demo")
    print("-" * 40)

    # Create test signal
    from audio_recorder import SimpleRecorder

    recorder = SimpleRecorder()
    test_file = "test_viz.wav"
    recorder.generate_test_tone(440, 2.0, test_file)

    # Test visualizations
    visualizer = TextVisualizer(width=60, height=10)
    processor = AudioProcessor()

    try:
        samples, _ = processor.load_wav(test_file)

        if samples:
            # Show different visualizations
            print("\n1. Waveform:")
            waveform = visualizer.draw_waveform(samples[:4410])  # First 0.1 second
            for line in waveform:
                print(line)

            print("\n2. Spectrum:")
            spectrum = visualizer.draw_spectrum(samples[:4410])
            for line in spectrum:
                print(line)

            print("\n3. Level Meters:")
            levels = visualizer.draw_levels(samples[:4410])
            for line in levels:
                print(line)

        # Generate full report
        print("\n4. Generating full report...")
        reporter = AudioReport()
        report_file = "audio_report.txt"
        if reporter.save_report(test_file, report_file):
            print(f"Full report saved to: {report_file}")

            # Show first few lines
            with open(report_file, 'r') as f:
                lines = f.readlines()
                print("\nFirst 10 lines of report:")
                for line in lines[:10]:
                    print(line.rstrip())

    finally:
        # Cleanup
        import os
        for file in [test_file, "audio_report.txt"]:
            if os.path.exists(file):
                os.remove(file)
                print(f"Cleaned up: {file}")

    print("\nVisualization demo complete!")


if __name__ == '__main__':
    demo()