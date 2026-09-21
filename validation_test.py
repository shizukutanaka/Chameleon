#!/usr/bin/env python3
"""
Basic validation test without external dependencies.
Exercises the real Chameleon stdlib core -- imports `main`, `core`,
`security_validator`, `advanced_validation` and runs `WAVProcessor` /
`BatchProcessor` against files this script writes. A self-test that only
validates its own helpers proves nothing about the product.
"""

import os
import sys
import time
import struct
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def create_test_wav(filename: str, frequency: float = 440.0, duration: float = 1.0,
                   sample_rate: int = 44100, amplitude: float = 0.5):
    """Fixture: write a spec-valid 16-bit PCM WAV without third-party libs."""
    samples = int(duration * sample_rate)

    audio_data = []
    for i in range(samples):
        t = i / sample_rate
        sample = int(amplitude * 32767 * __import__('math').sin(2 * __import__('math').pi * frequency * t))
        audio_data.append(sample)

    with open(filename, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + samples * 2))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        f.write(struct.pack('<H', 1))   # PCM
        f.write(struct.pack('<H', 1))   # mono
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', sample_rate * 2))
        f.write(struct.pack('<H', 2))
        f.write(struct.pack('<H', 16))
        f.write(b'data')
        f.write(struct.pack('<I', samples * 2))
        for sample in audio_data:
            f.write(struct.pack('<h', sample))


def test_wav_file_creation():
    """A fixture WAV must satisfy Chameleon's own reader."""
    print("Testing WAV file creation...")

    from core import WAVProcessor

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.wav")
        create_test_wav(test_file, 440.0, 1.0, 44100, 0.5)

        result = WAVProcessor().analyze(test_file)
        assert result.success, f"Chameleon rejected its fixture WAV: {result.message}"
        info = result.data
        assert info.format_tag == 1, f"Expected PCM, got format_tag={info.format_tag}"
        assert abs(info.duration - 1.0) < 0.01

        print("✓ WAV file creation test passed")


def test_basic_audio_analysis():
    """WAVProcessor.analyze reports real header/audio facts."""
    print("Testing basic audio analysis...")

    from core import WAVProcessor

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.wav")
        create_test_wav(test_file, 440.0, 2.0, 44100, 0.7)

        result = WAVProcessor().analyze(test_file)
        assert result.success, result.message
        info = result.data
        assert info.channels == 1
        assert info.sample_rate == 44100
        assert info.bit_depth == 16
        assert abs(info.duration - 2.0) < 0.1, f"Expected 2s, got {info.duration}s"
        assert info.peak_level > 0.5, "peak level not measured"

        print("✓ Basic audio analysis test passed")


def test_file_operations():
    """BatchProcessor processes a directory of real WAVs."""
    print("Testing file operations...")

    from core import BatchProcessor

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        for i in range(3):
            create_test_wav(str(test_dir / f"test_{i}.wav"), 440.0 + i * 100, 0.5, 44100, 0.3)

        results = BatchProcessor().process_directory(str(test_dir), "analyze")
        file_results = [r for r in results if r.data is not None or r.success]
        successes = [r for r in results if r.success]
        assert len(successes) >= 3, f"Expected 3 analyzed files, got {len(successes)}: {[r.message for r in results]}"

        print("✓ File operations test passed")


def test_performance_basic():
    """The real analyze path stays fast on small files."""
    print("Testing basic performance...")

    from core import WAVProcessor

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "perf.wav")
        create_test_wav(test_file, 440.0, 5.0, 44100, 0.5)

        start = time.time()
        for _ in range(5):
            result = WAVProcessor().analyze(test_file)
            assert result.success, result.message
        elapsed = time.time() - start

        assert elapsed < 5.0, f"5 analyses took {elapsed:.2f}s"
        print(f"✓ 5 analyses of a 5s file in {elapsed:.3f}s")
        print("✓ Performance test passed")


def test_security_validation():
    """Chameleon's own SecurityValidator enforces its contract."""
    print("Testing security validation...")

    from security_validator import SecurityValidator, SecurityConfig, SecurityError

    with tempfile.TemporaryDirectory() as tmpdir:
        good = os.path.join(tmpdir, "a.wav")
        create_test_wav(good)

        # Null bytes are rejected syntactically.
        validator = SecurityValidator(SecurityConfig())
        assert not validator.validate_path("test\x00.wav"), "null-byte path accepted"
        try:
            validator.validate_file_path("test\x00.wav")
            raise AssertionError("null-byte path passed validate_file_path")
        except SecurityError:
            pass

        # Reads of nonexistent files are rejected, not silently allowed.
        try:
            validator.validate_file_path(os.path.join(tmpdir, "missing.wav"), "read")
            raise AssertionError("missing file accepted for read")
        except SecurityError:
            pass

        # Containment: with trusted roots set, files outside are rejected.
        scoped = SecurityValidator(SecurityConfig(trusted_roots={tmpdir}))
        assert scoped.validate_file_path(good, "read"), "file inside trusted root rejected"
        try:
            scoped.validate_file_path("/etc/hostname", "read")
            raise AssertionError("file outside trusted roots accepted")
        except SecurityError:
            pass

        print("✓ Security validation test passed")


def test_core_modules():
    """The real Chameleon modules must import with no third-party deps."""
    print("Testing core module imports...")

    import importlib
    for module_name in ("main", "core", "security_validator", "advanced_validation"):
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name} imported")
        except Exception as e:
            print(f"✗ {module_name} failed to import: {e}")
            return False

    # Optional modules: informational only -- the stdlib core must not need them.
    for module, description in [
        ("numpy", "Advanced numerical processing"),
        ("scipy", "Advanced signal processing"),
        ("librosa", "Audio analysis features"),
        ("pyaudio", "Real-time audio processing"),
    ]:
        try:
            __import__(module)
            print(f"✓ Optional module {module} available: {description}")
        except ImportError:
            print(f"⚠ Optional module {module} missing: {description}")

    print("✓ Core module test completed")


def run_all_tests():
    print("=" * 60)
    print("Chameleon Audio System - Basic Validation Tests")
    print("=" * 60)

    tests = [
        test_core_modules,
        test_wav_file_creation,
        test_basic_audio_analysis,
        test_file_operations,
        test_performance_basic,
        test_security_validation,
    ]

    passed = 0
    failed = 0
    start_time = time.time()

    for test_func in tests:
        try:
            print(f"\n--- {test_func.__name__} ---")
            result = test_func()
            if result is False:
                failed += 1
            else:
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
        print("  pip install -e .[audio]")
    else:
        print("❌ Some tests failed. Please check the implementation.")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
