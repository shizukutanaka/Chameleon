#!/usr/bin/env python3
"""
Real-time Audio Streaming Module
Lightweight streaming without external dependencies
"""

import array
import queue
import threading
import time
import wave
from typing import Optional, Callable

class AudioStream:
    """Simple audio streaming with callback support"""

    def __init__(self, sample_rate: int = 44100, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.buffer = queue.Queue(maxsize=100)
        self.is_streaming = False
        self.callback = None
        self.thread = None

    def start_stream(self, callback: Optional[Callable] = None):
        """Start streaming with optional processing callback"""
        if self.is_streaming:
            return False

        self.is_streaming = True
        self.callback = callback
        self.thread = threading.Thread(target=self._stream_worker)
        self.thread.daemon = True
        self.thread.start()
        return True

    def stop_stream(self):
        """Stop streaming"""
        self.is_streaming = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.buffer.queue.clear()

    def _stream_worker(self):
        """Worker thread for streaming"""
        while self.is_streaming:
            try:
                # Get chunk from buffer
                if not self.buffer.empty():
                    chunk = self.buffer.get(timeout=0.01)

                    # Process with callback if provided
                    if self.callback:
                        processed = self.callback(chunk)
                        if processed:
                            self._output_chunk(processed)
                    else:
                        self._output_chunk(chunk)
                else:
                    time.sleep(0.001)
            except:
                continue

    def _output_chunk(self, chunk: array.array):
        """Output processed chunk (placeholder for actual output)"""
        # In real implementation, this would output to audio device
        pass

    def feed_audio(self, samples: array.array):
        """Feed audio samples to stream"""
        if not self.is_streaming:
            return False

        # Split into chunks
        for i in range(0, len(samples), self.chunk_size):
            chunk = samples[i:i + self.chunk_size]
            try:
                self.buffer.put(chunk, timeout=0.01)
            except queue.Full:
                # Drop chunk if buffer full
                pass
        return True

    def stream_file(self, filepath: str, callback: Optional[Callable] = None):
        """Stream audio file with optional processing"""
        try:
            with wave.open(filepath, 'rb') as wav:
                params = wav.getparams()

                self.start_stream(callback)

                # Read and stream chunks
                while self.is_streaming:
                    frames = wav.readframes(self.chunk_size)
                    if not frames:
                        break

                    chunk = array.array('h', frames)
                    self.feed_audio(chunk)

                    # Simulate real-time playback
                    time.sleep(self.chunk_size / self.sample_rate)

                self.stop_stream()
                return True

        except Exception as e:
            print(f"Stream error: {e}")
            self.stop_stream()
            return False


class AudioBuffer:
    """Ring buffer for audio streaming"""

    def __init__(self, size: int = 44100):
        self.size = size
        self.buffer = array.array('h', [0] * size)
        self.write_pos = 0
        self.read_pos = 0
        self.lock = threading.Lock()

    def write(self, samples: array.array) -> int:
        """Write samples to buffer"""
        with self.lock:
            written = 0
            for sample in samples:
                self.buffer[self.write_pos] = sample
                self.write_pos = (self.write_pos + 1) % self.size
                written += 1

                # Prevent overrun
                if self.write_pos == self.read_pos:
                    self.read_pos = (self.read_pos + 1) % self.size

            return written

    def read(self, count: int) -> array.array:
        """Read samples from buffer"""
        with self.lock:
            result = array.array('h')
            for _ in range(count):
                if self.read_pos == self.write_pos:
                    break
                result.append(self.buffer[self.read_pos])
                self.read_pos = (self.read_pos + 1) % self.size
            return result

    def available(self) -> int:
        """Get number of available samples"""
        with self.lock:
            if self.write_pos >= self.read_pos:
                return self.write_pos - self.read_pos
            else:
                return self.size - self.read_pos + self.write_pos

    def clear(self):
        """Clear buffer"""
        with self.lock:
            self.buffer = array.array('h', [0] * self.size)
            self.write_pos = 0
            self.read_pos = 0


class StreamProcessor:
    """Process audio streams in real-time"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.filters = []

    def add_filter(self, filter_func: Callable):
        """Add processing filter to chain"""
        self.filters.append(filter_func)

    def process_chunk(self, chunk: array.array) -> array.array:
        """Process chunk through filter chain"""
        result = chunk
        for filter_func in self.filters:
            result = filter_func(result)
        return result

    def create_delay_filter(self, delay_ms: int, decay: float = 0.5):
        """Create delay filter for streaming"""
        delay_buffer = array.array('h', [0] * int((delay_ms / 1000) * self.sample_rate))
        buffer_pos = [0]

        def delay_filter(chunk: array.array) -> array.array:
            result = array.array('h')
            for sample in chunk:
                # Get delayed sample
                delayed = delay_buffer[buffer_pos[0]]

                # Mix with current
                mixed = int(sample + delayed * decay)
                mixed = max(min(mixed, 32767), -32767)
                result.append(mixed)

                # Store current sample
                delay_buffer[buffer_pos[0]] = sample
                buffer_pos[0] = (buffer_pos[0] + 1) % len(delay_buffer)

            return result

        return delay_filter

    def create_volume_filter(self, gain: float = 1.0):
        """Create volume control filter"""
        def volume_filter(chunk: array.array) -> array.array:
            result = array.array('h')
            for sample in chunk:
                adjusted = int(sample * gain)
                adjusted = max(min(adjusted, 32767), -32767)
                result.append(adjusted)
            return result
        return volume_filter


def demo_streaming():
    """Demo streaming functionality"""
    print("Audio Streaming Demo")

    # Create stream processor
    processor = StreamProcessor()

    # Add filters
    processor.add_filter(processor.create_volume_filter(0.8))
    processor.add_filter(processor.create_delay_filter(100, 0.3))

    # Create stream
    stream = AudioStream()

    # Simulate streaming
    print("Simulating audio streaming...")

    # Generate test audio
    test_samples = array.array('h')
    for i in range(44100):  # 1 second
        import math
        sample = int(10000 * math.sin(2 * math.pi * 440 * i / 44100))
        test_samples.append(sample)

    # Stream with processing
    stream.start_stream(processor.process_chunk)
    stream.feed_audio(test_samples)
    time.sleep(1)
    stream.stop_stream()

    print("Streaming demo completed")

    # Test ring buffer
    print("\nTesting ring buffer...")
    buffer = AudioBuffer(size=100)

    # Write samples
    test_data = array.array('h', range(50))
    written = buffer.write(test_data)
    print(f"Written: {written} samples")
    print(f"Available: {buffer.available()} samples")

    # Read samples
    read_data = buffer.read(25)
    print(f"Read: {len(read_data)} samples")
    print(f"Remaining: {buffer.available()} samples")

    print("\nAll streaming tests completed")


if __name__ == '__main__':
    demo_streaming()