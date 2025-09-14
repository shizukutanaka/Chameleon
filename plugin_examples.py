#!/usr/bin/env python3
"""
Chameleon Audio System - Plugin Examples
========================================
Collection of example plugins demonstrating various capabilities
"""

import math
import random
import time
from typing import List, Dict, Any
from plugin_sdk import (
    PluginInterface, EffectPlugin, GeneratorPlugin, AnalyzerPlugin,
    PluginInfo, PluginType, PluginCategory, PluginContext
)


class AdvancedReverbPlugin(EffectPlugin):
    """Advanced reverb effect with multiple parameters"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Advanced Reverb",
            version="1.2.0",
            author="Chameleon Audio",
            description="Multi-tap delay reverb with modulation",
            plugin_type=PluginType.EFFECT,
            category=PluginCategory.REVERB,
            tags=["reverb", "delay", "spatial", "advanced"],
            parameters={
                "room_size": {"type": "float", "min": 0.1, "max": 1.0, "default": 0.5},
                "damping": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.3},
                "wet_level": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.3},
                "dry_level": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.7},
                "pre_delay": {"type": "float", "min": 0.0, "max": 0.1, "default": 0.02},
                "modulation_rate": {"type": "float", "min": 0.1, "max": 10.0, "default": 1.0},
                "modulation_depth": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.1},
                "enabled": {"type": "bool", "default": True}
            }
        )
    
    def initialize(self, context: PluginContext) -> bool:
        self.context = context
        self.sample_rate = context.sample_rate
        
        # Initialize parameters
        self.parameters = {
            "room_size": 0.5,
            "damping": 0.3,
            "wet_level": 0.3,
            "dry_level": 0.7,
            "pre_delay": 0.02,
            "modulation_rate": 1.0,
            "modulation_depth": 0.1,
            "enabled": True
        }
        
        # Initialize delay buffers
        max_delay = int(0.1 * self.sample_rate)  # 100ms max delay
        self.delay_buffers = [
            [0.0] * max_delay for _ in range(8)  # 8 delay taps
        ]
        self.delay_indices = [0] * 8
        
        # Delay times in samples
        base_delays = [0.017, 0.033, 0.051, 0.067, 0.083, 0.097, 0.113, 0.127]
        self.delay_lengths = [int(delay * self.sample_rate) for delay in base_delays]
        
        # Filter states for damping
        self.lowpass_states = [0.0] * 8
        
        # Modulation
        self.mod_phase = 0.0
        
        return True
    
    def apply_effect(self, samples: List[float], **params) -> List[float]:
        if not self.parameters.get("enabled", True):
            return samples
        
        room_size = self.parameters.get("room_size", 0.5)
        damping = self.parameters.get("damping", 0.3)
        wet_level = self.parameters.get("wet_level", 0.3)
        dry_level = self.parameters.get("dry_level", 0.7)
        pre_delay = self.parameters.get("pre_delay", 0.02)
        mod_rate = self.parameters.get("modulation_rate", 1.0)
        mod_depth = self.parameters.get("modulation_depth", 0.1)
        
        result = []
        pre_delay_samples = int(pre_delay * self.sample_rate)
        
        for sample in samples:
            # Pre-delay
            delayed_input = sample
            if len(result) >= pre_delay_samples:
                delayed_input = samples[len(result) - pre_delay_samples] if len(result) - pre_delay_samples >= 0 else sample
            
            # Multi-tap delay processing
            reverb_sum = 0.0
            
            for i in range(8):
                # Write input to delay buffer
                self.delay_buffers[i][self.delay_indices[i]] = delayed_input
                
                # Calculate modulated delay time
                mod_offset = mod_depth * math.sin(self.mod_phase + i * 0.7854)  # pi/4 phase offset
                delay_time = self.delay_lengths[i] + int(mod_offset * self.sample_rate * 0.01)
                delay_time = max(1, min(len(self.delay_buffers[i]) - 1, delay_time))
                
                # Read from delay buffer
                read_index = (self.delay_indices[i] - delay_time) % len(self.delay_buffers[i])
                delayed_sample = self.delay_buffers[i][read_index]
                
                # Apply damping (lowpass filter)
                self.lowpass_states[i] = damping * delayed_sample + (1 - damping) * self.lowpass_states[i]
                filtered_sample = self.lowpass_states[i]
                
                # Apply room size (feedback)
                feedback = filtered_sample * room_size * 0.3
                self.delay_buffers[i][self.delay_indices[i]] += feedback
                
                # Add to reverb sum with different gains for each tap
                tap_gain = 0.7 ** i  # Exponential decay
                reverb_sum += filtered_sample * tap_gain
                
                # Advance delay index
                self.delay_indices[i] = (self.delay_indices[i] + 1) % len(self.delay_buffers[i])
            
            # Update modulation phase
            self.mod_phase += 2 * math.pi * mod_rate / self.sample_rate
            if self.mod_phase > 2 * math.pi:
                self.mod_phase -= 2 * math.pi
            
            # Mix dry and wet signals
            output = dry_level * sample + wet_level * reverb_sum * 0.125  # Normalize
            result.append(output)
        
        return result


class WavetableOscillatorPlugin(GeneratorPlugin):
    """Wavetable oscillator with multiple waveforms"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Wavetable Oscillator",
            version="1.1.0",
            author="Chameleon Audio",
            description="Wavetable oscillator with morphing capabilities",
            plugin_type=PluginType.GENERATOR,
            category=PluginCategory.SYNTHESIS,
            tags=["oscillator", "wavetable", "synthesis", "morphing"],
            parameters={
                "frequency": {"type": "float", "min": 20.0, "max": 20000.0, "default": 440.0},
                "amplitude": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.5},
                "waveform": {"type": "int", "min": 0, "max": 4, "default": 0},
                "morph": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.0},
                "detune": {"type": "float", "min": -1200.0, "max": 1200.0, "default": 0.0},
                "phase_offset": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.0}
            }
        )
    
    def initialize(self, context: PluginContext) -> bool:
        self.context = context
        self.sample_rate = context.sample_rate
        
        self.parameters = {
            "frequency": 440.0,
            "amplitude": 0.5,
            "waveform": 0,
            "morph": 0.0,
            "detune": 0.0,
            "phase_offset": 0.0
        }
        
        self.state = {"phase": 0.0}
        
        # Create wavetables
        self.wavetable_size = 2048
        self.wavetables = self._create_wavetables()
        
        return True
    
    def _create_wavetables(self) -> List[List[float]]:
        """Create different waveform wavetables"""
        wavetables = []
        
        # Sine wave
        sine_table = []
        for i in range(self.wavetable_size):
            phase = 2 * math.pi * i / self.wavetable_size
            sine_table.append(math.sin(phase))
        wavetables.append(sine_table)
        
        # Square wave
        square_table = []
        for i in range(self.wavetable_size):
            phase = 2 * math.pi * i / self.wavetable_size
            square_table.append(1.0 if phase < math.pi else -1.0)
        wavetables.append(square_table)
        
        # Sawtooth wave
        saw_table = []
        for i in range(self.wavetable_size):
            saw_table.append(2.0 * i / self.wavetable_size - 1.0)
        wavetables.append(saw_table)
        
        # Triangle wave
        triangle_table = []
        for i in range(self.wavetable_size):
            if i < self.wavetable_size // 2:
                triangle_table.append(4.0 * i / self.wavetable_size - 1.0)
            else:
                triangle_table.append(3.0 - 4.0 * i / self.wavetable_size)
        wavetables.append(triangle_table)
        
        # Noise (for texture)
        noise_table = []
        for _ in range(self.wavetable_size):
            noise_table.append(random.uniform(-1.0, 1.0))
        wavetables.append(noise_table)
        
        return wavetables
    
    def _interpolate_wavetable(self, table: List[float], phase: float) -> float:
        """Linear interpolation in wavetable"""
        index = phase * len(table)
        i0 = int(index) % len(table)
        i1 = (i0 + 1) % len(table)
        frac = index - int(index)
        
        return table[i0] * (1 - frac) + table[i1] * frac
    
    def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
        frequency = self.parameters.get("frequency", 440.0)
        amplitude = self.parameters.get("amplitude", 0.5)
        waveform = int(self.parameters.get("waveform", 0))
        morph = self.parameters.get("morph", 0.0)
        detune_cents = self.parameters.get("detune", 0.0)
        phase_offset = self.parameters.get("phase_offset", 0.0)
        
        # Apply detune
        detune_ratio = 2 ** (detune_cents / 1200.0)
        actual_frequency = frequency * detune_ratio
        
        phase = self.state.get("phase", 0.0) + phase_offset
        samples = []
        
        for _ in range(int(duration * sample_rate)):
            # Calculate wavetable phase (0-1)
            wt_phase = (phase % (2 * math.pi)) / (2 * math.pi)
            
            # Get primary waveform
            waveform = max(0, min(len(self.wavetables) - 1, waveform))
            primary_sample = self._interpolate_wavetable(self.wavetables[waveform], wt_phase)
            
            # Morph with next waveform if morph > 0
            if morph > 0.0 and waveform < len(self.wavetables) - 1:
                next_waveform = waveform + 1
                secondary_sample = self._interpolate_wavetable(self.wavetables[next_waveform], wt_phase)
                sample = primary_sample * (1 - morph) + secondary_sample * morph
            else:
                sample = primary_sample
            
            samples.append(sample * amplitude)
            phase += 2 * math.pi * actual_frequency / sample_rate
        
        # Keep phase in reasonable range
        self.state["phase"] = phase % (2 * math.pi)
        return samples


class MultiSpectrumAnalyzerPlugin(AnalyzerPlugin):
    """Advanced spectrum analyzer with multiple analysis modes"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Multi-Spectrum Analyzer",
            version="1.0.0",
            author="Chameleon Audio",
            description="Advanced spectrum analysis with multiple modes",
            plugin_type=PluginType.ANALYZER,
            category=PluginCategory.ANALYSIS,
            tags=["analyzer", "spectrum", "fft", "advanced"],
            parameters={
                "fft_size": {"type": "int", "min": 128, "max": 8192, "default": 2048},
                "window_type": {"type": "int", "min": 0, "max": 3, "default": 1},
                "overlap": {"type": "float", "min": 0.0, "max": 0.75, "default": 0.5},
                "analysis_mode": {"type": "int", "min": 0, "max": 2, "default": 0}
            }
        )
    
    def initialize(self, context: PluginContext) -> bool:
        self.context = context
        self.sample_rate = context.sample_rate
        
        self.parameters = {
            "fft_size": 2048,
            "window_type": 1,  # 0=rectangular, 1=hanning, 2=hamming, 3=blackman
            "overlap": 0.5,
            "analysis_mode": 0  # 0=spectrum, 1=spectrogram, 2=phase
        }
        
        self.buffer = []
        return True
    
    def _apply_window(self, samples: List[float], window_type: int) -> List[float]:
        """Apply window function to samples"""
        n = len(samples)
        windowed = []
        
        for i, sample in enumerate(samples):
            if window_type == 0:  # Rectangular
                window_val = 1.0
            elif window_type == 1:  # Hanning
                window_val = 0.5 * (1 - math.cos(2 * math.pi * i / (n - 1)))
            elif window_type == 2:  # Hamming
                window_val = 0.54 - 0.46 * math.cos(2 * math.pi * i / (n - 1))
            elif window_type == 3:  # Blackman
                window_val = (0.42 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) + 
                             0.08 * math.cos(4 * math.pi * i / (n - 1)))
            else:
                window_val = 1.0
            
            windowed.append(sample * window_val)
        
        return windowed
    
    def _simple_fft(self, samples: List[float]) -> List[complex]:
        """Simple DFT implementation (for demonstration)"""
        n = len(samples)
        spectrum = []
        
        # Use smaller size for performance
        analysis_size = min(n, 512)
        
        for k in range(analysis_size // 2):  # Only positive frequencies
            real = 0.0
            imag = 0.0
            
            for i in range(analysis_size):
                angle = -2 * math.pi * k * i / analysis_size
                real += samples[i] * math.cos(angle)
                imag += samples[i] * math.sin(angle)
            
            spectrum.append(complex(real, imag))
        
        return spectrum
    
    def analyze_audio(self, samples: List[float], sample_rate: int) -> Dict[str, Any]:
        fft_size = int(self.parameters.get("fft_size", 2048))
        window_type = int(self.parameters.get("window_type", 1))
        overlap = self.parameters.get("overlap", 0.5)
        analysis_mode = int(self.parameters.get("analysis_mode", 0))
        
        if not samples:
            return {}
        
        # Adjust FFT size to available samples
        fft_size = min(fft_size, len(samples))
        
        # Take the most recent samples
        analysis_samples = samples[-fft_size:]
        
        # Apply window
        windowed_samples = self._apply_window(analysis_samples, window_type)
        
        # Perform FFT
        spectrum = self._simple_fft(windowed_samples)
        
        # Calculate magnitudes
        magnitudes = [abs(c) for c in spectrum]
        
        # Calculate phases
        phases = [math.atan2(c.imag, c.real) for c in spectrum]
        
        # Basic statistics
        if magnitudes:
            peak_magnitude = max(magnitudes)
            peak_index = magnitudes.index(peak_magnitude)
            peak_frequency = peak_index * sample_rate / (2 * len(magnitudes))
        else:
            peak_magnitude = 0
            peak_frequency = 0
        
        # Spectral features
        spectral_centroid = 0
        spectral_rolloff = 0
        
        if sum(magnitudes) > 0:
            # Spectral centroid
            weighted_sum = sum(f * mag for f, mag in enumerate(magnitudes))
            spectral_centroid = weighted_sum / sum(magnitudes)
            spectral_centroid = spectral_centroid * sample_rate / (2 * len(magnitudes))
            
            # Spectral rolloff (85% of energy)
            cumsum = 0
            total_energy = sum(mag**2 for mag in magnitudes)
            rolloff_threshold = 0.85 * total_energy
            
            for i, mag in enumerate(magnitudes):
                cumsum += mag**2
                if cumsum >= rolloff_threshold:
                    spectral_rolloff = i * sample_rate / (2 * len(magnitudes))
                    break
        
        # RMS and peak analysis
        rms = (sum(s**2 for s in samples) / len(samples)) ** 0.5
        peak = max(abs(s) for s in samples)
        
        # Zero crossing rate
        zero_crossings = sum(1 for i in range(1, len(samples)) 
                           if (samples[i-1] >= 0) != (samples[i] >= 0))
        zero_crossing_rate = zero_crossings / len(samples)
        
        result = {
            "peak_magnitude": peak_magnitude,
            "peak_frequency": peak_frequency,
            "spectral_centroid": spectral_centroid,
            "spectral_rolloff": spectral_rolloff,
            "rms": rms,
            "peak": peak,
            "zero_crossing_rate": zero_crossing_rate,
            "fft_size": fft_size,
            "window_type": window_type,
            "sample_rate": sample_rate
        }
        
        # Include spectrum data based on analysis mode
        if analysis_mode == 0:  # Spectrum
            result["spectrum_magnitudes"] = magnitudes[:min(50, len(magnitudes))]  # Limit size
        elif analysis_mode == 1:  # Spectrogram (would need history)
            result["current_spectrum"] = magnitudes[:min(50, len(magnitudes))]
        elif analysis_mode == 2:  # Phase
            result["spectrum_phases"] = phases[:min(50, len(phases))]
        
        return result


class AdaptiveCompressorPlugin(EffectPlugin):
    """Intelligent compressor with adaptive threshold"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Adaptive Compressor",
            version="1.0.0",
            author="Chameleon Audio",
            description="Intelligent compressor with adaptive threshold and program-dependent attack/release",
            plugin_type=PluginType.EFFECT,
            category=PluginCategory.DYNAMICS,
            tags=["compressor", "dynamics", "adaptive", "intelligent"],
            parameters={
                "ratio": {"type": "float", "min": 1.0, "max": 20.0, "default": 4.0},
                "threshold": {"type": "float", "min": -60.0, "max": 0.0, "default": -20.0},
                "attack_ms": {"type": "float", "min": 0.1, "max": 100.0, "default": 5.0},
                "release_ms": {"type": "float", "min": 10.0, "max": 5000.0, "default": 100.0},
                "knee_width": {"type": "float", "min": 0.0, "max": 10.0, "default": 2.0},
                "makeup_gain": {"type": "float", "min": -20.0, "max": 20.0, "default": 0.0},
                "adaptive_mode": {"type": "bool", "default": True},
                "enabled": {"type": "bool", "default": True}
            }
        )
    
    def initialize(self, context: PluginContext) -> bool:
        self.context = context
        self.sample_rate = context.sample_rate
        
        self.parameters = {
            "ratio": 4.0,
            "threshold": -20.0,
            "attack_ms": 5.0,
            "release_ms": 100.0,
            "knee_width": 2.0,
            "makeup_gain": 0.0,
            "adaptive_mode": True,
            "enabled": True
        }
        
        # State variables
        self.envelope = 0.0
        self.gain_reduction = 0.0
        
        # Adaptive analysis
        self.rms_history = [0.0] * 1000  # 1000 sample history
        self.rms_index = 0
        
        return True
    
    def _db_to_linear(self, db: float) -> float:
        """Convert dB to linear"""
        return 10 ** (db / 20.0)
    
    def _linear_to_db(self, linear: float) -> float:
        """Convert linear to dB"""
        return 20 * math.log10(max(1e-10, abs(linear)))
    
    def _soft_knee(self, input_db: float, threshold: float, ratio: float, knee_width: float) -> float:
        """Apply soft knee compression curve"""
        if knee_width <= 0:
            # Hard knee
            if input_db <= threshold:
                return input_db
            else:
                return threshold + (input_db - threshold) / ratio
        
        # Soft knee
        knee_start = threshold - knee_width / 2
        knee_end = threshold + knee_width / 2
        
        if input_db <= knee_start:
            return input_db
        elif input_db >= knee_end:
            return threshold + (input_db - threshold) / ratio
        else:
            # Smooth transition in knee region
            t = (input_db - knee_start) / knee_width
            # Quadratic interpolation
            return input_db - (t**2) * (input_db - threshold) * (1 - 1/ratio)
    
    def apply_effect(self, samples: List[float], **params) -> List[float]:
        if not self.parameters.get("enabled", True):
            return samples
        
        ratio = self.parameters.get("ratio", 4.0)
        threshold_db = self.parameters.get("threshold", -20.0)
        attack_ms = self.parameters.get("attack_ms", 5.0)
        release_ms = self.parameters.get("release_ms", 100.0)
        knee_width = self.parameters.get("knee_width", 2.0)
        makeup_gain_db = self.parameters.get("makeup_gain", 0.0)
        adaptive_mode = self.parameters.get("adaptive_mode", True)
        
        # Convert time constants to coefficients
        attack_coeff = 1 - math.exp(-1 / (attack_ms * self.sample_rate / 1000))
        release_coeff = 1 - math.exp(-1 / (release_ms * self.sample_rate / 1000))
        
        result = []
        
        for sample in samples:
            # Calculate input level in dB
            input_level = abs(sample)
            if input_level > 0:
                input_db = self._linear_to_db(input_level)
            else:
                input_db = -100  # Very quiet
            
            # Adaptive threshold adjustment
            if adaptive_mode:
                # Update RMS history
                self.rms_history[self.rms_index] = input_level**2
                self.rms_index = (self.rms_index + 1) % len(self.rms_history)
                
                # Calculate average RMS
                avg_rms = (sum(self.rms_history) / len(self.rms_history))**0.5
                avg_db = self._linear_to_db(avg_rms) if avg_rms > 0 else -100
                
                # Adapt threshold based on program material
                adaptation = (avg_db - threshold_db) * 0.1  # 10% adaptation
                adaptive_threshold = threshold_db + adaptation
            else:
                adaptive_threshold = threshold_db
            
            # Apply compression curve
            compressed_db = self._soft_knee(input_db, adaptive_threshold, ratio, knee_width)
            
            # Calculate required gain reduction
            required_gr = compressed_db - input_db
            
            # Smooth gain reduction with attack/release
            if required_gr < self.gain_reduction:
                # Attack (faster)
                self.gain_reduction += (required_gr - self.gain_reduction) * attack_coeff
            else:
                # Release (slower)
                self.gain_reduction += (required_gr - self.gain_reduction) * release_coeff
            
            # Apply gain reduction and makeup gain
            total_gain_db = self.gain_reduction + makeup_gain_db
            gain_linear = self._db_to_linear(total_gain_db)
            
            compressed_sample = sample * gain_linear
            result.append(compressed_sample)
        
        return result


# Plugin registry for easy access
EXAMPLE_PLUGINS = {
    "Advanced Reverb": AdvancedReverbPlugin,
    "Wavetable Oscillator": WavetableOscillatorPlugin,
    "Multi-Spectrum Analyzer": MultiSpectrumAnalyzerPlugin,
    "Adaptive Compressor": AdaptiveCompressorPlugin
}


def demo_example_plugins():
    """Demonstrate the example plugins"""
    from plugin_sdk import PluginManager
    
    print("=" * 60)
    print("CHAMELEON PLUGIN EXAMPLES DEMO")
    print("=" * 60)
    
    # Create plugin manager
    manager = PluginManager()
    
    # Register example plugins
    for name, plugin_class in EXAMPLE_PLUGINS.items():
        try:
            manager.plugin_classes[name] = plugin_class
            instance = plugin_class()
            manager.plugin_infos[name] = instance.get_info()
            print(f"Registered example plugin: {name}")
        except Exception as e:
            print(f"Failed to register {name}: {e}")
    
    # Load and test plugins
    print("\nTesting plugins:")
    
    # Test generator
    print("1. Testing Wavetable Oscillator...")
    if manager.load_plugin("Wavetable Oscillator"):
        manager.set_plugin_parameter("Wavetable Oscillator", "frequency", 880.0)
        manager.set_plugin_parameter("Wavetable Oscillator", "waveform", 1)  # Square
        manager.set_plugin_parameter("Wavetable Oscillator", "morph", 0.5)
        
        audio = manager.process_through_plugins(
            None, 
            ["Wavetable Oscillator"],
            duration=0.1,
            sample_rate=44100
        )
        
        if audio:
            print(f"   Generated {len(audio)} samples")
            
            # Test reverb on generated audio
            print("2. Testing Advanced Reverb...")
            if manager.load_plugin("Advanced Reverb"):
                manager.set_plugin_parameter("Advanced Reverb", "room_size", 0.8)
                manager.set_plugin_parameter("Advanced Reverb", "wet_level", 0.5)
                
                reverbed = manager.process_through_plugins(audio, ["Advanced Reverb"])
                print(f"   Processed through reverb: {len(reverbed)} samples")
            
            # Test analyzer
            print("3. Testing Multi-Spectrum Analyzer...")
            if manager.load_plugin("Multi-Spectrum Analyzer"):
                manager.set_plugin_parameter("Multi-Spectrum Analyzer", "fft_size", 1024)
                
                analysis = manager.process_through_plugins(
                    audio, 
                    ["Multi-Spectrum Analyzer"],
                    sample_rate=44100
                )
                
                if analysis:
                    print(f"   Analysis results:")
                    print(f"   Peak frequency: {analysis.get('peak_frequency', 0):.1f} Hz")
                    print(f"   Spectral centroid: {analysis.get('spectral_centroid', 0):.1f} Hz")
                    print(f"   RMS: {analysis.get('rms', 0):.4f}")
            
            # Test compressor
            print("4. Testing Adaptive Compressor...")
            if manager.load_plugin("Adaptive Compressor"):
                manager.set_plugin_parameter("Adaptive Compressor", "threshold", -10.0)
                manager.set_plugin_parameter("Adaptive Compressor", "ratio", 6.0)
                manager.set_plugin_parameter("Adaptive Compressor", "adaptive_mode", True)
                
                compressed = manager.process_through_plugins(audio, ["Adaptive Compressor"])
                print(f"   Compressed audio: {len(compressed)} samples")
                
                # Compare RMS levels
                original_rms = (sum(s**2 for s in audio) / len(audio))**0.5
                compressed_rms = (sum(s**2 for s in compressed) / len(compressed))**0.5
                print(f"   Original RMS: {original_rms:.4f}")
                print(f"   Compressed RMS: {compressed_rms:.4f}")
    
    # Show performance stats
    print("\nPerformance Statistics:")
    stats = manager.get_performance_stats()
    for plugin_name, perf in stats.items():
        print(f"  {plugin_name}:")
        print(f"    Calls: {perf['call_count']}")
        print(f"    Avg time: {perf['average_time']*1000:.2f}ms")
        print(f"    Throughput: {perf['calls_per_second']:.1f} calls/sec")
    
    print("\nExample plugins demo completed!")


if __name__ == "__main__":
    demo_example_plugins()