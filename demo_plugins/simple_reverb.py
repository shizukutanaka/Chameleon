"""
Simple Reverb Plugin for Chameleon Audio Processing System
Demonstrates audio effect plugin implementation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Dict, Any
from plugin_system import AudioEffectPlugin, PluginMetadata

class SimpleReverbPlugin(AudioEffectPlugin):
    """
    Simple reverb effect using delay lines
    """

    def __init__(self):
        super().__init__()
        self.delay_buffer: List[float] = []
        self.buffer_size = 0

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="SimpleReverb",
            version="1.0.0",
            author="Chameleon Team",
            description="Simple reverb effect with adjustable room size and decay",
            category="effect",
            tags=["reverb", "effect", "audio"],
            parameters={
                "room_size": {
                    "type": "float",
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "description": "Room size (0=small, 1=large)"
                },
                "decay": {
                    "type": "float",
                    "default": 0.3,
                    "min": 0.0,
                    "max": 0.9,
                    "description": "Decay amount"
                },
                "wet_level": {
                    "type": "float",
                    "default": 0.3,
                    "min": 0.0,
                    "max": 1.0,
                    "description": "Wet signal level"
                }
            }
        )

    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the reverb plugin"""
        self.logger.info("Initializing SimpleReverb plugin")

        # Initialize delay buffer (simple reverb approximation)
        self.buffer_size = 8820  # ~200ms at 44.1kHz
        self.delay_buffer = [0.0] * self.buffer_size
        self.buffer_index = 0

        return True

    def cleanup(self):
        """Cleanup plugin resources"""
        self.logger.info("Cleaning up SimpleReverb plugin")
        self.delay_buffer.clear()

    def process_audio(self, audio_data: List[float], sample_rate: int, **params) -> List[float]:
        """Process audio data with reverb effect"""
        room_size = params.get('room_size', 0.5)
        decay = params.get('decay', 0.3)
        wet_level = params.get('wet_level', 0.3)

        # Adjust buffer size based on room size
        delay_samples = int(room_size * self.buffer_size)
        if delay_samples == 0:
            delay_samples = 1

        output = []

        for sample in audio_data:
            # Get delayed sample
            delay_index = (self.buffer_index - delay_samples) % len(self.delay_buffer)
            delayed_sample = self.delay_buffer[delay_index]

            # Apply feedback
            feedback_sample = sample + (delayed_sample * decay)

            # Store in delay buffer
            self.delay_buffer[self.buffer_index] = feedback_sample
            self.buffer_index = (self.buffer_index + 1) % len(self.delay_buffer)

            # Mix wet and dry signals
            wet_signal = delayed_sample * wet_level
            dry_signal = sample * (1.0 - wet_level)
            output_sample = dry_signal + wet_signal

            # Prevent clipping
            output_sample = max(-1.0, min(1.0, output_sample))
            output.append(output_sample)

        return output

def create_plugin():
    return SimpleReverbPlugin()