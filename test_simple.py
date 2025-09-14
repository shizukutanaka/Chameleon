#!/usr/bin/env python3
"""
Simple Test Suite for Chameleon Audio System
Tests basic functionality without heavy dependencies
"""

import os
import sys
import tempfile
import unittest
import array
import math

# Test basic imports
def test_imports():
    """Test that core modules can be imported"""
    try:
        import audio_utils
        import audio_formats
        import config_manager
        import error_handler
        import performance
        print("✓ All core modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_audio_utils():
    """Test basic audio utilities"""
    try:
        import audio_utils
        
        # Test tone generation
        tone = audio_utils.generate_tone_cached(440, 0.1, 44100)
        if not tone or len(tone) == 0:
            print("✗ Tone generation failed")
            return False
        
        # Test file info
        test_file = __file__
        info = audio_utils.get_file_info(test_file)
        if not info or 'size_bytes' not in info:
            print("✗ File info failed")
            return False
        
        # Test samples conversion
        samples = [1000, -1000, 2000, -2000]
        byte_data = audio_utils.samples_to_bytes(samples)
        back_to_samples = audio_utils.bytes_to_samples(byte_data)
        if samples != back_to_samples:
            print("✗ Sample conversion failed")
            return False
        
        print("✓ Audio utilities working")
        return True
    except Exception as e:
        print(f"✗ Audio utils test failed: {e}")
        return False

def test_error_handler():
    """Test error handling system"""
    try:
        import error_handler
        
        # Test basic validation
        validator = error_handler.AudioValidator()
        
        # Test non-existent file
        result = validator.validate_file_path("nonexistent.wav")
        if result.is_valid:
            print("✗ Should reject non-existent file")
            return False
        
        # Test valid parameters
        params = {'gain': 1.0, 'pitch': 1.2}
        result = validator.validate_processing_parameters(params)
        if not result.is_valid:
            print("✗ Should accept valid parameters")
            return False
        
        # Test invalid parameters
        params = {'pitch': 5.0}  # Out of range
        result = validator.validate_processing_parameters(params)
        if result.is_valid:
            print("✗ Should reject invalid parameters")
            return False
        
        print("✓ Error handling working")
        return True
    except Exception as e:
        print(f"✗ Error handler test failed: {e}")
        return False

def test_performance():
    """Test performance monitoring"""
    try:
        import performance
        import time
        
        perf = performance.Performance()
        
        # Test timer
        perf.start_timer("test")
        time.sleep(0.01)
        elapsed = perf.end_timer("test")
        
        if elapsed <= 0:
            print("✗ Timer not working")
            return False
        
        # Test stats
        stats = perf.get_stats()
        if 'test' not in stats:
            print("✗ Stats not collected")
            return False
        
        print("✓ Performance monitoring working")
        return True
    except Exception as e:
        print(f"✗ Performance test failed: {e}")
        return False

def test_config_manager():
    """Test configuration management"""
    try:
        import config_manager
        
        # Test default config
        config = config_manager.get_config()
        if not config:
            print("✗ Cannot get default config")
            return False
        
        # Test getting values
        sample_rate = config.get('audio', 'sample_rate')
        if not sample_rate or sample_rate <= 0:
            print("✗ Invalid sample rate from config")
            return False
        
        print("✓ Configuration management working")
        return True
    except Exception as e:
        print(f"✗ Config manager test failed: {e}")
        return False

def test_audio_formats():
    """Test audio format handling"""
    try:
        import audio_formats
        
        # Test handler creation
        handler = audio_formats.AudioFormatHandler()
        if not handler:
            print("✗ Cannot create audio format handler")
            return False
        
        # Test format detection (basic)
        supported = handler.supported_formats
        if not supported or '.wav' not in supported:
            print("✗ WAV format not supported")
            return False
        
        print("✓ Audio format handler working")
        return True
    except Exception as e:
        print(f"✗ Audio format test failed: {e}")
        return False

def create_test_wav():
    """Create a simple test WAV file"""
    import wave
    
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    
    try:
        # Generate test audio
        sample_rate = 44100
        duration = 0.1  # 100ms
        samples = []
        
        for i in range(int(duration * sample_rate)):
            t = i / sample_rate
            value = int(16000 * math.sin(2 * math.pi * 440 * t))
            samples.append(value)
        
        # Write WAV file
        with wave.open(path, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            
            audio_array = array.array('h', samples)
            wav.writeframes(audio_array.tobytes())
        
        return path
    except Exception as e:
        if os.path.exists(path):
            os.remove(path)
        raise e

def test_file_operations():
    """Test actual file operations if possible"""
    try:
        import audio_formats
        
        # Create test WAV file
        test_file = create_test_wav()
        
        try:
            # Test loading
            handler = audio_formats.AudioFormatHandler()
            audio_data, metadata = handler.load_audio(test_file)
            
            if not audio_data or not metadata:
                print("✗ Cannot load test WAV file")
                return False
            
            if metadata['sample_rate'] != 44100:
                print("✗ Incorrect sample rate from test file")
                return False
            
            # Test saving
            output_file = test_file.replace('.wav', '_output.wav')
            success = handler.save_audio(audio_data, output_file, 
                                        sample_rate=metadata['sample_rate'],
                                        channels=metadata['channels'])
            
            if not success or not os.path.exists(output_file):
                print("✗ Cannot save audio file")
                return False
            
            print("✓ File operations working")
            return True
            
        finally:
            # Cleanup
            for file_path in [test_file, test_file.replace('.wav', '_output.wav')]:
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    except Exception as e:
        print(f"✗ File operations test failed: {e}")
        return False

def run_all_tests():
    """Run all simple tests"""
    print("Chameleon Audio System - Simple Test Suite")
    print("=" * 50)
    
    tests = [
        ("Module Imports", test_imports),
        ("Audio Utils", test_audio_utils),
        ("Error Handler", test_error_handler),
        ("Performance", test_performance),
        ("Config Manager", test_config_manager),
        ("Audio Formats", test_audio_formats),
        ("File Operations", test_file_operations)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests PASSED! ✓")
        return True
    else:
        print(f"System needs attention ({failed} failures)")
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)