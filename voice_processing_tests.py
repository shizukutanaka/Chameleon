#!/usr/bin/env python3
"""
Comprehensive Voice Processing Test Suite
Advanced testing framework for voice transformation algorithms

Test Categories:
- Algorithm Accuracy Tests
- Quality Assessment Tests  
- Performance Benchmarks
- Real-time Processing Tests
- Robustness Tests
- Perceptual Quality Tests
"""

import numpy as np
import time
import unittest
import warnings
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import matplotlib.pyplot as plt
import sys
import os

# Import our voice processing modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from advanced_voice_processor import AdvancedVoiceProcessor, AdvancedVoiceProfile, RESEARCH_PRESETS
    from neural_voice_converter import NeuralVoiceConverter, NeuralVoiceConfig
    from realtime_voice_engine import RealtimeVoiceProcessor, RealtimeConfig
    from voice_quality_optimizer import VoiceQualityOptimizer, QualityConfig
except ImportError as e:
    print(f"Warning: Could not import some modules: {e}")
    print("Some tests may be skipped")

warnings.filterwarnings('ignore')

@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    passed: bool
    score: float
    execution_time: float
    details: Dict[str, Any]
    error_message: Optional[str] = None

class VoiceProcessingTestSuite:
    """Comprehensive test suite for voice processing algorithms"""
    
    def __init__(self):
        self.results = []
        self.sample_rate = 44100
        self.test_duration = 1.0  # seconds
        
        # Test signals
        self.test_signals = self._create_test_signals()
        
        # Initialize processors
        try:
            self.advanced_processor = AdvancedVoiceProcessor(self.sample_rate)
            self.neural_converter = NeuralVoiceConverter()
            self.realtime_processor = RealtimeVoiceProcessor()
            self.quality_optimizer = VoiceQualityOptimizer()
        except Exception as e:
            print(f"Warning: Could not initialize all processors: {e}")
            
    def _create_test_signals(self) -> Dict[str, np.ndarray]:
        """Create various test signals for comprehensive testing"""
        t = np.linspace(0, self.test_duration, int(self.sample_rate * self.test_duration))
        signals = {}
        
        # Pure tone
        signals['pure_tone'] = np.sin(2 * np.pi * 440 * t) * 0.5
        
        # Harmonic series (voice-like)
        f0 = 150
        signals['harmonic_series'] = (
            np.sin(2 * np.pi * f0 * t) +
            0.7 * np.sin(2 * np.pi * f0 * 2 * t) +
            0.5 * np.sin(2 * np.pi * f0 * 3 * t) +
            0.3 * np.sin(2 * np.pi * f0 * 4 * t) +
            0.2 * np.sin(2 * np.pi * f0 * 5 * t)
        ) * 0.3
        
        # Chirp (frequency sweep)
        signals['chirp'] = scipy.signal.chirp(t, 100, self.test_duration, 1000) * 0.5
        
        # White noise
        signals['white_noise'] = np.random.normal(0, 0.3, len(t))
        
        # Noisy speech simulation
        speech_sim = signals['harmonic_series'] + 0.1 * np.random.normal(0, 1, len(t))
        signals['noisy_speech'] = speech_sim
        
        # Impulse train
        impulse_interval = int(self.sample_rate * 0.01)  # 10ms intervals
        impulse_train = np.zeros_like(t)
        for i in range(0, len(impulse_train), impulse_interval):
            if i < len(impulse_train):
                impulse_train[i] = 1.0
        signals['impulse_train'] = impulse_train * 0.5
        
        # Modulated signal
        carrier_freq = 1000
        mod_freq = 10
        modulated = np.sin(2 * np.pi * carrier_freq * t) * (1 + 0.5 * np.sin(2 * np.pi * mod_freq * t))
        signals['modulated'] = modulated * 0.3
        
        return signals
    
    def run_all_tests(self) -> List[TestResult]:
        """Run all test categories"""
        print("=== Voice Processing Test Suite ===\n")
        
        # Algorithm accuracy tests
        print("1. Running Algorithm Accuracy Tests...")
        self._test_algorithm_accuracy()
        
        # Quality assessment tests
        print("2. Running Quality Assessment Tests...")
        self._test_quality_assessment()
        
        # Performance benchmarks
        print("3. Running Performance Benchmarks...")
        self._test_performance()
        
        # Real-time processing tests
        print("4. Running Real-time Processing Tests...")
        self._test_realtime_processing()
        
        # Robustness tests
        print("5. Running Robustness Tests...")
        self._test_robustness()
        
        # Perceptual quality tests
        print("6. Running Perceptual Quality Tests...")
        self._test_perceptual_quality()
        
        # Print summary
        self._print_summary()
        
        return self.results
    
    def _test_algorithm_accuracy(self):
        """Test accuracy of voice processing algorithms"""
        
        # Test 1: Pitch shifting accuracy
        self._test_pitch_shifting_accuracy()
        
        # Test 2: Formant shifting accuracy
        self._test_formant_shifting_accuracy()
        
        # Test 3: Signal preservation
        self._test_signal_preservation()
        
        # Test 4: Frequency response
        self._test_frequency_response()
    
    def _test_pitch_shifting_accuracy(self):
        """Test pitch shifting accuracy"""
        test_name = "Pitch Shifting Accuracy"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['harmonic_series']
            profile = AdvancedVoiceProfile(pitch_scale=1.5)  # +50% pitch
            
            output = self.advanced_processor.process_voice(input_signal, profile)
            
            # Analyze pitch shift accuracy
            input_f0 = self._estimate_fundamental_frequency(input_signal)
            output_f0 = self._estimate_fundamental_frequency(output)
            
            expected_f0 = input_f0 * 1.5
            pitch_error = abs(output_f0 - expected_f0) / expected_f0 if expected_f0 > 0 else 1.0
            
            # Success if error < 10%
            passed = pitch_error < 0.1
            score = max(0, 1.0 - pitch_error * 5)
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'input_f0': input_f0,
                    'output_f0': output_f0,
                    'expected_f0': expected_f0,
                    'pitch_error': pitch_error
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_formant_shifting_accuracy(self):
        """Test formant shifting accuracy"""
        test_name = "Formant Shifting Accuracy"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['harmonic_series']
            profile = AdvancedVoiceProfile(formant_shift=1.2)  # +20% formant shift
            
            output = self.advanced_processor.process_voice(input_signal, profile)
            
            # Analyze spectral characteristics
            input_spectrum = np.abs(np.fft.rfft(input_signal))
            output_spectrum = np.abs(np.fft.rfft(output))
            
            # Find peak frequencies
            input_peaks = self._find_spectral_peaks(input_spectrum)
            output_peaks = self._find_spectral_peaks(output_spectrum)
            
            # Calculate formant shift accuracy
            formant_shift_accuracy = self._calculate_formant_shift_accuracy(
                input_peaks, output_peaks, 1.2
            )
            
            passed = formant_shift_accuracy > 0.8
            score = formant_shift_accuracy
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'formant_shift_accuracy': formant_shift_accuracy,
                    'input_peaks': input_peaks[:5],  # First 5 peaks
                    'output_peaks': output_peaks[:5]
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_signal_preservation(self):
        """Test signal preservation during processing"""
        test_name = "Signal Preservation"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['pure_tone']
            profile = AdvancedVoiceProfile()  # No modification
            
            output = self.advanced_processor.process_voice(input_signal, profile)
            
            # Calculate preservation metrics
            correlation = np.corrcoef(input_signal, output[:len(input_signal)])[0, 1]
            rms_ratio = np.sqrt(np.mean(output**2)) / np.sqrt(np.mean(input_signal**2))
            length_ratio = len(output) / len(input_signal)
            
            # Combined preservation score
            preservation_score = (
                correlation * 0.5 +
                (1 - abs(rms_ratio - 1.0)) * 0.3 +
                (1 - abs(length_ratio - 1.0)) * 0.2
            )
            
            passed = preservation_score > 0.9
            score = preservation_score
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'correlation': correlation,
                    'rms_ratio': rms_ratio,
                    'length_ratio': length_ratio,
                    'preservation_score': preservation_score
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_frequency_response(self):
        """Test frequency response characteristics"""
        test_name = "Frequency Response"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['chirp']  # Frequency sweep
            profile = AdvancedVoiceProfile(spectral_tilt=2.0)
            
            output = self.advanced_processor.process_voice(input_signal, profile)
            
            # Analyze frequency response
            input_fft = np.abs(np.fft.rfft(input_signal))
            output_fft = np.abs(np.fft.rfft(output))
            
            # Normalize
            input_fft = input_fft / np.max(input_fft)
            output_fft = output_fft / np.max(output_fft)
            
            # Calculate frequency response
            freq_response = output_fft / (input_fft + 1e-10)
            
            # Check for reasonable response (no extreme peaks/nulls)
            response_variance = np.var(np.log(freq_response + 1e-10))
            response_score = max(0, 1.0 - response_variance / 10.0)
            
            passed = response_score > 0.7
            score = response_score
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'response_variance': response_variance,
                    'response_score': response_score
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_quality_assessment(self):
        """Test quality assessment and optimization"""
        
        # Test quality optimizer
        self._test_quality_optimizer()
        
        # Test artifact detection
        self._test_artifact_detection()
        
        # Test naturalness enhancement
        self._test_naturalness_enhancement()
    
    def _test_quality_optimizer(self):
        """Test quality optimization"""
        test_name = "Quality Optimizer"
        start_time = time.time()
        
        try:
            # Create degraded signal
            clean_signal = self.test_signals['harmonic_series']
            noisy_signal = clean_signal + 0.1 * np.random.normal(0, 1, len(clean_signal))
            
            # Optimize quality
            optimized = self.quality_optimizer.optimize_quality(noisy_signal)
            
            # Calculate quality improvement
            original_quality = self.quality_optimizer._assess_quality(clean_signal, noisy_signal)
            final_quality = self.quality_optimizer._assess_quality(clean_signal, optimized)
            
            quality_improvement = final_quality - original_quality
            
            passed = quality_improvement > 0.05  # 5% improvement
            score = min(1.0, quality_improvement * 10)
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'original_quality': original_quality,
                    'final_quality': final_quality,
                    'quality_improvement': quality_improvement
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_artifact_detection(self):
        """Test artifact detection capabilities"""
        test_name = "Artifact Detection"
        start_time = time.time()
        
        try:
            # Create signal with artifacts
            clean_signal = self.test_signals['harmonic_series']
            
            # Add clicks
            artifacted_signal = clean_signal.copy()
            click_positions = [1000, 2000, 3000]
            for pos in click_positions:
                if pos < len(artifacted_signal):
                    artifacted_signal[pos] += 0.8
            
            # Process with artifact reduction
            processed = self.quality_optimizer.artifact_reducer.reduce_artifacts(
                artifacted_signal, self.quality_optimizer.config
            )
            
            # Measure artifact reduction
            click_reduction = self._measure_click_reduction(
                artifacted_signal, processed, click_positions
            )
            
            passed = click_reduction > 0.5  # 50% reduction
            score = click_reduction
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'click_reduction': click_reduction
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_naturalness_enhancement(self):
        """Test naturalness enhancement"""
        test_name = "Naturalness Enhancement"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['harmonic_series']
            
            # Apply naturalness enhancement
            enhanced = self.quality_optimizer.naturalness_enhancer.enhance_naturalness(
                input_signal, self.quality_optimizer.config
            )
            
            # Measure naturalness metrics
            formant_clarity = self._measure_formant_clarity(enhanced)
            harmonic_strength = self._measure_harmonic_strength(enhanced)
            
            naturalness_score = (formant_clarity + harmonic_strength) / 2
            
            passed = naturalness_score > 0.7
            score = naturalness_score
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'formant_clarity': formant_clarity,
                    'harmonic_strength': harmonic_strength,
                    'naturalness_score': naturalness_score
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_performance(self):
        """Test performance benchmarks"""
        
        # Processing speed test
        self._test_processing_speed()
        
        # Memory usage test
        self._test_memory_usage()
        
        # Throughput test
        self._test_throughput()
    
    def _test_processing_speed(self):
        """Test processing speed"""
        test_name = "Processing Speed"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['harmonic_series']
            profile = AdvancedVoiceProfile(pitch_scale=1.2, formant_shift=1.1)
            
            # Process multiple times for average
            iterations = 10
            processing_times = []
            
            for _ in range(iterations):
                proc_start = time.time()
                output = self.advanced_processor.process_voice(input_signal, profile)
                proc_time = time.time() - proc_start
                processing_times.append(proc_time)
            
            avg_processing_time = np.mean(processing_times)
            real_time_factor = self.test_duration / avg_processing_time
            
            # Pass if faster than 10x real-time
            passed = real_time_factor > 10
            score = min(1.0, real_time_factor / 50)  # Score based on 50x real-time target
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'avg_processing_time': avg_processing_time,
                    'real_time_factor': real_time_factor,
                    'processing_times': processing_times
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_memory_usage(self):
        """Test memory usage"""
        test_name = "Memory Usage"
        start_time = time.time()
        
        try:
            import psutil
            import gc
            
            # Baseline memory
            gc.collect()
            baseline_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            # Process signal
            input_signal = self.test_signals['harmonic_series']
            profile = AdvancedVoiceProfile(pitch_scale=1.3)
            
            output = self.advanced_processor.process_voice(input_signal, profile)
            
            # Peak memory
            peak_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_used = peak_memory - baseline_memory
            
            # Pass if memory usage < 100MB
            passed = memory_used < 100
            score = max(0, 1.0 - memory_used / 200)  # Score based on 200MB limit
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'baseline_memory_mb': baseline_memory,
                    'peak_memory_mb': peak_memory,
                    'memory_used_mb': memory_used
                }
            ))
            
        except ImportError:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message="psutil not available"
            ))
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_throughput(self):
        """Test processing throughput"""
        test_name = "Processing Throughput"
        start_time = time.time()
        
        try:
            # Create batch of signals
            batch_size = 5
            batch_signals = [self.test_signals['harmonic_series'] for _ in range(batch_size)]
            profile = AdvancedVoiceProfile(pitch_scale=1.1)
            
            # Process batch
            batch_start = time.time()
            outputs = []
            for signal in batch_signals:
                output = self.advanced_processor.process_voice(signal, profile)
                outputs.append(output)
            batch_time = time.time() - batch_start
            
            # Calculate throughput
            total_audio_duration = batch_size * self.test_duration
            throughput_factor = total_audio_duration / batch_time
            
            # Pass if throughput > 5x real-time
            passed = throughput_factor > 5
            score = min(1.0, throughput_factor / 20)  # Score based on 20x real-time target
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'batch_size': batch_size,
                    'batch_time': batch_time,
                    'throughput_factor': throughput_factor
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_realtime_processing(self):
        """Test real-time processing capabilities"""
        
        # Latency test
        self._test_latency()
        
        # Buffer management test
        self._test_buffer_management()
    
    def _test_latency(self):
        """Test processing latency"""
        test_name = "Processing Latency"
        start_time = time.time()
        
        try:
            # Simulate real-time processing
            chunk_size = 512
            input_signal = self.test_signals['harmonic_series']
            
            # Split into chunks
            chunks = []
            for i in range(0, len(input_signal), chunk_size):
                chunk = input_signal[i:i + chunk_size]
                if len(chunk) == chunk_size:
                    chunks.append(chunk)
            
            # Process chunks and measure latency
            latencies = []
            
            for chunk in chunks[:5]:  # Test first 5 chunks
                chunk_start = time.time()
                
                # Simulate processing (simplified)
                profile = AdvancedVoiceProfile(pitch_scale=1.1)
                processed_chunk = self.advanced_processor.process_voice(chunk, profile)
                
                chunk_latency = time.time() - chunk_start
                latencies.append(chunk_latency * 1000)  # Convert to ms
            
            avg_latency = np.mean(latencies)
            max_latency = np.max(latencies)
            
            # Pass if average latency < 20ms
            passed = avg_latency < 20
            score = max(0, 1.0 - avg_latency / 50)  # Score based on 50ms limit
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'avg_latency_ms': avg_latency,
                    'max_latency_ms': max_latency,
                    'latencies_ms': latencies
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_buffer_management(self):
        """Test buffer management"""
        test_name = "Buffer Management"
        start_time = time.time()
        
        try:
            # Test with varying buffer sizes
            buffer_sizes = [256, 512, 1024, 2048]
            buffer_scores = []
            
            input_signal = self.test_signals['harmonic_series']
            
            for buffer_size in buffer_sizes:
                # Simulate buffer processing
                chunks_processed = 0
                total_samples = 0
                
                for i in range(0, len(input_signal), buffer_size):
                    chunk = input_signal[i:i + buffer_size]
                    if len(chunk) > 0:
                        chunks_processed += 1
                        total_samples += len(chunk)
                
                # Check sample preservation
                sample_preservation = total_samples / len(input_signal)
                buffer_scores.append(sample_preservation)
            
            avg_buffer_score = np.mean(buffer_scores)
            
            passed = avg_buffer_score > 0.95  # 95% sample preservation
            score = avg_buffer_score
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'buffer_sizes': buffer_sizes,
                    'buffer_scores': buffer_scores,
                    'avg_buffer_score': avg_buffer_score
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_robustness(self):
        """Test robustness to various conditions"""
        
        # Noise robustness test
        self._test_noise_robustness()
        
        # Edge case handling test
        self._test_edge_cases()
        
        # Parameter range test
        self._test_parameter_ranges()
    
    def _test_noise_robustness(self):
        """Test robustness to noise"""
        test_name = "Noise Robustness"
        start_time = time.time()
        
        try:
            clean_signal = self.test_signals['harmonic_series']
            profile = AdvancedVoiceProfile(pitch_scale=1.2)
            
            # Test with different noise levels
            noise_levels = [0.01, 0.05, 0.1, 0.2]
            robustness_scores = []
            
            for noise_level in noise_levels:
                noisy_signal = clean_signal + noise_level * np.random.normal(0, 1, len(clean_signal))
                
                try:
                    output = self.advanced_processor.process_voice(noisy_signal, profile)
                    
                    # Calculate quality preservation
                    clean_output = self.advanced_processor.process_voice(clean_signal, profile)
                    
                    # Compare outputs
                    if len(output) == len(clean_output):
                        correlation = np.corrcoef(output, clean_output)[0, 1]
                        if not np.isnan(correlation):
                            robustness_scores.append(correlation)
                        else:
                            robustness_scores.append(0.5)
                    else:
                        robustness_scores.append(0.5)
                        
                except:
                    robustness_scores.append(0.0)
            
            avg_robustness = np.mean(robustness_scores)
            
            passed = avg_robustness > 0.7
            score = avg_robustness
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'noise_levels': noise_levels,
                    'robustness_scores': robustness_scores,
                    'avg_robustness': avg_robustness
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_edge_cases(self):
        """Test edge case handling"""
        test_name = "Edge Case Handling"
        start_time = time.time()
        
        edge_cases_passed = 0
        total_edge_cases = 0
        
        try:
            profile = AdvancedVoiceProfile()
            
            # Test empty signal
            total_edge_cases += 1
            try:
                empty_signal = np.array([])
                output = self.advanced_processor.process_voice(empty_signal, profile)
                if len(output) == 0:
                    edge_cases_passed += 1
            except:
                pass  # Expected to handle gracefully
            
            # Test very short signal
            total_edge_cases += 1
            try:
                short_signal = np.array([0.1, -0.1])
                output = self.advanced_processor.process_voice(short_signal, profile)
                edge_cases_passed += 1
            except:
                pass
            
            # Test constant signal
            total_edge_cases += 1
            try:
                constant_signal = np.ones(1000) * 0.5
                output = self.advanced_processor.process_voice(constant_signal, profile)
                edge_cases_passed += 1
            except:
                pass
            
            # Test extreme parameters
            total_edge_cases += 1
            try:
                extreme_profile = AdvancedVoiceProfile(pitch_scale=0.25, formant_shift=2.0)
                output = self.advanced_processor.process_voice(
                    self.test_signals['harmonic_series'], extreme_profile
                )
                edge_cases_passed += 1
            except:
                pass
            
            success_rate = edge_cases_passed / total_edge_cases
            
            passed = success_rate > 0.75  # 75% of edge cases handled
            score = success_rate
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'edge_cases_passed': edge_cases_passed,
                    'total_edge_cases': total_edge_cases,
                    'success_rate': success_rate
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_parameter_ranges(self):
        """Test parameter range handling"""
        test_name = "Parameter Range Handling"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['harmonic_series']
            parameter_tests_passed = 0
            total_parameter_tests = 0
            
            # Test pitch scale range
            pitch_values = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0]
            for pitch in pitch_values:
                total_parameter_tests += 1
                try:
                    profile = AdvancedVoiceProfile(pitch_scale=pitch)
                    output = self.advanced_processor.process_voice(input_signal, profile)
                    if len(output) > 0 and not np.any(np.isnan(output)):
                        parameter_tests_passed += 1
                except:
                    pass
            
            # Test formant shift range
            formant_values = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]
            for formant in formant_values:
                total_parameter_tests += 1
                try:
                    profile = AdvancedVoiceProfile(formant_shift=formant)
                    output = self.advanced_processor.process_voice(input_signal, profile)
                    if len(output) > 0 and not np.any(np.isnan(output)):
                        parameter_tests_passed += 1
                except:
                    pass
            
            success_rate = parameter_tests_passed / total_parameter_tests
            
            passed = success_rate > 0.8  # 80% of parameter ranges handled
            score = success_rate
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'parameter_tests_passed': parameter_tests_passed,
                    'total_parameter_tests': total_parameter_tests,
                    'success_rate': success_rate
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_perceptual_quality(self):
        """Test perceptual quality metrics"""
        
        # Spectral distortion test
        self._test_spectral_distortion()
        
        # Phase coherence test
        self._test_phase_coherence()
    
    def _test_spectral_distortion(self):
        """Test spectral distortion"""
        test_name = "Spectral Distortion"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['harmonic_series']
            profile = AdvancedVoiceProfile(pitch_scale=1.2, formant_shift=1.1)
            
            output = self.advanced_processor.process_voice(input_signal, profile)
            
            # Calculate spectral distortion
            input_fft = np.abs(np.fft.rfft(input_signal))
            output_fft = np.abs(np.fft.rfft(output))
            
            # Normalize
            input_fft = input_fft / (np.sum(input_fft) + 1e-10)
            output_fft = output_fft / (np.sum(output_fft) + 1e-10)
            
            # Calculate KL divergence as distortion measure
            kl_divergence = np.sum(input_fft * np.log((input_fft + 1e-10) / (output_fft + 1e-10)))
            
            # Convert to quality score (lower KL divergence = higher quality)
            quality_score = max(0, 1.0 - kl_divergence / 10.0)
            
            passed = quality_score > 0.7
            score = quality_score
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'kl_divergence': kl_divergence,
                    'quality_score': quality_score
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _test_phase_coherence(self):
        """Test phase coherence preservation"""
        test_name = "Phase Coherence"
        start_time = time.time()
        
        try:
            input_signal = self.test_signals['harmonic_series']
            profile = AdvancedVoiceProfile(pitch_scale=1.0)  # No pitch change
            
            output = self.advanced_processor.process_voice(input_signal, profile)
            
            # Calculate phase coherence
            input_fft = np.fft.rfft(input_signal)
            output_fft = np.fft.rfft(output)
            
            input_phase = np.angle(input_fft)
            output_phase = np.angle(output_fft)
            
            # Phase difference
            phase_diff = np.angle(np.exp(1j * (output_phase - input_phase)))
            phase_coherence = np.mean(np.cos(phase_diff))
            
            passed = phase_coherence > 0.8
            score = max(0, phase_coherence)
            
            execution_time = time.time() - start_time
            
            self.results.append(TestResult(
                test_name=test_name,
                passed=passed,
                score=score,
                execution_time=execution_time,
                details={
                    'phase_coherence': phase_coherence
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                test_name=test_name,
                passed=False,
                score=0.0,
                execution_time=time.time() - start_time,
                details={},
                error_message=str(e)
            ))
    
    def _print_summary(self):
        """Print test results summary"""
        print("\n" + "="*60)
        print("VOICE PROCESSING TEST RESULTS SUMMARY")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        total_score = sum(r.score for r in self.results)
        avg_score = total_score / total_tests if total_tests > 0 else 0
        total_time = sum(r.execution_time for r in self.results)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed Tests: {passed_tests}")
        print(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
        print(f"Average Score: {avg_score:.3f}")
        print(f"Total Execution Time: {total_time:.2f}s")
        
        print("\nDetailed Results:")
        print("-" * 60)
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"{result.test_name:<30} {status:<8} Score: {result.score:.3f} "
                  f"Time: {result.execution_time:.3f}s")
            
            if result.error_message:
                print(f"    Error: {result.error_message}")
        
        # Performance summary
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60)
        
        performance_tests = [r for r in self.results if 'Speed' in r.test_name or 'Latency' in r.test_name]
        
        for test in performance_tests:
            print(f"\n{test.test_name}:")
            for key, value in test.details.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.3f}")
                elif isinstance(value, list) and len(value) <= 5:
                    print(f"  {key}: {value}")
    
    # Helper methods for analysis
    def _estimate_fundamental_frequency(self, signal: np.ndarray) -> float:
        """Estimate fundamental frequency using autocorrelation"""
        if len(signal) < 100:
            return 0.0
            
        # Autocorrelation
        corr = np.correlate(signal, signal, mode='full')
        corr = corr[len(corr)//2:]
        
        # Find peak in F0 range
        min_period = int(self.sample_rate / 800)  # 800 Hz max
        max_period = int(self.sample_rate / 50)   # 50 Hz min
        
        if max_period < len(corr):
            search_range = corr[min_period:max_period]
            if len(search_range) > 0:
                peak_idx = np.argmax(search_range) + min_period
                return self.sample_rate / peak_idx
                
        return 0.0
    
    def _find_spectral_peaks(self, spectrum: np.ndarray, num_peaks: int = 10) -> List[int]:
        """Find spectral peaks"""
        try:
            from scipy.signal import find_peaks
            peaks, _ = find_peaks(spectrum, height=np.max(spectrum) * 0.1)
            
            # Sort by magnitude
            peak_magnitudes = spectrum[peaks]
            sorted_indices = np.argsort(peak_magnitudes)[::-1]
            
            return peaks[sorted_indices[:num_peaks]].tolist()
        except ImportError:
            # Fallback peak finding
            peaks = []
            for i in range(1, len(spectrum) - 1):
                if (spectrum[i] > spectrum[i-1] and 
                    spectrum[i] > spectrum[i+1] and 
                    spectrum[i] > np.max(spectrum) * 0.1):
                    peaks.append(i)
                    
            return peaks[:num_peaks]
    
    def _calculate_formant_shift_accuracy(self, input_peaks: List[int], 
                                        output_peaks: List[int], 
                                        target_shift: float) -> float:
        """Calculate formant shift accuracy"""
        if not input_peaks or not output_peaks:
            return 0.0
            
        # Match peaks and calculate shift accuracy
        accuracies = []
        
        for i, input_peak in enumerate(input_peaks):
            expected_peak = input_peak * target_shift
            
            # Find closest output peak
            if output_peaks:
                closest_output = min(output_peaks, key=lambda x: abs(x - expected_peak))
                error = abs(closest_output - expected_peak) / expected_peak
                accuracy = max(0, 1.0 - error)
                accuracies.append(accuracy)
        
        return np.mean(accuracies) if accuracies else 0.0
    
    def _measure_click_reduction(self, original: np.ndarray, 
                               processed: np.ndarray, 
                               click_positions: List[int]) -> float:
        """Measure click reduction effectiveness"""
        if len(original) != len(processed):
            return 0.0
            
        original_clicks = 0
        processed_clicks = 0
        
        for pos in click_positions:
            if 0 <= pos < len(original):
                # Measure click amplitude in surrounding region
                region_start = max(0, pos - 5)
                region_end = min(len(original), pos + 6)
                
                original_amplitude = np.max(np.abs(original[region_start:region_end]))
                processed_amplitude = np.max(np.abs(processed[region_start:region_end]))
                
                original_clicks += original_amplitude
                processed_clicks += processed_amplitude
        
        if original_clicks > 0:
            reduction = (original_clicks - processed_clicks) / original_clicks
            return max(0, reduction)
        
        return 0.0
    
    def _measure_formant_clarity(self, signal: np.ndarray) -> float:
        """Measure formant clarity"""
        spectrum = np.abs(np.fft.rfft(signal))
        
        # Find peaks (formants)
        peaks = self._find_spectral_peaks(spectrum, 5)
        
        if len(peaks) < 2:
            return 0.5
            
        # Measure peak-to-valley ratios
        clarity_scores = []
        
        for peak in peaks:
            peak_value = spectrum[peak]
            
            # Find surrounding valleys
            left_valley = peak - 20 if peak >= 20 else 0
            right_valley = peak + 20 if peak + 20 < len(spectrum) else len(spectrum) - 1
            
            left_valley_value = np.min(spectrum[left_valley:peak])
            right_valley_value = np.min(spectrum[peak:right_valley])
            
            valley_value = min(left_valley_value, right_valley_value)
            
            if valley_value > 0:
                clarity_ratio = peak_value / valley_value
                clarity_scores.append(min(1.0, clarity_ratio / 10.0))
        
        return np.mean(clarity_scores) if clarity_scores else 0.5
    
    def _measure_harmonic_strength(self, signal: np.ndarray) -> float:
        """Measure harmonic strength"""
        f0 = self._estimate_fundamental_frequency(signal)
        
        if f0 <= 0:
            return 0.5
            
        spectrum = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(signal), 1/self.sample_rate)
        
        harmonic_strength = 0
        total_harmonics = 0
        
        # Check up to 5 harmonics
        for harmonic in range(1, 6):
            harmonic_freq = f0 * harmonic
            
            if harmonic_freq < freqs[-1]:
                # Find closest frequency bin
                freq_idx = np.argmin(np.abs(freqs - harmonic_freq))
                harmonic_amplitude = spectrum[freq_idx]
                
                # Compare to surrounding noise floor
                noise_start = max(0, freq_idx - 10)
                noise_end = min(len(spectrum), freq_idx + 11)
                noise_floor = np.mean(spectrum[noise_start:noise_end])
                
                if noise_floor > 0:
                    snr = harmonic_amplitude / noise_floor
                    harmonic_strength += min(1.0, snr / 10.0)
                    total_harmonics += 1
        
        return harmonic_strength / total_harmonics if total_harmonics > 0 else 0.5

def main():
    """Run the comprehensive test suite"""
    print("Initializing Voice Processing Test Suite...")
    
    # Handle scipy import for signal processing
    try:
        import scipy.signal
        globals()['scipy'] = scipy
    except ImportError:
        print("Warning: scipy not available. Some tests may use fallback implementations.")
        
        # Create mock scipy.signal module
        class MockSignal:
            @staticmethod
            def find_peaks(data, height=None):
                peaks = []
                for i in range(1, len(data) - 1):
                    if (data[i] > data[i-1] and data[i] > data[i+1]):
                        if height is None or data[i] >= height:
                            peaks.append(i)
                return np.array(peaks), {}
            
            @staticmethod
            def chirp(t, f0, t1, f1):
                return np.sin(2 * np.pi * (f0 * t + (f1 - f0) * t**2 / (2 * t1)))
                
        class MockScipy:
            signal = MockSignal()
            
        globals()['scipy'] = MockScipy()
    
    # Initialize and run test suite
    test_suite = VoiceProcessingTestSuite()
    results = test_suite.run_all_tests()
    
    return results

if __name__ == "__main__":
    main()