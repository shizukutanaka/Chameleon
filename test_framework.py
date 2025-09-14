#!/usr/bin/env python3
"""
Chameleon Audio System - Comprehensive Testing Framework
========================================================
Production-ready testing infrastructure for all audio modules
"""

import unittest
import time
import random
import tempfile
import os
import json
import wave
import struct
import hashlib
import threading
import queue
from typing import List, Tuple, Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from enum import Enum

# Import all available Chameleon modules
import audio_processor
import stream_processor
import voice_processor
import audio_detector
import audio_utils
import performance
import quality_monitor
import fft_analysis
import file_optimizer
import compatibility
import config_manager
import error_handler
import plugins

# Try to import optional modules
try:
    import audio_processor_advanced
    HAS_ADVANCED_PROCESSOR = True
except ImportError:
    HAS_ADVANCED_PROCESSOR = False

try:
    import voice_processor_advanced
    HAS_ADVANCED_VOICE = True
except ImportError:
    HAS_ADVANCED_VOICE = False


class TestCategory(Enum):
    """Test categories for organization"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    STRESS = "stress"
    REGRESSION = "regression"
    SECURITY = "security"


@dataclass
class TestResult:
    """Test execution result"""
    name: str
    category: TestCategory
    passed: bool
    duration: float
    error: Optional[str] = None
    metrics: Dict[str, Any] = None


class AudioTestUtils:
    """Utility functions for audio testing"""
    
    @staticmethod
    def generate_sine_wave(frequency: float, duration: float, sample_rate: int = 44100) -> List[float]:
        """Generate sine wave test signal"""
        import math
        samples = []
        for i in range(int(sample_rate * duration)):
            t = i / sample_rate
            samples.append(math.sin(2 * math.pi * frequency * t))
        return samples
    
    @staticmethod
    def generate_noise(duration: float, sample_rate: int = 44100) -> List[float]:
        """Generate white noise test signal"""
        return [random.uniform(-1, 1) for _ in range(int(sample_rate * duration))]
    
    @staticmethod
    def generate_impulse(position: float, duration: float, sample_rate: int = 44100) -> List[float]:
        """Generate impulse test signal"""
        samples = [0.0] * int(sample_rate * duration)
        impulse_idx = int(position * sample_rate)
        if impulse_idx < len(samples):
            samples[impulse_idx] = 1.0
        return samples
    
    @staticmethod
    def calculate_snr(original: List[float], processed: List[float]) -> float:
        """Calculate signal-to-noise ratio"""
        import math
        if len(original) != len(processed):
            return float('-inf')
        
        signal_power = sum(s ** 2 for s in original) / len(original)
        noise = [processed[i] - original[i] for i in range(len(original))]
        noise_power = sum(n ** 2 for n in noise) / len(noise)
        
        if noise_power == 0:
            return float('inf')
        return 10 * math.log10(signal_power / noise_power)
    
    @staticmethod
    def calculate_thd(signal: List[float], fundamental_freq: float, sample_rate: int = 44100) -> float:
        """Calculate total harmonic distortion"""
        import math
        # Simplified THD calculation
        fft_result = fft_analysis.FFTAnalyzer().compute_fft(signal)
        fundamental_power = abs(fft_result[int(fundamental_freq)])
        harmonic_power = sum(abs(fft_result[i]) ** 2 for i in range(2, 10) 
                           if i * fundamental_freq < sample_rate / 2)
        
        if fundamental_power == 0:
            return float('inf')
        return math.sqrt(harmonic_power) / fundamental_power
    
    @staticmethod
    def create_test_wav(filename: str, samples: List[float], sample_rate: int = 44100):
        """Create test WAV file"""
        with wave.open(filename, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            
            # Convert float samples to 16-bit PCM
            pcm_data = []
            for sample in samples:
                pcm_value = int(max(-32768, min(32767, sample * 32767)))
                pcm_data.append(struct.pack('<h', pcm_value))
            
            wav.writeframes(b''.join(pcm_data))


class TestAudioProcessor(unittest.TestCase):
    """Unit tests for AudioProcessor module"""
    
    def setUp(self):
        self.processor = audio_processor.AudioProcessor()
        self.test_utils = AudioTestUtils()
    
    def test_normalize_audio(self):
        """Test audio normalization"""
        # Generate test signal
        signal = self.test_utils.generate_sine_wave(440, 1.0)
        signal = [s * 0.5 for s in signal]  # Scale down
        
        # Normalize
        normalized = self.processor.normalize(signal)
        
        # Check peak is close to 1.0
        peak = max(abs(s) for s in normalized)
        self.assertAlmostEqual(peak, 1.0, places=2)
    
    def test_apply_gain(self):
        """Test gain application"""
        signal = self.test_utils.generate_sine_wave(440, 0.1)
        gain_db = 6.0  # +6dB should double amplitude
        
        amplified = self.processor.apply_gain(signal, gain_db)
        
        # Check RMS increase
        import math
        rms_original = math.sqrt(sum(s ** 2 for s in signal) / len(signal))
        rms_amplified = math.sqrt(sum(s ** 2 for s in amplified) / len(amplified))
        
        ratio = rms_amplified / rms_original
        expected_ratio = 10 ** (gain_db / 20)
        
        self.assertAlmostEqual(ratio, expected_ratio, places=1)
    
    def test_apply_eq(self):
        """Test equalizer"""
        signal = self.test_utils.generate_noise(1.0)
        eq_bands = {
            100: -6,   # Cut bass
            1000: 0,   # Flat mids
            10000: 6   # Boost highs
        }
        
        equalized = self.processor.apply_eq(signal, eq_bands)
        
        # Basic check - output should have same length
        self.assertEqual(len(equalized), len(signal))
        
        # Check signal is modified
        self.assertNotEqual(signal[:100], equalized[:100])
    
    def test_compress_audio(self):
        """Test dynamic range compression"""
        # Create signal with dynamic range
        signal = []
        for i in range(44100):
            if i < 22050:
                signal.append(random.uniform(-0.3, 0.3))  # Quiet
            else:
                signal.append(random.uniform(-0.9, 0.9))  # Loud
        
        compressed = self.processor.compress(signal, threshold=-20, ratio=4)
        
        # Check dynamic range is reduced
        import math
        def calculate_dynamic_range(sig):
            rms_values = []
            window_size = 1024
            for i in range(0, len(sig) - window_size, window_size):
                window = sig[i:i+window_size]
                rms = math.sqrt(sum(s ** 2 for s in window) / len(window))
                if rms > 0:
                    rms_values.append(20 * math.log10(rms))
            return max(rms_values) - min(rms_values) if rms_values else 0
        
        dr_original = calculate_dynamic_range(signal)
        dr_compressed = calculate_dynamic_range(compressed)
        
        self.assertLess(dr_compressed, dr_original)


class TestStreamProcessor(unittest.TestCase):
    """Unit tests for StreamProcessor module"""
    
    def setUp(self):
        self.processor = stream_processor.StreamProcessor()
        self.test_utils = AudioTestUtils()
    
    def test_stream_initialization(self):
        """Test stream processor initialization"""
        self.assertIsNotNone(self.processor.input_queue)
        self.assertIsNotNone(self.processor.output_queue)
        self.assertIsInstance(self.processor.params, dict)
    
    def test_real_time_processing(self):
        """Test real-time processing latency"""
        # Start processor
        self.processor.start()
        
        # Send test data
        test_data = self.test_utils.generate_sine_wave(440, 0.1)
        
        start_time = time.time()
        self.processor.input_queue.put(test_data)
        
        # Wait for output
        timeout = 0.1  # 100ms timeout
        try:
            result = self.processor.output_queue.get(timeout=timeout)
            latency = time.time() - start_time
            
            # Check latency is under 10ms
            self.assertLess(latency, 0.01, "Latency exceeds 10ms requirement")
            
        except queue.Empty:
            self.fail("Stream processing timed out")
        
        finally:
            self.processor.stop()
    
    def test_buffer_management(self):
        """Test buffer overflow handling"""
        self.processor.start()
        
        try:
            # Flood the input queue
            for _ in range(1000):
                data = self.test_utils.generate_noise(0.01)
                self.processor.input_queue.put_nowait(data)
            
            # Should handle gracefully without crash
            time.sleep(0.5)
            
            # Check some data was processed
            processed_count = 0
            while not self.processor.output_queue.empty():
                self.processor.output_queue.get_nowait()
                processed_count += 1
            
            self.assertGreater(processed_count, 0, "No data was processed")
            
        finally:
            self.processor.stop()


class TestVoiceProcessor(unittest.TestCase):
    """Unit tests for VoiceProcessor module"""
    
    def setUp(self):
        self.processor = voice_processor.VoiceProcessor()
        self.test_utils = AudioTestUtils()
    
    def test_pitch_shift(self):
        """Test pitch shifting"""
        signal = self.test_utils.generate_sine_wave(440, 0.5)  # A4 note
        
        # Shift up one octave (12 semitones)
        shifted = self.processor.pitch_shift(signal, 12)
        
        # Basic validation
        self.assertEqual(len(shifted), len(signal))
        self.assertNotEqual(signal[:100], shifted[:100])
    
    def test_formant_shift(self):
        """Test formant shifting"""
        signal = self.test_utils.generate_sine_wave(200, 0.5)
        
        shifted = self.processor.formant_shift(signal, 1.5)
        
        self.assertEqual(len(shifted), len(signal))
        self.assertNotEqual(signal, shifted)
    
    def test_gender_change(self):
        """Test gender transformation"""
        signal = self.test_utils.generate_sine_wave(150, 1.0)  # Male pitch range
        
        # Transform to female
        female_voice = self.processor.change_gender(signal, 'female')
        
        self.assertEqual(len(female_voice), len(signal))
        self.assertNotEqual(signal, female_voice)


class TestFFTAnalysis(unittest.TestCase):
    """Unit tests for FFT Analysis module"""
    
    def setUp(self):
        self.analyzer = fft_analysis.FFTAnalyzer()
        self.test_utils = AudioTestUtils()
    
    def test_fft_computation(self):
        """Test FFT computation accuracy"""
        # Generate pure tone
        frequency = 1000
        signal = self.test_utils.generate_sine_wave(frequency, 1.0, 44100)
        
        # Compute FFT
        spectrum = self.analyzer.compute_fft(signal)
        
        # Find peak frequency
        peak_bin = max(range(len(spectrum)), key=lambda i: abs(spectrum[i]))
        peak_freq = peak_bin * 44100 / len(signal)
        
        # Check peak is at expected frequency (within 50Hz tolerance)
        self.assertAlmostEqual(peak_freq, frequency, delta=50)
    
    def test_spectral_features(self):
        """Test spectral feature extraction"""
        signal = self.test_utils.generate_noise(1.0)
        
        features = self.analyzer.extract_features(signal)
        
        # Check all features are computed
        expected_features = ['spectral_centroid', 'spectral_rolloff', 
                           'spectral_flux', 'zero_crossing_rate']
        
        for feature in expected_features:
            self.assertIn(feature, features)
            self.assertIsInstance(features[feature], (int, float))


class TestPerformanceModule(unittest.TestCase):
    """Performance and stress tests"""
    
    def setUp(self):
        self.monitor = performance.PerformanceMonitor()
        self.test_utils = AudioTestUtils()
    
    def test_cpu_usage_monitoring(self):
        """Test CPU usage tracking"""
        self.monitor.start_monitoring()
        
        # Perform intensive operation
        processor = audio_processor.AudioProcessor()
        signal = self.test_utils.generate_noise(5.0)
        
        for _ in range(10):
            processed = processor.compress(signal, -20, 4)
            processed = processor.apply_eq(processed, {100: -6, 1000: 0, 10000: 6})
        
        stats = self.monitor.get_stats()
        
        self.assertIn('cpu_percent', stats)
        self.assertIn('memory_mb', stats)
        self.assertIn('processing_time', stats)
        
        # CPU should be measurable
        self.assertGreater(stats['cpu_percent'], 0)
    
    def test_memory_usage(self):
        """Test memory usage tracking"""
        import gc
        gc.collect()
        
        initial_memory = self.monitor.get_memory_usage()
        
        # Allocate large audio buffers
        large_buffers = []
        for _ in range(100):
            buffer = self.test_utils.generate_noise(10.0)  # 10 seconds each
            large_buffers.append(buffer)
        
        peak_memory = self.monitor.get_memory_usage()
        
        # Clear buffers
        large_buffers.clear()
        gc.collect()
        
        final_memory = self.monitor.get_memory_usage()
        
        # Memory should spike and then drop
        self.assertGreater(peak_memory, initial_memory)
        self.assertLess(final_memory, peak_memory)
    
    def test_throughput(self):
        """Test processing throughput"""
        processor = audio_processor.AudioProcessor()
        
        # Process 100 seconds of audio
        total_samples = 0
        start_time = time.time()
        
        for _ in range(100):
            signal = self.test_utils.generate_sine_wave(440, 1.0)
            processed = processor.normalize(signal)
            total_samples += len(processed)
        
        duration = time.time() - start_time
        throughput = total_samples / duration
        
        # Should process at least 10x real-time (441,000 samples/sec minimum)
        self.assertGreater(throughput, 441000, "Throughput below 10x real-time")


class TestQualityMonitor(unittest.TestCase):
    """Unit tests for quality monitoring"""
    
    def setUp(self):
        self.monitor = quality_monitor.QualityMonitor()
        self.test_utils = AudioTestUtils()
    
    def test_clipping_detection(self):
        """Test clipping detection"""
        # Create clipped signal
        signal = self.test_utils.generate_sine_wave(440, 1.0)
        clipped = [max(-0.9, min(0.9, s * 2)) for s in signal]  # Clip at 0.9
        
        metrics = self.monitor.analyze(clipped)
        
        self.assertIn('clipping_detected', metrics)
        self.assertTrue(metrics['clipping_detected'])
    
    def test_noise_floor_measurement(self):
        """Test noise floor measurement"""
        # Create signal with noise
        signal = self.test_utils.generate_sine_wave(440, 1.0)
        noise = self.test_utils.generate_noise(1.0)
        
        # Mix signal with noise
        noisy = [signal[i] + noise[i] * 0.01 for i in range(len(signal))]
        
        metrics = self.monitor.analyze(noisy)
        
        self.assertIn('noise_floor_db', metrics)
        self.assertLess(metrics['noise_floor_db'], -40)  # Should be low
    
    def test_dynamic_range(self):
        """Test dynamic range measurement"""
        # Create dynamic signal
        signal = []
        for i in range(44100):
            if i < 22050:
                signal.extend(self.test_utils.generate_sine_wave(440, 0.01))
            else:
                signal.extend(self.test_utils.generate_sine_wave(440, 0.01))
                
        signal = signal[:44100]
        
        # Add dynamics
        for i in range(22050, 44100):
            signal[i] *= 10  # Make second half louder
        
        metrics = self.monitor.analyze(signal)
        
        self.assertIn('dynamic_range_db', metrics)
        self.assertGreater(metrics['dynamic_range_db'], 10)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and recovery"""
    
    def test_corrupt_file_handling(self):
        """Test handling of corrupt audio files"""
        handler = error_handler.ErrorHandler()
        
        # Create corrupt WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b'RIFF')  # Incomplete WAV header
            corrupt_file = f.name
        
        try:
            result = handler.safe_load_audio(corrupt_file)
            self.assertIsNone(result, "Should return None for corrupt file")
            
            # Check error was logged
            errors = handler.get_error_log()
            self.assertGreater(len(errors), 0)
            
        finally:
            os.unlink(corrupt_file)
    
    def test_recovery_mechanism(self):
        """Test automatic recovery from errors"""
        handler = error_handler.ErrorHandler()
        processor = audio_processor.AudioProcessor()
        
        # Simulate processing error
        def faulty_process(signal):
            if random.random() < 0.5:
                raise ValueError("Random processing error")
            return processor.normalize(signal)
        
        signal = AudioTestUtils().generate_sine_wave(440, 0.1)
        
        # Try with retry mechanism
        result = handler.with_retry(faulty_process, signal, max_retries=5)
        
        # Should eventually succeed
        self.assertIsNotNone(result)
    
    def test_graceful_degradation(self):
        """Test graceful degradation under resource pressure"""
        handler = error_handler.ErrorHandler()
        
        # Simulate resource exhaustion
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 95  # 95% memory usage
            
            # Should switch to low-quality mode
            mode = handler.get_processing_mode()
            self.assertEqual(mode, 'low_quality')


class IntegrationTestSuite(unittest.TestCase):
    """Integration tests for module interactions"""
    
    def test_full_processing_pipeline(self):
        """Test complete audio processing pipeline"""
        # Generate test audio
        test_utils = AudioTestUtils()
        signal = test_utils.generate_sine_wave(440, 2.0)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            test_file = f.name
            test_utils.create_test_wav(test_file, signal)
        
        try:
            # Load with compatibility layer
            compat = compatibility.AudioCompatibility()
            loaded = compat.load_audio(test_file)
            
            # Process through main processor
            processor = audio_processor.AudioProcessor()
            normalized = processor.normalize(loaded)
            compressed = processor.compress(normalized, -20, 4)
            
            # Apply voice processing
            voice = voice_processor.VoiceProcessor()
            pitched = voice.pitch_shift(compressed, 2)
            
            # Analyze with FFT
            analyzer = fft_analysis.FFTAnalyzer()
            spectrum = analyzer.compute_fft(pitched)
            
            # Monitor quality
            monitor = quality_monitor.QualityMonitor()
            metrics = monitor.analyze(pitched)
            
            # Save with optimizer
            optimizer = file_optimizer.FileOptimizer()
            output_file = test_file.replace('.wav', '_processed.wav')
            optimizer.optimize_and_save(pitched, output_file)
            
            # Verify output exists and is valid
            self.assertTrue(os.path.exists(output_file))
            
            # Verify can be loaded back
            reloaded = compat.load_audio(output_file)
            self.assertIsNotNone(reloaded)
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.unlink(test_file)
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_plugin_system(self):
        """Test plugin loading and execution"""
        plugin_mgr = plugins.PluginManager()
        
        # Create test plugin
        plugin_code = '''
class TestPlugin:
    def process(self, audio):
        return [s * 0.5 for s in audio]  # Simple gain reduction
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(plugin_code)
            plugin_file = f.name
        
        try:
            # Load plugin
            plugin_mgr.load_plugin(plugin_file)
            
            # Process audio through plugin
            signal = AudioTestUtils().generate_sine_wave(440, 0.1)
            processed = plugin_mgr.process_through_plugins(signal)
            
            # Verify processing occurred
            import math
            rms_original = math.sqrt(sum(s ** 2 for s in signal) / len(signal))
            rms_processed = math.sqrt(sum(s ** 2 for s in processed) / len(processed))
            
            self.assertAlmostEqual(rms_processed / rms_original, 0.5, places=1)
            
        finally:
            os.unlink(plugin_file)


class BenchmarkSuite:
    """Performance benchmark suite"""
    
    def __init__(self):
        self.results = []
        self.test_utils = AudioTestUtils()
    
    def run_all_benchmarks(self):
        """Run all performance benchmarks"""
        print("\n" + "="*60)
        print("CHAMELEON AUDIO SYSTEM - PERFORMANCE BENCHMARKS")
        print("="*60)
        
        self.benchmark_basic_processing()
        self.benchmark_fft_analysis()
        self.benchmark_voice_processing()
        self.benchmark_streaming()
        self.benchmark_file_operations()
        
        self.print_summary()
    
    def benchmark_basic_processing(self):
        """Benchmark basic audio processing"""
        processor = audio_processor.AudioProcessor()
        signal = self.test_utils.generate_noise(10.0)  # 10 seconds
        
        operations = [
            ('Normalize', lambda s: processor.normalize(s)),
            ('Gain +6dB', lambda s: processor.apply_gain(s, 6)),
            ('Compress', lambda s: processor.compress(s, -20, 4)),
            ('EQ 3-band', lambda s: processor.apply_eq(s, {100: -6, 1000: 0, 10000: 6})),
        ]
        
        print("\n[Basic Audio Processing]")
        for name, operation in operations:
            start = time.perf_counter()
            result = operation(signal)
            duration = time.perf_counter() - start
            
            throughput = len(signal) / duration / 44100  # x real-time
            print(f"  {name:15} {duration*1000:7.2f}ms  ({throughput:.1f}x real-time)")
            
            self.results.append({
                'category': 'Basic Processing',
                'operation': name,
                'duration_ms': duration * 1000,
                'throughput_x': throughput
            })
    
    def benchmark_fft_analysis(self):
        """Benchmark FFT analysis"""
        analyzer = fft_analysis.FFTAnalyzer()
        
        print("\n[FFT Analysis]")
        for size in [1024, 4096, 16384, 65536]:
            signal = self.test_utils.generate_noise(size / 44100)
            
            start = time.perf_counter()
            spectrum = analyzer.compute_fft(signal)
            duration = time.perf_counter() - start
            
            print(f"  FFT {size:6} pts: {duration*1000:7.2f}ms")
            
            self.results.append({
                'category': 'FFT',
                'operation': f'FFT {size}',
                'duration_ms': duration * 1000
            })
    
    def benchmark_voice_processing(self):
        """Benchmark voice processing"""
        processor = voice_processor.VoiceProcessor()
        signal = self.test_utils.generate_sine_wave(200, 5.0)  # 5 seconds
        
        operations = [
            ('Pitch Shift +3', lambda s: processor.pitch_shift(s, 3)),
            ('Formant Shift', lambda s: processor.formant_shift(s, 1.2)),
            ('Gender Change', lambda s: processor.change_gender(s, 'female')),
        ]
        
        print("\n[Voice Processing]")
        for name, operation in operations:
            start = time.perf_counter()
            result = operation(signal)
            duration = time.perf_counter() - start
            
            throughput = len(signal) / duration / 44100
            print(f"  {name:15} {duration*1000:7.2f}ms  ({throughput:.1f}x real-time)")
            
            self.results.append({
                'category': 'Voice',
                'operation': name,
                'duration_ms': duration * 1000,
                'throughput_x': throughput
            })
    
    def benchmark_streaming(self):
        """Benchmark streaming performance"""
        processor = stream_processor.StreamProcessor()
        
        print("\n[Streaming Performance]")
        
        # Measure latency
        latencies = []
        processor.start()
        
        try:
            for _ in range(100):
                chunk = self.test_utils.generate_sine_wave(440, 0.01)  # 10ms chunks
                
                start = time.perf_counter()
                processor.input_queue.put(chunk)
                result = processor.output_queue.get(timeout=0.1)
                latency = (time.perf_counter() - start) * 1000
                
                latencies.append(latency)
            
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)
            
            print(f"  Latency - Avg: {avg_latency:.2f}ms, Min: {min_latency:.2f}ms, Max: {max_latency:.2f}ms")
            
            self.results.append({
                'category': 'Streaming',
                'operation': 'Round-trip latency',
                'avg_ms': avg_latency,
                'min_ms': min_latency,
                'max_ms': max_latency
            })
            
        finally:
            processor.stop()
    
    def benchmark_file_operations(self):
        """Benchmark file I/O operations"""
        optimizer = file_optimizer.FileOptimizer()
        compat = compatibility.AudioCompatibility()
        
        print("\n[File Operations]")
        
        # Create test files of different sizes
        for seconds in [1, 10, 60]:
            signal = self.test_utils.generate_noise(seconds)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                test_file = f.name
                self.test_utils.create_test_wav(test_file, signal)
            
            try:
                # Benchmark read
                start = time.perf_counter()
                loaded = compat.load_audio(test_file)
                read_time = (time.perf_counter() - start) * 1000
                
                # Benchmark write
                output_file = test_file.replace('.wav', '_out.wav')
                start = time.perf_counter()
                optimizer.optimize_and_save(loaded, output_file)
                write_time = (time.perf_counter() - start) * 1000
                
                file_size_mb = os.path.getsize(test_file) / (1024 * 1024)
                
                print(f"  {seconds:3}s audio ({file_size_mb:.1f}MB): "
                      f"Read {read_time:6.1f}ms, Write {write_time:6.1f}ms")
                
                self.results.append({
                    'category': 'File I/O',
                    'operation': f'{seconds}s file',
                    'read_ms': read_time,
                    'write_ms': write_time,
                    'size_mb': file_size_mb
                })
                
            finally:
                os.unlink(test_file)
                if os.path.exists(output_file):
                    os.unlink(output_file)
    
    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        
        # Calculate aggregate metrics
        basic_throughput = [r['throughput_x'] for r in self.results 
                          if r.get('category') == 'Basic Processing' and 'throughput_x' in r]
        
        if basic_throughput:
            avg_throughput = sum(basic_throughput) / len(basic_throughput)
            print(f"\nAverage Processing Throughput: {avg_throughput:.1f}x real-time")
        
        streaming_results = [r for r in self.results if r.get('category') == 'Streaming']
        if streaming_results:
            avg_latency = streaming_results[0].get('avg_ms', 0)
            print(f"Average Streaming Latency: {avg_latency:.2f}ms")
        
        print(f"\nTotal Benchmarks Run: {len(self.results)}")
        print("\nPerformance Grade: ", end="")
        
        # Grade based on throughput and latency
        if avg_throughput > 50 and avg_latency < 5:
            print("A+ (Excellent)")
        elif avg_throughput > 20 and avg_latency < 10:
            print("A (Very Good)")
        elif avg_throughput > 10 and avg_latency < 20:
            print("B (Good)")
        else:
            print("C (Acceptable)")


def run_tests(category: Optional[str] = None, verbose: bool = False):
    """Run test suite"""
    
    # Create test suite
    if category:
        if category == 'unit':
            suite = unittest.TestSuite()
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAudioProcessor))
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestStreamProcessor)) 
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVoiceProcessor))
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFFTAnalysis))
        elif category == 'integration':
            suite = unittest.TestLoader().loadTestsFromTestCase(IntegrationTestSuite)
        elif category == 'performance':
            suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformanceModule)
        else:
            suite = unittest.TestSuite()
    else:
        # Load all tests
        suite = unittest.TestSuite()
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAudioProcessor))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestStreamProcessor))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVoiceProcessor))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFFTAnalysis))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPerformanceModule))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestQualityMonitor))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestErrorHandling))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(IntegrationTestSuite))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if result.testsRun > 0:
        print(f"Success Rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    else:
        print("Success Rate: N/A (no tests run)")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == 'benchmark':
            benchmark = BenchmarkSuite()
            benchmark.run_all_benchmarks()
        elif sys.argv[1] == 'coverage':
            # Run with coverage
            import coverage
            cov = coverage.Coverage()
            cov.start()
            
            success = run_tests(verbose=True)
            
            cov.stop()
            cov.save()
            
            print("\n" + "="*60)
            print("CODE COVERAGE REPORT")
            print("="*60)
            cov.report()
            
            sys.exit(0 if success else 1)
        else:
            # Run specific category
            success = run_tests(category=sys.argv[1], verbose=True)
            sys.exit(0 if success else 1)
    else:
        # Run all tests
        success = run_tests(verbose=False)
        
        if success:
            print("\n✅ All tests passed!")
        else:
            print("\n❌ Some tests failed!")
        
        sys.exit(0 if success else 1)