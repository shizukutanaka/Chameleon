#!/usr/bin/env python3
"""
Real-time Audio Processing Pipeline
Lightweight stream processing without external dependencies
"""

import array
import queue
import threading
import time
import wave
from typing import Callable, List, Optional, Any
from pathlib import Path

from chameleon import AudioProcessor
from audio_effects import AudioEffects
from audio_analyzer import AudioAnalyzer


class ProcessingPipeline:
    """Chain multiple audio processors in real-time"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.processors = []
        self.enabled = True

    def add_processor(self, name: str, func: Callable, **kwargs) -> None:
        """Add a processor to the pipeline"""
        self.processors.append({
            'name': name,
            'func': func,
            'kwargs': kwargs,
            'enabled': True
        })

    def process(self, samples: array.array) -> array.array:
        """Process samples through the pipeline"""
        if not self.enabled or not samples:
            return samples

        result = samples
        for processor in self.processors:
            if processor['enabled']:
                try:
                    result = processor['func'](result, **processor['kwargs'])
                except Exception as e:
                    print(f"Error in {processor['name']}: {e}")

        return result

    def toggle_processor(self, name: str, enabled: Optional[bool] = None) -> None:
        """Enable/disable a specific processor"""
        for processor in self.processors:
            if processor['name'] == name:
                if enabled is None:
                    processor['enabled'] = not processor['enabled']
                else:
                    processor['enabled'] = enabled
                break

    def clear(self) -> None:
        """Clear all processors"""
        self.processors.clear()


class StreamProcessor:
    """Real-time audio stream processor"""

    def __init__(self, sample_rate: int = 44100, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.input_queue = queue.Queue(maxsize=100)
        self.output_queue = queue.Queue(maxsize=100)
        self.pipeline = ProcessingPipeline(sample_rate)
        self.running = False
        self.thread = None
        self.stats = {
            'chunks_processed': 0,
            'total_samples': 0,
            'processing_time': 0,
            'dropped_chunks': 0
        }

    def start(self) -> None:
        """Start the processing thread"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._process_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self) -> None:
        """Stop the processing thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _process_loop(self) -> None:
        """Main processing loop"""
        while self.running:
            try:
                # Get input chunk
                chunk = self.input_queue.get(timeout=0.01)

                start_time = time.time()

                # Process through pipeline
                processed = self.pipeline.process(chunk)

                # Track stats
                self.stats['chunks_processed'] += 1
                self.stats['total_samples'] += len(chunk)
                self.stats['processing_time'] += time.time() - start_time

                # Put to output queue
                if not self.output_queue.full():
                    self.output_queue.put(processed)
                else:
                    self.stats['dropped_chunks'] += 1

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Processing error: {e}")

    def feed(self, samples: array.array) -> bool:
        """Feed samples to the processor"""
        if not self.running:
            return False

        try:
            self.input_queue.put(samples, timeout=0.001)
            return True
        except queue.Full:
            self.stats['dropped_chunks'] += 1
            return False

    def get_output(self, timeout: float = 0.01) -> Optional[array.array]:
        """Get processed output"""
        try:
            return self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_stats(self) -> dict:
        """Get processing statistics"""
        stats = self.stats.copy()
        if stats['chunks_processed'] > 0:
            stats['avg_processing_time'] = stats['processing_time'] / stats['chunks_processed']
            stats['realtime_factor'] = (stats['total_samples'] / self.sample_rate) / stats['processing_time'] if stats['processing_time'] > 0 else 0
        return stats


class FileStreamProcessor:
    """Process audio files in streaming fashion"""

    def __init__(self, sample_rate: int = 44100, chunk_size: int = 4096):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.processor = AudioProcessor(sample_rate)
        self.effects = AudioEffects(sample_rate)
        self.analyzer = AudioAnalyzer(sample_rate)

    def process_file_stream(self, input_file: str, output_file: str,
                           pipeline: ProcessingPipeline,
                           progress_callback: Optional[Callable] = None) -> bool:
        """Process a file in chunks with progress reporting"""

        try:
            # Open input file
            with wave.open(input_file, 'rb') as wav_in:
                params = wav_in.getparams()
                total_frames = params.nframes

                # Open output file
                with wave.open(output_file, 'wb') as wav_out:
                    wav_out.setparams(params)

                    frames_processed = 0

                    # Process in chunks
                    while frames_processed < total_frames:
                        # Read chunk
                        chunk_frames = min(self.chunk_size, total_frames - frames_processed)
                        raw_data = wav_in.readframes(chunk_frames)

                        # Convert to array
                        samples = array.array('h', raw_data)

                        # Process
                        processed = pipeline.process(samples)

                        # Write output
                        wav_out.writeframes(processed.tobytes())

                        frames_processed += chunk_frames

                        # Progress callback
                        if progress_callback:
                            progress = frames_processed / total_frames
                            progress_callback(progress, frames_processed, total_frames)

            return True

        except Exception as e:
            print(f"Stream processing error: {e}")
            return False


class RealtimeEffects:
    """Pre-configured real-time effects chains"""

    @staticmethod
    def create_voice_enhancer(sample_rate: int = 44100) -> ProcessingPipeline:
        """Create voice enhancement pipeline"""
        pipeline = ProcessingPipeline(sample_rate)
        processor = AudioProcessor(sample_rate)
        effects = AudioEffects(sample_rate)

        # High-pass filter to remove rumble
        pipeline.add_processor('high_pass', effects.high_pass_filter, cutoff_hz=80)

        # Noise reduction
        pipeline.add_processor('noise_reduction', processor.reduce_noise, noise_floor_db=-45)

        # Compression for consistent volume
        pipeline.add_processor('compressor', processor.apply_compressor,
                             threshold_db=-20, ratio=0.4)

        # Normalize
        pipeline.add_processor('normalize', processor.normalize, target_peak=0.9)

        return pipeline

    @staticmethod
    def create_music_enhancer(sample_rate: int = 44100) -> ProcessingPipeline:
        """Create music enhancement pipeline"""
        pipeline = ProcessingPipeline(sample_rate)
        processor = AudioProcessor(sample_rate)
        effects = AudioEffects(sample_rate)

        # Slight stereo enhancement (if stereo)
        pipeline.add_processor('normalize', processor.normalize, target_peak=0.85)

        # Compression for punch
        pipeline.add_processor('compressor', processor.apply_compressor,
                             threshold_db=-15, ratio=0.3)

        # Subtle chorus for richness
        pipeline.add_processor('chorus', effects.chorus, depth_ms=2, rate_hz=1.0)

        return pipeline

    @staticmethod
    def create_podcast_processor(sample_rate: int = 44100) -> ProcessingPipeline:
        """Create podcast processing pipeline"""
        pipeline = ProcessingPipeline(sample_rate)
        processor = AudioProcessor(sample_rate)
        effects = AudioEffects(sample_rate)

        # Remove low frequency rumble
        pipeline.add_processor('high_pass', effects.high_pass_filter, cutoff_hz=100)

        # Noise gate for silence
        pipeline.add_processor('noise_gate', effects.noise_gate,
                             threshold_db=-35, attack_ms=2, release_ms=50)

        # Compression for consistent levels
        pipeline.add_processor('compressor', processor.apply_compressor,
                             threshold_db=-25, ratio=0.5)

        # Final normalize
        pipeline.add_processor('normalize', processor.normalize, target_peak=0.95)

        return pipeline


def demo():
    """Demo real-time processing"""
    print("Real-time Audio Processing Demo")
    print("-" * 40)

    # Create stream processor
    stream = StreamProcessor()

    # Create voice enhancement pipeline
    voice_pipeline = RealtimeEffects.create_voice_enhancer()
    stream.pipeline = voice_pipeline

    # Start processing
    stream.start()

    print("Stream processor started")

    # Simulate audio chunks
    import math
    for i in range(10):
        # Create test chunk
        chunk = array.array('h')
        for j in range(1024):
            t = (i * 1024 + j) / 44100
            sample = int(5000 * math.sin(2 * math.pi * 440 * t))
            chunk.append(sample)

        # Feed to processor
        stream.feed(chunk)

        # Get output
        output = stream.get_output(timeout=0.1)
        if output:
            print(f"Processed chunk {i+1}: {len(output)} samples")

        time.sleep(0.01)

    # Get stats
    stats = stream.get_stats()
    print(f"\nProcessing stats:")
    print(f"  Chunks processed: {stats['chunks_processed']}")
    print(f"  Total samples: {stats['total_samples']}")
    print(f"  Avg processing time: {stats.get('avg_processing_time', 0)*1000:.2f}ms")
    print(f"  Realtime factor: {stats.get('realtime_factor', 0):.2f}x")

    # Stop processor
    stream.stop()
    print("\nDemo complete!")


if __name__ == '__main__':
    demo()