#!/usr/bin/env python3
"""
Simple Audio Mixer - Mix multiple audio sources
"""

import array
import wave
import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from chameleon import AudioProcessor


class SimpleAudioMixer:
    """Mix multiple audio tracks with basic controls"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.processor = AudioProcessor(sample_rate)
        self.tracks = []

    def add_track(self, filepath: str, volume: float = 1.0,
                  start_time: float = 0.0, fade_in: float = 0.0,
                  fade_out: float = 0.0) -> bool:
        """Add audio track with timing and effects"""

        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return False

        try:
            # Load audio
            samples, info = self.processor.load_wav(filepath)
            if not samples:
                return False

            # Apply volume
            if volume != 1.0:
                samples = self.processor.amplify(samples,
                                                self.processor.linear_to_db(volume))

            # Apply fades
            if fade_in > 0 or fade_out > 0:
                fade_in_samples = int(fade_in * info['sample_rate'])
                fade_out_samples = int(fade_out * info['sample_rate'])
                samples = self.processor.fade(samples, fade_in_samples, fade_out_samples)

            track = {
                'samples': samples,
                'volume': volume,
                'start_time': start_time,
                'start_sample': int(start_time * info['sample_rate']),
                'duration': len(samples) / info['sample_rate'],
                'filepath': filepath,
                'info': info
            }

            self.tracks.append(track)
            print(f"Added track: {Path(filepath).name} ({track['duration']:.2f}s)")
            return True

        except Exception as e:
            print(f"Error adding track {filepath}: {e}")
            return False

    def mix_tracks(self, output_length: Optional[float] = None) -> array.array:
        """Mix all tracks together"""

        if not self.tracks:
            return array.array('h')

        # Calculate output length
        if output_length is None:
            output_length = max(track['start_time'] + track['duration']
                              for track in self.tracks)

        output_samples = int(output_length * self.sample_rate)
        mixed = array.array('h', [0] * output_samples)

        print(f"Mixing {len(self.tracks)} tracks into {output_length:.2f}s")

        for i, track in enumerate(self.tracks):
            start_idx = track['start_sample']
            samples = track['samples']

            print(f"  Track {i+1}: {Path(track['filepath']).name} at {track['start_time']:.2f}s")

            # Add track samples to mix
            for j, sample in enumerate(samples):
                mix_idx = start_idx + j
                if mix_idx < len(mixed):
                    # Simple addition mixing (may clip)
                    mixed_value = mixed[mix_idx] + sample
                    # Clamp to prevent overflow
                    mixed[mix_idx] = max(min(mixed_value, 32767), -32768)

        return mixed

    def export_mix(self, output_path: str, output_length: Optional[float] = None,
                   normalize: bool = True) -> bool:
        """Export mixed audio to file"""

        try:
            mixed = self.mix_tracks(output_length)

            if not mixed:
                print("No audio to export")
                return False

            # Normalize to prevent clipping
            if normalize:
                mixed = self.processor.normalize(mixed, target_peak=0.95)
                print("Applied normalization")

            # Save to file
            success = self.processor.save_wav(output_path, mixed, self.sample_rate)

            if success:
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                duration = len(mixed) / self.sample_rate
                print(f"Exported: {output_path} ({duration:.2f}s, {size_mb:.1f}MB)")

            return success

        except Exception as e:
            print(f"Export error: {e}")
            return False

    def clear_tracks(self):
        """Clear all tracks"""
        self.tracks.clear()
        print("Cleared all tracks")

    def get_track_info(self) -> List[Dict]:
        """Get information about all tracks"""
        info = []
        for i, track in enumerate(self.tracks):
            info.append({
                'index': i,
                'filename': Path(track['filepath']).name,
                'start_time': track['start_time'],
                'duration': track['duration'],
                'volume': track['volume']
            })
        return info


class AutoMixer:
    """Automatic mixing with smart level adjustment"""

    def __init__(self, sample_rate: int = 44100):
        self.mixer = SimpleAudioMixer(sample_rate)
        self.processor = AudioProcessor(sample_rate)

    def auto_mix_files(self, file_list: List[str], output_path: str,
                       gap_seconds: float = 0.5) -> bool:
        """Automatically mix files with equal spacing"""

        if not file_list:
            return False

        self.mixer.clear_tracks()
        current_time = 0.0

        print(f"Auto-mixing {len(file_list)} files with {gap_seconds}s gaps")

        for filepath in file_list:
            if os.path.exists(filepath):
                # Auto-adjust volume based on file analysis
                samples, info = self.processor.load_wav(filepath)
                if samples:
                    # Analyze loudness and adjust
                    rms = self.processor.get_rms(samples)
                    target_rms = 8000  # Target RMS level
                    volume = target_rms / rms if rms > 0 else 1.0
                    volume = min(volume, 3.0)  # Limit boost

                    self.mixer.add_track(filepath, volume=volume,
                                       start_time=current_time,
                                       fade_in=0.1, fade_out=0.1)

                    current_time += info['duration'] + gap_seconds

        return self.mixer.export_mix(output_path, normalize=True)

    def create_podcast_mix(self, intro_file: str, content_files: List[str],
                          outro_file: str, output_path: str) -> bool:
        """Create podcast-style mix with intro/outro"""

        self.mixer.clear_tracks()
        current_time = 0.0

        # Add intro
        if intro_file and os.path.exists(intro_file):
            self.mixer.add_track(intro_file, volume=1.0, start_time=current_time)
            intro_info = self.processor._get_file_info(intro_file)
            if intro_info:
                current_time += intro_info['duration'] + 0.5

        # Add content with consistent levels
        for content_file in content_files:
            if os.path.exists(content_file):
                self.mixer.add_track(content_file, volume=0.9,
                                   start_time=current_time,
                                   fade_in=0.2, fade_out=0.2)

                content_info = self.processor._get_file_info(content_file)
                if content_info:
                    current_time += content_info['duration'] + 1.0

        # Add outro
        if outro_file and os.path.exists(outro_file):
            self.mixer.add_track(outro_file, volume=1.0, start_time=current_time)

        return self.mixer.export_mix(output_path, normalize=True)


def demo():
    """Demo mixing functionality"""
    print("Audio Mixer Demo")
    print("-" * 40)

    # Create test audio files first
    from audio_recorder import SimpleRecorder

    recorder = SimpleRecorder()

    # Generate test files
    test_files = []
    for i, freq in enumerate([440, 523, 659]):  # A, C, E notes
        filename = f"test_tone_{i+1}.wav"
        recorder.generate_test_tone(freq, 1.0, filename)
        test_files.append(filename)
        print(f"Generated {filename} ({freq}Hz)")

    # Test simple mixing
    print("\n1. Simple mixing test:")
    mixer = SimpleAudioMixer()

    # Add tracks at different times
    mixer.add_track(test_files[0], volume=1.0, start_time=0.0)
    mixer.add_track(test_files[1], volume=0.7, start_time=0.5)
    mixer.add_track(test_files[2], volume=0.5, start_time=1.0)

    # Show track info
    tracks = mixer.get_track_info()
    for track in tracks:
        print(f"  Track {track['index']}: {track['filename']} "
              f"at {track['start_time']}s (vol: {track['volume']})")

    # Export mix
    mixer.export_mix("mixed_output.wav")

    # Test auto-mixer
    print("\n2. Auto-mixing test:")
    auto_mixer = AutoMixer()
    auto_mixer.auto_mix_files(test_files, "auto_mixed.wav", gap_seconds=0.3)

    # Cleanup
    for file in test_files + ["mixed_output.wav", "auto_mixed.wav"]:
        if os.path.exists(file):
            os.remove(file)
            print(f"Cleaned up: {file}")

    print("\nMixer demo complete!")


if __name__ == '__main__':
    demo()