#!/usr/bin/env python3
"""
Comprehensive Test Suite for Chameleon Audio System
Tests core functionality, error handling, and performance
"""

import unittest
import tempfile
import os
import sys
import numpy as np
from pathlib import Path
import time
import wave

# Import modules to test
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import audio_processor as audio_proc
    import voice_processor as voice_proc
    import error_handler
    import audio_utils
    import config_manager
    from audio_formats import AudioFormatHandler
except ImportError as e:
    print(f"Import error: {e}")
    print("Some modules may not be available for testing")

class TestAudioProcessorOptimized(unittest.TestCase):
    """Test optimized audio processor"""
    
    def setUp(self):
        """Setup test environment"""
        self.sample_rate = 44100
        self.chunk_size = 1024
        self.processor = audio_proc.AudioProcessor(self.sample_rate, self.chunk_size)
        
        # Create test audio data
        duration = 1.0  # 1 second
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        self.test_samples = (np.sin(2 * np.pi * 440 * t) * 32767 * 0.5).astype(np.int16)
    
    def test_initialization(self):
        """Test processor initialization"""
        self.assertEqual(self.processor.sample_rate, self.sample_rate)
        self.assertEqual(self.processor.chunk_size, self.chunk_size)
        self.assertIsNotNone(self.processor.working_buffer)
        self.assertIsNotNone(self.processor._reverb_delays)
    
    def test_basic_processing(self):
        """Test basic audio processing without effects"""
        params = {'gain': 1.0}
        result = self.processor.process_audio(self.test_samples, params)
        
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(self.test_samples))
        self.assertEqual(result.dtype, np.int16)
    
    def test_gain_processing(self):
        """Test gain adjustment"""
        params = {'gain': 0.5}
        result = self.processor.process_audio(self.test_samples, params)
        
        # Result should be quieter
        self.assertLess(np.max(np.abs(result)), np.max(np.abs(self.test_samples)))
    
    def test_filter_processing(self):
        """Test filter application"""
        params = {'filter': 'lowpass', 'filter_cutoff': 0.5}
        result = self.processor.process_audio(self.test_samples, params)
        
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(self.test_samples))
    
    def test_reverb_processing(self):
        """Test reverb effect"""
        params = {'reverb': 0.3, 'room_size': 'medium'}
        result = self.processor.process_audio(self.test_samples, params)
        
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(self.test_samples))
    
    def test_delay_processing(self):
        """Test delay effect"""
        params = {'delay': 0.1, 'delay_feedback': 0.3}
        result = self.processor.process_audio(self.test_samples, params)
        
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(self.test_samples))
    
    def test_chorus_processing(self):
        """Test chorus effect"""
        params = {'chorus': 0.5}
        result = self.processor.process_audio(self.test_samples, params)
        
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(self.test_samples))
    
    def test_streaming_processing(self):
        """Test streaming processing"""
        chunk_bytes = self.test_samples[:self.chunk_size].tobytes()
        result_bytes = self.processor.process_streaming(chunk_bytes)
        
        self.assertIsInstance(result_bytes, bytes)
        self.assertGreater(len(result_bytes), 0)
    
    def test_performance_stats(self):
        """Test performance statistics"""
        stats = self.processor.get_performance_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('avg_time', stats)
        self.assertIn('real_time_factor', stats)

class TestVoiceProcessorOptimized(unittest.TestCase):
    """Test optimized voice processor"""
    
    def setUp(self):
        """Setup test environment"""
        self.sample_rate = 44100
        self.chunk_size = 1024
        self.processor = voice_proc.VoiceProcessor(self.sample_rate, self.chunk_size)
        
        # Create test audio data
        duration = 0.5  # 0.5 seconds
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        self.test_samples = (np.sin(2 * np.pi * 220 * t) * 32767 * 0.5).astype(np.int16)
        self.test_chunk_bytes = self.test_samples[:self.chunk_size].tobytes()
    
    def test_initialization(self):
        """Test processor initialization"""
        self.assertEqual(self.processor.sample_rate, self.sample_rate)
        self.assertEqual(self.processor.chunk_size, self.chunk_size)
        self.assertIsNotNone(self.processor.profile)
    
    def test_preset_loading(self):
        """Test preset loading"""
        preset_names = self.processor.get_preset_names()
        self.assertIn('normal', preset_names)
        self.assertIn('female', preset_names)
        self.assertIn('robot', preset_names)
        
        # Test loading a preset
        self.assertTrue(self.processor.load_preset('female'))
        self.assertFalse(self.processor.load_preset('nonexistent'))
    
    def test_voice_profile_setting(self):
        """Test voice profile setting"""
        profile = voice_proc.VoiceProfile(pitch=1.5, formant=1.2, speed=0.9)
        self.processor.set_profile(profile)
        
        self.assertEqual(self.processor.profile.pitch, 1.5)
        self.assertEqual(self.processor.profile.formant, 1.2)
        self.assertEqual(self.processor.profile.speed, 0.9)
    
    def test_chunk_processing(self):
        """Test chunk processing"""
        result_bytes = self.processor.process_chunk(self.test_chunk_bytes)
        
        self.assertIsInstance(result_bytes, bytes)
        self.assertEqual(len(result_bytes), len(self.test_chunk_bytes))
    
    def test_realtime_processing(self):
        """Test real-time processing"""
        result = self.processor.process_realtime(self.test_samples)
        
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), len(self.test_samples))
        self.assertEqual(result.dtype, np.int16)
    
    def test_pitch_shift_processing(self):
        """Test pitch shifting"""
        self.processor.load_preset('female')  # Higher pitch
        result = self.processor.process_realtime(self.test_samples)
        
        self.assertIsInstance(result, np.ndarray)
        # Note: Actual pitch change verification would require FFT analysis
    
    def test_batch_processing(self):
        """Test batch processing"""
        chunks = [self.test_samples[:512], self.test_samples[512:1024]]
        results = self.processor.batch_process(chunks)
        
        self.assertEqual(len(results), len(chunks))
        for result in results:
            self.assertIsInstance(result, np.ndarray)
    
    def test_custom_preset_creation(self):
        """Test custom preset creation"""
        success = self.processor.create_custom_preset('test_preset', 1.3, 1.1, 1.2, 0.2)
        self.assertTrue(success)
        
        # Test invalid parameters
        invalid = self.processor.create_custom_preset('invalid', 3.0, 1.0, 1.0, 0.0)  # pitch too high
        self.assertFalse(invalid)
    
    def test_performance_stats(self):
        """Test performance statistics"""
        # Process some chunks to generate stats
        for _ in range(5):
            self.processor.process_chunk(self.test_chunk_bytes)
        
        stats = self.processor.get_performance_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('chunks_processed', stats)
        self.assertGreater(stats['chunks_processed'], 0)

class TestErrorHandler(unittest.TestCase):
    """Test error handling and validation system"""
    
    def setUp(self):
        """Setup test environment"""
        self.error_handler = error_handler.ErrorHandler(debug_mode=True)
        self.validator = error_handler.AudioValidator(self.error_handler)
        self.monitor = error_handler.ResourceMonitor()
    
    def test_error_handling(self):
        """Test basic error handling"""
        def failing_function():
            raise ValueError("Test error")
        
        with self.assertRaises(ValueError):
            self.error_handler.handle_error(
                ValueError("Test error"),
                context={'test': 'context'},
                recovery_action=None
            )
    
    def test_error_decorator(self):
        """Test error handling decorator"""
        @self.error_handler.with_error_handling()
        def decorated_function(should_fail=False):
            if should_fail:
                raise RuntimeError("Decorated function failed")
            return "success"
        
        # Should succeed normally
        result = decorated_function(False)
        self.assertEqual(result, "success")
        
        # Should handle error
        result = decorated_function(True)
        self.assertIsNone(result)  # Returns None when error is handled
    
    def test_file_validation(self):
        """Test file validation"""
        # Test with nonexistent file
        result = self.validator.validate_file_path("/nonexistent/file.wav")
        self.assertFalse(result.is_valid)
        self.assertIn("does not exist", result.message)
        
        # Test with unsupported format
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name
        
        try:
            result = self.validator.validate_file_path(tmp_path)
            self.assertFalse(result.is_valid)
            self.assertIn("Unsupported format", result.message)
        finally:
            os.unlink(tmp_path)
    
    def test_output_path_validation(self):
        """Test output path validation"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "output.wav")
            result = self.validator.validate_output_path(output_path)
            self.assertTrue(result.is_valid)
    
    def test_audio_data_validation(self):
        """Test audio data validation"""
        # Valid data
        samples = np.random.randint(-1000, 1000, 44100, dtype=np.int16)
        result = self.validator.validate_audio_data(samples, 44100, 1)
        self.assertTrue(result.is_valid)
        
        # Empty data
        result = self.validator.validate_audio_data(np.array([]), 44100, 1)
        self.assertFalse(result.is_valid)
        self.assertIn("empty", result.message)
        
        # Invalid sample rate
        result = self.validator.validate_audio_data(samples, 5000, 1)  # Too low
        self.assertFalse(result.is_valid)
        self.assertIn("sample rate", result.message)
    
    def test_parameter_validation(self):
        """Test processing parameter validation"""
        # Valid parameters
        params = {'gain': 1.0, 'pitch': 1.2, 'reverb': 0.3}
        result = self.validator.validate_processing_parameters(params)
        self.assertTrue(result.is_valid)
        
        # Invalid pitch
        params = {'pitch': 3.0}  # Too high
        result = self.validator.validate_processing_parameters(params)
        self.assertFalse(result.is_valid)
        self.assertIn("Pitch out of range", result.message)
        
        # Non-numeric parameter
        params = {'gain': 'not_a_number'}
        result = self.validator.validate_processing_parameters(params)
        self.assertFalse(result.is_valid)
    
    def test_resource_monitoring(self):
        """Test resource monitoring"""
        # Memory check (should generally pass unless system is severely constrained)
        result = self.monitor.check_memory_usage()
        self.assertIsInstance(result.is_valid, bool)
        
        # Disk space check
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self.monitor.check_disk_space(tmp_dir, 1.0)  # 1MB required
            self.assertTrue(result.is_valid)  # Should have at least 1MB free
    
    def test_validation_decorators(self):
        """Test validation decorators"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(b"fake wav content")
            tmp_path = tmp.name
        
        try:
            @error_handler.validate_audio_file('input_file')
            def process_file(input_file):
                return "processed"
            
            # Should fail with invalid file
            with self.assertRaises(error_handler.FileValidationError):
                process_file(tmp_path)
        finally:
            os.unlink(tmp_path)

class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmarks and regression tests"""
    
    def setUp(self):
        """Setup benchmark environment"""
        self.sample_rate = 44100
        self.duration = 1.0  # 1 second of audio
        self.samples_count = int(self.sample_rate * self.duration)
        
        # Create test audio
        t = np.linspace(0, self.duration, self.samples_count)
        self.test_audio = (np.sin(2 * np.pi * 440 * t) * 32767 * 0.5).astype(np.int16)
        
        # Setup processors
        self.audio_processor = audio_proc.AudioProcessor(self.sample_rate)
        self.voice_processor = voice_proc.VoiceProcessor(self.sample_rate)
    
    def test_audio_processing_performance(self):
        """Benchmark audio processing performance"""
        params = {'gain': 0.8, 'reverb': 0.3, 'delay': 0.1}
        
        start_time = time.time()
        for _ in range(10):  # Process 10 times
            result = self.audio_processor.process_audio(self.test_audio, params)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time_per_second = total_time / 10
        real_time_factor = avg_time_per_second / self.duration
        
        print(f"Audio processing: {avg_time_per_second:.4f}s per second of audio")
        print(f"Real-time factor: {real_time_factor:.4f}")
        
        # Should be able to process faster than real-time
        self.assertLess(real_time_factor, 1.0, "Audio processing should be faster than real-time")
    
    def test_voice_processing_performance(self):
        """Benchmark voice processing performance"""
        self.voice_processor.load_preset('female')
        
        start_time = time.time()
        for _ in range(10):
            result = self.voice_processor.process_realtime(self.test_audio)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time_per_second = total_time / 10
        real_time_factor = avg_time_per_second / self.duration
        
        print(f"Voice processing: {avg_time_per_second:.4f}s per second of audio")
        print(f"Real-time factor: {real_time_factor:.4f}")
        
        # Should be able to process faster than real-time
        self.assertLess(real_time_factor, 1.0, "Voice processing should be faster than real-time")
    
    def test_chunk_processing_latency(self):
        """Test chunk processing latency for real-time use"""
        chunk_size = 1024
        chunk = self.test_audio[:chunk_size].tobytes()
        
        # Warm up
        for _ in range(5):
            self.voice_processor.process_chunk(chunk)
        
        # Measure latency
        latencies = []
        for _ in range(100):
            start_time = time.time()
            result = self.voice_processor.process_chunk(chunk)
            end_time = time.time()
            latencies.append(end_time - start_time)
        
        avg_latency = np.mean(latencies)
        max_latency = np.max(latencies)
        chunk_duration = chunk_size / self.sample_rate
        
        print(f"Average chunk latency: {avg_latency*1000:.2f}ms")
        print(f"Maximum chunk latency: {max_latency*1000:.2f}ms")
        print(f"Chunk duration: {chunk_duration*1000:.2f}ms")
        
        # Latency should be less than chunk duration for real-time processing
        self.assertLess(avg_latency, chunk_duration, 
                       "Average latency should be less than chunk duration")

class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        """Setup integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.sample_rate = 44100
        
        # Create a test WAV file
        self.test_wav_path = os.path.join(self.temp_dir, "test_input.wav")
        self.create_test_wav_file(self.test_wav_path)
    
    def tearDown(self):
        """Clean up integration test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_wav_file(self, filepath):
        """Create a test WAV file"""
        duration = 2.0  # 2 seconds
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 32767 * 0.5).astype(np.int16)
        
        with wave.open(filepath, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data.tobytes())
    
    def test_complete_voice_processing_workflow(self):
        """Test complete voice processing workflow"""
        # Validate input file
        validation = error_handler.validate_input_file(self.test_wav_path)
        self.assertTrue(validation.is_valid)
        
        # Setup output path
        output_path = os.path.join(self.temp_dir, "test_output.wav")
        validation = error_handler.validate_output_file(output_path)
        self.assertTrue(validation.is_valid)
        
        # This test demonstrates the workflow but doesn't use actual file I/O
        # since we don't have the full AudioFormatHandler implementation loaded
        print(f"Workflow test completed: {self.test_wav_path} -> {output_path}")

def run_all_tests():
    """Run all test suites"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestAudioProcessorOptimized,
        TestVoiceProcessorOptimized,
        TestErrorHandler,
        TestPerformanceBenchmarks,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*60}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)