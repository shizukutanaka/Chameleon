#!/usr/bin/env python3
"""
Advanced batch processing with progress indicators for Chameleon.
Provides parallel processing, progress tracking, and robust error handling.
"""

import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from pathlib import Path

# Import core modules
try:
    from .types import AudioData, get_fallback_logger
    from .core import generate_sine_wave, write_wav_file, read_wav_file
    from .audio_formats import AudioConverter, get_audio_info
    from .logger import get_logger, get_performance_logger
    logger = get_logger()
    perf_logger = get_performance_logger()
except ImportError:
    try:
        from types import AudioData, get_fallback_logger
        logger = get_fallback_logger(__name__)
        perf_logger = None
    except ImportError:
        # Complete fallback
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        perf_logger = None
        AudioData = Tuple[bytes, int, int, int]

class ProgressIndicator:
    """Lightweight progress indicator with multiple display modes"""
    
    def __init__(self, total: int, description: str = "Processing", 
                 show_rate: bool = True, show_eta: bool = True,
                 width: int = 40):
        self.total = total
        self.description = description
        self.show_rate = show_rate
        self.show_eta = show_eta
        self.width = width
        
        self.current = 0
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 0.1  # Update every 100ms max
        self.lock = threading.Lock()
        
        # Try to use tqdm if available, otherwise use simple progress
        self.use_tqdm = self._check_tqdm()
        
        if self.use_tqdm:
            import tqdm
            self.progress_bar = tqdm.tqdm(
                total=total,
                desc=description,
                unit="items",
                disable=not sys.stdout.isatty()
            )
        else:
            self.progress_bar = None
            self._print_initial()
    
    def _check_tqdm(self) -> bool:
        """Check if tqdm is available"""
        try:
            import tqdm
            return True
        except ImportError:
            return False
    
    def _print_initial(self):
        """Print initial progress line"""
        if sys.stdout.isatty():
            print(f"{self.description}: 0/{self.total} (0.0%)")
    
    def update(self, increment: int = 1):
        """Update progress by increment"""
        with self.lock:
            self.current += increment
            current_time = time.time()
            
            # Rate limiting for console updates
            if current_time - self.last_update < self.update_interval and self.current < self.total:
                if self.use_tqdm and self.progress_bar:
                    self.progress_bar.update(increment)
                return
            
            self.last_update = current_time
            
            if self.use_tqdm and self.progress_bar:
                self.progress_bar.update(increment)
            else:
                self._update_simple_progress()
    
    def _update_simple_progress(self):
        """Update simple text-based progress"""
        if not sys.stdout.isatty():
            return
        
        percent = (self.current / self.total) * 100
        elapsed = time.time() - self.start_time
        
        # Create progress bar
        filled = int((self.current / self.total) * self.width)
        bar = "█" * filled + "░" * (self.width - filled)
        
        status_parts = [f"{self.current}/{self.total} ({percent:.1f}%)"]
        
        if self.show_rate and elapsed > 0:
            rate = self.current / elapsed
            status_parts.append(f"{rate:.1f}/s")
        
        if self.show_eta and self.current > 0 and elapsed > 0:
            rate = self.current / elapsed
            remaining = (self.total - self.current) / rate
            eta_mins = int(remaining // 60)
            eta_secs = int(remaining % 60)
            status_parts.append(f"ETA {eta_mins:02d}:{eta_secs:02d}")
        
        status = " | ".join(status_parts)
        
        # Print with carriage return to overwrite
        print(f"\r{self.description}: [{bar}] {status}", end="", flush=True)
    
    def close(self):
        """Close progress indicator"""
        with self.lock:
            if self.use_tqdm and self.progress_bar:
                self.progress_bar.close()
            else:
                if sys.stdout.isatty():
                    print()  # New line after progress
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class BatchProcessor:
    """Advanced batch processor with parallel execution and progress tracking"""
    
    def __init__(self, max_workers: int = None, show_progress: bool = True):
        self.max_workers = max_workers or min(8, (os.cpu_count() or 1) + 2)
        self.show_progress = show_progress
        self.converter = AudioConverter()
        
        logger.info(f"Batch processor initialized with {self.max_workers} workers")
    
    def batch_generate_tones(self, frequencies: List[float], duration: float = 1.0,
                           sample_rate: int = 44100, output_dir: str = "./batch_output") -> Dict[str, Any]:
        """Generate multiple audio tones with progress tracking"""
        if not frequencies:
            logger.error("No frequencies provided for batch generation")
            return {"error": "No frequencies provided"}
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        def generate_single_tone(freq_info: Tuple[int, float]) -> Tuple[int, float, bool, str]:
            """Generate a single tone (worker function)"""
            index, frequency = freq_info
            try:
                # Generate audio
                audio_data = generate_sine_wave(frequency, duration, sample_rate)
                
                # Create output filename
                filename = f"tone_{frequency:.1f}Hz.wav"
                output_path = os.path.join(output_dir, filename)
                
                # Write file
                success = write_wav_file(output_path, audio_data)
                
                return index, frequency, success, output_path if success else ""
                
            except Exception as e:
                logger.error(f"Failed to generate tone for {frequency}Hz: {e}")
                return index, frequency, False, ""
        
        # Prepare work items
        work_items = list(enumerate(frequencies))
        results = {}
        
        start_time = time.time()
        if perf_logger:
            perf_logger.start_timing("batch_tone_generation")
        
        # Execute with progress tracking
        with ProgressIndicator(len(frequencies), "Generating tones") as progress:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_freq = {executor.submit(generate_single_tone, item): item for item in work_items}
                
                # Collect results as they complete
                for future in as_completed(future_to_freq):
                    index, frequency, success, output_path = future.result()
                    results[f"{frequency}Hz"] = {
                        'success': success,
                        'output_path': output_path,
                        'frequency': frequency
                    }
                    
                    if self.show_progress:
                        progress.update(1)
        
        elapsed_time = time.time() - start_time
        if perf_logger:
            perf_logger.end_timing("batch_tone_generation")
        
        # Compile summary
        successful = sum(1 for r in results.values() if r['success'])
        failed = len(results) - successful
        
        summary = {
            'total_files': len(frequencies),
            'successful': successful,
            'failed': failed,
            'success_rate': successful / len(frequencies) if frequencies else 0,
            'processing_time_seconds': elapsed_time,
            'output_directory': output_dir,
            'results': results
        }
        
        logger.info(f"Batch tone generation completed: {successful}/{len(frequencies)} successful in {elapsed_time:.2f}s")
        
        return summary
    
    def batch_convert_files(self, input_files: List[str], output_dir: str,
                          target_format: str, quality: str = 'high') -> Dict[str, Any]:
        """Convert multiple audio files with progress tracking"""
        if not input_files:
            logger.error("No input files provided for batch conversion")
            return {"error": "No input files provided"}
        
        # Filter existing files
        valid_files = [f for f in input_files if os.path.exists(f)]
        if not valid_files:
            logger.error("No valid input files found")
            return {"error": "No valid input files found"}
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        def convert_single_file(file_info: Tuple[int, str]) -> Tuple[int, str, bool, str, Dict[str, Any]]:
            """Convert a single file (worker function)"""
            index, input_file = file_info
            try:
                # Generate output filename
                input_name = Path(input_file).stem
                output_file = os.path.join(output_dir, f"{input_name}.{target_format}")
                
                # Get input file info
                file_info = get_audio_info(input_file) or {}
                
                # Convert file
                success = self.converter.convert_file(input_file, output_file, target_format, quality)
                
                return index, input_file, success, output_file if success else "", file_info
                
            except Exception as e:
                logger.error(f"Failed to convert {input_file}: {e}")
                return index, input_file, False, "", {}
        
        # Prepare work items
        work_items = list(enumerate(valid_files))
        results = {}
        
        start_time = time.time()
        if perf_logger:
            perf_logger.start_timing("batch_file_conversion")
        
        # Execute with progress tracking
        with ProgressIndicator(len(valid_files), f"Converting to {target_format.upper()}") as progress:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_file = {executor.submit(convert_single_file, item): item for item in work_items}
                
                # Collect results as they complete
                for future in as_completed(future_to_file):
                    index, input_file, success, output_file, file_info = future.result()
                    results[input_file] = {
                        'success': success,
                        'output_file': output_file,
                        'input_info': file_info
                    }
                    
                    if self.show_progress:
                        progress.update(1)
        
        elapsed_time = time.time() - start_time
        if perf_logger:
            perf_logger.end_timing("batch_file_conversion")
        
        # Compile summary
        successful = sum(1 for r in results.values() if r['success'])
        failed = len(results) - successful
        
        summary = {
            'total_files': len(valid_files),
            'successful': successful,
            'failed': failed,
            'success_rate': successful / len(valid_files) if valid_files else 0,
            'processing_time_seconds': elapsed_time,
            'target_format': target_format,
            'quality': quality,
            'output_directory': output_dir,
            'results': results
        }
        
        logger.info(f"Batch conversion completed: {successful}/{len(valid_files)} successful in {elapsed_time:.2f}s")
        
        return summary
    
    def batch_analyze_files(self, input_files: List[str]) -> Dict[str, Any]:
        """Analyze multiple audio files with progress tracking"""
        if not input_files:
            logger.error("No input files provided for batch analysis")
            return {"error": "No input files provided"}
        
        # Filter existing files
        valid_files = [f for f in input_files if os.path.exists(f)]
        if not valid_files:
            logger.error("No valid input files found")
            return {"error": "No valid input files found"}
        
        def analyze_single_file(file_info: Tuple[int, str]) -> Tuple[int, str, bool, Dict[str, Any]]:
            """Analyze a single file (worker function)"""
            index, input_file = file_info
            try:
                # Get file information
                file_info = get_audio_info(input_file)
                
                if file_info:
                    # Add file path info
                    file_info['file_path'] = input_file
                    file_info['file_name'] = os.path.basename(input_file)
                    return index, input_file, True, file_info
                else:
                    return index, input_file, False, {}
                    
            except Exception as e:
                logger.error(f"Failed to analyze {input_file}: {e}")
                return index, input_file, False, {}
        
        # Prepare work items
        work_items = list(enumerate(valid_files))
        results = {}
        
        start_time = time.time()
        if perf_logger:
            perf_logger.start_timing("batch_file_analysis")
        
        # Execute with progress tracking
        with ProgressIndicator(len(valid_files), "Analyzing files") as progress:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_file = {executor.submit(analyze_single_file, item): item for item in work_items}
                
                # Collect results as they complete
                for future in as_completed(future_to_file):
                    index, input_file, success, analysis = future.result()
                    if success:
                        results[input_file] = analysis
                    
                    if self.show_progress:
                        progress.update(1)
        
        elapsed_time = time.time() - start_time
        if perf_logger:
            perf_logger.end_timing("batch_file_analysis")
        
        # Compile summary statistics
        total_duration = sum(info.get('duration', 0) for info in results.values())
        total_size = sum(info.get('file_size', 0) for info in results.values())
        
        summary = {
            'total_files': len(valid_files),
            'analyzed': len(results),
            'failed': len(valid_files) - len(results),
            'processing_time_seconds': elapsed_time,
            'total_duration_seconds': total_duration,
            'total_size_bytes': total_size,
            'results': results
        }
        
        logger.info(f"Batch analysis completed: {len(results)}/{len(valid_files)} files analyzed in {elapsed_time:.2f}s")
        
        return summary

def batch_generate_tones(frequencies: List[float], duration: float = 1.0,
                        sample_rate: int = 44100, output_dir: str = "./batch_output",
                        max_workers: int = None, show_progress: bool = True) -> Dict[str, Any]:
    """Convenience function for batch tone generation"""
    processor = BatchProcessor(max_workers, show_progress)
    return processor.batch_generate_tones(frequencies, duration, sample_rate, output_dir)

def batch_convert_files(input_files: List[str], output_dir: str, target_format: str,
                       quality: str = 'high', max_workers: int = None,
                       show_progress: bool = True) -> Dict[str, Any]:
    """Convenience function for batch file conversion"""
    processor = BatchProcessor(max_workers, show_progress)
    return processor.batch_convert_files(input_files, output_dir, target_format, quality)

def batch_analyze_files(input_files: List[str], max_workers: int = None,
                       show_progress: bool = True) -> Dict[str, Any]:
    """Convenience function for batch file analysis"""
    processor = BatchProcessor(max_workers, show_progress)
    return processor.batch_analyze_files(input_files)

if __name__ == '__main__':
    # Test batch processing functionality
    print("Batch Processor Test")
    print("=" * 40)
    
    # Test tone generation
    test_frequencies = [220.0, 440.0, 880.0, 1320.0]
    result = batch_generate_tones(test_frequencies, duration=0.5, output_dir="./test_output")
    
    print(f"\nBatch tone generation results:")
    print(f"Total: {result['total_files']}")
    print(f"Successful: {result['successful']}")
    print(f"Failed: {result['failed']}")
    print(f"Success rate: {result['success_rate']:.1%}")
    print(f"Processing time: {result['processing_time_seconds']:.2f}s")
    
    # Test file analysis if test files exist
    test_files = []
    for ext in ['wav', 'mp3', 'flac']:
        test_file = f"test.{ext}"
        if os.path.exists(test_file):
            test_files.append(test_file)
    
    if test_files:
        print(f"\nTesting file analysis with {len(test_files)} files...")
        analysis_result = batch_analyze_files(test_files)
        print(f"Analysis completed: {analysis_result['analyzed']} files")