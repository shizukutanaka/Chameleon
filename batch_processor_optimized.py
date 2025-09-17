#!/usr/bin/env python3
"""
Optimized Batch Processor - Efficient multi-file processing
"""

import json
import logging
import multiprocessing
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import array
import wave

from audio_effects import AudioEffects
from audio_converter import AudioConverter

logger = logging.getLogger(__name__)

class OptimizedBatchProcessor:
    """Efficient batch processing with parallel execution"""

    def __init__(self, num_workers: Optional[int] = None):
        self.num_workers = num_workers or max(1, multiprocessing.cpu_count() - 1)
        self.effects = AudioEffects()
        self.converter = AudioConverter()
        self.results = []

    def process_file(self, task: Dict) -> Dict:
        """Process single file based on task parameters"""
        filepath = task['file']
        operation = task['operation']
        params = task.get('params', {})
        output_dir = task.get('output_dir', '')

        result = {'file': filepath, 'operation': operation}

        try:
            # Load audio
            with wave.open(filepath, 'rb') as wav:
                wav_params = wav.getparams()
                frames = wav.readframes(wav_params.nframes)
                samples = array.array('h', frames)

            # Apply operation
            processed = self._apply_operation(samples, operation, params)

            # Generate output path
            input_path = Path(filepath)
            if output_dir:
                output_path = Path(output_dir) / f"{input_path.stem}_{operation}{input_path.suffix}"
            else:
                output_path = input_path.parent / f"{input_path.stem}_{operation}{input_path.suffix}"

            # Save processed audio
            with wave.open(str(output_path), 'wb') as wav:
                wav.setnchannels(wav_params.nchannels)
                wav.setsampwidth(wav_params.sampwidth)
                wav.setframerate(wav_params.framerate)
                wav.writeframes(processed.tobytes())

            result['status'] = 'success'
            result['output'] = str(output_path)
            result['duration'] = wav_params.nframes / wav_params.framerate

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"Error processing {filepath}: {e}")

        return result

    def _apply_operation(self, samples: array.array, operation: str, params: Dict) -> array.array:
        """Apply specific operation to samples"""
        if operation == 'echo':
            return self.effects.echo(samples, **params)
        elif operation == 'chorus':
            return self.effects.chorus(samples, **params)
        elif operation == 'distortion':
            return self.effects.distortion(samples, **params)
        elif operation == 'lowpass':
            return self.effects.low_pass_filter(samples, **params)
        elif operation == 'highpass':
            return self.effects.high_pass_filter(samples, **params)
        elif operation == 'compressor':
            return self.effects.compressor(samples, **params)
        elif operation == 'tremolo':
            return self.effects.tremolo(samples, **params)
        elif operation == 'pitch':
            return self.effects.pitch_shift(samples, **params)
        elif operation == 'gate':
            return self.effects.noise_gate(samples, **params)
        elif operation == 'autogain':
            return self.effects.auto_gain(samples, **params)
        elif operation == 'resample':
            rate = params.get('target_rate', 44100)
            orig_rate = params.get('orig_rate', 44100)
            return self.converter.resample(samples, orig_rate, rate)
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def process_directory(self, input_dir: str, operation: str,
                         output_dir: Optional[str] = None,
                         params: Optional[Dict] = None) -> List[Dict]:
        """Process all WAV files in directory"""
        input_path = Path(input_dir)
        if not input_path.exists():
            raise FileNotFoundError(f"Directory not found: {input_dir}")

        # Create output directory if specified
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Prepare tasks
        tasks = []
        for wav_file in input_path.glob('*.wav'):
            task = {
                'file': str(wav_file),
                'operation': operation,
                'params': params or {},
                'output_dir': output_dir
            }
            tasks.append(task)

        # Process files
        if self.num_workers > 1 and len(tasks) > 1:
            # Parallel processing
            with multiprocessing.Pool(self.num_workers) as pool:
                self.results = pool.map(self.process_file, tasks)
        else:
            # Sequential processing
            self.results = [self.process_file(task) for task in tasks]

        return self.results

    def process_batch_config(self, config_file: str) -> List[Dict]:
        """Process batch from JSON configuration file"""
        with open(config_file, 'r') as f:
            config = json.load(f)

        tasks = config.get('tasks', [])
        self.results = []

        for task in tasks:
            if 'files' in task:
                # Multiple files with same operation
                for filepath in task['files']:
                    single_task = {
                        'file': filepath,
                        'operation': task['operation'],
                        'params': task.get('params', {}),
                        'output_dir': task.get('output_dir', '')
                    }
                    result = self.process_file(single_task)
                    self.results.append(result)
            elif 'directory' in task:
                # Process entire directory
                dir_results = self.process_directory(
                    task['directory'],
                    task['operation'],
                    task.get('output_dir'),
                    task.get('params', {})
                )
                self.results.extend(dir_results)

        return self.results

    def generate_report(self, output_file: str = 'batch_report.json'):
        """Generate processing report"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_files': len(self.results),
            'successful': sum(1 for r in self.results if r.get('status') == 'success'),
            'failed': sum(1 for r in self.results if r.get('status') == 'error'),
            'results': self.results
        }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        return report

    def create_chain_config(self, input_files: List[str],
                           operations: List[Dict],
                           output_dir: str = 'output') -> str:
        """Create configuration for chaining multiple operations"""
        config = {
            'description': 'Audio processing chain',
            'output_dir': output_dir,
            'tasks': []
        }

        for op_config in operations:
            task = {
                'files': input_files,
                'operation': op_config['operation'],
                'params': op_config.get('params', {}),
                'output_dir': output_dir
            }
            config['tasks'].append(task)

            # Update input files for next operation
            input_files = [
                str(Path(output_dir) / f"{Path(f).stem}_{op_config['operation']}{Path(f).suffix}")
                for f in input_files
            ]

        config_file = 'processing_chain.json'
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        return config_file


def main():
    """Command line interface for batch processing"""
    import argparse

    parser = argparse.ArgumentParser(description='Batch Audio Processor')
    parser.add_argument('command', choices=['process', 'config', 'chain'],
                       help='Processing command')
    parser.add_argument('input', help='Input directory or config file')
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('--operation', help='Operation to apply')
    parser.add_argument('--workers', type=int, help='Number of parallel workers')
    parser.add_argument('--params', help='Operation parameters (JSON string)')
    parser.add_argument('--report', default='batch_report.json',
                       help='Report output file')

    args = parser.parse_args()

    processor = OptimizedBatchProcessor(num_workers=args.workers)

    if args.command == 'process':
        # Process directory
        params = json.loads(args.params) if args.params else {}
        results = processor.process_directory(
            args.input,
            args.operation,
            args.output,
            params
        )

        # Generate report
        report = processor.generate_report(args.report)
        print(f"Processed {report['total_files']} files")
        print(f"Successful: {report['successful']}")
        print(f"Failed: {report['failed']}")
        print(f"Report saved: {args.report}")

    elif args.command == 'config':
        # Process from config file
        results = processor.process_batch_config(args.input)
        report = processor.generate_report(args.report)
        print(f"Batch processing completed: {len(results)} tasks")
        print(f"Report saved: {args.report}")

    elif args.command == 'chain':
        # Create processing chain
        print("Creating processing chain configuration...")
        # This would need additional implementation for full chain support
        pass

if __name__ == '__main__':
    main()