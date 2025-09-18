#!/usr/bin/env python3
"""
Audio Effects Module - Practical DSP effects
"""

import array
import math
from typing import Optional, Tuple

class AudioEffects:
    """Collection of practical audio effects"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.max_int16 = 32767

    # NOTE: Echo effect has been integrated into chameleon.py AudioProcessor.apply_echo()

    def chorus(self, samples: array.array, depth_ms: float = 3,
               rate_hz: float = 1.5) -> array.array:
        """Add chorus effect (simple delay modulation)"""
        result = array.array('h')
        depth_samples = int((depth_ms / 1000) * self.sample_rate)

        for i in range(len(samples)):
            # Calculate modulated delay
            mod = math.sin(2 * math.pi * rate_hz * i / self.sample_rate)
            delay = int(depth_samples * (1 + mod) / 2)

            # Get delayed sample
            if i - delay >= 0:
                mixed = (samples[i] + samples[i - delay]) // 2
            else:
                mixed = samples[i]

            result.append(max(min(mixed, self.max_int16), -self.max_int16))

        return result

    def distortion(self, samples: array.array, drive: float = 0.5) -> array.array:
        """Add distortion (soft clipping)"""
        result = array.array('h')
        threshold = self.max_int16 * (1 - drive)

        for s in samples:
            if abs(s) < threshold:
                result.append(s)
            else:
                # Soft clipping using tanh-like curve
                sign = 1 if s > 0 else -1
                clipped = threshold + (self.max_int16 - threshold) * math.tanh(
                    (abs(s) - threshold) / (self.max_int16 - threshold)
                )
                result.append(int(sign * clipped))

        return result

    # NOTE: Low-pass filter has been integrated into chameleon.py AudioProcessor.apply_low_pass_filter()

    def high_pass_filter(self, samples: array.array, cutoff_hz: float = 100) -> array.array:
        """Simple high-pass filter (first-order)"""
        result = array.array('h')
        rc = 1.0 / (2 * math.pi * cutoff_hz)
        dt = 1.0 / self.sample_rate
        alpha = rc / (rc + dt)

        prev_input = 0
        prev_output = 0

        for s in samples:
            filtered = alpha * (prev_output + s - prev_input)
            prev_input = s
            prev_output = filtered
            result.append(int(filtered))

        return result

    # NOTE: Compressor has been integrated into chameleon.py AudioProcessor.apply_compressor()

    def tremolo(self, samples: array.array, rate_hz: float = 5,
                depth: float = 0.5) -> array.array:
        """Tremolo effect (amplitude modulation)"""
        result = array.array('h')

        for i, s in enumerate(samples):
            # Generate LFO
            lfo = (1 + depth * math.sin(2 * math.pi * rate_hz * i / self.sample_rate)) / 2
            modulated = int(s * (1 - depth + depth * lfo))
            result.append(max(min(modulated, self.max_int16), -self.max_int16))

        return result

    def pitch_shift(self, samples: array.array, semitones: float) -> array.array:
        """Simple pitch shifting by resampling"""
        # Calculate speed factor from semitones
        factor = 2 ** (semitones / 12)

        # Resample
        result = array.array('h')
        for i in range(int(len(samples) / factor)):
            pos = i * factor
            idx = int(pos)
            frac = pos - idx

            if idx + 1 < len(samples):
                # Linear interpolation
                sample = samples[idx] * (1 - frac) + samples[idx + 1] * frac
            else:
                sample = samples[min(idx, len(samples) - 1)]

            result.append(int(sample))

        return result

    def noise_gate(self, samples: array.array, threshold_db: float = -40,
                   attack_ms: float = 1, release_ms: float = 100) -> array.array:
        """Noise gate to remove low-level noise"""
        result = array.array('h')
        threshold = self.max_int16 * (10 ** (threshold_db / 20))

        attack_samples = int((attack_ms / 1000) * self.sample_rate)
        release_samples = int((release_ms / 1000) * self.sample_rate)

        gate_open = False
        gate_level = 0.0

        for s in samples:
            abs_sample = abs(s)

            if abs_sample > threshold:
                # Open gate
                if not gate_open:
                    gate_open = True
                # Attack
                if gate_level < 1.0:
                    gate_level = min(1.0, gate_level + 1.0 / attack_samples)
            else:
                # Close gate
                if gate_open:
                    # Release
                    gate_level = max(0.0, gate_level - 1.0 / release_samples)
                    if gate_level == 0:
                        gate_open = False

            result.append(int(s * gate_level))

        return result

    def auto_gain(self, samples: array.array, target_rms: float = 0.2) -> array.array:
        """Automatic gain control to reach target RMS level"""
        if not samples:
            return samples

        # Calculate current RMS
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        if rms == 0:
            return samples

        # Calculate gain needed
        target_linear = target_rms * self.max_int16
        gain = target_linear / rms

        # Apply with limiting
        result = array.array('h')
        for s in samples:
            adjusted = int(s * gain)
            result.append(max(min(adjusted, self.max_int16), -self.max_int16))

        return result