#!/usr/bin/env python3
"""
Chameleon Audio System - Comprehensive Benchmark Suite
======================================================
Performance benchmarking for all audio processing capabilities
"""

import time
import os
import sys
import json
import random
import tempfile
import statistics
import multiprocessing
import concurrent.futures
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import struct
import wave

# Import all available Chameleon modules for benchmarking
import audio_processor
import stream_processor
import voice_processor
import audio_detector
import fft_analysis
import performance
import quality_monitor
import file_optimizer
import compatibility

# Try to import optional modules
try:
    import audio_processor_advanced
    HAS_ADVANCED_PROCESSOR = True
except ImportError:
    HAS_ADVANCED_PROCESSOR = False

try:
    import voice_processor_advanced
    HAS_ADVANCED_VOICE = True
except ImportError:
    HAS_ADVANCED_VOICE = False


class BenchmarkCategory(Enum):
    """Benchmark categories"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    MEMORY = "memory"
    QUALITY = "quality"
    SCALABILITY = "scalability"
    EFFICIENCY = "efficiency"


@dataclass
class BenchmarkResult:
    """Individual benchmark result"""
    name: str
    category: BenchmarkCategory
    value: float
    unit: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Complete benchmark report"""
    timestamp: float
    system_info: Dict[str, Any]
    results: List[BenchmarkResult]
    summary: Dict[str, Any]


class AudioGenerator:
    """Generate test audio for benchmarking"""
    
    @staticmethod
    def sine_wave(frequency: float, duration: float, sample_rate: int = 44100) -> List[float]:
        """Generate sine wave"""
        import math
        samples = []
        for i in range(int(sample_rate * duration)):
            t = i / sample_rate
            samples.append(math.sin(2 * math.pi * frequency * t))
        return samples
    
    @staticmethod
    def white_noise(duration: float, sample_rate: int = 44100) -> List[float]:
        """Generate white noise"""
        return [random.uniform(-1, 1) for _ in range(int(sample_rate * duration))]
    
    @staticmethod
    def pink_noise(duration: float, sample_rate: int = 44100) -> List[float]:
        """Generate pink noise (1/f noise)"""
        samples = []
        state = [random.random() for _ in range(7)]
        
        for _ in range(int(sample_rate * duration)):
            # Voss-McCartney algorithm
            white = random.random()
            state[0] = 0.99886 * state[0] + white * 0.0555179
            state[1] = 0.99332 * state[1] + white * 0.0750759
            state[2] = 0.96900 * state[2] + white * 0.1538520
            state[3] = 0.86650 * state[3] + white * 0.3104856
            state[4] = 0.55000 * state[4] + white * 0.5329522
            state[5] = -0.7616 * state[5] - white * 0.0168980
            pink = sum(state[:6]) + state[6] + white * 0.5362
            state[6] = white * 0.115926
            samples.append(pink / 5.0 - 0.5)
        
        return samples
    
    @staticmethod
    def complex_mix(duration: float, sample_rate: int = 44100) -> List[float]:
        """Generate complex audio mix"""
        import math
        samples = []
        
        for i in range(int(sample_rate * duration)):
            t = i / sample_rate
            # Mix multiple frequencies
            sample = (
                0.3 * math.sin(2 * math.pi * 440 * t) +  # A4
                0.2 * math.sin(2 * math.pi * 554.37 * t) +  # C#5
                0.2 * math.sin(2 * math.pi * 659.25 * t) +  # E5
                0.1 * math.sin(2 * math.pi * 880 * t) +  # A5
                0.2 * random.uniform(-0.1, 0.1)  # Some noise
            )
            samples.append(sample)
        
        return samples
    
    @staticmethod
    def save_wav(filename: str, samples: List[float], sample_rate: int = 44100):
        """Save samples to WAV file"""
        with wave.open(filename, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            
            pcm_data = []
            for sample in samples:
                pcm_value = int(max(-32768, min(32767, sample * 32767)))
                pcm_data.append(struct.pack('<h', pcm_value))
            
            wav.writeframes(b''.join(pcm_data))


class LatencyBenchmark:
    """Benchmark processing latency"""
    
    def __init__(self):
        self.generator = AudioGenerator()
        self.results = []
    
    def measure_function_latency(self, func, *args, iterations: int = 100) -> Dict[str, float]:
        """Measure function execution latency"""
        latencies = []
        
        for _ in range(iterations):
            start = time.perf_counter()
            func(*args)
            latency = (time.perf_counter() - start) * 1000  # Convert to ms
            latencies.append(latency)
        
        return {
            'min': min(latencies),
            'max': max(latencies),
            'mean': statistics.mean(latencies),
            'median': statistics.median(latencies),
            'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0,
            'p95': sorted(latencies)[int(len(latencies) * 0.95)],
            'p99': sorted(latencies)[int(len(latencies) * 0.99)]
        }
    
    def benchmark_basic_operations(self):
        """Benchmark basic audio operations"""
        print("\n[Latency - Basic Operations]")
        processor = audio_processor.AudioProcessor()
        
        # Test different buffer sizes
        for buffer_ms in [10, 50, 100, 500]:
            samples = int(44100 * buffer_ms / 1000)
            signal = self.generator.sine_wave(440, buffer_ms / 1000)
            
            # Normalize
            stats = self.measure_function_latency(processor.normalize, signal)
            print(f"  Normalize {buffer_ms:3}ms buffer: {stats['mean']:.3f}ms (σ={stats['stdev']:.3f})")
            
            self.results.append(BenchmarkResult(
                name=f"normalize_{buffer_ms}ms",
                category=BenchmarkCategory.LATENCY,
                value=stats['mean'],
                unit="ms",
                metadata=stats
            ))
    
    def benchmark_streaming_latency(self):
        """Benchmark streaming latency"""
        print("\n[Latency - Streaming]")
        processor = stream_processor.StreamProcessor()
        processor.start()
        
        try:
            # Test round-trip latency
            latencies = []
            for _ in range(100):
                chunk = self.generator.sine_wave(440, 0.01)  # 10ms chunks
                
                start = time.perf_counter()
                processor.input_queue.put(chunk)
                result = processor.output_queue.get(timeout=0.1)
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)
            
            stats = {
                'mean': statistics.mean(latencies),
                'min': min(latencies),
                'max': max(latencies),
                'p95': sorted(latencies)[95]
            }
            
            print(f"  Round-trip: {stats['mean']:.2f}ms (min={stats['min']:.2f}, p95={stats['p95']:.2f})")
            
            self.results.append(BenchmarkResult(
                name="streaming_roundtrip",
                category=BenchmarkCategory.LATENCY,
                value=stats['mean'],
                unit="ms",
                metadata=stats
            ))
            
        finally:
            processor.stop()
    
    def benchmark_complex_chain(self):
        """Benchmark complex processing chain"""
        print("\n[Latency - Complex Chain]")
        
        processor = audio_processor.AudioProcessor()
        voice = voice_processor.VoiceProcessor()
        
        signal = self.generator.complex_mix(0.1)  # 100ms
        
        def complex_chain(s):
            s = processor.normalize(s)
            s = processor.compress(s, -20, 4)
            s = processor.apply_eq(s, {100: -6, 1000: 0, 10000: 6})
            s = voice.pitch_shift(s, 2)
            return s
        
        stats = self.measure_function_latency(complex_chain, signal, iterations=50)
        
        print(f"  Full chain: {stats['mean']:.2f}ms (σ={stats['stdev']:.2f}, p99={stats['p99']:.2f})")
        
        self.results.append(BenchmarkResult(
            name="complex_chain",
            category=BenchmarkCategory.LATENCY,
            value=stats['mean'],
            unit="ms",
            metadata=stats
        ))


class ThroughputBenchmark:
    """Benchmark processing throughput"""
    
    def __init__(self):
        self.generator = AudioGenerator()
        self.results = []
    
    def benchmark_single_thread(self):
        """Benchmark single-threaded throughput"""
        print("\n[Throughput - Single Thread]")
        processor = audio_processor.AudioProcessor()
        
        # Process large audio buffer
        duration = 60  # 60 seconds of audio
        signal = self.generator.white_noise(duration)
        
        operations = [
            ('Normalize', lambda s: processor.normalize(s)),
            ('Compress', lambda s: processor.compress(s, -20, 4)),
            ('EQ', lambda s: processor.apply_eq(s, {100: -6, 1000: 0, 10000: 6})),
            ('Gain', lambda s: processor.apply_gain(s, 6)),
        ]
        
        for name, operation in operations:
            start = time.perf_counter()
            result = operation(signal)
            elapsed = time.perf_counter() - start
            
            throughput_x = duration / elapsed  # Times real-time
            samples_per_sec = len(signal) / elapsed
            
            print(f"  {name:10} {throughput_x:6.1f}x real-time ({samples_per_sec/1e6:.2f}M samples/sec)")
            
            self.results.append(BenchmarkResult(
                name=f"throughput_{name.lower()}",
                category=BenchmarkCategory.THROUGHPUT,
                value=throughput_x,
                unit="x_realtime",
                metadata={'samples_per_sec': samples_per_sec}
            ))
    
    def benchmark_parallel_processing(self):
        """Benchmark parallel processing throughput"""
        print("\n[Throughput - Parallel Processing]")
        
        processor = audio_processor.AudioProcessor()
        num_cores = multiprocessing.cpu_count()
        
        # Split audio into chunks for parallel processing
        duration = 60
        chunk_duration = duration / num_cores
        chunks = [self.generator.white_noise(chunk_duration) for _ in range(num_cores)]
        
        # Sequential processing
        start = time.perf_counter()
        for chunk in chunks:
            processor.normalize(chunk)
        sequential_time = time.perf_counter() - start
        
        # Parallel processing
        start = time.perf_counter()
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_cores) as executor:
            futures = [executor.submit(processor.normalize, chunk) for chunk in chunks]
            results = [f.result() for f in futures]
        parallel_time = time.perf_counter() - start
        
        speedup = sequential_time / parallel_time
        efficiency = speedup / num_cores * 100
        
        print(f"  Cores: {num_cores}")
        print(f"  Sequential: {sequential_time:.2f}s")
        print(f"  Parallel: {parallel_time:.2f}s")
        print(f"  Speedup: {speedup:.2f}x")
        print(f"  Efficiency: {efficiency:.1f}%")
        
        self.results.append(BenchmarkResult(
            name="parallel_speedup",
            category=BenchmarkCategory.THROUGHPUT,
            value=speedup,
            unit="x",
            metadata={
                'cores': num_cores,
                'efficiency': efficiency,
                'sequential_time': sequential_time,
                'parallel_time': parallel_time
            }
        ))
    
    def benchmark_fft_throughput(self):
        """Benchmark FFT throughput"""
        print("\n[Throughput - FFT Analysis]")
        analyzer = fft_analysis.FFTAnalyzer()
        
        fft_sizes = [512, 1024, 2048, 4096, 8192, 16384]
        
        for size in fft_sizes:
            signal = self.generator.white_noise(size / 44100)
            
            # Measure throughput
            iterations = max(10, 10000 // size)  # More iterations for smaller sizes
            start = time.perf_counter()
            
            for _ in range(iterations):
                spectrum = analyzer.compute_fft(signal)
            
            elapsed = time.perf_counter() - start
            ffts_per_sec = iterations / elapsed
            
            print(f"  FFT {size:5}: {ffts_per_sec:8.1f} ops/sec")
            
            self.results.append(BenchmarkResult(
                name=f"fft_{size}",
                category=BenchmarkCategory.THROUGHPUT,
                value=ffts_per_sec,
                unit="ops/sec",
                metadata={'fft_size': size}
            ))


class MemoryBenchmark:
    """Benchmark memory usage"""
    
    def __init__(self):
        self.generator = AudioGenerator()
        self.results = []
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def benchmark_memory_efficiency(self):
        """Benchmark memory efficiency"""
        print("\n[Memory - Efficiency]")
        import gc
        
        # Test different audio durations
        durations = [1, 10, 60, 300]  # seconds
        
        for duration in durations:
            gc.collect()
            initial_memory = self.get_memory_usage()
            
            # Load audio
            signal = self.generator.complex_mix(duration)
            loaded_memory = self.get_memory_usage()
            
            # Process audio
            processor = audio_processor.AudioProcessor()
            processed = processor.normalize(signal)
            processed = processor.compress(processed, -20, 4)
            processed_memory = self.get_memory_usage()
            
            # Calculate memory usage
            load_overhead = loaded_memory - initial_memory
            process_overhead = processed_memory - loaded_memory
            
            # Expected memory (float32 = 4 bytes per sample)
            expected_mb = (len(signal) * 4) / 1024 / 1024
            efficiency = expected_mb / load_overhead * 100 if load_overhead > 0 else 0
            
            print(f"  {duration:3}s audio: Load={load_overhead:.1f}MB, "
                  f"Process=+{process_overhead:.1f}MB, Efficiency={efficiency:.1f}%")
            
            self.results.append(BenchmarkResult(
                name=f"memory_{duration}s",
                category=BenchmarkCategory.MEMORY,
                value=load_overhead,
                unit="MB",
                metadata={
                    'duration': duration,
                    'process_overhead': process_overhead,
                    'efficiency': efficiency
                }
            ))
            
            # Cleanup
            del signal
            del processed
            gc.collect()
    
    def benchmark_streaming_memory(self):
        """Benchmark streaming memory usage"""
        print("\n[Memory - Streaming]")
        import gc
        
        processor = stream_processor.StreamProcessor()
        processor.start()
        
        try:
            gc.collect()
            initial_memory = self.get_memory_usage()
            
            # Stream 1000 chunks
            for i in range(1000):
                chunk = self.generator.sine_wave(440, 0.01)  # 10ms chunks
                processor.input_queue.put(chunk)
                
                # Consume output to prevent queue buildup
                try:
                    processor.output_queue.get_nowait()
                except:
                    pass
                
                if i % 100 == 0:
                    current_memory = self.get_memory_usage()
                    overhead = current_memory - initial_memory
                    print(f"  After {i:4} chunks: {overhead:.1f}MB overhead")
            
            final_memory = self.get_memory_usage()
            total_overhead = final_memory - initial_memory
            
            print(f"  Final overhead: {total_overhead:.1f}MB")
            
            self.results.append(BenchmarkResult(
                name="streaming_memory",
                category=BenchmarkCategory.MEMORY,
                value=total_overhead,
                unit="MB",
                metadata={'chunks': 1000}
            ))
            
        finally:
            processor.stop()


class QualityBenchmark:
    """Benchmark processing quality"""
    
    def __init__(self):
        self.generator = AudioGenerator()
        self.results = []
    
    def calculate_snr(self, original: List[float], processed: List[float]) -> float:
        """Calculate signal-to-noise ratio"""
        import math
        
        if len(original) != len(processed):
            return float('-inf')
        
        signal_power = sum(s ** 2 for s in original) / len(original)
        noise = [processed[i] - original[i] for i in range(len(original))]
        noise_power = sum(n ** 2 for n in noise) / len(noise)
        
        if noise_power == 0:
            return float('inf')
        
        return 10 * math.log10(signal_power / noise_power)
    
    def calculate_thd(self, signal: List[float], fundamental: float = 440) -> float:
        """Calculate total harmonic distortion"""
        analyzer = fft_analysis.FFTAnalyzer()
        spectrum = analyzer.compute_fft(signal)
        
        # Find fundamental bin
        bin_resolution = 44100 / len(spectrum)
        fundamental_bin = int(fundamental / bin_resolution)
        
        if fundamental_bin >= len(spectrum):
            return float('inf')
        
        fundamental_power = abs(spectrum[fundamental_bin]) ** 2
        
        # Sum harmonic powers (2nd through 10th)
        harmonic_power = 0
        for harmonic in range(2, 11):
            harmonic_bin = fundamental_bin * harmonic
            if harmonic_bin < len(spectrum):
                harmonic_power += abs(spectrum[harmonic_bin]) ** 2
        
        if fundamental_power == 0:
            return float('inf')
        
        import math
        return math.sqrt(harmonic_power / fundamental_power) * 100  # Percentage
    
    def benchmark_processing_quality(self):
        """Benchmark audio processing quality"""
        print("\n[Quality - Processing]")
        
        processor = audio_processor.AudioProcessor()
        original = self.generator.sine_wave(440, 1.0)
        
        # Test different processing
        tests = [
            ('Normalize', lambda s: processor.normalize(s)),
            ('Compress Light', lambda s: processor.compress(s, -30, 2)),
            ('Compress Heavy', lambda s: processor.compress(s, -10, 10)),
            ('EQ Subtle', lambda s: processor.apply_eq(s, {100: -3, 1000: 0, 10000: 3})),
            ('EQ Extreme', lambda s: processor.apply_eq(s, {100: -12, 1000: 6, 10000: 12})),
        ]
        
        for name, process in tests:
            processed = process(original.copy())
            
            snr = self.calculate_snr(original, processed)
            thd = self.calculate_thd(processed)
            
            quality_score = min(100, max(0, snr)) * (1 - min(thd, 10) / 10)
            
            print(f"  {name:15} SNR={snr:5.1f}dB, THD={thd:5.2f}%, Score={quality_score:5.1f}")
            
            self.results.append(BenchmarkResult(
                name=f"quality_{name.lower().replace(' ', '_')}",
                category=BenchmarkCategory.QUALITY,
                value=quality_score,
                unit="score",
                metadata={'snr': snr, 'thd': thd}
            ))
    
    def benchmark_codec_quality(self):
        """Benchmark codec quality vs compression"""
        print("\n[Quality - Compression]")
        
        # Would test advanced_codecs if available
        original = self.generator.complex_mix(1.0)
        
        # Simulate compression by quantization
        bit_depths = [16, 12, 8, 4]
        
        for bits in bit_depths:
            max_val = 2 ** (bits - 1) - 1
            quantized = [int(s * max_val) / max_val for s in original]
            
            snr = self.calculate_snr(original, quantized)
            compression_ratio = 16 / bits  # Assuming 16-bit original
            
            print(f"  {bits:2}-bit: SNR={snr:5.1f}dB, Compression={compression_ratio:.1f}x")
            
            self.results.append(BenchmarkResult(
                name=f"codec_{bits}bit",
                category=BenchmarkCategory.QUALITY,
                value=snr,
                unit="dB",
                metadata={'bits': bits, 'compression': compression_ratio}
            ))


class ScalabilityBenchmark:
    """Benchmark system scalability"""
    
    def __init__(self):
        self.generator = AudioGenerator()
        self.results = []
    
    def benchmark_channel_scaling(self):
        """Benchmark multi-channel processing"""
        print("\n[Scalability - Channels]")
        
        processor = audio_processor_advanced.AdvancedAudioProcessor()
        base_signal = self.generator.sine_wave(440, 1.0)
        
        for channels in [1, 2, 6, 8, 16, 32]:
            # Create multi-channel signal
            multi_channel = [base_signal.copy() for _ in range(channels)]
            
            start = time.perf_counter()
            
            # Process each channel
            for ch in multi_channel:
                processor.spectral_gate(ch, -40)
            
            elapsed = time.perf_counter() - start
            throughput = channels / elapsed
            
            print(f"  {channels:2} channels: {elapsed*1000:.1f}ms ({throughput:.1f} ch/sec)")
            
            self.results.append(BenchmarkResult(
                name=f"channels_{channels}",
                category=BenchmarkCategory.SCALABILITY,
                value=throughput,
                unit="channels/sec",
                metadata={'channels': channels, 'time_ms': elapsed * 1000}
            ))
    
    def benchmark_concurrent_streams(self):
        """Benchmark concurrent stream handling"""
        print("\n[Scalability - Concurrent Streams]")
        
        stream_counts = [1, 2, 4, 8, 16]
        
        for count in stream_counts:
            processors = [stream_processor.StreamProcessor() for _ in range(count)]
            
            # Start all processors
            for p in processors:
                p.start()
            
            try:
                # Send data to all streams
                start = time.perf_counter()
                
                for _ in range(100):  # 100 chunks per stream
                    chunk = self.generator.sine_wave(440, 0.01)
                    for p in processors:
                        p.input_queue.put(chunk)
                
                # Wait for processing
                for p in processors:
                    for _ in range(100):
                        try:
                            p.output_queue.get(timeout=0.1)
                        except:
                            pass
                
                elapsed = time.perf_counter() - start
                throughput = (count * 100) / elapsed  # chunks/sec
                
                print(f"  {count:2} streams: {throughput:.1f} chunks/sec")
                
                self.results.append(BenchmarkResult(
                    name=f"streams_{count}",
                    category=BenchmarkCategory.SCALABILITY,
                    value=throughput,
                    unit="chunks/sec",
                    metadata={'streams': count}
                ))
                
            finally:
                for p in processors:
                    p.stop()
    
    def benchmark_file_batch_processing(self):
        """Benchmark batch file processing"""
        print("\n[Scalability - Batch Files]")
        
        optimizer = file_optimizer.FileOptimizer()
        
        # Create test files
        file_counts = [1, 10, 50, 100]
        
        for count in file_counts:
            temp_files = []
            
            try:
                # Create temporary files
                for i in range(count):
                    signal = self.generator.sine_wave(440 + i, 0.1)  # 100ms each
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                        temp_file = f.name
                        self.generator.save_wav(temp_file, signal)
                        temp_files.append(temp_file)
                
                # Process batch
                start = time.perf_counter()
                
                for file in temp_files:
                    optimizer.optimize_file(file)
                
                elapsed = time.perf_counter() - start
                files_per_sec = count / elapsed
                
                print(f"  {count:3} files: {elapsed:.2f}s ({files_per_sec:.1f} files/sec)")
                
                self.results.append(BenchmarkResult(
                    name=f"batch_{count}",
                    category=BenchmarkCategory.SCALABILITY,
                    value=files_per_sec,
                    unit="files/sec",
                    metadata={'file_count': count}
                ))
                
            finally:
                # Cleanup
                for file in temp_files:
                    try:
                        os.unlink(file)
                    except:
                        pass


class EfficiencyBenchmark:
    """Benchmark computational efficiency"""
    
    def __init__(self):
        self.generator = AudioGenerator()
        self.results = []
    
    def benchmark_algorithm_efficiency(self):
        """Compare algorithm implementations"""
        print("\n[Efficiency - Algorithms]")
        
        signal = self.generator.white_noise(10.0)  # 10 seconds
        
        # Compare different FFT sizes for spectral analysis
        analyzer = fft_analysis.FFTAnalyzer()
        
        fft_sizes = [256, 512, 1024, 2048, 4096]
        for size in fft_sizes:
            # Take appropriate chunk
            chunk = signal[:size]
            
            start = time.perf_counter()
            for _ in range(100):
                spectrum = analyzer.compute_fft(chunk)
            elapsed = time.perf_counter() - start
            
            ops_per_sec = 100 / elapsed
            efficiency = ops_per_sec * size / 1e6  # Mega-samples/sec
            
            print(f"  FFT-{size:4}: {ops_per_sec:6.1f} ops/sec "
                  f"({efficiency:.2f} Msamples/sec)")
            
            self.results.append(BenchmarkResult(
                name=f"fft_efficiency_{size}",
                category=BenchmarkCategory.EFFICIENCY,
                value=efficiency,
                unit="Msamples/sec",
                metadata={'fft_size': size, 'ops_per_sec': ops_per_sec}
            ))
    
    def benchmark_cache_efficiency(self):
        """Benchmark cache efficiency"""
        print("\n[Efficiency - Cache]")
        
        processor = audio_processor.AudioProcessor()
        
        # Test different buffer sizes for cache efficiency
        buffer_sizes = [64, 256, 1024, 4096, 16384, 65536]
        
        for size in buffer_sizes:
            signal = self.generator.sine_wave(440, size / 44100)
            
            # Warm up cache
            processor.normalize(signal)
            
            # Measure with warm cache
            iterations = max(10, 100000 // size)
            start = time.perf_counter()
            
            for _ in range(iterations):
                processor.normalize(signal)
            
            elapsed = time.perf_counter() - start
            samples_per_sec = (size * iterations) / elapsed
            
            print(f"  Buffer {size:6}: {samples_per_sec/1e6:6.2f} Msamples/sec")
            
            self.results.append(BenchmarkResult(
                name=f"cache_{size}",
                category=BenchmarkCategory.EFFICIENCY,
                value=samples_per_sec / 1e6,
                unit="Msamples/sec",
                metadata={'buffer_size': size}
            ))


class ComprehensiveBenchmark:
    """Run all benchmarks and generate report"""
    
    def __init__(self):
        self.benchmarks = [
            LatencyBenchmark(),
            ThroughputBenchmark(),
            MemoryBenchmark(),
            QualityBenchmark(),
            ScalabilityBenchmark(),
            EfficiencyBenchmark()
        ]
        self.all_results = []
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        import platform
        import psutil
        
        return {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            'memory_gb': psutil.virtual_memory().total / (1024**3),
            'chameleon_version': '2.0.0'
        }
    
    def run_all(self):
        """Run all benchmarks"""
        print("="*70)
        print("CHAMELEON AUDIO SYSTEM - COMPREHENSIVE BENCHMARK SUITE")
        print("="*70)
        
        system_info = self.get_system_info()
        print(f"\nSystem: {system_info['platform']}")
        print(f"CPU: {system_info['cpu_count']} cores @ {system_info['cpu_freq']:.0f}MHz")
        print(f"Memory: {system_info['memory_gb']:.1f}GB")
        print(f"Python: {system_info['python_version']}")
        
        # Run each benchmark category
        for benchmark in self.benchmarks:
            if isinstance(benchmark, LatencyBenchmark):
                benchmark.benchmark_basic_operations()
                benchmark.benchmark_streaming_latency()
                benchmark.benchmark_complex_chain()
                
            elif isinstance(benchmark, ThroughputBenchmark):
                benchmark.benchmark_single_thread()
                benchmark.benchmark_fft_throughput()
                # Skip parallel for simplicity
                
            elif isinstance(benchmark, MemoryBenchmark):
                benchmark.benchmark_memory_efficiency()
                benchmark.benchmark_streaming_memory()
                
            elif isinstance(benchmark, QualityBenchmark):
                benchmark.benchmark_processing_quality()
                benchmark.benchmark_codec_quality()
                
            elif isinstance(benchmark, ScalabilityBenchmark):
                benchmark.benchmark_channel_scaling()
                benchmark.benchmark_concurrent_streams()
                
            elif isinstance(benchmark, EfficiencyBenchmark):
                benchmark.benchmark_algorithm_efficiency()
                benchmark.benchmark_cache_efficiency()
            
            # Collect results
            self.all_results.extend(benchmark.results)
        
        # Generate report
        self.generate_report(system_info)
    
    def generate_report(self, system_info: Dict[str, Any]):
        """Generate benchmark report"""
        print("\n" + "="*70)
        print("BENCHMARK SUMMARY")
        print("="*70)
        
        # Group results by category
        categories = {}
        for result in self.all_results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)
        
        # Print summary by category
        for category, results in categories.items():
            print(f"\n[{category.value.upper()}]")
            
            if category == BenchmarkCategory.LATENCY:
                latencies = [r.value for r in results if 'streaming' not in r.name]
                if latencies:
                    print(f"  Average Latency: {statistics.mean(latencies):.2f}ms")
                    print(f"  Min Latency: {min(latencies):.2f}ms")
                
            elif category == BenchmarkCategory.THROUGHPUT:
                throughputs = [r.value for r in results if r.unit == 'x_realtime']
                if throughputs:
                    print(f"  Average Throughput: {statistics.mean(throughputs):.1f}x real-time")
                    print(f"  Max Throughput: {max(throughputs):.1f}x real-time")
                
            elif category == BenchmarkCategory.QUALITY:
                scores = [r.value for r in results if r.unit == 'score']
                if scores:
                    print(f"  Average Quality Score: {statistics.mean(scores):.1f}/100")
                
            elif category == BenchmarkCategory.MEMORY:
                overheads = [r.value for r in results]
                if overheads:
                    print(f"  Average Memory Overhead: {statistics.mean(overheads):.1f}MB")
        
        # Calculate overall grade
        grade = self.calculate_grade()
        
        print("\n" + "="*70)
        print(f"OVERALL PERFORMANCE GRADE: {grade}")
        print("="*70)
        
        # Save detailed report
        self.save_json_report(system_info)
    
    def calculate_grade(self) -> str:
        """Calculate overall performance grade"""
        scores = []
        
        # Latency score (lower is better, <10ms = 100)
        latency_results = [r for r in self.all_results 
                          if r.category == BenchmarkCategory.LATENCY]
        if latency_results:
            avg_latency = statistics.mean([r.value for r in latency_results])
            latency_score = max(0, min(100, 100 * (1 - avg_latency / 50)))
            scores.append(latency_score)
        
        # Throughput score (higher is better, >50x = 100)
        throughput_results = [r for r in self.all_results 
                             if r.category == BenchmarkCategory.THROUGHPUT 
                             and r.unit == 'x_realtime']
        if throughput_results:
            avg_throughput = statistics.mean([r.value for r in throughput_results])
            throughput_score = max(0, min(100, avg_throughput * 2))
            scores.append(throughput_score)
        
        # Quality score (direct)
        quality_results = [r for r in self.all_results 
                          if r.category == BenchmarkCategory.QUALITY 
                          and r.unit == 'score']
        if quality_results:
            avg_quality = statistics.mean([r.value for r in quality_results])
            scores.append(avg_quality)
        
        # Calculate final score
        if not scores:
            return "N/A"
        
        final_score = statistics.mean(scores)
        
        if final_score >= 95:
            return "A+ (Outstanding)"
        elif final_score >= 90:
            return "A (Excellent)"
        elif final_score >= 85:
            return "A- (Very Good)"
        elif final_score >= 80:
            return "B+ (Good)"
        elif final_score >= 75:
            return "B (Above Average)"
        elif final_score >= 70:
            return "B- (Satisfactory)"
        elif final_score >= 65:
            return "C+ (Acceptable)"
        elif final_score >= 60:
            return "C (Adequate)"
        else:
            return "C- (Needs Improvement)"
    
    def save_json_report(self, system_info: Dict[str, Any]):
        """Save detailed JSON report"""
        report = BenchmarkReport(
            timestamp=time.time(),
            system_info=system_info,
            results=self.all_results,
            summary={
                'total_benchmarks': len(self.all_results),
                'grade': self.calculate_grade(),
                'categories': list(set(r.category.value for r in self.all_results))
            }
        )
        
        # Convert to JSON-serializable format
        report_dict = {
            'timestamp': report.timestamp,
            'system_info': report.system_info,
            'results': [
                {
                    'name': r.name,
                    'category': r.category.value,
                    'value': r.value,
                    'unit': r.unit,
                    'metadata': r.metadata
                }
                for r in report.results
            ],
            'summary': report.summary
        }
        
        filename = f"benchmark_report_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump(report_dict, f, indent=2)
        
        print(f"\nDetailed report saved to: {filename}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Chameleon Audio System Benchmark Suite')
    parser.add_argument('--category', choices=['latency', 'throughput', 'memory', 
                                               'quality', 'scalability', 'efficiency'],
                       help='Run specific benchmark category')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick benchmark (subset of tests)')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    
    args = parser.parse_args()
    
    if args.category:
        # Run specific category
        if args.category == 'latency':
            benchmark = LatencyBenchmark()
            benchmark.benchmark_basic_operations()
            benchmark.benchmark_streaming_latency()
        elif args.category == 'throughput':
            benchmark = ThroughputBenchmark()
            benchmark.benchmark_single_thread()
        elif args.category == 'memory':
            benchmark = MemoryBenchmark()
            benchmark.benchmark_memory_efficiency()
        elif args.category == 'quality':
            benchmark = QualityBenchmark()
            benchmark.benchmark_processing_quality()
        elif args.category == 'scalability':
            benchmark = ScalabilityBenchmark()
            benchmark.benchmark_channel_scaling()
        elif args.category == 'efficiency':
            benchmark = EfficiencyBenchmark()
            benchmark.benchmark_algorithm_efficiency()
    else:
        # Run comprehensive benchmark
        benchmark = ComprehensiveBenchmark()
        benchmark.run_all()


if __name__ == "__main__":
    main()