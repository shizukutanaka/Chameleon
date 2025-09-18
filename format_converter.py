#!/usr/bin/env python3
"""
Format Converter - Convert between different audio formats
"""

import array
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from chameleon import AudioProcessor


class FormatConverter:
    """Convert between audio formats using available tools"""

    def __init__(self):
        self.processor = AudioProcessor()
        self.supported_input = {'.wav', '.raw', '.pcm'}
        self.supported_output = {'.wav', '.raw', '.pcm'}

    def detect_external_tools(self) -> Dict[str, bool]:
        """Detect available external conversion tools"""
        tools = {}

        # Check for FFmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            tools['ffmpeg'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            tools['ffmpeg'] = False

        # Check for SoX
        try:
            subprocess.run(['sox', '--version'], capture_output=True, check=True)
            tools['sox'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            tools['sox'] = False

        return tools

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """Get list of supported input and output formats"""
        tools = self.detect_external_tools()

        input_formats = list(self.supported_input)
        output_formats = list(self.supported_output)

        if tools.get('ffmpeg'):
            input_formats.extend(['.mp3', '.flac', '.ogg', '.m4a', '.aac'])
            output_formats.extend(['.mp3', '.flac', '.ogg'])

        if tools.get('sox'):
            input_formats.extend(['.aiff', '.au', '.snd'])
            output_formats.extend(['.aiff', '.au'])

        return {
            'input': sorted(set(input_formats)),
            'output': sorted(set(output_formats))
        }

    def convert_file(self, input_path: str, output_path: str,
                    target_format: Optional[str] = None,
                    sample_rate: Optional[int] = None,
                    channels: Optional[int] = None,
                    quality: str = 'high') -> bool:
        """Convert audio file to different format"""

        if not os.path.exists(input_path):
            print(f"Input file not found: {input_path}")
            return False

        # Determine target format
        if target_format is None:
            target_format = Path(output_path).suffix.lower()

        input_format = Path(input_path).suffix.lower()

        print(f"Converting {input_format} → {target_format}")

        # Check if we can handle this conversion
        if input_format in self.supported_input and target_format in self.supported_output:
            return self._convert_native(input_path, output_path, sample_rate, channels)

        # Try external tools
        tools = self.detect_external_tools()

        if tools.get('ffmpeg'):
            return self._convert_with_ffmpeg(input_path, output_path, sample_rate,
                                           channels, quality)
        elif tools.get('sox'):
            return self._convert_with_sox(input_path, output_path, sample_rate, channels)

        print(f"No converter available for {input_format} → {target_format}")
        return False

    def _convert_native(self, input_path: str, output_path: str,
                       sample_rate: Optional[int] = None,
                       channels: Optional[int] = None) -> bool:
        """Convert using native Python capabilities"""

        try:
            # Load audio
            samples, info = self.processor.load_wav(input_path)
            if not samples:
                return False

            target_rate = sample_rate or info['sample_rate']
            target_channels = channels or info['channels']

            # Resample if needed
            if target_rate != info['sample_rate']:
                samples = self.processor.resample(samples, info['sample_rate'], target_rate)

            # Convert channels if needed
            if target_channels != info['channels']:
                samples = self._convert_channels(samples, info['channels'], target_channels)

            # Save in target format
            output_format = Path(output_path).suffix.lower()

            if output_format == '.wav':
                return self.processor.save_wav(output_path, samples, target_rate, target_channels)
            elif output_format in ['.raw', '.pcm']:
                return self._save_raw(output_path, samples)

            return False

        except Exception as e:
            print(f"Native conversion error: {e}")
            return False

    def _convert_with_ffmpeg(self, input_path: str, output_path: str,
                           sample_rate: Optional[int], channels: Optional[int],
                           quality: str) -> bool:
        """Convert using FFmpeg"""

        try:
            cmd = ['ffmpeg', '-i', input_path, '-y']

            # Add quality settings
            output_format = Path(output_path).suffix.lower()

            if output_format == '.mp3':
                if quality == 'high':
                    cmd.extend(['-codec:a', 'libmp3lame', '-b:a', '320k'])
                elif quality == 'medium':
                    cmd.extend(['-codec:a', 'libmp3lame', '-b:a', '192k'])
                else:
                    cmd.extend(['-codec:a', 'libmp3lame', '-b:a', '128k'])

            elif output_format == '.flac':
                cmd.extend(['-codec:a', 'flac'])
                if quality == 'high':
                    cmd.extend(['-compression_level', '8'])

            elif output_format == '.ogg':
                if quality == 'high':
                    cmd.extend(['-codec:a', 'libvorbis', '-q:a', '8'])
                else:
                    cmd.extend(['-codec:a', 'libvorbis', '-q:a', '5'])

            # Add sample rate if specified
            if sample_rate:
                cmd.extend(['-ar', str(sample_rate)])

            # Add channel count if specified
            if channels:
                cmd.extend(['-ac', str(channels)])

            cmd.append(output_path)

            # Run conversion
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"FFmpeg conversion successful")
                return True
            else:
                print(f"FFmpeg error: {result.stderr}")
                return False

        except Exception as e:
            print(f"FFmpeg conversion error: {e}")
            return False

    def _convert_with_sox(self, input_path: str, output_path: str,
                         sample_rate: Optional[int], channels: Optional[int]) -> bool:
        """Convert using SoX"""

        try:
            cmd = ['sox', input_path]

            # Add sample rate if specified
            if sample_rate:
                cmd.extend(['-r', str(sample_rate)])

            # Add channel count if specified
            if channels:
                cmd.extend(['-c', str(channels)])

            cmd.append(output_path)

            # Run conversion
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"SoX conversion successful")
                return True
            else:
                print(f"SoX error: {result.stderr}")
                return False

        except Exception as e:
            print(f"SoX conversion error: {e}")
            return False

    def _convert_channels(self, samples: array.array, orig_channels: int,
                         target_channels: int) -> array.array:
        """Convert between mono and stereo"""
        if orig_channels == target_channels:
            return samples

        result = array.array('h')

        if orig_channels == 1 and target_channels == 2:
            # Mono to stereo: duplicate channel
            for s in samples:
                result.append(s)
                result.append(s)

        elif orig_channels == 2 and target_channels == 1:
            # Stereo to mono: average channels
            for i in range(0, len(samples) - 1, 2):
                mono = (samples[i] + samples[i + 1]) // 2
                result.append(mono)

        return result

    def _save_raw(self, output_path: str, samples: array.array) -> bool:
        """Save as raw PCM"""
        try:
            with open(output_path, 'wb') as f:
                f.write(samples.tobytes())
            return True
        except Exception as e:
            print(f"Error saving raw file: {e}")
            return False

    def batch_convert(self, input_dir: str, output_dir: str,
                     target_format: str, **kwargs) -> Dict[str, bool]:
        """Batch convert all files in directory"""

        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if not input_path.exists():
            print(f"Input directory not found: {input_dir}")
            return {}

        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)

        results = {}
        supported = self.get_supported_formats()['input']

        # Find audio files
        audio_files = []
        for ext in supported:
            audio_files.extend(input_path.glob(f"*{ext}"))

        print(f"Found {len(audio_files)} audio files")

        # Convert each file
        for input_file in audio_files:
            output_file = output_path / f"{input_file.stem}.{target_format.lstrip('.')}"

            print(f"Converting: {input_file.name}")
            success = self.convert_file(str(input_file), str(output_file),
                                      target_format, **kwargs)
            results[str(input_file)] = success

        return results

    def get_conversion_info(self, input_path: str, target_format: str) -> Dict:
        """Get information about potential conversion"""

        if not os.path.exists(input_path):
            return {'error': 'File not found'}

        try:
            # Get input file info
            info = self.processor._get_file_info(input_path)
            if not info:
                return {'error': 'Could not analyze input file'}

            input_size = os.path.getsize(input_path)
            input_format = Path(input_path).suffix.lower()

            # Estimate output size
            estimated_size = self._estimate_output_size(info, target_format)

            # Check if conversion is possible
            supported = self.get_supported_formats()
            can_convert = (input_format in supported['input'] and
                          target_format in supported['output'])

            tools = self.detect_external_tools()

            return {
                'input_format': input_format,
                'target_format': target_format,
                'input_size_mb': input_size / (1024 * 1024),
                'estimated_output_mb': estimated_size / (1024 * 1024),
                'duration_s': info['duration'],
                'sample_rate': info['sample_rate'],
                'channels': info['channels'],
                'can_convert': can_convert,
                'available_tools': tools,
                'requires_external_tool': target_format not in ['.wav', '.raw', '.pcm']
            }

        except Exception as e:
            return {'error': str(e)}

    def _estimate_output_size(self, info: Dict, target_format: str) -> int:
        """Estimate output file size"""

        duration = info['duration']
        sample_rate = info['sample_rate']
        channels = info['channels']

        if target_format == '.wav':
            # Uncompressed: duration * sample_rate * channels * 2 bytes + header
            return int(duration * sample_rate * channels * 2) + 1000

        elif target_format == '.flac':
            # FLAC typically achieves 50-60% compression
            uncompressed = duration * sample_rate * channels * 2
            return int(uncompressed * 0.55)

        elif target_format == '.mp3':
            # MP3 320kbps
            return int(duration * 320 * 1000 / 8)

        elif target_format == '.ogg':
            # OGG typically smaller than MP3
            return int(duration * 192 * 1000 / 8)

        else:
            # Default to WAV size
            return int(duration * sample_rate * channels * 2)


def demo():
    """Demo format conversion"""
    print("Format Converter Demo")
    print("-" * 40)

    converter = FormatConverter()

    # Check available tools
    print("1. Available conversion tools:")
    tools = converter.detect_external_tools()
    for tool, available in tools.items():
        status = "✓" if available else "✗"
        print(f"  {status} {tool}")

    # Show supported formats
    print("\n2. Supported formats:")
    formats = converter.get_supported_formats()
    print(f"  Input:  {', '.join(formats['input'])}")
    print(f"  Output: {', '.join(formats['output'])}")

    # Create test file
    from audio_recorder import SimpleRecorder
    import os

    recorder = SimpleRecorder()
    test_file = "format_test.wav"
    recorder.generate_test_tone(440, 2.0, test_file)

    if os.path.exists(test_file):
        # Test conversion info
        print(f"\n3. Conversion analysis:")
        info = converter.get_conversion_info(test_file, '.wav')
        if 'error' not in info:
            print(f"  Input: {info['input_format']} ({info['input_size_mb']:.1f}MB)")
            print(f"  Duration: {info['duration_s']:.1f}s")
            print(f"  Sample rate: {info['sample_rate']}Hz")
            print(f"  Can convert: {info['can_convert']}")

        # Test native conversion
        print(f"\n4. Native WAV conversion:")
        output_file = "converted_test.wav"
        success = converter.convert_file(test_file, output_file,
                                       sample_rate=22050, channels=1)

        if success and os.path.exists(output_file):
            original_size = os.path.getsize(test_file)
            converted_size = os.path.getsize(output_file)
            print(f"  ✓ Conversion successful")
            print(f"  Original: {original_size} bytes")
            print(f"  Converted: {converted_size} bytes")

            # Test raw format
            raw_file = "test.raw"
            converter.convert_file(output_file, raw_file, '.raw')
            if os.path.exists(raw_file):
                raw_size = os.path.getsize(raw_file)
                print(f"  Raw PCM: {raw_size} bytes")
                os.remove(raw_file)

            os.remove(output_file)
        else:
            print(f"  ✗ Conversion failed")

        # Cleanup
        os.remove(test_file)

    print("\nFormat conversion demo complete!")


if __name__ == '__main__':
    demo()