#!/usr/bin/env python3
"""
Basic validation test without external dependencies
Tests core functionality that doesn't require numpy/scipy
"""

import os
import sys
import time
import struct
import tempfile
from pathlib import Path

def create_test_wav(filename: str, frequency: float = 440.0, duration: float = 1.0,
                   sample_rate: int = 44100, amplitude: float = 0.5):
    """Create a simple test WAV file without numpy"""
    samples = int(duration * sample_rate)

    # Generate sine wave samples
    audio_data = []
    for i in range(samples):
        t = i / sample_rate
        sample = int(amplitude * 32767 * __import__('math').sin(2 * __import__('math').pi * frequency * t))
        audio_data.append(sample)

    # Write WAV file
    with open(filename, 'wb') as f:
        # RIFF header
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + samples * 2))
        f.write(b'WAVE')

        # fmt chunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))  # Chunk size
        f.write(struct.pack('<H', 1))   # Audio format (PCM)
        f.write(struct.pack('<H', 1))   # Channels
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', sample_rate * 2))  # Byte rate
        f.write(struct.pack('<H', 2))   # Block align
        f.write(struct.pack('<H', 16))  # Bits per sample

        # data chunk
        f.write(b'data')
        f.write(struct.pack('<I', samples * 2))

        # Write audio samples
        for sample in audio_data:
            f.write(struct.pack('<h', sample))

def test_wav_file_creation():
    """Test WAV file creation and validation"""
    print("Testing WAV file creation...")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.wav")

        # Create test file
        create_test_wav(test_file, 440.0, 1.0, 44100, 0.5)

        # Validate file exists and has reasonable size
        assert os.path.exists(test_file), "Test file was not created"
        file_size = os.path.getsize(test_file)
        assert file_size > 100, f"File too small: {file_size} bytes"

        # Validate WAV header
        with open(test_file, 'rb') as f:
            header = f.read(12)
            assert header[:4] == b'RIFF', "Missing RIFF header"
            assert header[8:12] == b'WAVE', "Missing WAVE header"

        print("✓ WAV file creation test passed")

def test_basic_audio_analysis():
    """Test basic audio analysis without external libraries"""
    print("Testing basic audio analysis...")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.wav")
        create_test_wav(test_file, 440.0, 2.0, 44100, 0.7)

        # Read WAV file header
        with open(test_file, 'rb') as f:
            # Skip RIFF header
            f.seek(12)

            # Read fmt chunk
            chunk_id = f.read(4)
            assert chunk_id == b'fmt ', f"Expected fmt chunk, got {chunk_id}"

            chunk_size = struct.unpack('<I', f.read(4))[0]
            format_tag = struct.unpack('<H', f.read(2))[0]
            channels = struct.unpack('<H', f.read(2))[0]
            sample_rate = struct.unpack('<I', f.read(4))[0]
            byte_rate = struct.unpack('<I', f.read(4))[0]
            block_align = struct.unpack('<H', f.read(2))[0]
            bits_per_sample = struct.unpack('<H', f.read(2))[0]

            # Validate format
            assert format_tag == 1, f"Expected PCM format, got {format_tag}"
            assert channels == 1, f"Expected mono, got {channels} channels"
            assert sample_rate == 44100, f"Expected 44100Hz, got {sample_rate}Hz"
            assert bits_per_sample == 16, f"Expected 16-bit, got {bits_per_sample}-bit"

            # Find data chunk
            while True:
                chunk_header = f.read(8)
                if len(chunk_header) != 8:
                    break

                chunk_id = chunk_header[:4]
                chunk_size = struct.unpack('<I', chunk_header[4:8])[0]

                if chunk_id == b'data':
                    # Calculate duration
                    duration = chunk_size / (sample_rate * channels * (bits_per_sample // 8))
                    assert abs(duration - 2.0) < 0.1, f"Expected 2s duration, got {duration}s"
                    break
                else:
                    f.seek(chunk_size, 1)

        print("✓ Basic audio analysis test passed")

def test_file_operations():
    """Test file I/O operations"""
    print("Testing file operations...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test directory operations
        test_dir = Path(tmpdir)
        assert test_dir.exists(), "Temp directory not accessible"
        assert test_dir.is_dir(), "Path is not a directory"

        # Test file creation
        test_files = []
        for i in range(3):
            filename = f"test_{i}.wav"
            filepath = test_dir / filename
            create_test_wav(str(filepath), 440.0 + i * 100, 0.5, 44100, 0.3)
            test_files.append(filepath)

        # Test file listing
        wav_files = list(test_dir.glob("*.wav"))
        assert len(wav_files) == 3, f"Expected 3 WAV files, found {len(wav_files)}"

        # Test file sizes
        for filepath in test_files:
            size = filepath.stat().st_size
            assert size > 100, f"File {filepath.name} too small: {size} bytes"

        print("✓ File operations test passed")

def test_performance_basic():
    """Test basic performance without heavy computations"""
    print("Testing basic performance...")

    # Test file creation speed
    start_time = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(10):
            test_file = os.path.join(tmpdir, f"perf_test_{i}.wav")
            create_test_wav(test_file, 440.0, 0.1, 44100, 0.5)  # 0.1s files

    creation_time = time.time() - start_time

    # Should create 10 small files quickly
    assert creation_time < 5.0, f"File creation too slow: {creation_time:.2f}s"

    print(f"✓ Created 10 files in {creation_time:.3f}s")

    # Test file reading speed
    start_time = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "read_test.wav")
        create_test_wav(test_file, 440.0, 5.0, 44100, 0.5)  # 5s file

        # Read file multiple times
        for _ in range(5):
            with open(test_file, 'rb') as f:
                data = f.read()
                assert len(data) > 1000, "File data too small"

    read_time = time.time() - start_time

    print(f"✓ Read 5s file 5 times in {read_time:.3f}s")
    print("✓ Performance test passed")

def test_security_validation():
    """Exercise the real SecurityValidator -- previously this test only
    re-checked its own private pattern list and printed a verdict, so it
    could never fail."""
    print("Testing security validation...")

    from security_validator import SecurityValidator, SecurityError, SecurityConfig

    # An explicit default config keeps the checks deterministic regardless
    # of any CHAMELEON_TRUSTED_ROOTS the ambient environment may set.
    validator = SecurityValidator(SecurityConfig())

    # Inputs the validator must reject (returns False / raises
    # SecurityError rather than crashing). An overlong filename used to
    # leak a raw OSError out of every validator entry point.
    rejected = [
        ("..\\..\\windows\\system32", "backslash traversal"),
        ("test\x00.wav", "embedded NUL"),
        ("a" * 1000 + ".wav", "overlong filename"),
    ]
    for path, why in rejected:
        try:
            result = validator.validate_path(path)
        except Exception as e:
            raise AssertionError(
                f"validate_path crashed on {why}: {type(e).__name__}: {e}")
        assert result is False, f"validate_path accepted {why}: {path[:50]}"

        try:
            validator.validate_file_path(path, operation="read")
        except SecurityError:
            pass
        except Exception as e:
            raise AssertionError(
                f"validate_file_path raised {type(e).__name__} not "
                f"SecurityError on {why}: {e}")
        else:
            raise AssertionError(
                f"validate_file_path accepted {why}: {path[:50]}")
        print(f"✓ Rejected {why}: {path[:50]}...")

    # A plain in-tree name must validate (no false positives on the
    # common case).
    assert validator.validate_path("ok.wav") is True
    print("✓ Ordinary filename validates")

    # Trusted-root containment: with roots configured, a resolved path
    # outside every root is rejected even though the spelling is clean.
    with tempfile.TemporaryDirectory() as tmpdir:
        validator = SecurityValidator(SecurityConfig(trusted_roots={tmpdir}))
        inside = os.path.join(tmpdir, "inside.wav")
        assert validator.validate_path(inside) is True
        assert validator.validate_path("/etc/passwd") is False
        try:
            validator.validate_file_path("/etc/passwd", operation="read")
        except SecurityError:
            pass
        else:
            raise AssertionError("/etc/passwd accepted outside trusted root")
    print("✓ Trusted-root containment enforced")

    # File size limit: the validator's own cap, not a re-declared constant.
    import security_validator
    cap = security_validator.DEFAULT_MAX_FILE_SIZE
    with tempfile.TemporaryDirectory() as tmpdir:
        validator = SecurityValidator(SecurityConfig(max_file_size=cap))
        probe = os.path.join(tmpdir, "probe.wav")
        with open(probe, "wb") as fh:
            fh.write(b"RIFF" + b"\x00" * 32)
        assert validator.validate_file_size(probe) is True
        print(f"✓ validate_file_size honours the {cap:,}-byte cap")

    print("✓ Security validation test passed")

def test_core_modules():
    """Test that core modules can be imported"""
    print("Testing core module imports...")

    # Test basic Python modules
    try:
        import os
        import sys
        import time
        import json
        import struct
        import hashlib
        import tempfile
        import threading
        import argparse
        from pathlib import Path
        from typing import Dict, List, Optional, Any, Tuple, Union
        from dataclasses import dataclass
        from functools import lru_cache
        import logging
        print("✓ All required standard library modules available")
    except ImportError as e:
        print(f"✗ Missing standard library module: {e}")
        return False

    # Optional modules -- mirrors the [audio] extra in pyproject.toml.
    # (rich/click used to be listed here but nothing imports them; the
    # soundfile reader in main.py was missing.)
    optional_modules = [
        ("numpy", "Advanced numerical processing"),
        ("scipy", "Advanced signal processing"),
        ("librosa", "Audio analysis features"),
        ("soundfile", "Non-WAV audio file I/O"),
        ("pyaudio", "Real-time audio processing"),
    ]

    for module, description in optional_modules:
        try:
            __import__(module)
            print(f"✓ Optional module {module} available: {description}")
        except ImportError:
            print(f"⚠ Optional module {module} missing: {description}")

    print("✓ Core module test completed")

def run_all_tests():
    """Run all validation tests"""
    print("=" * 60)
    print("Chameleon Audio System - Basic Validation Tests")
    print("=" * 60)

    tests = [
        test_core_modules,
        test_wav_file_creation,
        test_basic_audio_analysis,
        test_file_operations,
        test_performance_basic,
        test_security_validation
    ]

    passed = 0
    failed = 0
    start_time = time.time()

    for test_func in tests:
        try:
            print(f"\n--- {test_func.__name__} ---")
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            failed += 1

    total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print(f"Total time: {total_time:.2f}s")
    print("=" * 60)

    if failed == 0:
        print("🎉 All basic validation tests passed!")
        print("The core Chameleon system is ready for use.")
        print("\nTo install optional dependencies for advanced features:")
        print("  pip install -e .[audio]   # numpy scipy librosa soundfile pyaudio")
    else:
        print("❌ Some tests failed. Please check the implementation.")

    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)