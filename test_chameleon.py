#!/usr/bin/env python3
"""
Simple test suite for Chameleon Voice Processor
"""

import os
import sys
import tempfile
import unittest

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (
    generate_sine_wave, write_wav_file, read_wav_file, get_system_capabilities,
    validate_audio_params, load_config, normalize_audio, trim_silence,
    generate_chord, mix_audio
)
from perf import (
    FastSineGenerator, PerformanceProfiler
)
from batch_processor import batch_generate_tones, batch_convert_files
from audio_formats import convert_audio_file, get_audio_info

class TestChameleonCore(unittest.TestCase):
    """Test core functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.wav")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
    
    def test_sine_wave_generation(self):
        """Test sine wave generation."""
        # Generate a 440Hz tone for 0.1 seconds
        audio_data = generate_sine_wave(440.0, 0.1, 44100)
        
        # Check audio data format
        self.assertEqual(len(audio_data), 4)  # (data, sample_rate, channels, sample_width)
        data, sample_rate, channels, sample_width = audio_data
        
        # Verify audio parameters
        self.assertEqual(sample_rate, 44100)
        self.assertEqual(channels, 1)
        self.assertEqual(sample_width, 2)
        
        # Data should not be empty
        self.assertGreater(len(data), 0)
    
    def test_wav_file_write_read(self):
        """Test WAV file writing and reading."""
        # Generate test audio
        audio_data = generate_sine_wave(880.0, 0.05, 44100)
        
        # Write to file
        success = write_wav_file(self.test_file, audio_data)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.test_file))
        
        # Read back
        result = read_wav_file(self.test_file)
        self.assertIsNotNone(result)
        
        read_audio, info = result
        
        # Verify audio format
        self.assertEqual(read_audio[1], 44100)  # Sample rate
        self.assertEqual(read_audio[2], 1)      # Channels
        self.assertEqual(read_audio[3], 2)      # Sample width
        
        # Verify metadata
        self.assertIn('duration', info)
        self.assertIn('size_bytes', info)  # Changed from size_mb to size_bytes
        self.assertAlmostEqual(info['duration'], 0.05, places=2)
    
    def test_invalid_file_operations(self):
        """Test error handling for invalid operations."""
        # Try to read non-existent file
        result = read_wav_file("nonexistent.wav")
        self.assertIsNone(result)
        
        # Try to write invalid audio data
        invalid_audio = (b"", 0, 0, 0)  # Invalid parameters
        success = write_wav_file(self.test_file, invalid_audio)
        self.assertFalse(success)
    
    def test_system_capabilities(self):
        """Test system capabilities detection."""
        caps = get_system_capabilities()
        
        # Should always have basic audio capability
        self.assertIn('basic_audio', caps)
        self.assertTrue(caps['basic_audio'])
        
        # Should return dict with boolean values
        for capability, available in caps.items():
            self.assertIsInstance(available, bool)

class TestChameleonPerf(unittest.TestCase):
    """Test performance monitoring."""
    
    def test_fast_sine_generator(self):
        """Test fast sine wave generation."""
        # Test that FastSineGenerator can generate audio
        audio_data = FastSineGenerator.generate(440.0, 0.1, 44100)
        self.assertIsNotNone(audio_data)
        
        # Verify audio data format
        data, sample_rate, channels, sample_width = audio_data
        self.assertEqual(sample_rate, 44100)
        self.assertEqual(channels, 1)
        self.assertEqual(sample_width, 2)

class TestChameleonIntegration(unittest.TestCase):
    """Test integration scenarios."""
    
    def test_full_audio_pipeline(self):
        """Test complete audio processing pipeline."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_file = f.name
        
        try:
            # Generate tone
            audio_data = generate_sine_wave(880.0, 0.2, 44100)  # A4 note, 0.2 seconds
            
            # Write to file
            write_success = write_wav_file(temp_file, audio_data)
            self.assertTrue(write_success)
            
            # Read back and verify
            result = read_wav_file(temp_file)
            self.assertIsNotNone(result)
            
            read_audio, info = result
            
            # Verify duration is approximately correct (0.2 seconds)
            self.assertAlmostEqual(info['duration'], 0.2, places=1)
            
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

class TestChameleonValidation(unittest.TestCase):
    """Test validation and error handling."""
    
    def test_audio_parameter_validation(self):
        """Test audio parameter validation."""
        # Valid parameters
        self.assertTrue(validate_audio_params(440.0, 1.0, 44100))
        self.assertTrue(validate_audio_params(20.0, 0.01, 8000))
        
        # Invalid frequency
        self.assertFalse(validate_audio_params(0, 1.0, 44100))
        self.assertFalse(validate_audio_params(-100, 1.0, 44100))
        self.assertFalse(validate_audio_params(50000, 1.0, 44100))
        
        # Invalid duration
        self.assertFalse(validate_audio_params(440, 0, 44100))
        self.assertFalse(validate_audio_params(440, -1, 44100))
        self.assertFalse(validate_audio_params(440, 1000, 44100))  # Too long
        
        # Invalid sample rate
        self.assertFalse(validate_audio_params(440, 1.0, 0))
        self.assertFalse(validate_audio_params(440, 1.0, -44100))
    
    def test_config_loading(self):
        """Test configuration loading."""
        config = load_config()
        
        # Should have audio configuration
        self.assertIn('sample_rate', config)
        self.assertIn('channels', config)
        
        # Values should be reasonable
        self.assertGreater(config['sample_rate'], 0)
        self.assertGreater(config['channels'], 0)

class TestChameleonPerformance(unittest.TestCase):
    """Test performance features."""
    
    def test_fast_sine_generator(self):
        """Test LUT-based fast sine generation."""
        # Generate using fast method
        fast_audio = FastSineGenerator.generate(440, 0.1, 44100)
        self.assertIsNotNone(fast_audio)
        
        # Should have same format as regular generation
        self.assertEqual(len(fast_audio), 4)
        data, sample_rate, channels, sample_width = fast_audio
        self.assertEqual(sample_rate, 44100)
        self.assertEqual(channels, 1)
        self.assertEqual(sample_width, 2)

class TestChameleonAudioProcessing(unittest.TestCase):
    """Test advanced audio processing features."""
    
    def setUp(self):
        """Set up audio processing tests."""
        self.test_audio = generate_sine_wave(440, 0.1, 44100)
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up audio processing tests."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_audio_normalization(self):
        """Test audio normalization."""
        normalized = normalize_audio(self.test_audio, target_amplitude=0.5)
        if normalized:
            self.assertEqual(len(normalized), len(self.test_audio))
    
    def test_silence_trimming(self):
        """Test silence trimming."""
        # Create audio with silence at start and end
        silence_data = bytes(1000)  # 1000 bytes of silence
        audio_with_silence = (silence_data + self.test_audio[0] + silence_data, 
                             self.test_audio[1], self.test_audio[2], self.test_audio[3])
        
        trimmed = trim_silence(audio_with_silence, threshold=0.01)
        if trimmed:
            # Trimmed audio should be shorter
            self.assertLess(len(trimmed[0]), len(audio_with_silence[0]))

    def test_error_recovery(self):
        """Test error recovery mechanisms."""
        # Test invalid operations don't crash
        try:
            # Invalid audio generation
            audio = generate_sine_wave(-1, -1, -1)  # Should handle gracefully
        except Exception as e:
            # Should not crash completely
            pass
        
        # Test invalid file operations
        result = read_wav_file("/invalid/path/file.wav")
        self.assertIsNone(result)

def run_tests():
    """Run all tests and return success status."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestChameleonCore))
    suite.addTests(loader.loadTestsFromTestCase(TestChameleonPerf))
    suite.addTests(loader.loadTestsFromTestCase(TestChameleonIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestChameleonValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestChameleonPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestChameleonAudioProcessing))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()

if __name__ == "__main__":
    print("Running Chameleon Test Suite...")
    print("=" * 50)
    
    success = run_tests()
    
    print("=" * 50)
    if success:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)