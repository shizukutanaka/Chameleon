#!/usr/bin/env python3
"""
Real-time Voice Transformation Engine
Optimized for low-latency voice processing with advanced algorithms

Features:
- Real-time PSOLA pitch shifting
- Low-latency formant modification  
- Adaptive buffer management
- Multi-threaded processing pipeline
- Quality optimization for real-time constraints
"""

import numpy as np
import threading
import queue
import time
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from collections import deque
import warnings

warnings.filterwarnings('ignore')

@dataclass
class RealtimeConfig:
    """Configuration for real-time voice processing"""
    sample_rate: int = 44100
    buffer_size: int = 512      # Small buffer for low latency
    overlap_size: int = 256     # Overlap for smooth processing
    max_latency_ms: float = 10.0  # Maximum acceptable latency
    
    # Processing threads
    num_threads: int = 2
    
    # Quality vs performance trade-offs
    quality_mode: str = 'balanced'  # 'speed', 'balanced', 'quality'
    
    # Adaptive parameters
    adaptive_buffer: bool = True
    quality_monitoring: bool = True

class AdaptiveBuffer:
    """Adaptive buffering system for optimal latency/quality balance"""
    
    def __init__(self, config: RealtimeConfig):
        self.config = config
        self.min_buffer_size = 256
        self.max_buffer_size = 2048
        self.current_buffer_size = config.buffer_size
        
        # Performance monitoring
        self.latency_history = deque(maxlen=100)
        self.quality_history = deque(maxlen=100)
        self.adaptation_count = 0
        
    def adapt_buffer_size(self, current_latency: float, quality_score: float):
        """Adapt buffer size based on performance metrics"""
        if not self.config.adaptive_buffer:
            return self.current_buffer_size
            
        target_latency = self.config.max_latency_ms
        
        # Store metrics
        self.latency_history.append(current_latency)
        self.quality_history.append(quality_score)
        
        # Adaptation logic
        if len(self.latency_history) >= 10:  # Need sufficient history
            avg_latency = np.mean(list(self.latency_history)[-10:])
            avg_quality = np.mean(list(self.quality_history)[-10:])
            
            # If latency is too high, reduce buffer size
            if avg_latency > target_latency * 1.2:
                new_size = max(self.min_buffer_size, 
                             int(self.current_buffer_size * 0.8))
                
            # If quality is poor but latency is good, increase buffer size
            elif avg_quality < 0.7 and avg_latency < target_latency * 0.8:
                new_size = min(self.max_buffer_size, 
                             int(self.current_buffer_size * 1.2))
            else:
                new_size = self.current_buffer_size
                
            if new_size != self.current_buffer_size:
                self.current_buffer_size = new_size
                self.adaptation_count += 1
                
        return self.current_buffer_size
    
    def get_optimal_overlap(self) -> int:
        """Get optimal overlap size based on current buffer"""
        return min(self.current_buffer_size // 2, self.config.overlap_size)

class FastPitchShifter:
    """Optimized pitch shifter for real-time processing"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.pitch_buffer = np.zeros(4096)
        self.phase_vocoder = FastPhaseVocoder(sample_rate)
        
    def shift_pitch_realtime(self, audio_chunk: np.ndarray, 
                           pitch_factor: float) -> np.ndarray:
        """Real-time pitch shifting with minimal latency"""
        if abs(pitch_factor - 1.0) < 0.01:
            return audio_chunk
            
        # Use phase vocoder for high-quality pitch shifting
        return self.phase_vocoder.process_chunk(audio_chunk, pitch_factor)

class FastPhaseVocoder:
    """Fast phase vocoder implementation for real-time pitch shifting"""
    
    def __init__(self, sample_rate: int = 44100, frame_size: int = 1024):
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.hop_size = frame_size // 4
        
        # Pre-computed windows
        self.analysis_window = np.hanning(frame_size)
        self.synthesis_window = np.hanning(frame_size)
        
        # Phase accumulation
        self.phase_accumulator = np.zeros(frame_size // 2 + 1)
        self.previous_phase = np.zeros(frame_size // 2 + 1)
        
        # Overlap-add buffer
        self.output_buffer = np.zeros(frame_size * 2)
        
    def process_chunk(self, input_chunk: np.ndarray, pitch_factor: float) -> np.ndarray:
        """Process audio chunk with pitch shifting"""
        # Ensure chunk is the right size
        if len(input_chunk) != self.hop_size:
            # Pad or trim
            if len(input_chunk) < self.hop_size:
                input_chunk = np.pad(input_chunk, (0, self.hop_size - len(input_chunk)))
            else:
                input_chunk = input_chunk[:self.hop_size]
                
        # Shift buffer and add new input
        self.pitch_buffer = np.roll(self.pitch_buffer, -self.hop_size)
        self.pitch_buffer[-self.hop_size:] = input_chunk
        
        # Extract frame for analysis
        frame = self.pitch_buffer[-self.frame_size:] * self.analysis_window
        
        # FFT
        spectrum = np.fft.rfft(frame)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)
        
        # Phase unwrapping and modification
        phase_diff = phase - self.previous_phase
        self.previous_phase = phase.copy()
        
        # Unwrap phase difference
        phase_diff = np.unwrap(phase_diff)
        
        # True frequency estimation
        true_freq = phase_diff / (2 * np.pi / self.sample_rate * self.hop_size)
        
        # Modify for pitch shifting
        target_freq = true_freq * pitch_factor
        
        # Update phase accumulator
        self.phase_accumulator += 2 * np.pi * target_freq / self.sample_rate * self.hop_size
        
        # Construct output spectrum
        output_spectrum = magnitude * np.exp(1j * self.phase_accumulator)
        
        # IFFT
        output_frame = np.fft.irfft(output_spectrum, n=self.frame_size)
        
        # Apply synthesis window
        output_frame *= self.synthesis_window
        
        # Overlap-add
        self.output_buffer[:self.frame_size] += output_frame
        
        # Extract output chunk
        output_chunk = self.output_buffer[:self.hop_size].copy()
        
        # Shift output buffer
        self.output_buffer = np.roll(self.output_buffer, -self.hop_size)
        self.output_buffer[-self.hop_size:] = 0
        
        return output_chunk

class FastFormantProcessor:
    """Fast formant processing for real-time applications"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.formant_filters = self._create_formant_filters()
        
    def _create_formant_filters(self) -> List[Dict]:
        """Create formant frequency filters"""
        # Typical formant frequencies for vowels
        formant_freqs = [
            {'center': 500, 'bandwidth': 80},   # F1
            {'center': 1500, 'bandwidth': 120}, # F2  
            {'center': 2500, 'bandwidth': 150}, # F3
        ]
        
        filters = []
        for formant in formant_freqs:
            # Create bandpass filter
            center = formant['center']
            bandwidth = formant['bandwidth']
            
            # Simple IIR bandpass filter coefficients
            Q = center / bandwidth
            omega = 2 * np.pi * center / self.sample_rate
            alpha = np.sin(omega) / (2 * Q)
            
            # Bandpass filter coefficients
            b0 = alpha
            b1 = 0
            b2 = -alpha
            a0 = 1 + alpha
            a1 = -2 * np.cos(omega)
            a2 = 1 - alpha
            
            # Normalize
            filters.append({
                'b': np.array([b0, b1, b2]) / a0,
                'a': np.array([1, a1/a0, a2/a0]),
                'state': np.zeros(2)  # Filter delay line
            })
            
        return filters
    
    def process_formants_realtime(self, audio_chunk: np.ndarray, 
                                formant_shift: float) -> np.ndarray:
        """Real-time formant processing"""
        if abs(formant_shift - 1.0) < 0.01:
            return audio_chunk
            
        # Apply formant shifting using spectral warping
        return self._spectral_warp(audio_chunk, formant_shift)
    
    def _spectral_warp(self, audio: np.ndarray, warp_factor: float) -> np.ndarray:
        """Fast spectral warping for formant shifting"""
        # Simple all-pass filter chain for frequency warping
        # This is a simplified implementation
        
        # Design all-pass filters for warping
        warped = audio.copy()
        
        if warp_factor > 1.0:
            # Higher formants - emphasize high frequencies
            alpha = min(0.3, (warp_factor - 1.0) * 0.5)
            
            # High-pass emphasis
            for i in range(1, len(warped)):
                warped[i] = audio[i] + alpha * (audio[i] - audio[i-1])
                
        elif warp_factor < 1.0:
            # Lower formants - emphasize low frequencies  
            alpha = min(0.3, (1.0 - warp_factor) * 0.5)
            
            # Low-pass emphasis  
            for i in range(1, len(warped)):
                warped[i] = audio[i] * (1 - alpha) + audio[i-1] * alpha
                
        return warped

class RealtimeVoiceProcessor:
    """Main real-time voice processing engine"""
    
    def __init__(self, config: Optional[RealtimeConfig] = None):
        self.config = config or RealtimeConfig()
        
        # Processing components
        self.pitch_shifter = FastPitchShifter(self.config.sample_rate)
        self.formant_processor = FastFormantProcessor(self.config.sample_rate)
        self.adaptive_buffer = AdaptiveBuffer(self.config)
        
        # Threading components
        self.input_queue = queue.Queue(maxsize=10)
        self.output_queue = queue.Queue(maxsize=10)
        self.processing_threads = []
        self.running = False
        
        # Performance monitoring
        self.latency_tracker = LatencyTracker()
        self.quality_monitor = QualityMonitor()
        
        # Processing parameters
        self.voice_params = {
            'pitch_factor': 1.0,
            'formant_shift': 1.0,
            'gain': 1.0
        }
        
        print(f"Real-time Voice Processor initialized:")
        print(f"  - Sample rate: {self.config.sample_rate} Hz")
        print(f"  - Buffer size: {self.config.buffer_size} samples")
        print(f"  - Target latency: {self.config.max_latency_ms} ms")
        print(f"  - Processing threads: {self.config.num_threads}")
    
    def start_processing(self, input_callback: Callable[[np.ndarray], None],
                        output_callback: Callable[[], Optional[np.ndarray]]):
        """Start real-time processing"""
        if self.running:
            return
            
        self.running = True
        
        # Start processing threads
        for i in range(self.config.num_threads):
            thread = threading.Thread(
                target=self._processing_worker,
                args=(i,),
                daemon=True
            )
            thread.start()
            self.processing_threads.append(thread)
            
        # Start I/O threads
        input_thread = threading.Thread(
            target=self._input_worker,
            args=(input_callback,),
            daemon=True
        )
        input_thread.start()
        
        output_thread = threading.Thread(
            target=self._output_worker, 
            args=(output_callback,),
            daemon=True
        )
        output_thread.start()
        
        print("Real-time processing started")
    
    def stop_processing(self):
        """Stop real-time processing"""
        self.running = False
        
        # Wait for threads to finish
        for thread in self.processing_threads:
            thread.join(timeout=1.0)
            
        self.processing_threads.clear()
        
        # Clear queues
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break
                
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break
                
        print("Real-time processing stopped")
    
    def update_voice_params(self, **params):
        """Update voice processing parameters"""
        self.voice_params.update(params)
        
    def _input_worker(self, input_callback: Callable[[np.ndarray], None]):
        """Input thread worker"""
        while self.running:
            try:
                # Get audio chunk from input callback
                audio_chunk = input_callback()
                
                if audio_chunk is not None and len(audio_chunk) > 0:
                    timestamp = time.time()
                    
                    # Add to processing queue
                    try:
                        self.input_queue.put((audio_chunk, timestamp), timeout=0.001)
                    except queue.Full:
                        # Drop oldest if queue is full
                        try:
                            self.input_queue.get_nowait()
                            self.input_queue.put((audio_chunk, timestamp))
                        except queue.Empty:
                            pass
                            
            except Exception as e:
                if self.running:  # Only log if we're still supposed to be running
                    print(f"Input worker error: {e}")
                    
            time.sleep(0.001)  # Small sleep to prevent busy waiting
    
    def _output_worker(self, output_callback: Callable[[np.ndarray], None]):
        """Output thread worker"""
        while self.running:
            try:
                # Get processed audio from output queue
                processed_audio, original_timestamp = self.output_queue.get(timeout=0.01)
                
                # Calculate latency
                latency_ms = (time.time() - original_timestamp) * 1000
                self.latency_tracker.add_measurement(latency_ms)
                
                # Send to output callback
                output_callback(processed_audio)
                
                # Adapt buffer size based on performance
                if self.config.adaptive_buffer:
                    quality_score = self.quality_monitor.get_current_quality()
                    new_buffer_size = self.adaptive_buffer.adapt_buffer_size(
                        latency_ms, quality_score
                    )
                    
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    print(f"Output worker error: {e}")
    
    def _processing_worker(self, worker_id: int):
        """Main processing thread worker"""
        while self.running:
            try:
                # Get audio chunk from input queue
                audio_chunk, timestamp = self.input_queue.get(timeout=0.01)
                
                # Process audio
                processed_chunk = self._process_audio_chunk(audio_chunk)
                
                # Add to output queue
                try:
                    self.output_queue.put((processed_chunk, timestamp), timeout=0.001)
                except queue.Full:
                    # Drop oldest if queue is full
                    try:
                        self.output_queue.get_nowait()
                        self.output_queue.put((processed_chunk, timestamp))
                    except queue.Empty:
                        pass
                        
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    print(f"Processing worker {worker_id} error: {e}")
    
    def _process_audio_chunk(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Process a single audio chunk"""
        processed = audio_chunk.copy().astype(np.float32)
        
        # Apply pitch shifting
        if abs(self.voice_params['pitch_factor'] - 1.0) > 0.01:
            processed = self.pitch_shifter.shift_pitch_realtime(
                processed, self.voice_params['pitch_factor']
            )
            
        # Apply formant processing
        if abs(self.voice_params['formant_shift'] - 1.0) > 0.01:
            processed = self.formant_processor.process_formants_realtime(
                processed, self.voice_params['formant_shift']
            )
            
        # Apply gain
        if abs(self.voice_params['gain'] - 1.0) > 0.01:
            processed *= self.voice_params['gain']
            
        # Quality monitoring
        self.quality_monitor.analyze_chunk(audio_chunk, processed)
        
        # Clip to prevent distortion
        processed = np.clip(processed, -0.99, 0.99)
        
        return processed
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            'latency_ms': self.latency_tracker.get_average_latency(),
            'quality_score': self.quality_monitor.get_current_quality(),
            'buffer_size': self.adaptive_buffer.current_buffer_size,
            'adaptation_count': self.adaptive_buffer.adaptation_count,
            'queue_sizes': {
                'input': self.input_queue.qsize(),
                'output': self.output_queue.qsize()
            }
        }

class LatencyTracker:
    """Track processing latency"""
    
    def __init__(self, history_size: int = 100):
        self.history = deque(maxlen=history_size)
        
    def add_measurement(self, latency_ms: float):
        """Add latency measurement"""
        self.history.append(latency_ms)
        
    def get_average_latency(self) -> float:
        """Get average latency"""
        if len(self.history) == 0:
            return 0.0
        return np.mean(list(self.history))
    
    def get_latency_stats(self) -> Dict[str, float]:
        """Get detailed latency statistics"""
        if len(self.history) == 0:
            return {'avg': 0, 'min': 0, 'max': 0, 'std': 0}
            
        latencies = list(self.history)
        return {
            'avg': np.mean(latencies),
            'min': np.min(latencies),
            'max': np.max(latencies),
            'std': np.std(latencies)
        }

class QualityMonitor:
    """Monitor audio quality metrics"""
    
    def __init__(self):
        self.quality_history = deque(maxlen=50)
        
    def analyze_chunk(self, original: np.ndarray, processed: np.ndarray):
        """Analyze quality of processed audio chunk"""
        # Simple quality metrics
        
        # Signal-to-noise ratio estimate
        original_rms = np.sqrt(np.mean(original**2))
        processed_rms = np.sqrt(np.mean(processed**2))
        
        if original_rms > 0:
            rms_ratio = processed_rms / original_rms
            
            # Correlation coefficient
            if len(original) == len(processed):
                correlation = np.corrcoef(original, processed[:len(original)])[0, 1]
                if np.isnan(correlation):
                    correlation = 0.0
            else:
                correlation = 0.0
                
            # Combined quality score
            quality_score = min(1.0, correlation * 0.8 + (1.0 - abs(rms_ratio - 1.0)) * 0.2)
            
            self.quality_history.append(quality_score)
            
    def get_current_quality(self) -> float:
        """Get current quality score"""
        if len(self.quality_history) == 0:
            return 1.0
        return np.mean(list(self.quality_history))

# Demo function for real-time processing
def demo_realtime_processing():
    """Demonstrate real-time voice processing"""
    print("=== Real-time Voice Processing Demo ===\n")
    
    # Configuration
    config = RealtimeConfig(
        sample_rate=44100,
        buffer_size=512,
        max_latency_ms=10.0,
        num_threads=2,
        quality_mode='balanced'
    )
    
    # Initialize processor
    processor = RealtimeVoiceProcessor(config)
    
    # Test data simulation
    test_duration = 3.0  # seconds
    chunk_size = config.buffer_size
    sample_rate = config.sample_rate
    
    # Generate test audio
    t_total = np.linspace(0, test_duration, int(sample_rate * test_duration))
    test_audio = np.sin(2 * np.pi * 150 * t_total) * 0.5  # 150 Hz sine wave
    
    # Split into chunks
    audio_chunks = []
    for i in range(0, len(test_audio), chunk_size):
        chunk = test_audio[i:i + chunk_size]
        if len(chunk) == chunk_size:
            audio_chunks.append(chunk)
    
    # Simulation variables
    chunk_index = 0
    output_chunks = []
    
    def input_callback() -> Optional[np.ndarray]:
        nonlocal chunk_index
        if chunk_index < len(audio_chunks):
            chunk = audio_chunks[chunk_index]
            chunk_index += 1
            return chunk
        return None
    
    def output_callback(processed_chunk: np.ndarray):
        output_chunks.append(processed_chunk)
    
    # Set voice parameters
    processor.update_voice_params(
        pitch_factor=1.3,    # Higher pitch
        formant_shift=1.1,   # Brighter formants
        gain=0.8             # Reduce volume slightly
    )
    
    print("Starting real-time processing simulation...")
    
    # Start processing
    processor.start_processing(input_callback, output_callback)
    
    # Simulate real-time by waiting
    start_time = time.time()
    while time.time() - start_time < test_duration + 1.0 and chunk_index <= len(audio_chunks):
        time.sleep(0.1)
        
        # Print stats periodically
        if int((time.time() - start_time) * 10) % 10 == 0:
            stats = processor.get_performance_stats()
            print(f"Latency: {stats['latency_ms']:.1f}ms, "
                  f"Quality: {stats['quality_score']:.2f}, "
                  f"Buffer: {stats['buffer_size']} samples")
    
    # Stop processing
    processor.stop_processing()
    
    # Results
    total_output_samples = sum(len(chunk) for chunk in output_chunks)
    total_input_samples = sum(len(chunk) for chunk in audio_chunks)
    
    print(f"\nProcessing completed:")
    print(f"  Input chunks: {len(audio_chunks)}")
    print(f"  Output chunks: {len(output_chunks)}")
    print(f"  Sample preservation: {total_output_samples/total_input_samples:.3f}")
    
    # Final statistics
    final_stats = processor.get_performance_stats()
    print(f"\nFinal performance statistics:")
    for key, value in final_stats.items():
        if isinstance(value, dict):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value:.3f}")

if __name__ == "__main__":
    demo_realtime_processing()