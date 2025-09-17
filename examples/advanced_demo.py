#!/usr/bin/env python3
"""
Advanced demo showcasing complex audio processing capabilities
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import array
import math
import json
from pathlib import Path

from chameleon import AudioProcessor
from audio_effects import AudioEffects
from audio_analyzer import AudioAnalyzer
from audio_stream import AudioStream
from chameleon import BatchProcessor

def create_complex_audio():
    """Create a complex test audio with multiple frequencies"""
    print("Creating complex test audio...")
    processor = AudioProcessor()
    samples = array.array('h')

    duration = 3.0  # 3 seconds
    sample_rate = 44100
    num_samples = int(duration * sample_rate)

    for i in range(num_samples):
        t = i / sample_rate
        # Mix multiple frequencies with envelope
        envelope = math.exp(-t * 0.5)  # Decay envelope

        # Fundamental + harmonics
        signal = 0
        signal += 0.5 * math.sin(2 * math.pi * 440 * t)  # A4
        signal += 0.3 * math.sin(2 * math.pi * 880 * t)  # A5
        signal += 0.2 * math.sin(2 * math.pi * 1320 * t)  # Harmonic

        # Add some vibrato
        vibrato = math.sin(2 * math.pi * 5 * t) * 0.1
        signal *= (1 + vibrato)

        # Apply envelope and convert to int16
        sample = int(16000 * envelope * signal)
        samples.append(max(-32767, min(32767, sample)))

    processor.save_wav('complex_audio.wav', samples, sample_rate)
    print("✓ Created complex_audio.wav")
    return samples, sample_rate

def demo_real_time_analysis():
    """Demo: Real-time audio analysis"""
    print("\n" + "="*50)
    print("Demo 1: Real-time Audio Analysis")
    print("="*50)

    analyzer = AudioAnalyzer()
    processor = AudioProcessor()

    # Load or create audio
    samples, sr = create_complex_audio()

    # Analyze audio properties
    print("\nAnalyzing audio properties...")

    # Get frequency spectrum
    freqs, magnitudes = analyzer.get_frequency_spectrum(samples, sr)
    dominant_freq = analyzer.find_dominant_frequency(samples, sr)

    # Get various metrics
    rms = analyzer.get_rms(samples)
    peak = analyzer.get_peak_amplitude(samples)
    dynamic_range = analyzer.get_dynamic_range(samples)
    zcr = analyzer.get_zero_crossing_rate(samples, sr)
    spectral_centroid = analyzer.get_spectral_centroid(samples, sr)

    print(f"  Dominant Frequency: {dominant_freq:.2f} Hz")
    print(f"  RMS Level: {20 * math.log10(rms/32767):.2f} dB")
    print(f"  Peak Level: {20 * math.log10(peak/32767):.2f} dB")
    print(f"  Dynamic Range: {dynamic_range:.2f} dB")
    print(f"  Zero Crossing Rate: {zcr:.2f} Hz")
    print(f"  Spectral Centroid: {spectral_centroid:.2f} Hz")

    # Detect onset
    onset_times = analyzer.detect_onset(samples, sr)
    if onset_times:
        print(f"  Onset detected at: {onset_times[0]:.3f}s")

def demo_streaming_processing():
    """Demo: Streaming audio processing"""
    print("\n" + "="*50)
    print("Demo 2: Streaming Audio Processing")
    print("="*50)

    stream = AudioStream(buffer_size=1024)
    effects = AudioEffects()
    processor = AudioProcessor()

    # Load audio
    samples, sr = processor.load_wav('complex_audio.wav')

    print("\nProcessing audio in streaming chunks...")
    processed_chunks = []
    chunk_size = 1024

    # Process in chunks
    for i in range(0, len(samples), chunk_size):
        chunk = samples[i:i+chunk_size]

        # Apply effects to chunk
        chunk = effects.auto_gain(chunk, target_level=0.7)

        # Add to stream buffer
        stream.add_to_buffer(chunk)

        # Get processed chunk
        if stream.get_buffer_size() >= chunk_size:
            processed = stream.read_from_buffer(chunk_size)
            processed_chunks.extend(processed)

    # Save processed stream
    processor.save_wav('streamed_output.wav', array.array('h', processed_chunks), sr)
    print(f"✓ Processed {len(processed_chunks)} samples in streaming mode")
    print("✓ Saved to streamed_output.wav")

def demo_batch_processing():
    """Demo: Parallel batch processing"""
    print("\n" + "="*50)
    print("Demo 3: Parallel Batch Processing")
    print("="*50)

    # Create batch configuration
    batch_config = {
        "input_dir": ".",
        "output_dir": "./batch_output",
        "operations": [
            {"type": "normalize", "params": {"peak": 0.9}},
            {"type": "effects", "params": {"echo": True, "delay_ms": 200}},
            {"type": "compress", "params": {"threshold": 0.7, "ratio": 0.5}}
        ],
        "parallel": True,
        "num_workers": 2
    }

    # Save config
    with open('batch_config.json', 'w') as f:
        json.dump(batch_config, f, indent=2)

    print("\nBatch processing configuration:")
    print("  - Normalize to 90% peak")
    print("  - Add echo effect (200ms delay)")
    print("  - Apply compression (threshold: 0.7)")
    print("  - Parallel processing with 2 workers")

    # Create output directory
    Path("batch_output").mkdir(exist_ok=True)

    # Process batch
    batch_processor = OptimizedBatchProcessor()

    # Create some test files
    processor = AudioProcessor()
    for i in range(3):
        samples = array.array('h', [int(16000 * math.sin(2 * math.pi * (440 + i*110) * t/44100))
                                    for t in range(44100)])
        processor.save_wav(f'test_batch_{i}.wav', samples, 44100)

    print("\n✓ Created 3 test files for batch processing")
    print("✓ Batch configuration saved to batch_config.json")

def demo_adaptive_processing():
    """Demo: Adaptive audio processing based on content"""
    print("\n" + "="*50)
    print("Demo 4: Adaptive Content-Aware Processing")
    print("="*50)

    processor = AudioProcessor()
    analyzer = AudioAnalyzer()
    effects = AudioEffects()

    # Load audio
    samples, sr = processor.load_wav('complex_audio.wav')

    print("\nAnalyzing audio content for adaptive processing...")

    # Analyze audio characteristics
    rms = analyzer.get_rms(samples)
    dynamic_range = analyzer.get_dynamic_range(samples)
    dominant_freq = analyzer.find_dominant_frequency(samples, sr)

    # Adaptive processing based on analysis
    result = samples

    # If low volume, apply auto-gain
    if rms < 5000:
        print("  Low volume detected - applying auto-gain")
        result = effects.auto_gain(result, target_level=0.7)

    # If low dynamic range, apply expansion
    if dynamic_range < 20:
        print("  Low dynamic range detected - applying expansion")
        result = effects.compressor(result, threshold=0.5, ratio=0.3, attack_ms=10)

    # If high frequency content, apply subtle low-pass
    if dominant_freq > 2000:
        print("  High frequency content - applying subtle filtering")
        result = effects.low_pass_filter(result, sr, cutoff=8000)

    # Always apply noise gate for cleanup
    print("  Applying noise gate for cleanup")
    result = effects.noise_gate(result, threshold=0.02)

    processor.save_wav('adaptive_output.wav', result, sr)
    print("\n✓ Adaptive processing completed")
    print("✓ Saved to adaptive_output.wav")

def main():
    print("\n" + "="*60)
    print("   CHAMELEON AUDIO SYSTEM - ADVANCED DEMONSTRATION")
    print("="*60)

    try:
        demo_real_time_analysis()
        demo_streaming_processing()
        demo_batch_processing()
        demo_adaptive_processing()

        print("\n" + "="*60)
        print("   ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nGenerated files:")
        print("  - complex_audio.wav (source)")
        print("  - streamed_output.wav")
        print("  - adaptive_output.wav")
        print("  - batch_config.json")
        print("  - test_batch_*.wav (batch inputs)")

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()