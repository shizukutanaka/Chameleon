#!/usr/bin/env python3
"""
Simple Benchmark Tool for Chameleon Audio System
Tests performance of core audio processing functions
"""

import time
import array
import sys
import math
from typing import Dict, List

# Import modules to benchmark
import audio_processor
import voice_processor
import audio_utils

def generate_test_audio(duration: float = 1.0, sample_rate: int = 44100) -> bytes:
    """Generate test audio data"""
    samples = []
    num_samples = int(duration * sample_rate)
    
    # Generate mixed frequency signal
    for i in range(num_samples):
        t = i / sample_rate
        # Mix of 440Hz and 880Hz
        value = int(16000 * (0.5 * math.sin(2 * math.pi * 440 * t) + 
                            0.3 * math.sin(2 * math.pi * 880 * t)))
        samples.append(value)
    
    arr = array.array('h', samples)
    return arr.tobytes()


class Benchmark:
    """Simple benchmarking utility"""
    
    def __init__(self):
        self.results = {}
    
    def run_test(self, name: str, func, *args, iterations: int = 100):
        """Run a benchmark test"""
        print(f"Testing {name}...")
        
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            result = func(*args)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        self.results[name] = {
            'average': avg_time * 1000,  # Convert to ms
            'min': min_time * 1000,
            'max': max_time * 1000,
            'iterations': iterations
        }
        
        return result
    
    def benchmark_audio_processor(self):
        """Benchmark AudioProcessor"""
        processor = audio_processor.AudioProcessor()
        test_audio = generate_test_audio(0.1)  # 100ms of audio
        
        # Test basic processing
        self.run_test(
            "AudioProcessor.process (no effects)",
            processor.process,
            test_audio
        )
        
        # Test with reverb
        self.run_test(
            "AudioProcessor.process (reverb)",
            lambda: processor.process(test_audio, reverb=0.5)
        )
        
        # Test with multiple effects
        self.run_test(
            "AudioProcessor.process (multiple effects)",
            lambda: processor.process(test_audio, reverb=0.3, delay=0.1, gain=1.2)
        )
        
        # Test cache performance
        processor.clear_cache()
        
        # First run (cache miss)
        self.run_test(
            "AudioProcessor.process (cache miss)",
            lambda: processor.process(test_audio, reverb=0.5),
            iterations=10
        )
        
        # Second run (cache hit)
        self.run_test(
            "AudioProcessor.process (cache hit)",
            lambda: processor.process(test_audio, reverb=0.5),
            iterations=10
        )
        
        cache_stats = processor.get_cache_stats()
        print(f"Cache stats: {cache_stats}")
    
    def benchmark_voice_processor(self):
        """Benchmark VoiceProcessor"""
        processor = voice_processor.VoiceProcessor()
        test_audio = generate_test_audio(0.1)  # 100ms of audio
        
        # Test presets
        for preset_name in ['normal', 'male', 'female', 'robot']:
            processor.load_preset(preset_name)
            self.run_test(
                f"VoiceProcessor.process ({preset_name} preset)",
                processor.process_chunk,
                test_audio,
                iterations=50
            )
        
        # Test custom parameters
        processor.profile.pitch = 1.5
        processor.profile.formant = 0.8
        self.run_test(
            "VoiceProcessor.process (custom)",
            processor.process_chunk,
            test_audio,
            iterations=50
        )
    
    def benchmark_utility_functions(self):
        """Benchmark utility functions"""
        test_audio = generate_test_audio(0.1)
        
        # Test tone generation
        self.run_test(
            "generate_tone",
            audio_processor.generate_tone,
            440.0,
            0.1,
            iterations=50
        )
        
        # Test audio mixing
        audio2 = generate_test_audio(0.1)
        self.run_test(
            "mix_audio",
            audio_processor.mix_audio,
            test_audio,
            audio2,
            0.5,
            iterations=50
        )
        
        # Test peak detection
        self.run_test(
            "detect_peak",
            audio_processor.detect_peak,
            test_audio,
            iterations=200
        )
        
        # Test RMS calculation
        self.run_test(
            "calculate_rms",
            audio_processor.calculate_rms,
            test_audio,
            iterations=200
        )
        
        # Test fade application
        self.run_test(
            "apply_fade",
            audio_processor.apply_fade,
            test_audio,
            0.01,
            0.01,
            iterations=100
        )
    
    def print_results(self):
        """Print benchmark results"""
        print("\n" + "="*60)
        print("BENCHMARK RESULTS")
        print("="*60)
        
        for name, stats in self.results.items():
            print(f"\n{name}:")
            print(f"  Average: {stats['average']:.3f} ms")
            print(f"  Min:     {stats['min']:.3f} ms")
            print(f"  Max:     {stats['max']:.3f} ms")
            print(f"  Iterations: {stats['iterations']}")
        
        # Calculate throughput
        print("\n" + "-"*60)
        print("THROUGHPUT ANALYSIS")
        print("-"*60)
        
        for name, stats in self.results.items():
            if "process" in name.lower():
                # Assume 100ms of audio processed
                audio_duration_ms = 100
                avg_time = stats['average']
                if avg_time > 0:
                    rtf = avg_time / audio_duration_ms  # Real-Time Factor
                    print(f"{name}: RTF = {rtf:.3f} (lower is better)")
    
    def run_all(self):
        """Run all benchmarks"""
        print("Starting Chameleon Audio System Benchmark")
        print("="*60)
        
        try:
            self.benchmark_audio_processor()
            self.benchmark_voice_processor()
            self.benchmark_utility_functions()
            self.print_results()
            
            # Memory usage estimate
            import sys
            print("\n" + "-"*60)
            print("MEMORY USAGE")
            print("-"*60)
            
            # Get size of key objects
            ap = audio_processor.AudioProcessor()
            vp = voice_processor.VoiceProcessor()
            
            print(f"AudioProcessor size: ~{sys.getsizeof(ap)} bytes")
            print(f"VoiceProcessor size: ~{sys.getsizeof(vp)} bytes")
            
        except Exception as e:
            print(f"Benchmark error: {e}")
            return False
        
        return True


def main():
    """Main benchmark entry point"""
    import math
    
    benchmark = Benchmark()
    success = benchmark.run_all()
    
    if success:
        print("\nBenchmark completed successfully!")
        return 0
    else:
        print("\nBenchmark failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())