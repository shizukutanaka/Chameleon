#!/usr/bin/env python3
"""
Memory Optimizer - Efficient processing for large audio files
"""

import array
import os
import tempfile
import wave
import gc
from typing import Callable, Optional, Tuple, Iterator, Dict, Any
from pathlib import Path

from chameleon import AudioProcessor


class ChunkedProcessor:
    """Process large audio files in memory-efficient chunks"""

    def __init__(self, chunk_size: int = 44100 * 10):  # 10 seconds default
        self.chunk_size = chunk_size
        self.processor = AudioProcessor()
        self.overlap_size = 1024  # Overlap for smooth transitions

    def process_file_chunked(self, input_path: str, output_path: str,
                           processor_func: Callable,
                           progress_callback: Optional[Callable] = None,
                           **kwargs) -> bool:
        """Process large file in chunks with overlap handling"""

        try:
            # Get file info first
            info = self.processor._get_file_info(input_path)
            if not info:
                return False

            total_frames = info['nframes']
            sample_rate = info['sample_rate']

            # Adjust chunk size based on file size
            file_size = os.path.getsize(input_path)
            optimal_chunk = self._calculate_optimal_chunk_size(file_size)
            working_chunk_size = min(self.chunk_size, optimal_chunk)

            print(f"Processing {total_frames:,} frames in chunks of {working_chunk_size:,}")

            # Open input and output files
            with wave.open(input_path, 'rb') as wav_in:
                with wave.open(output_path, 'wb') as wav_out:
                    # Set output parameters
                    wav_out.setparams(wav_in.getparams())

                    frames_processed = 0
                    overlap_buffer = array.array('h')

                    while frames_processed < total_frames:
                        # Calculate chunk size for this iteration
                        remaining_frames = total_frames - frames_processed
                        current_chunk_size = min(working_chunk_size, remaining_frames)

                        # Read chunk with overlap
                        if overlap_buffer:
                            # Start with overlap from previous chunk
                            chunk_data = overlap_buffer
                            frames_to_read = current_chunk_size - len(overlap_buffer)
                        else:
                            chunk_data = array.array('h')
                            frames_to_read = current_chunk_size

                        # Read new data
                        if frames_to_read > 0:
                            raw_data = wav_in.readframes(frames_to_read)
                            new_samples = array.array('h', raw_data)
                            chunk_data.extend(new_samples)

                        # Process chunk
                        if chunk_data:
                            processed_chunk = processor_func(chunk_data, **kwargs)

                            # Handle overlap for next chunk
                            if frames_processed + len(processed_chunk) < total_frames:
                                # Save overlap for next iteration
                                overlap_start = max(0, len(processed_chunk) - self.overlap_size)
                                overlap_buffer = processed_chunk[overlap_start:]
                                write_chunk = processed_chunk[:overlap_start]
                            else:
                                # Last chunk, write everything
                                write_chunk = processed_chunk
                                overlap_buffer = array.array('h')

                            # Write processed data
                            if write_chunk:
                                wav_out.writeframes(write_chunk.tobytes())

                        frames_processed += len(chunk_data) - len(overlap_buffer)

                        # Progress callback
                        if progress_callback:
                            progress = frames_processed / total_frames
                            progress_callback(progress, frames_processed, total_frames)

                        # Force garbage collection
                        del chunk_data
                        if 'processed_chunk' in locals():
                            del processed_chunk
                        gc.collect()

            return True

        except Exception as e:
            print(f"Chunked processing error: {e}")
            return False

    def _calculate_optimal_chunk_size(self, file_size: int) -> int:
        """Calculate optimal chunk size based on available memory"""
        # Estimate available memory (simplified)
        try:
            import psutil
            available_mb = psutil.virtual_memory().available / (1024 * 1024)
        except ImportError:
            # Fallback if psutil not available
            available_mb = 1024  # Assume 1GB available

        # Use at most 25% of available memory
        target_memory_mb = min(available_mb * 0.25, 200)  # Cap at 200MB

        # Convert to samples (2 bytes per sample)
        samples_per_mb = (1024 * 1024) // 2
        optimal_samples = int(target_memory_mb * samples_per_mb)

        # Align to second boundaries
        optimal_samples = (optimal_samples // 44100) * 44100

        return max(44100, optimal_samples)  # Minimum 1 second

    def stream_process(self, input_path: str, processor_func: Callable,
                      **kwargs) -> Iterator[array.array]:
        """Stream process file yielding chunks"""

        try:
            with wave.open(input_path, 'rb') as wav_in:
                params = wav_in.getparams()
                total_frames = params.nframes

                frames_read = 0
                while frames_read < total_frames:
                    # Read chunk
                    frames_to_read = min(self.chunk_size, total_frames - frames_read)
                    raw_data = wav_in.readframes(frames_to_read)

                    if not raw_data:
                        break

                    # Convert to samples
                    samples = array.array('h', raw_data)

                    # Process chunk
                    processed = processor_func(samples, **kwargs)

                    yield processed

                    frames_read += frames_to_read

        except Exception as e:
            print(f"Stream processing error: {e}")


class MemoryMonitor:
    """Monitor memory usage during processing"""

    def __init__(self):
        self.peak_memory = 0
        self.start_memory = 0

    def start_monitoring(self):
        """Start memory monitoring"""
        try:
            import psutil
            self.start_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            self.peak_memory = self.start_memory
        except ImportError:
            self.start_memory = 0
            self.peak_memory = 0

    def update_peak(self):
        """Update peak memory usage"""
        try:
            import psutil
            current = psutil.Process().memory_info().rss / (1024 * 1024)
            self.peak_memory = max(self.peak_memory, current)
        except ImportError:
            pass

    def get_stats(self) -> Dict[str, float]:
        """Get memory usage statistics"""
        try:
            import psutil
            current = psutil.Process().memory_info().rss / (1024 * 1024)
        except ImportError:
            current = 0
        return {
            'start_mb': self.start_memory,
            'current_mb': current,
            'peak_mb': self.peak_memory,
            'used_mb': max(0, current - self.start_memory)
        }


class LargeFileProcessor:
    """Specialized processor for very large audio files"""

    def __init__(self):
        self.chunked = ChunkedProcessor()
        self.monitor = MemoryMonitor()

    def process_large_file(self, input_path: str, operation: str,
                          output_path: Optional[str] = None,
                          **kwargs) -> bool:
        """Process large file with memory optimization"""

        if not os.path.exists(input_path):
            print(f"File not found: {input_path}")
            return False

        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        print(f"Processing {file_size_mb:.1f}MB file: {Path(input_path).name}")

        if output_path is None:
            output_path = f"{Path(input_path).stem}_processed.wav"

        # Start memory monitoring
        self.monitor.start_monitoring()

        # Select processing function
        processor_func = self._get_processor_function(operation)
        if not processor_func:
            print(f"Unknown operation: {operation}")
            return False

        def progress_callback(progress, current, total):
            self.monitor.update_peak()
            percent = progress * 100
            current_frames = current / 44100  # Convert to seconds
            total_frames = total / 44100
            print(f"\rProgress: {percent:5.1f}% ({current_frames:.1f}s/{total_frames:.1f}s)", end='')

        # Process file
        success = self.chunked.process_file_chunked(
            input_path, output_path, processor_func,
            progress_callback=progress_callback,
            **kwargs
        )

        print()  # New line after progress

        # Show memory stats
        stats = self.monitor.get_stats()
        print(f"Memory usage: {stats['used_mb']:.1f}MB used, {stats['peak_mb']:.1f}MB peak")

        if success:
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"Output: {output_path} ({output_size_mb:.1f}MB)")

        return success

    def _get_processor_function(self, operation: str) -> Optional[Callable]:
        """Get processing function for operation"""
        processor = AudioProcessor()

        functions = {
            'normalize': lambda samples, **kwargs: processor.normalize(samples, kwargs.get('target_peak', 0.95)),
            'denoise': lambda samples, **kwargs: processor.reduce_noise(samples, kwargs.get('noise_floor_db', -40)),
            'amplify': lambda samples, **kwargs: processor.amplify(samples, kwargs.get('gain_db', 6)),
            'compress': lambda samples, **kwargs: processor.apply_compressor(samples,
                                                                           kwargs.get('threshold_db', -20),
                                                                           kwargs.get('ratio', 0.3))
        }

        return functions.get(operation)

    def estimate_processing_time(self, input_path: str, operation: str) -> Dict[str, float]:
        """Estimate processing time for large file"""
        if not os.path.exists(input_path):
            return {'error': 'File not found'}

        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)

        # Benchmark with small sample
        try:
            processor = AudioProcessor()
            samples, _ = processor.load_wav(input_path)

            if not samples:
                return {'error': 'Could not load file'}

            # Process small sample and measure time
            import time
            test_samples = samples[:44100]  # 1 second
            processor_func = self._get_processor_function(operation)

            if not processor_func:
                return {'error': 'Unknown operation'}

            start_time = time.time()
            processor_func(test_samples)
            processing_time = time.time() - start_time

            # Extrapolate for full file
            file_duration = len(samples) / 44100
            estimated_total_time = processing_time * file_duration

            return {
                'file_size_mb': file_size_mb,
                'file_duration_s': file_duration,
                'estimated_time_s': estimated_total_time,
                'processing_speed': file_duration / processing_time if processing_time > 0 else 0
            }

        except Exception as e:
            return {'error': str(e)}


def demo():
    """Demo memory-optimized processing"""
    print("Memory-Optimized Processing Demo")
    print("-" * 40)

    # Create a larger test file
    from audio_recorder import SimpleRecorder
    import os

    recorder = SimpleRecorder()

    # Generate longer test file
    test_file = "large_test.wav"
    print("Generating 5-second test file...")
    recorder.generate_test_tone(440, 5.0, test_file)

    if os.path.exists(test_file):
        size_mb = os.path.getsize(test_file) / (1024 * 1024)
        print(f"Test file: {size_mb:.1f}MB")

        # Test large file processor
        processor = LargeFileProcessor()

        # Estimate processing time
        print("\n1. Processing time estimation:")
        estimate = processor.estimate_processing_time(test_file, 'normalize')
        if 'error' not in estimate:
            print(f"File duration: {estimate['file_duration_s']:.1f}s")
            print(f"Estimated processing time: {estimate['estimated_time_s']:.2f}s")
            print(f"Processing speed: {estimate['processing_speed']:.1f}x realtime")

        # Test chunked processing
        print("\n2. Chunked processing:")
        success = processor.process_large_file(
            test_file, 'normalize',
            output_path="normalized_large.wav",
            target_peak=0.9
        )

        if success:
            print("✓ Chunked processing successful")
        else:
            print("✗ Chunked processing failed")

        # Test memory monitoring
        print("\n3. Memory monitoring:")
        monitor = MemoryMonitor()
        monitor.start_monitoring()

        # Simulate some processing
        chunked = ChunkedProcessor(chunk_size=22050)  # Smaller chunks
        temp_output = "temp_output.wav"

        def simple_amplify(samples, gain_db=3):
            proc = AudioProcessor()
            return proc.amplify(samples, gain_db)

        chunked.process_file_chunked(test_file, temp_output, simple_amplify, gain_db=3)

        stats = monitor.get_stats()
        print(f"Memory stats: {stats['used_mb']:.1f}MB used, peak {stats['peak_mb']:.1f}MB")

        # Cleanup
        for file in [test_file, "normalized_large.wav", temp_output]:
            if os.path.exists(file):
                os.remove(file)
                print(f"Cleaned up: {file}")

    print("\nMemory optimization demo complete!")


if __name__ == '__main__':
    demo()