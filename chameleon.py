#!/usr/bin/env python3
"""
Chameleon Audio System - Unified Optimized Edition
High-performance audio processing with automatic optimization
"""

import array
import json
import logging
import math
import os
import sys
import time
import wave
import multiprocessing
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union
from functools import lru_cache
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

# Try to import numpy for optimized operations
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

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
    """High-performance audio processor with automatic optimization"""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.use_numpy = HAS_NUMPY
        self._cache = {}  # Cache for repeated operations
        self._error_count = 0
        self._last_error = None

    def _to_numpy(self, samples: Union[array.array, 'np.ndarray']) -> 'np.ndarray':
        """Convert to numpy array if available"""
        if not HAS_NUMPY:
            return samples
        if isinstance(samples, np.ndarray):
            return samples
        return np.frombuffer(samples, dtype=np.int16)

    def _from_numpy(self, data: Union[array.array, 'np.ndarray']) -> array.array:
        """Convert from numpy to array.array"""
        if not HAS_NUMPY or isinstance(data, array.array):
            return data
        return array.array('h', data.astype(np.int16))

    @lru_cache(maxsize=32)
    def _get_file_info(self, filepath: str) -> Optional[Dict]:
        """Get cached file information"""
        try:
            with wave.open(filepath, 'rb') as wav:
                params = wav.getparams()
                return {
                    'channels': params.nchannels,
                    'sample_rate': params.framerate,
                    'duration': params.nframes / params.framerate,
                    'nframes': params.nframes,
                    'sample_width': params.sampwidth
                }
        except Exception:
            return None

    def load_wav(self, filepath: str) -> Tuple[array.array, Dict]:
        """Load WAV file with caching and error recovery"""
        try:
            # Check cache first
            cache_key = f"load_{filepath}_{os.path.getmtime(filepath)}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            with wave.open(filepath, 'rb') as wav:
                params = wav.getparams()
                frames = wav.readframes(params.nframes)
                samples = array.array('h', frames)

                info = {
                    'channels': params.nchannels,
                    'sample_rate': params.framerate,
                    'duration': params.nframes / params.framerate,
                    'nframes': params.nframes,
                    'sample_width': params.sampwidth
                }

                # Cache if file is small enough
                if len(samples) < 10 * self.sample_rate:  # Cache files < 10 seconds
                    self._cache[cache_key] = (array.array('h', samples), info.copy())

                return samples, info

        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            self._error_count += 1
            self._last_error = str(e)

            # Try recovery with raw PCM
            try:
                with open(filepath, 'rb') as f:
                    data = f.read()
                    samples = array.array('h', data)
                    info = {'channels': 1, 'sample_rate': self.sample_rate,
                           'duration': len(samples) / self.sample_rate}
                    return samples, info
            except:
                return array.array('h'), {}

    def save_wav(self, filepath: str, samples: Union[array.array, 'np.ndarray'],
                 sample_rate: Optional[int] = None, channels: int = CHANNELS) -> bool:
        """Save samples to WAV file with automatic format conversion"""
        try:
            rate = sample_rate or self.sample_rate

            # Convert numpy array if needed
            if HAS_NUMPY and isinstance(samples, np.ndarray):
                samples = self._from_numpy(samples)

            with wave.open(filepath, 'wb') as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(SAMPLE_WIDTH)
                wav.setframerate(rate)
                wav.writeframes(samples.tobytes())
            return True

        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")
            self._error_count += 1
            self._last_error = str(e)

            # Try alternative save method
            try:
                # Save as raw PCM
                with open(filepath + '.raw', 'wb') as f:
                    f.write(samples.tobytes())
                logger.info(f"Saved as raw PCM: {filepath}.raw")
                return True
            except:
                return False

    def normalize(self, samples: Union[array.array, 'np.ndarray'],
                  target_peak: float = 0.95) -> Union[array.array, 'np.ndarray']:
        """Normalize audio with automatic optimization"""
        if not samples or len(samples) == 0:
            return samples

        # Use numpy if available for faster processing
        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            peak = np.abs(data).max()
            if peak == 0:
                return samples
            scale = (target_peak * MAX_INT16) / peak
            result = (data * scale).clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            # Pure Python fallback
            peak = max(abs(min(samples)), abs(max(samples)))
            if peak == 0:
                return samples
            scale = (target_peak * MAX_INT16) / peak
            return array.array('h', [int(max(min(s * scale, MAX_INT16), -MAX_INT16)) for s in samples])

    def amplify(self, samples: Union[array.array, 'np.ndarray'], gain_db: float) -> Union[array.array, 'np.ndarray']:
        """Apply gain with optimization"""
        gain_linear = 10 ** (gain_db / 20)

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            result = (data * gain_linear).clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            result = array.array('h')
            for s in samples:
                amplified = int(s * gain_linear)
                result.append(max(min(amplified, MAX_INT16), -MAX_INT16))
            return result

    def fade(self, samples: Union[array.array, 'np.ndarray'],
             fade_in_ms: int = 0, fade_out_ms: int = 0) -> Union[array.array, 'np.ndarray']:
        """Apply fade with optimization"""
        if not samples:
            return samples

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples).astype(np.float32)

            # Fade in
            if fade_in_ms > 0:
                fade_samples = int((fade_in_ms / 1000) * self.sample_rate)
                fade_samples = min(fade_samples, len(data))
                fade_curve = np.linspace(0, 1, fade_samples)
                data[:fade_samples] *= fade_curve

            # Fade out
            if fade_out_ms > 0:
                fade_samples = int((fade_out_ms / 1000) * self.sample_rate)
                fade_samples = min(fade_samples, len(data))
                fade_curve = np.linspace(1, 0, fade_samples)
                data[-fade_samples:] *= fade_curve

            result = data.clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
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

    def trim_silence(self, samples: Union[array.array, 'np.ndarray'],
                     threshold_db: float = -40) -> Union[array.array, 'np.ndarray']:
        """Remove silence with optimization"""
        if not samples:
            return samples

        threshold = MAX_INT16 * (10 ** (threshold_db / 20))

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            mask = np.abs(data) > threshold
            indices = np.where(mask)[0]
            if len(indices) == 0:
                return samples[:0]  # Return empty array of same type
            return data[indices[0]:indices[-1]+1]
        else:
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

            return samples[start:end]

    def reverse(self, samples: Union[array.array, 'np.ndarray']) -> Union[array.array, 'np.ndarray']:
        """Reverse audio"""
        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            return data[::-1]
        else:
            return array.array('h', reversed(samples))

    def change_speed(self, samples: Union[array.array, 'np.ndarray'],
                     speed_factor: float) -> Union[array.array, 'np.ndarray']:
        """Change playback speed with optimization"""
        if speed_factor == 1.0:
            return samples

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples)
            # Simple linear interpolation for speed change
            old_length = len(data)
            new_length = int(old_length / speed_factor)
            old_indices = np.arange(0, old_length)
            new_indices = np.linspace(0, old_length - 1, new_length)
            result = np.interp(new_indices, old_indices, data).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples, array.array) else result
        else:
            # Simple decimation/interpolation
            result = array.array('h')
            for i in range(int(len(samples) / speed_factor)):
                index = int(i * speed_factor)
                if index < len(samples):
                    result.append(samples[index])
            return result

    def mix(self, samples1: Union[array.array, 'np.ndarray'],
            samples2: Union[array.array, 'np.ndarray'],
            ratio: float = 0.5) -> Union[array.array, 'np.ndarray']:
        """Mix two audio signals with optimization"""
        if self.use_numpy and HAS_NUMPY:
            data1 = self._to_numpy(samples1)
            data2 = self._to_numpy(samples2)
            min_len = min(len(data1), len(data2))
            mixed = (data1[:min_len] * ratio + data2[:min_len] * (1 - ratio))
            result = mixed.clip(-MAX_INT16, MAX_INT16).astype(np.int16)
            return self._from_numpy(result) if isinstance(samples1, array.array) else result
        else:
            length = min(len(samples1), len(samples2))
            result = array.array('h')
            for i in range(length):
                mixed = int(samples1[i] * ratio + samples2[i] * (1 - ratio))
                result.append(max(min(mixed, MAX_INT16), -MAX_INT16))
            return result

    def get_statistics(self, samples: Union[array.array, 'np.ndarray']) -> Dict:
        """Get audio statistics with optimization"""
        if not samples or len(samples) == 0:
            return {'rms': 0, 'peak': 0, 'avg': 0, 'duration': 0}

        if self.use_numpy and HAS_NUMPY:
            data = self._to_numpy(samples).astype(np.float32)
            rms = np.sqrt(np.mean(data ** 2))
            peak = np.abs(data).max()
            avg = np.mean(np.abs(data))
        else:
            squared_sum = sum(s * s for s in samples)
            rms = math.sqrt(squared_sum / len(samples))
            peak = max(abs(min(samples)), abs(max(samples)))
            avg = sum(abs(s) for s in samples) / len(samples)

        return {
            'rms': float(rms),
            'peak': float(peak),
            'avg': float(avg),
            'duration': len(samples) / self.sample_rate,
            'samples': len(samples)
        }


class BatchProcessor:
    """Optimized batch processor with parallel execution"""

    def __init__(self, num_workers: Optional[int] = None):
        self.num_workers = num_workers or max(1, multiprocessing.cpu_count() - 1)
        self.processor = AudioProcessor()
        self.results = []
        self.errors = []

    def process_file(self, task: Dict) -> Dict:
        """Process single file with error recovery"""
        filepath = task['file']
        operation = task['operation']
        params = task.get('params', {})
        output_path = task.get('output_path')

        result = {
            'file': filepath,
            'operation': operation,
            'status': 'pending',
            'start_time': time.time()
        }

        try:
            # Load audio
            samples, info = self.processor.load_wav(filepath)
            if not samples:
                raise ValueError("Failed to load audio file")

            # Apply operation
            if operation == 'normalize':
                processed = self.processor.normalize(samples, params.get('peak', 0.95))
            elif operation == 'amplify':
                processed = self.processor.amplify(samples, params.get('gain', 0))
            elif operation == 'fade':
                processed = self.processor.fade(samples,
                                               params.get('fade_in', 0),
                                               params.get('fade_out', 0))
            elif operation == 'trim':
                processed = self.processor.trim_silence(samples, params.get('threshold', -40))
            elif operation == 'reverse':
                processed = self.processor.reverse(samples)
            elif operation == 'speed':
                processed = self.processor.change_speed(samples, params.get('factor', 1.0))
            elif operation == 'statistics':
                result['statistics'] = self.processor.get_statistics(samples)
                result['status'] = 'success'
                result['duration'] = time.time() - result['start_time']
                return result
            else:
                raise ValueError(f"Unknown operation: {operation}")

            # Save output
            if output_path:
                success = self.processor.save_wav(output_path, processed, info['sample_rate'])
                result['output'] = output_path
                result['status'] = 'success' if success else 'failed'
            else:
                result['status'] = 'success'

            result['duration'] = time.time() - result['start_time']

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['duration'] = time.time() - result['start_time']
            self.errors.append(result)
            logger.error(f"Error processing {filepath}: {e}")

        return result

    def process_directory(self, input_dir: str, output_dir: str = None,
                         operation: str = 'normalize', params: Dict = None,
                         pattern: str = '*.wav', parallel: bool = True) -> List[Dict]:
        """Process all files in directory with parallel execution"""
        input_path = Path(input_dir)
        if not input_path.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return []

        # Find all matching files
        files = list(input_path.glob(pattern))
        if not files:
            logger.warning(f"No files matching pattern {pattern} in {input_dir}")
            return []

        # Prepare output directory
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

        # Create tasks
        tasks = []
        for file_path in files:
            task = {
                'file': str(file_path),
                'operation': operation,
                'params': params or {}
            }

            if output_dir:
                output_file = output_path / f"{file_path.stem}_{operation}{file_path.suffix}"
                task['output_path'] = str(output_file)

            tasks.append(task)

        # Process files
        logger.info(f"Processing {len(tasks)} files with {self.num_workers} workers")

        if parallel and len(tasks) > 1:
            # Parallel processing
            with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
                results = list(executor.map(self.process_file, tasks))
        else:
            # Sequential processing
            results = [self.process_file(task) for task in tasks]

        # Summary
        successful = sum(1 for r in results if r['status'] == 'success')
        failed = sum(1 for r in results if r['status'] != 'success')

        logger.info(f"Batch processing complete: {successful} successful, {failed} failed")

        self.results = results
        return results

    def process_chain(self, filepath: str, operations: List[Dict],
                      output_path: str = None) -> Dict:
        """Apply chain of operations to single file"""
        result = {
            'file': filepath,
            'operations': operations,
            'status': 'pending',
            'start_time': time.time()
        }

        try:
            # Load audio
            samples, info = self.processor.load_wav(filepath)
            if not samples:
                raise ValueError("Failed to load audio file")

            # Apply each operation in sequence
            processed = samples
            for op in operations:
                operation = op['type']
                params = op.get('params', {})

                if operation == 'normalize':
                    processed = self.processor.normalize(processed, params.get('peak', 0.95))
                elif operation == 'amplify':
                    processed = self.processor.amplify(processed, params.get('gain', 0))
                elif operation == 'fade':
                    processed = self.processor.fade(processed,
                                                   params.get('fade_in', 0),
                                                   params.get('fade_out', 0))
                elif operation == 'trim':
                    processed = self.processor.trim_silence(processed, params.get('threshold', -40))
                elif operation == 'reverse':
                    processed = self.processor.reverse(processed)
                elif operation == 'speed':
                    processed = self.processor.change_speed(processed, params.get('factor', 1.0))

            # Save output
            if output_path:
                success = self.processor.save_wav(output_path, processed, info['sample_rate'])
                result['output'] = output_path
                result['status'] = 'success' if success else 'failed'
            else:
                result['status'] = 'success'

            result['duration'] = time.time() - result['start_time']

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['duration'] = time.time() - result['start_time']
            logger.error(f"Error in processing chain for {filepath}: {e}")

        return result

    def generate_report(self, output_file: str = None) -> Dict:
        """Generate processing report"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_files': len(self.results),
            'successful': sum(1 for r in self.results if r['status'] == 'success'),
            'failed': sum(1 for r in self.results if r['status'] != 'success'),
            'total_duration': sum(r.get('duration', 0) for r in self.results),
            'errors': self.errors,
            'details': self.results
        }

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {output_file}")

        return report


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(description='Chameleon Audio Processor')
    parser.add_argument('command', choices=['process', 'batch', 'info', 'chain'],
                       help='Command to execute')
    parser.add_argument('input', help='Input WAV file or directory')
    parser.add_argument('-o', '--output', help='Output file or directory')
    parser.add_argument('--operation', default='normalize',
                       choices=['normalize', 'amplify', 'fade', 'trim', 'reverse', 'speed', 'mix', 'statistics'],
                       help='Processing operation')
    parser.add_argument('--gain', type=float, default=0, help='Gain in dB (for amplify)')
    parser.add_argument('--fade-in', type=int, default=0, help='Fade in duration (ms)')
    parser.add_argument('--fade-out', type=int, default=0, help='Fade out duration (ms)')
    parser.add_argument('--threshold', type=float, default=-40, help='Silence threshold (dB)')
    parser.add_argument('--speed', type=float, default=1.0, help='Speed factor')
    parser.add_argument('--peak', type=float, default=0.95, help='Target peak for normalize')
    parser.add_argument('--pattern', default='*.wav', help='File pattern for batch processing')
    parser.add_argument('--parallel', action='store_true', help='Enable parallel processing')
    parser.add_argument('--workers', type=int, help='Number of parallel workers')
    parser.add_argument('--report', help='Generate report file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    processor = AudioProcessor()
    batch_processor = BatchProcessor(num_workers=args.workers)

    if args.command == 'process':
        # Single file processing
        samples, info = processor.load_wav(args.input)
        if not samples:
            logger.error(f"Failed to load {args.input}")
            sys.exit(1)

        # Apply operation
        if args.operation == 'normalize':
            result = processor.normalize(samples, args.peak)
        elif args.operation == 'amplify':
            result = processor.amplify(samples, args.gain)
        elif args.operation == 'fade':
            result = processor.fade(samples, args.fade_in, args.fade_out)
        elif args.operation == 'trim':
            result = processor.trim_silence(samples, args.threshold)
        elif args.operation == 'reverse':
            result = processor.reverse(samples)
        elif args.operation == 'speed':
            result = processor.change_speed(samples, args.speed)
        elif args.operation == 'statistics':
            stats = processor.get_statistics(samples)
            print(json.dumps(stats, indent=2))
            sys.exit(0)
        else:
            logger.error(f"Unknown operation: {args.operation}")
            sys.exit(1)

        # Save output
        if args.output:
            if processor.save_wav(args.output, result, info['sample_rate']):
                logger.info(f"Saved to {args.output}")
            else:
                logger.error(f"Failed to save {args.output}")
                sys.exit(1)

    elif args.command == 'batch':
        # Batch processing
        params = {
            'peak': args.peak,
            'gain': args.gain,
            'fade_in': args.fade_in,
            'fade_out': args.fade_out,
            'threshold': args.threshold,
            'factor': args.speed
        }

        results = batch_processor.process_directory(
            args.input,
            args.output,
            args.operation,
            params,
            args.pattern,
            args.parallel
        )

        if args.report:
            batch_processor.generate_report(args.report)

    elif args.command == 'info':
        # Display file information
        info = processor._get_file_info(args.input)
        if info:
            samples, _ = processor.load_wav(args.input)
            stats = processor.get_statistics(samples)
            info.update(stats)
            print(json.dumps(info, indent=2))
        else:
            logger.error(f"Failed to read {args.input}")
            sys.exit(1)

    elif args.command == 'chain':
        # Chain processing (read operations from JSON)
        if args.output and os.path.exists(args.output):
            with open(args.output, 'r') as f:
                operations = json.load(f)
            result = batch_processor.process_chain(args.input, operations)
            print(json.dumps(result, indent=2))
        else:
            logger.error("Chain command requires operations JSON file")
            sys.exit(1)

    # Display performance info if numpy is available
    if args.verbose:
        if HAS_NUMPY:
            logger.info("NumPy optimization: ENABLED")
        else:
            logger.info("NumPy optimization: DISABLED (install numpy for better performance)")

        if processor._error_count > 0:
            logger.warning(f"Total errors encountered: {processor._error_count}")
            if processor._last_error:
                logger.warning(f"Last error: {processor._last_error}")


if __name__ == '__main__':
    main()