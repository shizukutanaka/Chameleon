#!/usr/bin/env python3
"""
Real-time Audio Effects Processing
Low-latency effect chains with modular architecture
"""

import warnings
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
import numpy as np
from collections import deque
import threading
import queue

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    warnings.warn("PyAudio not installed. Real-time processing disabled.")

try:
    import scipy.signal as signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

@dataclass
class EffectParameters:
    """Parameters for audio effects"""
    enabled: bool = True
    mix: float = 1.0  # Dry/wet mix (0=dry, 1=wet)
    params: Dict[str, Any] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}

class AudioEffect(ABC):
    """Base class for audio effects"""

    def __init__(self, name: str):
        self.name = name
        self.sample_rate = 44100
        self.bypass = False

    @abstractmethod
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio through effect"""
        pass

    def initialize(self, sample_rate: int) -> None:
        """Initialize effect with sample rate"""
        self.sample_rate = sample_rate

    def reset(self) -> None:
        """Reset effect state"""
        pass

class Delay(AudioEffect):
    """Delay effect with feedback"""

    def __init__(self, delay_time: float = 0.25, feedback: float = 0.5, mix: float = 0.5):
        super().__init__("Delay")
        self.delay_time = delay_time
        self.feedback = feedback
        self.mix = mix
        self.buffer = None
        self.buffer_size = 0
        self.write_index = 0

    def initialize(self, sample_rate: int) -> None:
        super().initialize(sample_rate)
        self.buffer_size = int(self.delay_time * sample_rate)
        self.buffer = np.zeros(self.buffer_size)
        self.write_index = 0

    def process(self, audio: np.ndarray) -> np.ndarray:
        if self.buffer is None:
            self.initialize(self.sample_rate)

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Read from delay buffer
            read_index = (self.write_index - self.buffer_size + i) % self.buffer_size
            delayed = self.buffer[read_index]

            # Mix and feedback
            output[i] = audio[i] * (1 - self.mix) + delayed * self.mix
            self.buffer[self.write_index] = audio[i] + delayed * self.feedback

            self.write_index = (self.write_index + 1) % self.buffer_size

        return output

class Reverb(AudioEffect):
    """Algorithmic reverb using comb and allpass filters"""

    def __init__(self, room_size: float = 0.5, damping: float = 0.5, mix: float = 0.3):
        super().__init__("Reverb")
        self.room_size = room_size
        self.damping = damping
        self.mix = mix
        self.comb_delays = []
        self.allpass_delays = []

    def initialize(self, sample_rate: int) -> None:
        super().initialize(sample_rate)

        # Comb filter delays (in samples)
        comb_times = [0.0297, 0.0371, 0.0411, 0.0437]
        self.comb_delays = []
        for time in comb_times:
            delay_samples = int(time * sample_rate * (0.5 + self.room_size))
            self.comb_delays.append({
                'buffer': np.zeros(delay_samples),
                'index': 0,
                'size': delay_samples
            })

        # Allpass filter delays
        allpass_times = [0.005, 0.0017]
        self.allpass_delays = []
        for time in allpass_times:
            delay_samples = int(time * sample_rate)
            self.allpass_delays.append({
                'buffer': np.zeros(delay_samples),
                'index': 0,
                'size': delay_samples
            })

    def process(self, audio: np.ndarray) -> np.ndarray:
        if not self.comb_delays:
            self.initialize(self.sample_rate)

        output = np.zeros_like(audio)

        # Process through parallel comb filters
        comb_output = np.zeros_like(audio)
        for comb in self.comb_delays:
            for i in range(len(audio)):
                delayed = comb['buffer'][comb['index']]
                comb['buffer'][comb['index']] = audio[i] + delayed * (1 - self.damping)
                comb_output[i] += delayed
                comb['index'] = (comb['index'] + 1) % comb['size']

        comb_output /= len(self.comb_delays)

        # Process through series allpass filters
        allpass_output = comb_output.copy()
        for allpass in self.allpass_delays:
            temp = np.zeros_like(audio)
            for i in range(len(allpass_output)):
                delayed = allpass['buffer'][allpass['index']]
                temp[i] = -allpass_output[i] + delayed
                allpass['buffer'][allpass['index']] = allpass_output[i] + delayed * 0.5
                allpass['index'] = (allpass['index'] + 1) % allpass['size']
            allpass_output = temp

        # Mix dry and wet
        return audio * (1 - self.mix) + allpass_output * self.mix

class Compressor(AudioEffect):
    """Dynamic range compressor"""

    def __init__(self, threshold: float = -20, ratio: float = 4, attack: float = 0.003, release: float = 0.1):
        super().__init__("Compressor")
        self.threshold_db = threshold
        self.ratio = ratio
        self.attack = attack
        self.release = release
        self.envelope = 0

    def process(self, audio: np.ndarray) -> np.ndarray:
        threshold_linear = 10 ** (self.threshold_db / 20)
        attack_coeff = np.exp(-1 / (self.attack * self.sample_rate))
        release_coeff = np.exp(-1 / (self.release * self.sample_rate))

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            input_level = abs(audio[i])

            # Envelope follower
            if input_level > self.envelope:
                self.envelope = input_level + (self.envelope - input_level) * attack_coeff
            else:
                self.envelope = input_level + (self.envelope - input_level) * release_coeff

            # Calculate gain reduction
            if self.envelope > threshold_linear:
                gain_db = (self.threshold_db - 20 * np.log10(self.envelope)) * (1 - 1/self.ratio)
                gain = 10 ** (gain_db / 20)
            else:
                gain = 1.0

            output[i] = audio[i] * gain

        return output

class Distortion(AudioEffect):
    """Distortion/overdrive effect"""

    def __init__(self, drive: float = 0.5, tone: float = 0.5, level: float = 0.7):
        super().__init__("Distortion")
        self.drive = drive
        self.tone = tone
        self.level = level

    def process(self, audio: np.ndarray) -> np.ndarray:
        # Pre-gain
        driven = audio * (1 + self.drive * 10)

        # Soft clipping
        output = np.tanh(driven * 0.7) / 0.7

        # Tone control (simple high-shelf filter)
        if HAS_SCIPY and self.tone != 0.5:
            # High-shelf filter
            freq = 1000 + self.tone * 3000
            sos = signal.butter(2, freq, btype='high', fs=self.sample_rate, output='sos')
            high_freq = signal.sosfilt(sos, output)
            output = output * (1 - self.tone) + high_freq * self.tone

        return output * self.level

class Chorus(AudioEffect):
    """Chorus effect using modulated delays"""

    def __init__(self, depth: float = 0.5, rate: float = 1.5, mix: float = 0.5):
        super().__init__("Chorus")
        self.depth = depth
        self.rate = rate
        self.mix = mix
        self.lfo_phase = 0
        self.delay_buffer = None

    def initialize(self, sample_rate: int) -> None:
        super().initialize(sample_rate)
        max_delay = 0.03  # 30ms max delay
        self.buffer_size = int(max_delay * sample_rate)
        self.delay_buffer = np.zeros(self.buffer_size)
        self.write_index = 0

    def process(self, audio: np.ndarray) -> np.ndarray:
        if self.delay_buffer is None:
            self.initialize(self.sample_rate)

        output = np.zeros_like(audio)
        lfo_increment = 2 * np.pi * self.rate / self.sample_rate

        for i in range(len(audio)):
            # LFO for delay modulation
            lfo = np.sin(self.lfo_phase)
            self.lfo_phase += lfo_increment
            if self.lfo_phase > 2 * np.pi:
                self.lfo_phase -= 2 * np.pi

            # Calculate delay time
            delay_samples = int((0.01 + 0.01 * self.depth * lfo) * self.sample_rate)
            read_index = (self.write_index - delay_samples) % self.buffer_size

            # Linear interpolation for smooth delay
            frac = delay_samples - int(delay_samples)
            idx1 = read_index
            idx2 = (read_index + 1) % self.buffer_size
            delayed = self.delay_buffer[idx1] * (1 - frac) + self.delay_buffer[idx2] * frac

            # Write to buffer
            self.delay_buffer[self.write_index] = audio[i]
            self.write_index = (self.write_index + 1) % self.buffer_size

            # Mix
            output[i] = audio[i] * (1 - self.mix) + delayed * self.mix

        return output

class Phaser(AudioEffect):
    """Phaser effect using allpass filters"""

    def __init__(self, rate: float = 0.5, depth: float = 1.0, feedback: float = 0.7):
        super().__init__("Phaser")
        self.rate = rate
        self.depth = depth
        self.feedback = feedback
        self.lfo_phase = 0
        self.allpass_state = np.zeros(4)  # 4-stage phaser

    def process(self, audio: np.ndarray) -> np.ndarray:
        output = np.zeros_like(audio)
        lfo_increment = 2 * np.pi * self.rate / self.sample_rate

        for i in range(len(audio)):
            # LFO
            lfo = np.sin(self.lfo_phase)
            self.lfo_phase += lfo_increment
            if self.lfo_phase > 2 * np.pi:
                self.lfo_phase -= 2 * np.pi

            # Allpass coefficient
            coeff = (1 - self.depth * (lfo + 1) / 2) * 0.9

            # Process through allpass stages
            signal_in = audio[i] + output[i-1] * self.feedback if i > 0 else audio[i]

            for stage in range(4):
                temp = signal_in - coeff * self.allpass_state[stage]
                self.allpass_state[stage] = temp * coeff + self.allpass_state[stage]
                signal_in = self.allpass_state[stage]

            output[i] = signal_in

        return (audio + output) * 0.5

class EffectChain:
    """Chain multiple effects together"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.effects: List[AudioEffect] = []
        self.bypass = False

    def add_effect(self, effect: AudioEffect) -> None:
        """Add effect to chain"""
        effect.initialize(self.sample_rate)
        self.effects.append(effect)

    def remove_effect(self, name: str) -> None:
        """Remove effect by name"""
        self.effects = [e for e in self.effects if e.name != name]

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio through effect chain"""
        if self.bypass:
            return audio

        result = audio.copy()
        for effect in self.effects:
            if not effect.bypass:
                result = effect.process(result)

        return result

    def reset(self) -> None:
        """Reset all effects"""
        for effect in self.effects:
            effect.reset()

class RealtimeProcessor:
    """Real-time audio processor with effect chains"""

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 512):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.effect_chain = EffectChain(sample_rate)
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.processing = False
        self.stream = None

    def start(self) -> None:
        """Start real-time processing"""
        if not HAS_PYAUDIO:
            raise RuntimeError("PyAudio not available")

        self.processing = True
        p = pyaudio.PyAudio()

        def audio_callback(in_data, frame_count, time_info, status):
            # Convert input to numpy
            audio = np.frombuffer(in_data, dtype=np.float32)

            # Process through effect chain
            processed = self.effect_chain.process(audio)

            # Convert back to bytes
            output = processed.astype(np.float32).tobytes()

            return (output, pyaudio.paContinue)

        self.stream = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            output=True,
            frames_per_buffer=self.buffer_size,
            stream_callback=audio_callback
        )

        self.stream.start_stream()

    def stop(self) -> None:
        """Stop real-time processing"""
        self.processing = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

    def add_effect(self, effect: AudioEffect) -> None:
        """Add effect to processing chain"""
        self.effect_chain.add_effect(effect)

# Example usage
if __name__ == "__main__":
    print("Real-time Audio Effects Processor")

    # Create effect chain
    chain = EffectChain()

    # Add effects
    chain.add_effect(Compressor(threshold=-15, ratio=3))
    chain.add_effect(Distortion(drive=0.3, tone=0.6))
    chain.add_effect(Delay(delay_time=0.375, feedback=0.4, mix=0.3))
    chain.add_effect(Reverb(room_size=0.7, damping=0.5, mix=0.2))

    print(f"Effect chain created with {len(chain.effects)} effects")
    print("Effects:", [e.name for e in chain.effects])