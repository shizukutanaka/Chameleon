#!/usr/bin/env python3
"""
Performance benchmarking for Chameleon Audio System
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import array
import math
import json
from datetime import datetime
from pathlib import Path

from chameleon import AudioProcessor
from audio_effects import AudioEffects
from audio_analyzer import AudioAnalyzer
from audio_converter import AudioConverter

class Benchmark:
    def __init__(self):
        self.results = {}
        self.processor = AudioProcessor()
        self.effects = AudioEffects()
        self.analyzer = AudioAnalyzer()
        self.converter = AudioConverter()

    def create_test_samples(self, duration=1.0, sample_rate=44100):
        """Create test audio samples"""
        num_samples = int(duration * sample_rate)
        samples = array.array('h')
        for i in range(num_samples):
            t = i / sample_rate
            sample = int(16000 * math.sin(2 * math.pi * 440 * t))
            samples.append(sample)
        return samples

    def time_operation(self, func, *args, iterations=100):
        """Time an operation over multiple iterations"""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func(*args)
            end = time.perf_counter()
            times.append(end - start)

        return {
            'mean': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'total': sum(times),
            'iterations': iterations
        }

    def benchmark_basic_operations(self):
        """Benchmark basic audio operations"""
        print("\nBenchmarking Basic Operations...")
        samples = self.create_test_samples(1.0)

        operations = {
            'normalize': lambda: self.processor.normalize(samples.copy()),
            'amplify': lambda: self.processor.amplify(samples.copy(), 6),
            'fade': lambda: self.processor.fade(samples.copy(), 44100, 100, 100),
            'trim_silence': lambda: self.processor.trim_silence(samples.copy()),
            'reverse': lambda: self.processor.reverse(samples.copy()),
            'change_speed': lambda: self.processor.change_speed(samples.copy(), 1.5)
        }

        results = {}
        for name, op in operations.items():
            print(f"  Testing {name}...", end='')
            results[name] = self.time_operation(op, iterations=50)
            print(f" {results[name]['mean']*1000:.2f}ms avg")

        self.results['basic_operations'] = results

    def benchmark_effects(self):
        """Benchmark audio effects"""
        print("\nBenchmarking Audio Effects...")
        samples = self.create_test_samples(0.5)  # Shorter for effects
        sr = 44100

        effects = {
            'echo': lambda: self.effects.echo(samples.copy(), sr, 200, 0.5),
            'chorus': lambda: self.effects.chorus(samples.copy(), sr, 0.3),
            'distortion': lambda: self.effects.distortion(samples.copy(), 0.5),
            'low_pass': lambda: self.effects.low_pass_filter(samples.copy(), sr, 2000),
            'compressor': lambda: self.effects.compressor(samples.copy(), 0.7, 0.5),
            'tremolo': lambda: self.effects.tremolo(samples.copy(), sr, 5, 0.5),
            'pitch_shift': lambda: self.effects.pitch_shift(samples.copy(), 1.2),
            'noise_gate': lambda: self.effects.noise_gate(samples.copy(), 0.1),
            'auto_gain': lambda: self.effects.auto_gain(samples.copy(), 0.7)
        }

        results = {}
        for name, effect in effects.items():
            print(f"  Testing {name}...", end='')
            results[name] = self.time_operation(effect, iterations=30)
            print(f" {results[name]['mean']*1000:.2f}ms avg")

        self.results['effects'] = results

    def benchmark_analysis(self):
        """Benchmark analysis operations"""
        print("\nBenchmarking Analysis Operations...")
        samples = self.create_test_samples(1.0)
        sr = 44100

        operations = {
            'get_rms': lambda: self.analyzer.get_rms(samples),
            'get_peak': lambda: self.analyzer.get_peak_amplitude(samples),
            'dynamic_range': lambda: self.analyzer.get_dynamic_range(samples),
            'zero_crossing': lambda: self.analyzer.get_zero_crossing_rate(samples, sr),
            'dominant_freq': lambda: self.analyzer.find_dominant_frequency(samples, sr),
            'spectral_centroid': lambda: self.analyzer.get_spectral_centroid(samples, sr),
            'detect_onset': lambda: self.analyzer.detect_onset(samples, sr)
        }

        results = {}
        for name, op in operations.items():
            print(f"  Testing {name}...", end='')
            results[name] = self.time_operation(op, iterations=50)
            print(f" {results[name]['mean']*1000:.2f}ms avg")

        self.results['analysis'] = results

    def benchmark_optimization(self):
        """Test numpy optimization if available"""
        print("\nChecking optimization status...")

        try:
            import numpy as np
            print("  NumPy available: Yes")

            # Test with numpy optimization
            samples = self.create_test_samples(2.0)
            result = self.time_operation(
                lambda: self.processor.normalize(samples.copy()),
                iterations=50
            )
            print(f"  Processing speed: {result['mean']*1000:.2f}ms avg")

            self.results['optimization'] = {
                'numpy_available': True,
                'normalize_time': result
            }
        except ImportError:
            print("  NumPy available: No (install numpy for better performance)")
            self.results['optimization'] = {
                'numpy_available': False
            }

    def benchmark_file_io(self):
        """Benchmark file I/O operations"""
        print("\nBenchmarking File I/O...")
        samples = self.create_test_samples(1.0)
        test_file = 'benchmark_test.wav'

        # Write benchmark
        write_time = self.time_operation(
            lambda: self.processor.save_wav(test_file, samples, 44100),
            iterations=20
        )

        # Read benchmark
        read_time = self.time_operation(
            lambda: self.processor.load_wav(test_file),
            iterations=20
        )

        # Clean up
        Path(test_file).unlink(missing_ok=True)

        print(f"  Write: {write_time['mean']*1000:.2f}ms avg")
        print(f"  Read: {read_time['mean']*1000:.2f}ms avg")

        self.results['file_io'] = {
            'write': write_time,
            'read': read_time
        }

    def generate_report(self):
        """Generate benchmark report"""
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)

        # Calculate totals
        total_ops = 0
        total_time = 0

        for category, ops in self.results.items():
            if isinstance(ops, dict):
                for op_name, timing in ops.items():
                    if isinstance(timing, dict) and 'iterations' in timing:
                        total_ops += timing['iterations']
                        total_time += timing['total']

        # Performance metrics
        print(f"\nTotal Operations: {total_ops}")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Operations/Second: {total_ops/total_time:.0f}")

        # Find fastest/slowest
        all_ops = []
        for category, ops in self.results.items():
            if isinstance(ops, dict):
                for op_name, timing in ops.items():
                    if isinstance(timing, dict) and 'mean' in timing:
                        all_ops.append((f"{category}/{op_name}", timing['mean']))

        all_ops.sort(key=lambda x: x[1])

        print("\nFastest Operations:")
        for name, time_ms in all_ops[:5]:
            print(f"  {name}: {time_ms*1000:.3f}ms")

        print("\nSlowest Operations:")
        for name, time_ms in all_ops[-5:]:
            print(f"  {name}: {time_ms*1000:.3f}ms")

        # Save detailed report
        report = {
            'timestamp': datetime.now().isoformat(),
            'system': {
                'python_version': sys.version,
                'platform': sys.platform
            },
            'results': self.results,
            'summary': {
                'total_operations': total_ops,
                'total_time': total_time,
                'ops_per_second': total_ops/total_time if total_time > 0 else 0
            }
        }

        with open('benchmark_report.json', 'w') as f:
            json.dump(report, f, indent=2)

        print("\n✓ Detailed report saved to benchmark_report.json")

    def run_all(self):
        """Run all benchmarks"""
        print("\n" + "="*60)
        print("CHAMELEON AUDIO SYSTEM - PERFORMANCE BENCHMARK")
        print("="*60)

        start_time = time.time()

        self.benchmark_basic_operations()
        self.benchmark_effects()
        self.benchmark_analysis()
        self.benchmark_optimization()
        self.benchmark_file_io()

        total_time = time.time() - start_time

        self.generate_report()

        print(f"\nBenchmark completed in {total_time:.2f}s")
        print("="*60)

def main():
    benchmark = Benchmark()
    benchmark.run_all()

if __name__ == '__main__':
    main()