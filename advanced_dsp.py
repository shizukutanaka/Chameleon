#!/usr/bin/env python3
"""
Advanced DSP Effects - Professional digital signal processing effects
High-quality filters, modulators, and creative audio effects
"""

import math
import struct
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from collections import deque
from enum import Enum

class FilterType(Enum):
    LOWPASS = "lowpass"
    HIGHPASS = "highpass"
    BANDPASS = "bandpass"
    BANDSTOP = "bandstop"
    ALLPASS = "allpass"
    PEAK = "peak"
    LOW_SHELF = "low_shelf"
    HIGH_SHELF = "high_shelf"

class WaveShape(Enum):
    SINE = "sine"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    SQUARE = "square"
    NOISE = "noise"

@dataclass
class FilterParameters:
    """Filter parameter set"""
    type: FilterType
    frequency: float
    q_factor: float = 1.0
    gain: float = 0.0  # For peak/shelf filters (dB)

@dataclass
class ModulationParameters:
    """Modulation parameter set"""
    rate: float  # Hz
    depth: float  # 0.0 - 1.0
    shape: WaveShape
    phase: float = 0.0

class BiquadFilter:
    """High-quality biquad filter implementation"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.reset()
    
    def reset(self):
        """Reset filter state"""
        self.x1 = self.x2 = 0.0
        self.y1 = self.y2 = 0.0
        self.b0 = self.b1 = self.b2 = 0.0
        self.a1 = self.a2 = 0.0
    
    def set_parameters(self, params: FilterParameters):
        """Set filter parameters and calculate coefficients"""
        freq = params.frequency
        q = params.q_factor
        gain = params.gain
        
        # Normalize frequency
        w = 2.0 * math.pi * freq / self.sample_rate
        cos_w = math.cos(w)
        sin_w = math.sin(w)
        alpha = sin_w / (2.0 * q)
        
        if params.type == FilterType.LOWPASS:
            self._set_lowpass(cos_w, alpha)
        elif params.type == FilterType.HIGHPASS:
            self._set_highpass(cos_w, alpha)
        elif params.type == FilterType.BANDPASS:
            self._set_bandpass(cos_w, alpha)
        elif params.type == FilterType.BANDSTOP:
            self._set_bandstop(cos_w, alpha)
        elif params.type == FilterType.ALLPASS:
            self._set_allpass(cos_w, alpha)
        elif params.type == FilterType.PEAK:
            self._set_peak(cos_w, sin_w, alpha, gain)
        elif params.type == FilterType.LOW_SHELF:
            self._set_low_shelf(cos_w, sin_w, alpha, gain)
        elif params.type == FilterType.HIGH_SHELF:
            self._set_high_shelf(cos_w, sin_w, alpha, gain)
    
    def _set_lowpass(self, cos_w: float, alpha: float):
        """Lowpass filter coefficients"""
        b0 = (1.0 - cos_w) / 2.0
        b1 = 1.0 - cos_w
        b2 = (1.0 - cos_w) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w
        a2 = 1.0 - alpha
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _set_highpass(self, cos_w: float, alpha: float):
        """Highpass filter coefficients"""
        b0 = (1.0 + cos_w) / 2.0
        b1 = -(1.0 + cos_w)
        b2 = (1.0 + cos_w) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w
        a2 = 1.0 - alpha
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _set_bandpass(self, cos_w: float, alpha: float):
        """Bandpass filter coefficients"""
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w
        a2 = 1.0 - alpha
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _set_bandstop(self, cos_w: float, alpha: float):
        """Bandstop (notch) filter coefficients"""
        b0 = 1.0
        b1 = -2.0 * cos_w
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w
        a2 = 1.0 - alpha
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _set_allpass(self, cos_w: float, alpha: float):
        """Allpass filter coefficients"""
        b0 = 1.0 - alpha
        b1 = -2.0 * cos_w
        b2 = 1.0 + alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w
        a2 = 1.0 - alpha
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _set_peak(self, cos_w: float, sin_w: float, alpha: float, gain_db: float):
        """Peak/notch filter coefficients"""
        A = math.pow(10, gain_db / 40.0)
        
        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w
        a2 = 1.0 - alpha / A
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _set_low_shelf(self, cos_w: float, sin_w: float, alpha: float, gain_db: float):
        """Low shelf filter coefficients"""
        A = math.pow(10, gain_db / 40.0)
        beta = math.sqrt(A) / 1.0  # Q = 1.0 for shelf
        
        b0 = A * ((A + 1) - (A - 1) * cos_w + beta * sin_w)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w)
        b2 = A * ((A + 1) - (A - 1) * cos_w - beta * sin_w)
        a0 = (A + 1) + (A - 1) * cos_w + beta * sin_w
        a1 = -2 * ((A - 1) + (A + 1) * cos_w)
        a2 = (A + 1) + (A - 1) * cos_w - beta * sin_w
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _set_high_shelf(self, cos_w: float, sin_w: float, alpha: float, gain_db: float):
        """High shelf filter coefficients"""
        A = math.pow(10, gain_db / 40.0)
        beta = math.sqrt(A) / 1.0  # Q = 1.0 for shelf
        
        b0 = A * ((A + 1) + (A - 1) * cos_w + beta * sin_w)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w)
        b2 = A * ((A + 1) + (A - 1) * cos_w - beta * sin_w)
        a0 = (A + 1) - (A - 1) * cos_w + beta * sin_w
        a1 = 2 * ((A - 1) - (A + 1) * cos_w)
        a2 = (A + 1) - (A - 1) * cos_w - beta * sin_w
        
        self._normalize_coefficients(b0, b1, b2, a0, a1, a2)
    
    def _normalize_coefficients(self, b0: float, b1: float, b2: float,
                               a0: float, a1: float, a2: float):
        """Normalize filter coefficients"""
        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0
    
    def process_sample(self, input_sample: float) -> float:
        """Process single sample through filter"""
        output = (self.b0 * input_sample + 
                 self.b1 * self.x1 + 
                 self.b2 * self.x2 - 
                 self.a1 * self.y1 - 
                 self.a2 * self.y2)
        
        # Update history
        self.x2 = self.x1
        self.x1 = input_sample
        self.y2 = self.y1
        self.y1 = output
        
        return output

class LFO:
    """Low Frequency Oscillator for modulation"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.phase = 0.0
        self.params = ModulationParameters(1.0, 0.5, WaveShape.SINE)
    
    def set_parameters(self, params: ModulationParameters):
        """Set LFO parameters"""
        self.params = params
        self.phase = params.phase
    
    def get_next_sample(self) -> float:
        """Get next modulation sample"""
        # Calculate phase increment
        phase_increment = 2.0 * math.pi * self.params.rate / self.sample_rate
        
        # Generate waveform
        if self.params.shape == WaveShape.SINE:
            value = math.sin(self.phase)
        elif self.params.shape == WaveShape.TRIANGLE:
            value = 2.0 * abs(2.0 * (self.phase / (2.0 * math.pi) - 0.5)) - 1.0
        elif self.params.shape == WaveShape.SAWTOOTH:
            value = 2.0 * (self.phase / (2.0 * math.pi)) - 1.0
        elif self.params.shape == WaveShape.SQUARE:
            value = 1.0 if math.sin(self.phase) >= 0 else -1.0
        elif self.params.shape == WaveShape.NOISE:
            import random
            value = 2.0 * random.random() - 1.0
        else:
            value = 0.0
        
        # Apply depth
        value *= self.params.depth
        
        # Update phase
        self.phase += phase_increment
        if self.phase >= 2.0 * math.pi:
            self.phase -= 2.0 * math.pi
        
        return value

class DelayLine:
    """Digital delay line with interpolation"""
    
    def __init__(self, max_delay_samples: int):
        self.buffer = [0.0] * max_delay_samples
        self.buffer_size = max_delay_samples
        self.write_index = 0
    
    def write_sample(self, sample: float):
        """Write sample to delay line"""
        self.buffer[self.write_index] = sample
        self.write_index = (self.write_index + 1) % self.buffer_size
    
    def read_sample(self, delay_samples: float) -> float:
        """Read sample with fractional delay (linear interpolation)"""
        # Calculate read position
        read_pos = self.write_index - delay_samples
        if read_pos < 0:
            read_pos += self.buffer_size
        
        # Linear interpolation
        index1 = int(read_pos) % self.buffer_size
        index2 = (index1 + 1) % self.buffer_size
        fraction = read_pos - int(read_pos)
        
        return (self.buffer[index1] * (1.0 - fraction) + 
                self.buffer[index2] * fraction)

class AdvancedDSPProcessor:
    """Advanced DSP effects processor"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        
        # Initialize effect components
        self.filters = {}
        self.lfos = {}
        self.delay_lines = {}
        
        # State variables
        self.compressor_envelope = 0.0
        self.gate_envelope = 0.0
        self.saturation_state = 0.0
        
    def apply_parametric_eq(self, samples: List[float], 
                           eq_bands: List[FilterParameters]) -> List[float]:
        """Apply parametric EQ with multiple bands"""
        if not eq_bands:
            return samples
        
        # Create filters for each band
        filters = []
        for i, band in enumerate(eq_bands):
            filter_id = f"eq_band_{i}"
            if filter_id not in self.filters:
                self.filters[filter_id] = BiquadFilter(self.sample_rate)
            
            self.filters[filter_id].set_parameters(band)
            filters.append(self.filters[filter_id])
        
        # Process samples through all EQ bands
        processed = []
        for sample in samples:
            output = sample
            for filter_obj in filters:
                output = filter_obj.process_sample(output)
            processed.append(output)
        
        return processed
    
    def apply_chorus(self, samples: List[float], 
                    rate: float = 0.5, depth: float = 0.003,
                    delay_ms: float = 20.0, feedback: float = 0.2,
                    mix: float = 0.5) -> List[float]:
        """Apply chorus effect"""
        # Initialize delay line and LFO
        delay_samples = int(delay_ms * self.sample_rate / 1000.0)
        max_delay = delay_samples + int(depth * self.sample_rate)
        
        if "chorus_delay" not in self.delay_lines:
            self.delay_lines["chorus_delay"] = DelayLine(max_delay * 2)
        
        if "chorus_lfo" not in self.lfos:
            self.lfos["chorus_lfo"] = LFO(self.sample_rate)
            self.lfos["chorus_lfo"].set_parameters(
                ModulationParameters(rate, depth, WaveShape.SINE)
            )
        
        delay_line = self.delay_lines["chorus_delay"]
        lfo = self.lfos["chorus_lfo"]
        
        processed = []
        for sample in samples:
            # Get modulated delay time
            mod_value = lfo.get_next_sample()
            variable_delay = delay_samples + mod_value * self.sample_rate
            
            # Read delayed sample
            delayed = delay_line.read_sample(variable_delay)
            
            # Apply feedback
            delay_input = sample + delayed * feedback
            delay_line.write_sample(delay_input)
            
            # Mix dry and wet signals
            output = sample * (1.0 - mix) + delayed * mix
            processed.append(output)
        
        return processed
    
    def apply_flanger(self, samples: List[float],
                     rate: float = 0.2, depth: float = 0.002,
                     delay_ms: float = 5.0, feedback: float = 0.7,
                     mix: float = 0.5) -> List[float]:
        """Apply flanger effect (short delay chorus)"""
        return self.apply_chorus(samples, rate, depth, delay_ms, feedback, mix)
    
    def apply_phaser(self, samples: List[float],
                    rate: float = 0.5, depth: float = 0.8,
                    stages: int = 4, feedback: float = 0.6,
                    mix: float = 0.5) -> List[float]:
        """Apply phaser effect using allpass filters"""
        # Create allpass filter chain
        filters = []
        for i in range(stages):
            filter_id = f"phaser_stage_{i}"
            if filter_id not in self.filters:
                self.filters[filter_id] = BiquadFilter(self.sample_rate)
            filters.append(self.filters[filter_id])
        
        # Create LFO for modulation
        if "phaser_lfo" not in self.lfos:
            self.lfos["phaser_lfo"] = LFO(self.sample_rate)
            self.lfos["phaser_lfo"].set_parameters(
                ModulationParameters(rate, depth, WaveShape.SINE)
            )
        
        lfo = self.lfos["phaser_lfo"]
        
        # Process samples
        processed = []
        for sample in samples:
            # Get modulated frequency
            mod_value = lfo.get_next_sample()
            center_freq = 1000.0  # Center frequency
            mod_freq = center_freq * (1.0 + mod_value * 0.5)
            
            # Update allpass filters
            for filter_obj in filters:
                params = FilterParameters(FilterType.ALLPASS, mod_freq, 0.707)
                filter_obj.set_parameters(params)
            
            # Process through allpass chain
            filtered = sample
            for filter_obj in filters:
                filtered = filter_obj.process_sample(filtered)
            
            # Apply feedback
            output_with_feedback = sample + filtered * feedback
            
            # Mix dry and wet
            output = sample * (1.0 - mix) + output_with_feedback * mix
            processed.append(output)
        
        return processed
    
    def apply_multiband_compressor(self, samples: List[float],
                                  bands: List[Tuple[float, float, float, float]]) -> List[float]:
        """
        Apply multiband compression
        bands: List of (freq, threshold, ratio, attack_ms, release_ms)
        """
        if not bands:
            return samples
        
        # Split into frequency bands
        band_signals = []
        crossover_freqs = [band[0] for band in bands[1:]]  # Skip first band frequency
        
        # Create bandpass/lowpass/highpass filters for each band
        for i, (freq, threshold, ratio, attack_ms, release_ms) in enumerate(bands):
            filter_id = f"multiband_{i}"
            
            if i == 0:  # First band - lowpass
                if len(bands) > 1:
                    filter_params = FilterParameters(FilterType.LOWPASS, crossover_freqs[0], 0.707)
                else:
                    # Single band - no filtering
                    band_signals.append(samples[:])
                    continue
            elif i == len(bands) - 1:  # Last band - highpass
                filter_params = FilterParameters(FilterType.HIGHPASS, freq, 0.707)
            else:  # Middle bands - bandpass
                # This is simplified - real multiband would use more sophisticated crossovers
                filter_params = FilterParameters(FilterType.BANDPASS, freq, 1.0)
            
            if filter_id not in self.filters:
                self.filters[filter_id] = BiquadFilter(self.sample_rate)
            
            self.filters[filter_id].set_parameters(filter_params)
            
            # Filter the signal
            band_signal = []
            for sample in samples:
                filtered = self.filters[filter_id].process_sample(sample)
                band_signal.append(filtered)
            
            # Apply compression to this band
            compressed_band = self._apply_compressor(
                band_signal, threshold, ratio, attack_ms, release_ms
            )
            band_signals.append(compressed_band)
        
        # Sum all bands
        processed = []
        for i in range(len(samples)):
            output = sum(band[i] for band in band_signals if i < len(band))
            processed.append(output)
        
        return processed
    
    def _apply_compressor(self, samples: List[float], 
                         threshold: float, ratio: float,
                         attack_ms: float, release_ms: float) -> List[float]:
        """Apply dynamic range compression"""
        attack_coeff = math.exp(-1.0 / (attack_ms * self.sample_rate / 1000.0))
        release_coeff = math.exp(-1.0 / (release_ms * self.sample_rate / 1000.0))
        
        envelope = 0.0
        processed = []
        
        for sample in samples:
            # Envelope follower
            level = abs(sample)
            if level > envelope:
                envelope = level + (envelope - level) * attack_coeff
            else:
                envelope = level + (envelope - level) * release_coeff
            
            # Calculate gain reduction
            if envelope > threshold:
                gain_reduction = threshold + (envelope - threshold) / ratio
                gain = gain_reduction / envelope if envelope > 0 else 1.0
            else:
                gain = 1.0
            
            # Apply gain
            output = sample * gain
            processed.append(output)
        
        return processed
    
    def apply_tube_saturation(self, samples: List[float],
                             drive: float = 2.0, bias: float = 0.0,
                             tone: float = 0.5) -> List[float]:
        """Apply analog tube saturation"""
        processed = []
        
        for sample in samples:
            # Apply drive
            driven = sample * drive + bias
            
            # Tube saturation curve (hyperbolic tangent)
            saturated = math.tanh(driven)
            
            # Apply tone control (simple high-frequency roll-off)
            self.saturation_state = (saturated * tone + 
                                   self.saturation_state * (1.0 - tone))
            
            processed.append(self.saturation_state)
        
        return processed
    
    def apply_bitcrusher(self, samples: List[float],
                        bit_depth: int = 8, sample_rate_reduction: int = 4) -> List[float]:
        """Apply bitcrusher effect"""
        max_value = (2 ** (bit_depth - 1)) - 1
        
        processed = []
        counter = 0
        last_quantized = 0.0
        
        for sample in samples:
            # Sample rate reduction
            if counter % sample_rate_reduction == 0:
                # Bit depth reduction
                quantized = round(sample * max_value) / max_value
                quantized = max(-1.0, min(1.0, quantized))
                last_quantized = quantized
            
            processed.append(last_quantized)
            counter += 1
        
        return processed
    
    def apply_ring_modulator(self, samples: List[float],
                           frequency: float = 100.0, depth: float = 1.0) -> List[float]:
        """Apply ring modulation effect"""
        processed = []
        phase = 0.0
        phase_increment = 2.0 * math.pi * frequency / self.sample_rate
        
        for sample in samples:
            # Generate carrier wave
            carrier = math.sin(phase) * depth
            
            # Ring modulation (multiplication)
            modulated = sample * (1.0 + carrier)
            
            processed.append(modulated)
            
            # Update phase
            phase += phase_increment
            if phase >= 2.0 * math.pi:
                phase -= 2.0 * math.pi
        
        return processed
    
    def apply_vocoder(self, carrier: List[float], modulator: List[float],
                     bands: int = 16) -> List[float]:
        """Simple vocoder implementation"""
        if len(carrier) != len(modulator):
            min_len = min(len(carrier), len(modulator))
            carrier = carrier[:min_len]
            modulator = modulator[:min_len]
        
        # Create band filters
        freq_min = 100.0
        freq_max = 8000.0
        
        carrier_bands = []
        modulator_bands = []
        
        for i in range(bands):
            # Logarithmic frequency spacing
            freq = freq_min * math.pow(freq_max / freq_min, i / (bands - 1))
            bandwidth = freq * 0.2  # 20% bandwidth
            
            # Create bandpass filters
            carrier_filter = BiquadFilter(self.sample_rate)
            modulator_filter = BiquadFilter(self.sample_rate)
            
            params = FilterParameters(FilterType.BANDPASS, freq, freq / bandwidth)
            carrier_filter.set_parameters(params)
            modulator_filter.set_parameters(params)
            
            # Filter signals
            carrier_band = [carrier_filter.process_sample(s) for s in carrier]
            modulator_band = [modulator_filter.process_sample(s) for s in modulator]
            
            carrier_bands.append(carrier_band)
            modulator_bands.append(modulator_band)
        
        # Apply envelope following and mixing
        processed = [0.0] * len(carrier)
        
        for band_idx in range(bands):
            carrier_band = carrier_bands[band_idx]
            modulator_band = modulator_bands[band_idx]
            
            envelope = 0.0
            envelope_coeff = 0.99  # Envelope follower coefficient
            
            for i in range(len(carrier_band)):
                # Extract envelope from modulator
                mod_level = abs(modulator_band[i])
                envelope = mod_level + (envelope - mod_level) * envelope_coeff
                
                # Apply envelope to carrier
                vocoded = carrier_band[i] * envelope
                processed[i] += vocoded / bands  # Mix and normalize
        
        return processed

def apply_advanced_effect(audio_data: bytes, effect_type: str, 
                         parameters: Dict[str, Any], 
                         sample_rate: int = 44100) -> bytes:
    """High-level function to apply advanced DSP effects"""
    
    # Convert bytes to samples
    samples = []
    for i in range(0, len(audio_data) - 1, 2):
        sample = struct.unpack('<h', audio_data[i:i+2])[0] / 32768.0
        samples.append(sample)
    
    if not samples:
        return audio_data
    
    # Create processor
    processor = AdvancedDSPProcessor(sample_rate)
    
    # Apply effect
    if effect_type == 'parametric_eq':
        bands = []
        for band_params in parameters.get('bands', []):
            filter_type = FilterType(band_params.get('type', 'peak'))
            freq = band_params.get('frequency', 1000.0)
            q = band_params.get('q', 1.0)
            gain = band_params.get('gain', 0.0)
            bands.append(FilterParameters(filter_type, freq, q, gain))
        
        processed = processor.apply_parametric_eq(samples, bands)
    
    elif effect_type == 'chorus':
        processed = processor.apply_chorus(
            samples,
            rate=parameters.get('rate', 0.5),
            depth=parameters.get('depth', 0.003),
            delay_ms=parameters.get('delay_ms', 20.0),
            feedback=parameters.get('feedback', 0.2),
            mix=parameters.get('mix', 0.5)
        )
    
    elif effect_type == 'flanger':
        processed = processor.apply_flanger(
            samples,
            rate=parameters.get('rate', 0.2),
            depth=parameters.get('depth', 0.002),
            delay_ms=parameters.get('delay_ms', 5.0),
            feedback=parameters.get('feedback', 0.7),
            mix=parameters.get('mix', 0.5)
        )
    
    elif effect_type == 'phaser':
        processed = processor.apply_phaser(
            samples,
            rate=parameters.get('rate', 0.5),
            depth=parameters.get('depth', 0.8),
            stages=parameters.get('stages', 4),
            feedback=parameters.get('feedback', 0.6),
            mix=parameters.get('mix', 0.5)
        )
    
    elif effect_type == 'tube_saturation':
        processed = processor.apply_tube_saturation(
            samples,
            drive=parameters.get('drive', 2.0),
            bias=parameters.get('bias', 0.0),
            tone=parameters.get('tone', 0.5)
        )
    
    elif effect_type == 'bitcrusher':
        processed = processor.apply_bitcrusher(
            samples,
            bit_depth=parameters.get('bit_depth', 8),
            sample_rate_reduction=parameters.get('sample_rate_reduction', 4)
        )
    
    elif effect_type == 'ring_modulator':
        processed = processor.apply_ring_modulator(
            samples,
            frequency=parameters.get('frequency', 100.0),
            depth=parameters.get('depth', 1.0)
        )
    
    else:
        print(f"Unknown effect type: {effect_type}")
        processed = samples
    
    # Convert back to bytes
    output = b''
    for sample in processed:
        sample = max(-1.0, min(1.0, sample))
        sample_int = int(sample * 32767)
        output += struct.pack('<h', sample_int)
    
    return output

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 4:
        print("Usage:")
        print("  python advanced_dsp.py <effect> <input.wav> <output.wav> [parameters]")
        print("\nAvailable effects:")
        print("  chorus, flanger, phaser, tube_saturation, bitcrusher, ring_modulator")
        print("\nExample:")
        print("  python advanced_dsp.py chorus input.wav output.wav rate=0.3 depth=0.005 mix=0.7")
        sys.exit(1)
    
    effect_type = sys.argv[1]
    input_file = sys.argv[2]
    output_file = sys.argv[3]
    
    # Parse parameters
    parameters = {}
    for arg in sys.argv[4:]:
        if '=' in arg:
            key, value = arg.split('=', 1)
            try:
                # Try to convert to float
                parameters[key] = float(value)
            except ValueError:
                # Keep as string
                parameters[key] = value
    
    try:
        import wave
        
        # Load audio
        with wave.open(input_file, 'rb') as wav_in:
            params = wav_in.getparams()
            audio_data = wav_in.readframes(params.nframes)
            sample_rate = params.framerate
        
        print(f"Applying {effect_type} effect...")
        if parameters:
            print(f"Parameters: {parameters}")
        
        # Apply effect
        processed_data = apply_advanced_effect(audio_data, effect_type, parameters, sample_rate)
        
        # Save result
        with wave.open(output_file, 'wb') as wav_out:
            wav_out.setparams(params)
            wav_out.writeframes(processed_data)
        
        print(f"Effect applied successfully: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")