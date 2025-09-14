#!/usr/bin/env python3
"""
Lightweight Real-time Audio Processor
Optimized for low-latency audio processing without heavy dependencies
"""

import array
import threading
import queue
import time
import math
from typing import Optional, Callable, Any, List, Dict
from collections import deque

import audio_processor
import voice_processor


class MemoryBuffer:
    """Lightweight circular buffer for audio data"""
    
    def __init__(self, size: int):
        self.size = size
        self.buffer = bytearray(size)
        self.write_pos = 0
        self.read_pos = 0
        self.available_bytes = 0
        self.lock = threading.Lock()
    
    def write(self, data: bytes) -> int:
        """Write data to buffer, returns bytes written"""
        if not data:
            return 0
            
        with self.lock:
            bytes_to_write = min(len(data), self.size - self.available_bytes)
            if bytes_to_write <= 0:
                return 0
            
            # Handle wrap-around
            if self.write_pos + bytes_to_write <= self.size:
                self.buffer[self.write_pos:self.write_pos + bytes_to_write] = data[:bytes_to_write]
            else:
                # Split write across buffer end
                first_part = self.size - self.write_pos
                self.buffer[self.write_pos:] = data[:first_part]
                self.buffer[:bytes_to_write - first_part] = data[first_part:bytes_to_write]
            
            self.write_pos = (self.write_pos + bytes_to_write) % self.size
            self.available_bytes += bytes_to_write
            
            return bytes_to_write
    
    def read(self, size: int) -> bytes:
        """Read data from buffer"""
        with self.lock:
            bytes_to_read = min(size, self.available_bytes)
            if bytes_to_read <= 0:
                return b''
            
            # Handle wrap-around
            if self.read_pos + bytes_to_read <= self.size:
                data = bytes(self.buffer[self.read_pos:self.read_pos + bytes_to_read])
            else:
                # Split read across buffer end
                first_part = self.size - self.read_pos
                data = bytes(self.buffer[self.read_pos:] + self.buffer[:bytes_to_read - first_part])
            
            self.read_pos = (self.read_pos + bytes_to_read) % self.size
            self.available_bytes -= bytes_to_read
            
            return data
    
    def available(self) -> int:
        """Get available bytes to read"""
        return self.available_bytes
    
    def space(self) -> int:
        """Get available space to write"""
        return self.size - self.available_bytes


class StreamProcessor:
    """
    Lightweight real-time audio processor with minimal latency
    """
    
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size  # Smaller chunks for lower latency
        
        # Processors
        self.audio_proc = audio_processor.AudioProcessor(sample_rate, chunk_size)
        self.voice_proc = voice_processor.VoiceProcessor(sample_rate, chunk_size)
        
        # Streaming state
        self.is_streaming = False
        self.processing_thread = None
        
        # Processing queues
        self.input_queue = queue.Queue(maxsize=16)  # Input audio chunks
        self.output_queue = queue.Queue(maxsize=16)  # Processed audio chunks
        
        # Lightweight buffers
        buffer_size = chunk_size * 8  # 8 chunks buffer
        self.input_buffer = MemoryBuffer(buffer_size * 2)  # bytes
        self.output_buffer = MemoryBuffer(buffer_size * 2)
        
        # Processing parameters
        self.voice_preset = 'normal'
        self.audio_params = {}
        self.params = {  # Initialize params dict
            'voice_preset': 'normal'
        }
        
        # Statistics
        self.processed_chunks = 0
        self.processing_errors = 0
        self.latency_history = deque(maxlen=100)
        self.performance_stats = {
            'avg_latency_ms': 0.0,
            'buffer_overruns': 0,
            'buffer_underruns': 0
        }
    
    def set_voice_preset(self, preset: str):
        """Set voice transformation preset"""
        if self.voice_proc.load_preset(preset):
            self.voice_preset = preset
    
    def set_audio_parameters(self, **params):
        """Set audio processing parameters"""
        self.audio_params.update(params)
    
    def process_chunk_realtime(self, chunk_data: bytes) -> bytes:
        """Process single chunk with minimal latency"""
        if not chunk_data:
            return chunk_data
        
        start_time = time.perf_counter()
        
        try:
            # Apply voice transformation first (usually primary)
            if self.voice_preset != 'normal':
                processed = self.voice_proc.process_chunk(chunk_data)
            else:
                processed = chunk_data
            
            # Apply audio effects if any
            if self.audio_params:
                processed = self.audio_proc.process_audio(processed, self.audio_params)
            
            # Track latency
            latency = time.perf_counter() - start_time
            self.latency_history.append(latency)
            
            # Update stats
            if len(self.latency_history) > 0:
                self.performance_stats['avg_latency_ms'] = sum(self.latency_history) / len(self.latency_history) * 1000
            
            self.processed_chunks += 1
            return processed
            
        except Exception as e:
            self.processing_errors += 1
            return chunk_data  # Return original on error
    
    def feed_audio(self, data: bytes) -> int:
        """Feed audio data for processing"""
        if not self.is_streaming:
            return 0
        
        bytes_written = self.input_buffer.write(data)
        if bytes_written < len(data):
            self.performance_stats['buffer_overruns'] += 1
        
        return bytes_written
    
    def get_processed_audio(self, size: int) -> bytes:
        """Get processed audio data"""
        if not self.is_streaming:
            return b''
        
        data = self.output_buffer.read(size)
        if len(data) < size and self.output_buffer.available() == 0:
            self.performance_stats['buffer_underruns'] += 1
        
        return data
    
    def _processing_loop(self):
        """Main processing loop for real-time operation"""
        chunk_bytes = self.chunk_size * 2  # 16-bit samples
        
        while self.is_streaming:
            try:
                # Check if we have enough input data
                if self.input_buffer.available() >= chunk_bytes:
                    # Read input chunk
                    input_chunk = self.input_buffer.read(chunk_bytes)
                    
                    # Process it
                    processed_chunk = self.process_chunk_realtime(input_chunk)
                    
                    # Write to output buffer
                    if self.output_buffer.space() >= len(processed_chunk):
                        self.output_buffer.write(processed_chunk)
                    else:
                        # Output buffer full, skip this chunk
                        self.performance_stats['buffer_overruns'] += 1
                else:
                    # Not enough input data, wait briefly
                    time.sleep(0.001)  # 1ms
                    
            except Exception as e:
                self.processing_errors += 1
                time.sleep(0.001)
    
    def start_streaming(self, duration: Optional[float] = None):
        """Start real-time processing"""
        if self.is_streaming:
            return False
        
        self.is_streaming = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        # If duration specified, stop after that time
        if duration:
            def stop_after_duration():
                time.sleep(duration)
                self.stop_streaming()
            
            timer_thread = threading.Thread(target=stop_after_duration, daemon=True)
            timer_thread.start()
        
        return True
    
    def stop_streaming(self):
        """Stop real-time processing"""
        self.is_streaming = False
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)
    
    def is_active(self) -> bool:
        """Check if streaming is active"""
        return self.is_streaming and (self.processing_thread is None or self.processing_thread.is_alive())
    
    def get_buffer_status(self) -> Dict[str, Any]:
        """Get buffer status information"""
        return {
            'input_available': self.input_buffer.available(),
            'input_space': self.input_buffer.space(),
            'output_available': self.output_buffer.available(), 
            'output_space': self.output_buffer.space(),
            'input_usage_percent': (self.input_buffer.available() / self.input_buffer.size) * 100,
            'output_usage_percent': (self.output_buffer.available() / self.output_buffer.size) * 100
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get detailed performance statistics"""
        buffer_status = self.get_buffer_status()
        
        # Calculate real-time factor
        chunk_duration_ms = (self.chunk_size / self.sample_rate) * 1000
        real_time_factor = self.performance_stats['avg_latency_ms'] / chunk_duration_ms if chunk_duration_ms > 0 else 0
        
        return {
            'is_streaming': self.is_streaming,
            'processed_chunks': self.processed_chunks,
            'processing_errors': self.processing_errors,
            'error_rate': (self.processing_errors / max(1, self.processed_chunks)) * 100,
            'avg_latency_ms': self.performance_stats['avg_latency_ms'],
            'real_time_factor': real_time_factor,
            'buffer_overruns': self.performance_stats['buffer_overruns'],
            'buffer_underruns': self.performance_stats['buffer_underruns'],
            'current_preset': self.voice_preset,
            'buffer_status': buffer_status
        }
    
    def reset_stats(self):
        """Reset performance statistics"""
        self.processed_chunks = 0
        self.processing_errors = 0
        self.latency_history.clear()
        self.performance_stats = {
            'avg_latency_ms': 0.0,
            'buffer_overruns': 0,
            'buffer_underruns': 0
        }
    
    def start_stream(self, input_callback: Callable, output_callback: Callable):
        """Start streaming processing"""
        if self.is_streaming:
            return False
        
        self.is_streaming = True
        self.processed_chunks = 0
        self.processing_errors = 0
        self.latency_samples = []
        
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        
        # Start I/O thread
        io_thread = threading.Thread(
            target=self._io_loop,
            args=(input_callback, output_callback),
            daemon=True
        )
        io_thread.start()
        
        return True
    
    def set_voice_preset(self, preset_name: str):
        """Set voice processing preset"""
        self.params['voice_preset'] = preset_name
        self.voice_preset = preset_name
        if self.voice_proc.load_preset(preset_name):
            print(f"Loaded voice preset: {preset_name}")
        else:
            print(f"Warning: Could not load voice preset: {preset_name}")
    
    def stop_stream(self):
        """Stop streaming processing"""
        self.is_streaming = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
    
    def _processing_loop(self):
        """Main processing loop"""
        while self.is_streaming:
            try:
                # Get input chunk
                chunk_data = self.input_queue.get(timeout=0.1)
                timestamp = time.time()
                
                # Process chunk
                if 'voice_preset' in self.params:
                    # Voice processing
                    self.voice_proc.load_preset(self.params['voice_preset'])
                    processed = self.voice_proc.process_chunk(chunk_data)
                else:
                    # Audio effects processing
                    processed = self.audio_proc.process_audio(chunk_data, self.params)
                
                # Calculate latency
                latency = time.time() - timestamp
                self.latency_samples.append(latency * 1000)  # ms
                
                # Keep only recent latency samples
                if len(self.latency_samples) > 100:
                    self.latency_samples = self.latency_samples[-100:]
                
                # Send to output
                self.output_queue.put(processed, timeout=0.1)
                self.processed_chunks += 1
                
            except queue.Empty:
                continue
            except Exception as e:
                self.processing_errors += 1
                if self.processing_errors > 10:
                    print(f"Too many processing errors: {e}")
                    break
    
    def _io_loop(self, input_callback: Callable, output_callback: Callable):
        """I/O loop for handling audio input/output"""
        while self.is_streaming:
            try:
                # Get input audio
                chunk = input_callback(self.chunk_size)
                if chunk:
                    self.input_queue.put(chunk, timeout=0.1)
                
                # Send output audio
                try:
                    processed = self.output_queue.get(timeout=0.1)
                    output_callback(processed)
                except queue.Empty:
                    # Send silence if no processed audio available
                    silence = bytes(self.chunk_size * 2)  # 16-bit silence
                    output_callback(silence)
                
            except Exception as e:
                print(f"I/O error: {e}")
                break
    
    def get_stats(self) -> dict:
        """Get streaming statistics"""
        avg_latency = 0
        if self.latency_samples:
            avg_latency = sum(self.latency_samples) / len(self.latency_samples)
        
        return {
            'processed_chunks': self.processed_chunks,
            'processing_errors': self.processing_errors,
            'average_latency_ms': avg_latency,
            'input_queue_size': self.input_queue.qsize(),
            'output_queue_size': self.output_queue.qsize()
        }


class MemoryBuffer:
    """
    Circular buffer for audio streaming with overflow protection
    """
    
    def __init__(self, size: int = 4096):
        self.size = size
        self.buffer = bytearray(size)
        self.read_pos = 0
        self.write_pos = 0
        self.available = 0
        self.overflows = 0
    
    def write(self, data: bytes) -> int:
        """Write data to buffer, return bytes written"""
        if not data:
            return 0
        
        bytes_to_write = min(len(data), self.size - self.available)
        if bytes_to_write < len(data):
            self.overflows += 1
        
        # Write in chunks to handle wrap-around
        written = 0
        for byte_val in data[:bytes_to_write]:
            self.buffer[self.write_pos] = byte_val
            self.write_pos = (self.write_pos + 1) % self.size
            written += 1
        
        self.available += written
        return written
    
    def read(self, num_bytes: int) -> bytes:
        """Read data from buffer"""
        bytes_to_read = min(num_bytes, self.available)
        result = bytearray()
        
        for _ in range(bytes_to_read):
            result.append(self.buffer[self.read_pos])
            self.read_pos = (self.read_pos + 1) % self.size
        
        self.available -= bytes_to_read
        return bytes(result)
    
    def peek(self, num_bytes: int) -> bytes:
        """Peek at data without removing from buffer"""
        bytes_to_peek = min(num_bytes, self.available)
        result = bytearray()
        read_pos = self.read_pos
        
        for _ in range(bytes_to_peek):
            result.append(self.buffer[read_pos])
            read_pos = (read_pos + 1) % self.size
        
        return bytes(result)
    
    def available_space(self) -> int:
        """Get available space in buffer"""
        return self.size - self.available
    
    def clear(self):
        """Clear buffer"""
        self.read_pos = 0
        self.write_pos = 0
        self.available = 0