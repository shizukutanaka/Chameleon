#!/usr/bin/env python3
"""
Chameleon Audio System - Unified Lightweight Edition
Practical audio processing without bloat
"""

import array
import json
import logging
import math
import os
import sys
import time
import wave
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

__version__ = "1.0.0"

# Setup logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Audio constants
SAMPLE_RATE = 44100
CHANNELS = 1
SAMPLE_WIDTH = 2
MAX_INT16 = 32767

class AudioProcessor:
    """Simple, efficient audio processor"""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate

    def load_wav(self, filepath: str) -> Tuple[array.array, Dict]:
        """Load WAV file"""
        try:
            with wave.open(filepath, 'rb') as wav:
                params = wav.getparams()
                frames = wav.readframes(params.nframes)
                samples = array.array('h', frames)

                info = {
                    'channels': params.nchannels,
                    'sample_rate': params.framerate,
                    'duration': params.nframes / params.framerate,
                    'samples': params.nframes
                }
                return samples, info
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return array.array('h'), {}

    def save_wav(self, filepath: str, samples: array.array,
                 sample_rate: int = None) -> bool:
        """Save samples to WAV file"""
        try:
            rate = sample_rate or self.sample_rate
            with wave.open(filepath, 'wb') as wav:
                wav.setnchannels(CHANNELS)
                wav.setsampwidth(SAMPLE_WIDTH)
                wav.setframerate(rate)
                wav.writeframes(samples.tobytes())
            return True
        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")
            return False

    def normalize(self, samples: array.array, target_peak: float = 0.95) -> array.array:
        """Normalize audio to target peak level"""
        if not samples:
            return samples

        peak = max(abs(min(samples)), abs(max(samples)))
        if peak == 0:
            return samples

        scale = (target_peak * MAX_INT16) / peak
        return array.array('h', [int(s * scale) for s in samples])

    def amplify(self, samples: array.array, gain_db: float) -> array.array:
        """Apply gain in dB"""
        gain_linear = 10 ** (gain_db / 20)
        result = array.array('h')

        for s in samples:
            amplified = int(s * gain_linear)
            # Clipping protection
            amplified = max(min(amplified, MAX_INT16), -MAX_INT16)
            result.append(amplified)

        return result

    def fade(self, samples: array.array, fade_in_ms: int = 0,
             fade_out_ms: int = 0) -> array.array:
        """Apply fade in/out"""
        if not samples:
            return samples

        result = array.array('h', samples)

        # Fade in
        if fade_in_ms > 0:
            fade_samples = int((fade_in_ms / 1000) * self.sample_rate)
            for i in range(min(fade_samples, len(result))):
                factor = i / fade_samples
                result[i] = int(result[i] * factor)

        # Fade out
        if fade_out_ms > 0:
            fade_samples = int((fade_out_ms / 1000) * self.sample_rate)
            start = len(result) - fade_samples
            for i in range(max(0, start), len(result)):
                factor = (len(result) - i) / fade_samples
                result[i] = int(result[i] * factor)

        return result

    def trim_silence(self, samples: array.array, threshold_db: float = -40) -> array.array:
        """Remove silence from start and end"""
        if not samples:
            return samples

        threshold = MAX_INT16 * (10 ** (threshold_db / 20))

        # Find start
        start = 0
        for i, s in enumerate(samples):
            if abs(s) > threshold:
                start = i
                break

        # Find end
        end = len(samples)
        for i in range(len(samples) - 1, -1, -1):
            if abs(samples[i]) > threshold:
                end = i + 1
                break

        return samples[start:end] if start < end else array.array('h')

    def reverse(self, samples: array.array) -> array.array:
        """Reverse audio"""
        result = array.array('h', samples)
        result.reverse()
        return result

    def speed_change(self, samples: array.array, factor: float) -> array.array:
        """Change playback speed (simple resampling)"""
        if factor <= 0 or factor == 1:
            return samples

        result = array.array('h')
        for i in range(int(len(samples) / factor)):
            idx = int(i * factor)
            if idx < len(samples):
                result.append(samples[idx])

        return result

    def mix(self, samples1: array.array, samples2: array.array,
            ratio: float = 0.5) -> array.array:
        """Mix two audio signals"""
        length = min(len(samples1), len(samples2))
        result = array.array('h')

        for i in range(length):
            mixed = int(samples1[i] * ratio + samples2[i] * (1 - ratio))
            mixed = max(min(mixed, MAX_INT16), -MAX_INT16)
            result.append(mixed)

        return result

    def get_statistics(self, samples: array.array) -> Dict:
        """Calculate audio statistics"""
        if not samples:
            return {'error': 'No samples'}

        return {
            'duration': len(samples) / self.sample_rate,
            'samples': len(samples),
            'peak': max(abs(min(samples)), abs(max(samples))),
            'rms': math.sqrt(sum(s*s for s in samples) / len(samples)),
            'dc_offset': sum(samples) / len(samples)
        }

class BatchProcessor:
    """Process multiple audio files"""

    def __init__(self, processor: AudioProcessor):
        self.processor = processor
        self.results = []

    def process_files(self, files: List[str], operation: str, **params) -> List[Dict]:
        """Process multiple files with same operation"""
        self.results = []

        for filepath in files:
            try:
                # Load
                samples, info = self.processor.load_wav(filepath)
                if not samples:
                    self.results.append({'file': filepath, 'error': 'Failed to load'})
                    continue

                # Process
                if operation == 'normalize':
                    processed = self.processor.normalize(samples, **params)
                elif operation == 'amplify':
                    processed = self.processor.amplify(samples, **params)
                elif operation == 'fade':
                    processed = self.processor.fade(samples, **params)
                elif operation == 'trim':
                    processed = self.processor.trim_silence(samples, **params)
                elif operation == 'reverse':
                    processed = self.processor.reverse(samples)
                elif operation == 'speed':
                    processed = self.processor.speed_change(samples, **params)
                elif operation == 'stats':
                    stats = self.processor.get_statistics(samples)
                    self.results.append({'file': filepath, 'stats': stats})
                    continue
                else:
                    self.results.append({'file': filepath, 'error': f'Unknown operation: {operation}'})
                    continue

                # Save
                output = filepath.replace('.wav', f'_{operation}.wav')
                if self.processor.save_wav(output, processed):
                    self.results.append({'file': filepath, 'output': output, 'success': True})
                else:
                    self.results.append({'file': filepath, 'error': 'Failed to save'})

            except Exception as e:
                self.results.append({'file': filepath, 'error': str(e)})

        return self.results

    def save_report(self, filepath: str = 'batch_report.json'):
        """Save processing report"""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.results, f, indent=2)
            return True
        except:
            return False

def main():
    """Command line interface"""
    import argparse

    parser = argparse.ArgumentParser(description='Chameleon Audio Processor')
    parser.add_argument('command', choices=['process', 'batch', 'info', 'convert'],
                       help='Command to execute')
    parser.add_argument('input', help='Input WAV file or directory')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('--operation', choices=['normalize', 'amplify', 'fade', 'trim',
                                                'reverse', 'speed', 'mix', 'stats'],
                       default='normalize', help='Processing operation')
    parser.add_argument('--gain', type=float, default=0, help='Gain in dB (for amplify)')
    parser.add_argument('--fade-in', type=int, default=0, help='Fade in duration (ms)')
    parser.add_argument('--fade-out', type=int, default=0, help='Fade out duration (ms)')
    parser.add_argument('--threshold', type=float, default=-40, help='Silence threshold (dB)')
    parser.add_argument('--speed', type=float, default=1.0, help='Speed factor')
    parser.add_argument('--peak', type=float, default=0.95, help='Target peak for normalize')
    parser.add_argument('--mix-with', help='Second file for mixing')
    parser.add_argument('--mix-ratio', type=float, default=0.5, help='Mix ratio (0-1)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Create processor
    processor = AudioProcessor()

    if args.command == 'info':
        # Show file info
        samples, info = processor.load_wav(args.input)
        if info:
            print(f"File: {args.input}")
            print(f"  Channels: {info['channels']}")
            print(f"  Sample Rate: {info['sample_rate']} Hz")
            print(f"  Duration: {info['duration']:.2f} seconds")
            print(f"  Samples: {info['samples']}")

            stats = processor.get_statistics(samples)
            print(f"  Peak: {stats['peak']}")
            print(f"  RMS: {stats['rms']:.2f}")
            print(f"  DC Offset: {stats['dc_offset']:.2f}")

    elif args.command == 'process':
        # Process single file
        samples, info = processor.load_wav(args.input)
        if not samples:
            print(f"Error: Failed to load {args.input}")
            return 1

        # Apply operation
        if args.operation == 'normalize':
            processed = processor.normalize(samples, args.peak)
        elif args.operation == 'amplify':
            processed = processor.amplify(samples, args.gain)
        elif args.operation == 'fade':
            processed = processor.fade(samples, args.fade_in, args.fade_out)
        elif args.operation == 'trim':
            processed = processor.trim_silence(samples, args.threshold)
        elif args.operation == 'reverse':
            processed = processor.reverse(samples)
        elif args.operation == 'speed':
            processed = processor.speed_change(samples, args.speed)
        elif args.operation == 'mix' and args.mix_with:
            samples2, _ = processor.load_wav(args.mix_with)
            if samples2:
                processed = processor.mix(samples, samples2, args.mix_ratio)
            else:
                print(f"Error: Failed to load mix file {args.mix_with}")
                return 1
        elif args.operation == 'stats':
            stats = processor.get_statistics(samples)
            print(json.dumps(stats, indent=2))
            return 0
        else:
            print(f"Error: Invalid operation {args.operation}")
            return 1

        # Save output
        output = args.output or args.input.replace('.wav', f'_{args.operation}.wav')
        if processor.save_wav(output, processed):
            print(f"Saved: {output}")
        else:
            print(f"Error: Failed to save {output}")
            return 1

    elif args.command == 'batch':
        # Batch processing
        batch = BatchProcessor(processor)

        # Get files
        if os.path.isdir(args.input):
            files = list(Path(args.input).glob('*.wav'))
        else:
            files = [args.input]

        # Process
        params = {}
        if args.operation == 'amplify':
            params['gain_db'] = args.gain
        elif args.operation == 'fade':
            params['fade_in_ms'] = args.fade_in
            params['fade_out_ms'] = args.fade_out
        elif args.operation == 'trim':
            params['threshold_db'] = args.threshold
        elif args.operation == 'speed':
            params['factor'] = args.speed
        elif args.operation == 'normalize':
            params['target_peak'] = args.peak

        results = batch.process_files([str(f) for f in files], args.operation, **params)

        # Show results
        for r in results:
            if 'error' in r:
                print(f"Error: {r['file']} - {r['error']}")
            elif 'stats' in r:
                print(f"Stats: {r['file']}")
                print(json.dumps(r['stats'], indent=2))
            else:
                print(f"Success: {r['file']} -> {r.get('output', 'processed')}")

        # Save report
        report_file = args.output or 'batch_report.json'
        if batch.save_report(report_file):
            print(f"Report saved: {report_file}")

    elif args.command == 'convert':
        # Simple format conversion (WAV to WAV with different params)
        samples, info = processor.load_wav(args.input)
        if not samples:
            print(f"Error: Failed to load {args.input}")
            return 1

        output = args.output or args.input.replace('.wav', '_converted.wav')
        if processor.save_wav(output, samples):
            print(f"Converted: {output}")
        else:
            print(f"Error: Failed to save {output}")
            return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())