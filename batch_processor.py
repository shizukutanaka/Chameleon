#!/usr/bin/env python3
"""
Batch Audio Processor - Process multiple files with smart detection
"""

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from chameleon import AudioProcessor
from audio_converter import AudioConverter
from audio_visualizer import AudioReport


class SmartBatchProcessor:
    """Intelligent batch processing with format detection"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.processor = AudioProcessor()
        self.converter = AudioConverter()
        self.stats = {
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'total_time': 0
        }

    def find_audio_files(self, directory: str, recursive: bool = True) -> List[Dict]:
        """Find and analyze audio files in directory"""

        audio_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.aiff', '.au', '.raw'}
        found_files = []

        search_path = Path(directory)
        if not search_path.exists():
            print(f"Directory not found: {directory}")
            return []

        # Find files
        pattern = "**/*" if recursive else "*"
        for file_path in search_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                # Basic file info
                file_info = {
                    'path': str(file_path),
                    'name': file_path.name,
                    'size': file_path.stat().st_size,
                    'extension': file_path.suffix.lower(),
                    'detected_format': None,
                    'valid': False
                }

                # Try format detection
                detected = self.processor.detect_format(str(file_path))
                if detected:
                    file_info['detected_format'] = detected
                    file_info['valid'] = True

                found_files.append(file_info)

        print(f"Found {len(found_files)} audio files in {directory}")
        return found_files

    def process_file(self, file_info: Dict, operation: str, **kwargs) -> Dict:
        """Process a single file with the specified operation"""

        result = {
            'file': file_info['path'],
            'operation': operation,
            'success': False,
            'output_file': None,
            'error': None,
            'processing_time': 0
        }

        start_time = time.time()

        try:
            input_path = file_info['path']

            if operation == 'convert':
                result.update(self._convert_file(input_path, **kwargs))

            elif operation == 'normalize':
                result.update(self._normalize_file(input_path, **kwargs))

            elif operation == 'analyze':
                result.update(self._analyze_file(input_path, **kwargs))

            elif operation == 'denoise':
                result.update(self._denoise_file(input_path, **kwargs))

            elif operation == 'compress':
                result.update(self._compress_file(input_path, **kwargs))

            else:
                result['error'] = f"Unknown operation: {operation}"

        except Exception as e:
            result['error'] = str(e)

        result['processing_time'] = time.time() - start_time
        return result

    def _convert_file(self, input_path: str, output_format: str = 'wav',
                     output_dir: str = None, **kwargs) -> Dict:
        """Convert file to different format"""

        if output_dir is None:
            output_dir = os.path.dirname(input_path)

        input_name = Path(input_path).stem
        output_path = os.path.join(output_dir, f"{input_name}.{output_format}")

        # For now, only support WAV output (can be extended)
        if output_format.lower() != 'wav':
            return {'error': f"Format {output_format} not supported yet"}

        # Load and resave
        samples, info = self.processor.load_wav(input_path)
        if not samples:
            return {'error': 'Could not load audio'}

        success = self.processor.save_wav(output_path, samples, info['sample_rate'])

        return {
            'success': success,
            'output_file': output_path if success else None
        }

    def _normalize_file(self, input_path: str, output_dir: str = None,
                       target_peak: float = 0.95, **kwargs) -> Dict:
        """Normalize audio file"""

        if output_dir is None:
            output_dir = os.path.dirname(input_path)

        input_name = Path(input_path).stem
        output_path = os.path.join(output_dir, f"{input_name}_normalized.wav")

        samples, info = self.processor.load_wav(input_path)
        if not samples:
            return {'error': 'Could not load audio'}

        # Normalize
        normalized = self.processor.normalize(samples, target_peak)

        success = self.processor.save_wav(output_path, normalized, info['sample_rate'])

        return {
            'success': success,
            'output_file': output_path if success else None
        }

    def _analyze_file(self, input_path: str, output_dir: str = None,
                     **kwargs) -> Dict:
        """Generate analysis report"""

        if output_dir is None:
            output_dir = os.path.dirname(input_path)

        input_name = Path(input_path).stem
        report_path = os.path.join(output_dir, f"{input_name}_analysis.txt")

        reporter = AudioReport()
        success = reporter.save_report(input_path, report_path)

        return {
            'success': success,
            'output_file': report_path if success else None
        }

    def _denoise_file(self, input_path: str, output_dir: str = None,
                     noise_floor_db: float = -40, **kwargs) -> Dict:
        """Apply noise reduction"""

        if output_dir is None:
            output_dir = os.path.dirname(input_path)

        input_name = Path(input_path).stem
        output_path = os.path.join(output_dir, f"{input_name}_denoised.wav")

        samples, info = self.processor.load_wav(input_path)
        if not samples:
            return {'error': 'Could not load audio'}

        # Apply noise reduction
        denoised = self.processor.reduce_noise(samples, noise_floor_db)

        success = self.processor.save_wav(output_path, denoised, info['sample_rate'])

        return {
            'success': success,
            'output_file': output_path if success else None
        }

    def _compress_file(self, input_path: str, output_dir: str = None,
                      threshold_db: float = -20, ratio: float = 0.3, **kwargs) -> Dict:
        """Apply compression"""

        if output_dir is None:
            output_dir = os.path.dirname(input_path)

        input_name = Path(input_path).stem
        output_path = os.path.join(output_dir, f"{input_name}_compressed.wav")

        samples, info = self.processor.load_wav(input_path)
        if not samples:
            return {'error': 'Could not load audio'}

        # Apply compression
        compressed = self.processor.apply_compressor(samples, threshold_db, ratio)

        success = self.processor.save_wav(output_path, compressed, info['sample_rate'])

        return {
            'success': success,
            'output_file': output_path if success else None
        }

    def process_batch(self, files: List[Dict], operation: str,
                     progress_callback: Optional[Callable] = None,
                     **kwargs) -> List[Dict]:
        """Process multiple files in parallel"""

        if not files:
            return []

        print(f"Processing {len(files)} files with operation: {operation}")
        print(f"Using {self.max_workers} workers")

        results = []
        self.stats = {'processed': 0, 'failed': 0, 'skipped': 0, 'total_time': 0}

        start_time = time.time()

        # Process files
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for file_info in files:
                # Skip invalid files
                if not file_info.get('valid', False):
                    self.stats['skipped'] += 1
                    if progress_callback:
                        progress_callback(len(results), len(files), f"Skipped: {file_info['name']}")
                    continue

                future = executor.submit(self.process_file, file_info, operation, **kwargs)
                futures.append((future, file_info))

            # Collect results
            for future, file_info in futures:
                result = future.result()
                results.append(result)

                if result['success']:
                    self.stats['processed'] += 1
                    status = f"✓ {Path(file_info['path']).name}"
                else:
                    self.stats['failed'] += 1
                    status = f"✗ {Path(file_info['path']).name}: {result.get('error', 'Unknown error')}"

                if progress_callback:
                    progress_callback(len(results), len(files), status)

        self.stats['total_time'] = time.time() - start_time

        return results

    def print_summary(self, results: List[Dict]):
        """Print processing summary"""
        print("\n" + "=" * 60)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 60)
        print(f"Total files: {len(results) + self.stats['skipped']}")
        print(f"Processed: {self.stats['processed']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Skipped: {self.stats['skipped']}")
        print(f"Total time: {self.stats['total_time']:.2f}s")

        if self.stats['processed'] > 0:
            avg_time = self.stats['total_time'] / self.stats['processed']
            print(f"Average time per file: {avg_time:.2f}s")

        # Show failed files
        failed_files = [r for r in results if not r['success']]
        if failed_files:
            print(f"\nFailed files ({len(failed_files)}):")
            for result in failed_files[:5]:  # Show first 5
                print(f"  - {Path(result['file']).name}: {result.get('error', 'Unknown error')}")


class BatchOperations:
    """Pre-configured batch operations"""

    @staticmethod
    def normalize_directory(directory: str, output_dir: str = None,
                          recursive: bool = True) -> bool:
        """Normalize all audio files in directory"""

        processor = SmartBatchProcessor()
        files = processor.find_audio_files(directory, recursive)

        if not files:
            print("No audio files found")
            return False

        def progress(completed, total, status):
            percent = (completed / total) * 100
            print(f"[{percent:5.1f}%] {status}")

        results = processor.process_batch(
            files, 'normalize',
            output_dir=output_dir,
            progress_callback=progress
        )

        processor.print_summary(results)
        return processor.stats['processed'] > 0

    @staticmethod
    def denoise_directory(directory: str, output_dir: str = None,
                         noise_floor_db: float = -40) -> bool:
        """Apply noise reduction to all files"""

        processor = SmartBatchProcessor()
        files = processor.find_audio_files(directory)

        if not files:
            return False

        results = processor.process_batch(
            files, 'denoise',
            output_dir=output_dir,
            noise_floor_db=noise_floor_db
        )

        processor.print_summary(results)
        return processor.stats['processed'] > 0

    @staticmethod
    def analyze_directory(directory: str, output_dir: str = None) -> bool:
        """Generate analysis reports for all files"""

        processor = SmartBatchProcessor()
        files = processor.find_audio_files(directory)

        if not files:
            return False

        results = processor.process_batch(
            files, 'analyze',
            output_dir=output_dir
        )

        processor.print_summary(results)
        return processor.stats['processed'] > 0


def demo():
    """Demo batch processing"""
    print("Batch Processor Demo")
    print("-" * 40)

    # Create test directory with multiple files
    test_dir = tempfile.mkdtemp(prefix="batch_test_")
    print(f"Created test directory: {test_dir}")

    try:
        # Generate test files
        from audio_recorder import SimpleRecorder

        recorder = SimpleRecorder()
        test_files = []

        frequencies = [220, 440, 880, 1760]  # Different notes
        for i, freq in enumerate(frequencies):
            filename = os.path.join(test_dir, f"test_tone_{freq}hz.wav")
            recorder.generate_test_tone(freq, 1.0, filename)
            test_files.append(filename)
            print(f"Generated: {Path(filename).name}")

        # Test batch processing
        print(f"\n1. Testing file discovery:")
        processor = SmartBatchProcessor(max_workers=2)
        files = processor.find_audio_files(test_dir)

        for file_info in files:
            print(f"  {file_info['name']}: {file_info['detected_format']} "
                  f"({file_info['size']} bytes)")

        # Test batch normalization
        print(f"\n2. Testing batch normalization:")
        results = processor.process_batch(files, 'normalize')

        # Show results
        for result in results:
            status = "✓" if result['success'] else "✗"
            filename = Path(result['file']).name
            print(f"  {status} {filename} ({result['processing_time']:.2f}s)")

        processor.print_summary(results)

        # Test high-level operations
        print(f"\n3. Testing high-level batch operations:")
        output_dir = os.path.join(test_dir, "processed")
        os.makedirs(output_dir, exist_ok=True)

        BatchOperations.denoise_directory(test_dir, output_dir)

    finally:
        # Cleanup
        shutil.rmtree(test_dir)
        print(f"\nCleaned up test directory: {test_dir}")

    print("\nBatch processing demo complete!")


if __name__ == '__main__':
    demo()