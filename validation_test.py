#!/usr/bin/env python3
"""
Basic validation test without external dependencies.

Exercises the *product* in the dependency-free configuration -- real
`core.analyze`/`core.trim_silence` runs and the real `SecurityValidator` --
not the environment around it. An earlier version of this file hand-parsed
WAVs and greped paths against its own pattern list: it verified `tempfile`
and `struct`, never imported a product module, and still printed "The core
Chameleon system is ready for use." A gate step that cannot fail is not a
gate. See CHARTER.md §9 (2026-09-22).
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
    """A product parser must accept the fixture we hand it"""
    print("Testing WAV file creation...")

    import core
    import security_validator

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.wav")

        # Create test file
        create_test_wav(test_file, 440.0, 1.0, 44100, 0.5)

        # Validate file exists and has reasonable size
        assert os.path.exists(test_file), "Test file was not created"
        file_size = os.path.getsize(test_file)
        assert file_size > 100, f"File too small: {file_size} bytes"

        # The product's own validators must accept what we feed it
        assert security_validator.SecurityValidator.validate_audio_content(test_file), \
            "SecurityValidator rejected a real WAV"
        info = core.WAVProcessor()._read_wav_header(test_file)
        assert info is not None, "product WAV parser rejected the fixture"
        assert info.sample_rate == 44100 and info.channels == 1 and info.bit_depth == 16, \
            f"parser read wrong format: {info.sample_rate}Hz/{info.channels}ch/{info.bit_depth}b"

        print("✓ WAV file creation test passed")

def test_basic_audio_analysis():
    """core.analyze must report the fixture's real format"""
    print("Testing basic audio analysis...")

    import core

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.wav")
        create_test_wav(test_file, 440.0, 2.0, 44100, 0.7)

        result = core.analyze(test_file)
        assert result.success, f"core.analyze failed on a valid WAV: {result.message}"
        info = result.data  # AudioInfo on success (dict only on the error path)
        assert info.channels == 1, f"Expected mono, got {info.channels} channels"
        assert info.sample_rate == 44100, f"Expected 44100Hz, got {info.sample_rate}Hz"
        assert info.bit_depth == 16, f"Expected 16-bit, got {info.bit_depth}-bit"
        assert abs(info.duration - 2.0) < 0.1, f"Expected 2s duration, got {info.duration}s"

        print("✓ Basic audio analysis test passed")

def test_file_operations():
    """The batch of fixtures must run through the product end to end"""
    print("Testing file operations...")

    import core

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

        # Every file must analyze successfully through the product
        for filepath in test_files:
            result = core.analyze(str(filepath))
            assert result.success, f"core.analyze failed on {filepath.name}: {result.message}"

        # ...and a processing op must produce a real output file
        out = test_dir / "trimmed.wav"
        trimmed = core.trim_silence(str(test_files[0]), str(out), 0.01)
        assert trimmed.success, f"core.trim_silence failed: {trimmed.message}"
        assert out.exists(), "trim_silence reported success but wrote no file"

        print("✓ File operations test passed")

def test_performance_basic():
    """The product's stdlib analysis must complete on real fixtures quickly"""
    print("Testing basic performance...")

    import core

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "read_test.wav")
        create_test_wav(test_file, 440.0, 5.0, 44100, 0.5)  # 5s file

        # Analyze it several times through the real pipeline
        start_time = time.time()
        for _ in range(5):
            result = core.analyze(test_file)
            assert result.success, f"core.analyze failed: {result.message}"
        analyze_time = time.time() - start_time

        # Generous bound: this is a smoke check, not a benchmark
        assert analyze_time < 30.0, f"Analysis too slow: {analyze_time:.2f}s"

        print(f"✓ Analyzed 5s file 5 times in {analyze_time:.3f}s")

    print("✓ Performance test passed")

def test_security_validation():
    """The real SecurityValidator must reject what it claims to reject"""
    print("Testing security validation...")

    from security_validator import SecurityValidator, SecurityConfig

    # Path-shape checks: embedded NUL is rejected by the product, not by a
    # local pattern list.
    validator = SecurityValidator()
    assert not validator.validate_path("test\x00.wav"), \
        "null-byte filename passed the product's path validation"

    with tempfile.TemporaryDirectory() as tmpdir:
        inside = Path(tmpdir) / "ok.wav"
        create_test_wav(str(inside), 440.0, 0.1, 44100, 0.5)
        outside = Path(tempfile.gettempdir()).parent / "etc_passwd_probe.wav"

        # Trusted-root containment: with a root configured, files outside it
        # are refused; files inside are accepted.
        scoped = SecurityValidator(SecurityConfig(trusted_roots={tmpdir}))
        assert scoped.validate_path(str(inside)), \
            "file inside the trusted root was rejected"
        assert not scoped.validate_path(str(outside)), \
            "file outside the trusted root was accepted"
        assert not scoped.validate_path(str(Path(tmpdir) / ".." / "escape.wav")), \
            "traversal out of the trusted root was accepted"

        # Size cap: the same file is refused under a smaller configured limit
        small_cap = SecurityValidator(SecurityConfig(max_file_size=10))
        assert not small_cap.validate_file_size(str(inside)), \
            "file over the configured size cap was accepted"
        assert validator.validate_file_size(str(inside)), \
            "file under the default size cap was rejected"

        # Content check: a script payload under a .wav name is refused
        evil = Path(tmpdir) / "evil.wav"
        evil.write_bytes(b"<?php echo 1; ?>" + b"\x00" * 32)
        assert not validator.validate_audio_content(str(evil)), \
            "script payload in a .wav passed content validation"

        # Filename scrub: shell-hostile characters are removed, not kept
        sanitized = validator.sanitize_filename('a<b>|c.wav')
        assert "<" not in sanitized and ">" not in sanitized and "|" not in sanitized, \
            f"sanitize_filename kept hostile characters: {sanitized!r}"

    print("✓ Security validation test passed")

def test_core_modules():
    """The dependency-free product modules must import in this environment"""
    print("Testing core module imports...")

    # These are the modules the zero-dependency core is made of -- if any of
    # them acquired a third-party import, the whole differentiator is gone.
    product_modules = [
        "core", "security_validator", "advanced_validation",
        "bs1770_loudness", "batch_automation", "midi_analysis",
        "ux_improvements", "personal_config", "spectral_utils", "main",
    ]
    for name in product_modules:
        try:
            __import__(name)
        except ImportError as e:
            print(f"✗ Product module {name} failed to import: {e}")
            raise

    print("✓ All dependency-free product modules import cleanly")

    # Optional extras are informational, not a check -- report what is present
    optional_modules = [
        ("numpy", "Advanced numerical processing"),
        ("scipy", "Advanced signal processing"),
        ("librosa", "Audio analysis features"),
        ("pyaudio", "Real-time audio processing"),
        ("rich", "Enhanced CLI interface"),
        ("click", "Advanced CLI features")
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
        print("  pip install numpy scipy librosa pyaudio rich click")
    else:
        print("❌ Some tests failed. Please check the implementation.")

    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
