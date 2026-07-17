"""
Tone Generator Plugin for Chameleon Audio Processing System
Demonstrates audio generator plugin implementation
"""

import math
from typing import List, Dict, Any
from plugin_system import AudioGeneratorPlugin, PluginMetadata

class ToneGeneratorPlugin(AudioGeneratorPlugin):
    """
    Multi-waveform tone generator
    """

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ToneGenerator",
            version="1.0.0",
            author="Chameleon Team",
            description="Multi-waveform tone generator with sine, square, sawtooth, and triangle waves",
            category="generator",
            tags=["generator", "tone", "oscillator"],
            parameters={
                "frequency": {
                    "type": "float",
                    "default": 440.0,
                    "min": 20.0,
                    "max": 20000.0,
                    "description": "Frequency in Hz"
                },
                "waveform": {
                    "type": "string",
                    "default": "sine",
                    "options": ["sine", "square", "sawtooth", "triangle"],
                    "description": "Waveform type"
                },
                "amplitude": {
                    "type": "float",
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "description": "Amplitude (0-1)"
                },
                "phase": {
                    "type": "float",
                    "default": 0.0,
                    "min": 0.0,
                    "max": 360.0,
                    "description": "Phase offset in degrees"
                }
            }
        )

    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the tone generator"""
        self.logger.info("Initializing ToneGenerator plugin")
        return True

    def cleanup(self):
        """Cleanup plugin resources"""
        self.logger.info("Cleaning up ToneGenerator plugin")

    def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
        """Generate audio tone"""
        frequency = params.get('frequency', 440.0)
        waveform = params.get('waveform', 'sine')
        amplitude = params.get('amplitude', 0.5)
        phase_degrees = params.get('phase', 0.0)

        # Convert phase to radians
        phase = math.radians(phase_degrees)

        samples = []
        num_samples = int(duration * sample_rate)

        for i in range(num_samples):
            t = i / sample_rate
            angle = 2 * math.pi * frequency * t + phase

            if waveform == 'sine':
                sample = math.sin(angle)
            elif waveform == 'square':
                sample = 1.0 if math.sin(angle) >= 0 else -1.0
            elif waveform == 'sawtooth':
                # Sawtooth from -1 to 1
                sample = 2.0 * (angle / (2 * math.pi) % 1.0) - 1.0
            elif waveform == 'triangle':
                # Triangle wave
                normalized = (angle / (2 * math.pi)) % 1.0
                if normalized < 0.5:
                    sample = 4.0 * normalized - 1.0
                else:
                    sample = 3.0 - 4.0 * normalized
            else:
                sample = math.sin(angle)  # Default to sine

            # Apply amplitude
            sample *= amplitude

            # Prevent clipping
            sample = max(-1.0, min(1.0, sample))
            samples.append(sample)

        return samples

def create_plugin():
    return ToneGeneratorPlugin()