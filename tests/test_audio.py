#!/usr/bin/env python3
"""
Test suite for audio processing modules
"""

import array
import math
import os
import tempfile
import wave
from pathlib import Path

def create_test_wav(filepath: str, duration: float = 1.0, frequency: float = 440.0,
                    sample_rate: int = 44100) -> bool:
    """Create a test WAV file with a sine wave"""
    try:
        num_samples = int(duration * sample_rate)
        samples = array.array('h')

        for i in range(num_samples):
            t = i / sample_rate
            sample = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * t))
            samples.append(sample)

        with wave.open(filepath, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(samples.tobytes())

        return True
    except Exception as e:
        print(f"Error creating test file: {e}")
        return False

def test_basic_processing():
    """Test basic audio processing functions"""
    print("Testing basic audio processing...")

    # Import main module
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from chameleon import AudioProcessor

    # Create test file
    test_file = 'test_input.wav'
    if not create_test_wav(test_file):
        print("Failed to create test file")
        return False

    try:
        processor = AudioProcessor()

        # Test load
        samples, info = processor.load_wav(test_file)
        assert len(samples) > 0, "Failed to load samples"
        assert info['sample_rate'] == 44100, "Incorrect sample rate"
        print("✓ Load WAV")

        # Test normalize
        normalized = processor.normalize(samples)
        assert len(normalized) == len(samples), "Normalize changed length"
        print("✓ Normalize")

        # Test amplify
        amplified = processor.amplify(samples, 6.0)
        assert len(amplified) == len(samples), "Amplify changed length"
        print("✓ Amplify")

        # Test fade
        faded = processor.fade(samples, fade_in_ms=100, fade_out_ms=100)
        assert len(faded) == len(samples), "Fade changed length"
        print("✓ Fade")

        # Test trim silence
        trimmed = processor.trim_silence(samples, threshold_db=-30)
        assert len(trimmed) <= len(samples), "Trim increased length"
        print("✓ Trim silence")

        # Test reverse
        reversed_audio = processor.reverse(samples)
        assert len(reversed_audio) == len(samples), "Reverse changed length"
        print("✓ Reverse")

        # Test speed change
        faster = processor.speed_change(samples, 1.5)
        assert len(faster) < len(samples), "Speed up didn't reduce length"
        print("✓ Speed change")

        # Test save
        output_file = 'test_output.wav'
        assert processor.save_wav(output_file, normalized), "Failed to save"
        assert os.path.exists(output_file), "Output file not created"
        print("✓ Save WAV")

        # Cleanup
        os.remove(test_file)
        os.remove(output_file)

        return True

    except Exception as e:
        print(f"Test failed: {e}")
        return False

def test_effects():
    """Test audio effects"""
    print("\nTesting audio effects...")

    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from audio_effects import AudioEffects

    # Create test samples
    samples = array.array('h', [int(1000 * math.sin(i/10)) for i in range(1000)])

    try:
        effects = AudioEffects()

        # Test echo
        echoed = effects.echo(samples, delay_ms=100)
        assert len(echoed) == len(samples), "Echo changed length"
        print("✓ Echo")

        # Test chorus
        chorused = effects.chorus(samples)
        assert len(chorused) == len(samples), "Chorus changed length"
        print("✓ Chorus")

        # Test distortion
        distorted = effects.distortion(samples, drive=0.7)
        assert len(distorted) == len(samples), "Distortion changed length"
        print("✓ Distortion")

        # Test filters
        lowpassed = effects.low_pass_filter(samples, cutoff_hz=500)
        assert len(lowpassed) == len(samples), "Low-pass changed length"
        print("✓ Low-pass filter")

        highpassed = effects.high_pass_filter(samples, cutoff_hz=200)
        assert len(highpassed) == len(samples), "High-pass changed length"
        print("✓ High-pass filter")

        # Test compressor
        compressed = effects.compressor(samples)
        assert len(compressed) == len(samples), "Compressor changed length"
        print("✓ Compressor")

        # Test tremolo
        tremolo = effects.tremolo(samples)
        assert len(tremolo) == len(samples), "Tremolo changed length"
        print("✓ Tremolo")

        # Test pitch shift
        pitched = effects.pitch_shift(samples, semitones=2)
        print("✓ Pitch shift")

        # Test noise gate
        gated = effects.noise_gate(samples)
        assert len(gated) == len(samples), "Noise gate changed length"
        print("✓ Noise gate")

        # Test auto gain
        auto_gained = effects.auto_gain(samples)
        assert len(auto_gained) == len(samples), "Auto gain changed length"
        print("✓ Auto gain")

        return True

    except Exception as e:
        print(f"Effects test failed: {e}")
        return False

def test_converter():
    """Test audio converter"""
    print("\nTesting audio converter...")

    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from audio_converter import AudioConverter

    try:
        converter = AudioConverter()

        # Test resample
        samples = array.array('h', [i for i in range(1000)])
        resampled = converter.resample(samples, 44100, 22050)
        assert len(resampled) < len(samples), "Downsample didn't reduce length"
        print("✓ Resample")

        # Test channel conversion
        mono = array.array('h', [i for i in range(100)])
        stereo = converter.change_channels(mono, 1, 2)
        assert len(stereo) == len(mono) * 2, "Mono to stereo failed"
        print("✓ Channel conversion")

        # Test stereo split/merge
        left, right = converter.split_stereo(stereo)
        assert len(left) == len(mono), "Split stereo failed"

        merged = converter.merge_channels(left, right)
        assert len(merged) == len(stereo), "Merge channels failed"
        print("✓ Split/merge stereo")

        # Test silence generation
        silence = converter.create_silence(100, 44100)
        assert len(silence) == 4410, "Silence generation failed"
        assert all(s == 0 for s in silence), "Silence not silent"
        print("✓ Generate silence")

        return True

    except Exception as e:
        print(f"Converter test failed: {e}")
        return False

def test_batch_processor():
    """Test batch processor"""
    print("\nTesting batch processor...")

    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from batch_processor_optimized import OptimizedBatchProcessor

    # Create test directory
    test_dir = Path('test_batch')
    test_dir.mkdir(exist_ok=True)

    try:
        # Create test files
        for i in range(3):
            create_test_wav(str(test_dir / f'test_{i}.wav'), duration=0.5)

        processor = OptimizedBatchProcessor(num_workers=1)

        # Test directory processing
        results = processor.process_directory(
            str(test_dir),
            'echo',
            params={'delay_ms': 200}
        )

        assert len(results) == 3, "Wrong number of results"
        assert all(r['status'] == 'success' for r in results), "Some files failed"
        print("✓ Directory processing")

        # Test report generation
        report = processor.generate_report('test_report.json')
        assert report['total_files'] == 3, "Wrong file count in report"
        print("✓ Report generation")

        # Cleanup
        import shutil
        shutil.rmtree(test_dir)
        os.remove('test_report.json')

        return True

    except Exception as e:
        print(f"Batch processor test failed: {e}")
        # Cleanup on error
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir)
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("Running Chameleon Audio System Tests")
    print("=" * 50)

    results = []

    # Run test suites
    results.append(("Basic Processing", test_basic_processing()))
    results.append(("Effects", test_effects()))
    results.append(("Converter", test_converter()))
    results.append(("Batch Processor", test_batch_processor()))

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    return all(p for _, p in results)

if __name__ == '__main__':
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)