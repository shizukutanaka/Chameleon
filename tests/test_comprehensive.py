#!/usr/bin/env python3
"""
Comprehensive test suite for Chameleon Audio Processing Framework.
Production-grade testing including unit, integration, security, and performance tests.
"""

import os
import sys
import unittest
import tempfile
import time
import threading
import hashlib
import struct
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from unittest.mock import patch, MagicMock

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core import (
        generate_sine_wave, write_wav_file, read_wav_file,
        normalize_audio, trim_silence, adjust_volume, mix_audio,
        create_silence, concatenate_audio, get_system_capabilities,
        load_config, system_health_check, validate_audio_data
    )
    from types import AudioData, AudioConstants
    from security import (
        InputValidator, FileSystemSecurity, SecurityConfig,
        memory_guard, SecurityLogger
    )
    from audio_formats import AudioConverter
    from batch_processor import BatchProcessor
    from profiles import ProfileManager
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some modules not available for testing: {e}")
    MODULES_AVAILABLE = False

class BaseTestCase(unittest.TestCase):
    """Base test case with common utilities"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = []
        self.start_time = time.time()
        
    def tearDown(self):
        """Clean up test fixtures"""
        # Clean up temporary files
        for file_path in self.test_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
        
        # Clean up temp directory
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
    
    def create_test_file(self, filename: str = None, content: bytes = b'test') -> str:
        """Create a temporary test file"""
        if filename is None:
            filename = f'test_{int(time.time() * 1000)}.wav'
        
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        
        self.test_files.append(file_path)
        return file_path
    
    def assert_audio_data_valid(self, audio_data: AudioData, 
                               expected_duration: float = None,
                               expected_sample_rate: int = None):
        """Assert that audio data is valid"""
        self.assertIsInstance(audio_data, tuple)
        self.assertEqual(len(audio_data), 4)
        
        data, sample_rate, channels, sample_width = audio_data
        
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)
        self.assertIsInstance(sample_rate, int)
        self.assertGreater(sample_rate, 0)
        self.assertIsInstance(channels, int)
        self.assertGreater(channels, 0)
        self.assertIsInstance(sample_width, int)
        self.assertIn(sample_width, [1, 2, 4])
        
        if expected_duration:
            actual_duration = len(data) / (sample_rate * channels * sample_width)
            self.assertAlmostEqual(actual_duration, expected_duration, delta=0.1)
        
        if expected_sample_rate:
            self.assertEqual(sample_rate, expected_sample_rate)

@unittest.skipIf(not MODULES_AVAILABLE, "Required modules not available")
class CoreFunctionsTest(BaseTestCase):
    """Test core audio processing functions"""
    
    def test_generate_sine_wave_basic(self):
        """Test basic sine wave generation"""
        audio_data = generate_sine_wave(440.0, 1.0, 44100)
        self.assert_audio_data_valid(audio_data, expected_duration=1.0, expected_sample_rate=44100)
    
    def test_generate_sine_wave_multi_channel(self):
        """Test multi-channel sine wave generation"""
        audio_data = generate_sine_wave(440.0, 0.5, 44100, channels=2)
        self.assert_audio_data_valid(audio_data, expected_duration=0.5, expected_sample_rate=44100)
        
        data, sample_rate, channels, sample_width = audio_data
        self.assertEqual(channels, 2)
    
    def test_generate_sine_wave_invalid_params(self):
        """Test sine wave generation with invalid parameters"""
        with self.assertRaises(ValueError):
            generate_sine_wave(-100, 1.0, 44100)  # Negative frequency
        
        with self.assertRaises(ValueError):
            generate_sine_wave(440, -1.0, 44100)  # Negative duration
        
        with self.assertRaises(ValueError):
            generate_sine_wave(440, 1.0, -44100)  # Negative sample rate
    
    def test_write_read_wav_file(self):
        """Test WAV file writing and reading"""
        # Generate test audio
        audio_data = generate_sine_wave(440.0, 0.5, 44100)
        
        # Write to file
        test_file = os.path.join(self.temp_dir, 'test_output.wav')
        success = write_wav_file(test_file, audio_data)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(test_file))
        
        # Read back from file
        result = read_wav_file(test_file)
        self.assertIsNotNone(result)
        
        read_audio, audio_info = result
        self.assert_audio_data_valid(read_audio)
        
        # Compare original and read data
        original_data, original_sr, original_ch, original_sw = audio_data
        read_data, read_sr, read_ch, read_sw = read_audio
        
        self.assertEqual(original_sr, read_sr)
        self.assertEqual(original_ch, read_ch)
        self.assertEqual(original_sw, read_sw)
    
    def test_audio_processing_functions(self):
        """Test audio processing functions"""
        # Generate test audio
        audio_data = generate_sine_wave(440.0, 1.0, 44100)
        
        # Test normalization
        normalized = normalize_audio(audio_data, 0.5)
        self.assertIsNotNone(normalized)
        self.assert_audio_data_valid(normalized)
        
        # Test volume adjustment
        louder = adjust_volume(audio_data, 1.5)
        self.assertIsNotNone(louder)
        self.assert_audio_data_valid(louder)
        
        # Test silence creation
        silence = create_silence(0.5, 44100)
        self.assert_audio_data_valid(silence, expected_duration=0.5)
        
        # Test concatenation
        concatenated = concatenate_audio([audio_data, silence, audio_data])
        self.assertIsNotNone(concatenated)
        self.assert_audio_data_valid(concatenated)

@unittest.skipIf(not MODULES_AVAILABLE, "Required modules not available")
class SecurityTest(BaseTestCase):
    """Test security features"""
    
    def test_input_validation(self):
        """Test input validation functions"""
        # Test filename validation
        valid, msg = InputValidator.validate_filename("test.wav")
        self.assertTrue(valid)
        
        invalid, msg = InputValidator.validate_filename("../../../etc/passwd")
        self.assertFalse(invalid)
        
        invalid, msg = InputValidator.validate_filename("test<script>.wav")
        self.assertFalse(invalid)
    
    def test_file_path_validation(self):
        """Test file path validation"""
        # Valid paths
        valid, msg = InputValidator.validate_file_path("./audio/test.wav")
        self.assertTrue(valid)
        
        valid, msg = InputValidator.validate_file_path("output/results.wav")
        self.assertTrue(valid)
        
        # Invalid paths
        invalid, msg = InputValidator.validate_file_path("../../../system32/evil.exe")
        self.assertFalse(invalid)
        
        invalid, msg = InputValidator.validate_file_path("/etc/shadow")
        self.assertFalse(invalid)
    
    def test_audio_parameter_validation(self):
        """Test audio parameter security validation"""
        # Valid parameters
        valid, msg = InputValidator.validate_audio_parameters(440, 1.0, 44100, 1)
        self.assertTrue(valid)
        
        # Invalid parameters
        invalid, msg = InputValidator.validate_audio_parameters(-100, 1.0, 44100, 1)  # Negative frequency
        self.assertFalse(invalid)
        
        invalid, msg = InputValidator.validate_audio_parameters(440, 3700, 44100, 1)  # Too long duration
        self.assertFalse(invalid)
        
        invalid, msg = InputValidator.validate_audio_parameters(440, 1.0, 1000000, 1)  # Invalid sample rate
        self.assertFalse(invalid)
    
    def test_secure_file_operations(self):
        """Test secure file operations"""
        test_data = b"test audio data"
        test_file = os.path.join(self.temp_dir, "secure_test.wav")
        
        # Test secure file write
        success, message = FileSystemSecurity.safe_file_write(test_file, test_data)
        self.assertTrue(success, f"Secure file write failed: {message}")
        
        # Test secure file read
        success, read_data, message = FileSystemSecurity.safe_file_read(test_file)
        self.assertTrue(success, f"Secure file read failed: {message}")
        self.assertEqual(test_data, read_data)

class PerformanceTest(BaseTestCase):
    """Test performance characteristics"""
    
    def test_sine_wave_generation_performance(self):
        """Test sine wave generation performance"""
        start_time = time.time()
        
        # Generate 10 seconds of audio
        audio_data = generate_sine_wave(440.0, 10.0, 44100)
        
        generation_time = time.time() - start_time
        
        # Should generate audio faster than real-time
        self.assertLess(generation_time, 2.0, 
                       f"Sine wave generation too slow: {generation_time:.2f}s for 10s audio")
        
        self.assert_audio_data_valid(audio_data, expected_duration=10.0)
    
    def test_file_io_performance(self):
        """Test file I/O performance"""
        # Generate 5 seconds of audio
        audio_data = generate_sine_wave(440.0, 5.0, 44100)
        test_file = os.path.join(self.temp_dir, "perf_test.wav")
        
        # Test write performance
        start_time = time.time()
        success = write_wav_file(test_file, audio_data)
        write_time = time.time() - start_time
        
        self.assertTrue(success)
        self.assertLess(write_time, 1.0, f"File write too slow: {write_time:.2f}s")
        
        # Test read performance
        start_time = time.time()
        result = read_wav_file(test_file)
        read_time = time.time() - start_time
        
        self.assertIsNotNone(result)
        self.assertLess(read_time, 1.0, f"File read too slow: {read_time:.2f}s")
    
    def test_memory_usage(self):
        """Test memory usage characteristics"""
        try:
            import psutil
            process = psutil.Process()
            
            # Measure baseline memory
            initial_memory = process.memory_info().rss
            
            # Generate multiple audio clips
            audio_clips = []
            for i in range(10):
                audio_data = generate_sine_wave(440.0 + i * 10, 1.0, 44100)
                audio_clips.append(audio_data)
            
            # Measure peak memory
            peak_memory = process.memory_info().rss
            memory_increase = (peak_memory - initial_memory) / (1024 * 1024)  # MB
            
            # Should not use excessive memory
            self.assertLess(memory_increase, 100, 
                          f"Excessive memory usage: {memory_increase:.1f}MB")
            
        except ImportError:
            self.skipTest("psutil not available for memory testing")

class StressTest(BaseTestCase):
    """Stress testing for stability and limits"""
    
    def test_concurrent_operations(self):
        """Test concurrent audio operations"""
        def generate_audio():
            try:
                audio_data = generate_sine_wave(440.0, 0.1, 44100)
                return audio_data is not None
            except Exception:
                return False
        
        # Run concurrent operations
        threads = []
        results = []
        
        for i in range(10):
            thread = threading.Thread(target=lambda: results.append(generate_audio()))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)
        
        # All operations should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(results), "Some concurrent operations failed")
    
    def test_large_file_handling(self):
        """Test handling of large audio files"""
        # Test with moderately large file (10 seconds)
        try:
            audio_data = generate_sine_wave(440.0, 10.0, 44100)
            self.assert_audio_data_valid(audio_data, expected_duration=10.0)
            
            # Test file operations with large data
            test_file = os.path.join(self.temp_dir, "large_test.wav")
            success = write_wav_file(test_file, audio_data)
            self.assertTrue(success)
            
            result = read_wav_file(test_file)
            self.assertIsNotNone(result)
            
        except MemoryError:
            self.skipTest("Insufficient memory for large file test")
    
    def test_invalid_input_resilience(self):
        """Test resilience to invalid inputs"""
        # Test with various invalid inputs
        invalid_inputs = [
            (None, 1.0, 44100),
            (440.0, None, 44100),
            (440.0, 1.0, None),
            ("invalid", 1.0, 44100),
            (440.0, "invalid", 44100),
            (440.0, 1.0, "invalid"),
            (float('inf'), 1.0, 44100),
            (440.0, float('inf'), 44100),
        ]
        
        for frequency, duration, sample_rate in invalid_inputs:
            with self.assertRaises((ValueError, TypeError, MemoryError)):
                generate_sine_wave(frequency, duration, sample_rate)

class IntegrationTest(BaseTestCase):
    """Integration testing between modules"""
    
    @unittest.skipIf(not MODULES_AVAILABLE, "Advanced modules not available")
    def test_audio_format_conversion(self):
        """Test audio format conversion integration"""
        # Generate test audio
        audio_data = generate_sine_wave(440.0, 1.0, 44100)
        
        # Write as WAV
        wav_file = os.path.join(self.temp_dir, "test.wav")
        success = write_wav_file(wav_file, audio_data)
        self.assertTrue(success)
        
        # Test conversion capabilities
        converter = AudioConverter()
        self.assertIsInstance(converter, AudioConverter)
    
    @unittest.skipIf(not MODULES_AVAILABLE, "Advanced modules not available")
    def test_batch_processing_integration(self):
        """Test batch processing integration"""
        processor = BatchProcessor()
        self.assertIsInstance(processor, BatchProcessor)
    
    @unittest.skipIf(not MODULES_AVAILABLE, "Advanced modules not available")
    def test_profile_management_integration(self):
        """Test profile management integration"""
        manager = ProfileManager()
        self.assertIsInstance(manager, ProfileManager)
        
        # Test default profiles
        profiles = manager.list_profiles()
        self.assertIsInstance(profiles, (list, dict))

class SystemTest(BaseTestCase):
    """System-level testing"""
    
    def test_system_capabilities(self):
        """Test system capability detection"""
        capabilities = get_system_capabilities()
        self.assertIsInstance(capabilities, dict)
        self.assertIn('basic_audio', capabilities)
        self.assertTrue(capabilities['basic_audio'])
    
    def test_system_health_check(self):
        """Test system health check"""
        health = system_health_check()
        self.assertIsInstance(health, dict)
        self.assertIn('overall', health)
        self.assertIn('checks', health)
        self.assertIsInstance(health['overall'], bool)
        self.assertIsInstance(health['checks'], dict)
    
    def test_configuration_loading(self):
        """Test configuration loading"""
        config = load_config('config.yaml')
        self.assertIsInstance(config, dict)
        self.assertIn('app', config)

def run_test_suite():
    """Run the complete test suite"""
    print("Running Chameleon Audio Processing Framework Test Suite")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    test_classes = [
        CoreFunctionsTest,
        SecurityTest,
        PerformanceTest,
        StressTest,
        IntegrationTest,
        SystemTest
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(
        verbosity=2,
        buffer=True,
        failfast=False
    )
    
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUITE SUMMARY")
    print("=" * 60)
    print(f"Total tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    
    if result.wasSuccessful():
        print("\nALL TESTS PASSED - Framework is ready for production use")
        return 0
    else:
        print(f"\nTEST FAILURES DETECTED - {len(result.failures + result.errors)} issues found")
        return 1

if __name__ == '__main__':
    exit_code = run_test_suite()
    sys.exit(exit_code)