#!/usr/bin/env python3
"""
Basic usage examples for Chameleon Audio System
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chameleon import AudioProcessor
from audio_effects import AudioEffects
from audio_converter import AudioConverter

def example_normalize():
    """Example: Normalize audio volume"""
    print("Example 1: Normalizing audio...")
    processor = AudioProcessor()

    # Load and normalize
    samples, info = processor.load_wav('input.wav')
    normalized = processor.normalize(samples, target_peak=0.95)
    processor.save_wav('normalized.wav', normalized, info['sample_rate'])
    print("✓ Normalized audio saved to normalized.wav")

def example_add_effects():
    """Example: Add echo and chorus effects"""
    print("\nExample 2: Adding effects...")
    processor = AudioProcessor()
    effects = AudioEffects()

    # Load audio
    samples, info = processor.load_wav('input.wav')

    # Add echo
    with_echo = effects.echo(samples, info['sample_rate'], delay_ms=300, decay=0.5)

    # Add chorus
    with_chorus = effects.chorus(with_echo, info['sample_rate'], depth=0.3)

    processor.save_wav('with_effects.wav', with_chorus, info['sample_rate'])
    print("✓ Effects applied and saved to with_effects.wav")

def example_convert_format():
    """Example: Convert sample rate and channels"""
    print("\nExample 3: Format conversion...")
    processor = AudioProcessor()
    converter = AudioConverter()

    # Load audio
    samples, info = processor.load_wav('input.wav')

    # Resample to 22050 Hz
    resampled = converter.resample(samples, info['sample_rate'], 22050)

    # Convert to stereo if mono
    if info['channels'] == 1:
        stereo = converter.mono_to_stereo(resampled)
        processor.save_wav('converted.wav', stereo, 22050, channels=2)
    else:
        processor.save_wav('converted.wav', resampled, 22050)

    print("✓ Format converted and saved to converted.wav")

def example_chain_processing():
    """Example: Chain multiple operations"""
    print("\nExample 4: Processing chain...")
    processor = AudioProcessor()
    effects = AudioEffects()

    # Load audio
    samples, info = processor.load_wav('input.wav')

    # Processing chain
    result = samples
    result = processor.trim_silence(result, threshold_db=-40)
    result = processor.normalize(result)
    result = effects.compressor(result, threshold=0.7, ratio=0.5)
    result = processor.fade(result, info['sample_rate'], fade_in_ms=100, fade_out_ms=200)

    processor.save_wav('processed.wav', result, info['sample_rate'])
    print("✓ Chain processing completed and saved to processed.wav")

if __name__ == '__main__':
    print("=" * 50)
    print("Chameleon Audio System - Basic Examples")
    print("=" * 50)

    # Note: These examples assume 'input.wav' exists
    # Create a test file first if needed

    import array
    import wave
    import math

    # Create test input file
    print("\nCreating test input file...")
    samples = array.array('h')
    for i in range(44100):  # 1 second at 44.1kHz
        t = i / 44100
        sample = int(16000 * math.sin(2 * math.pi * 440 * t))  # 440 Hz sine wave
        samples.append(sample)

    with wave.open('input.wav', 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(samples.tobytes())
    print("✓ Created input.wav\n")

    try:
        example_normalize()
        example_add_effects()
        example_convert_format()
        example_chain_processing()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure 'input.wav' exists in the current directory")