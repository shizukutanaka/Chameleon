"""
SimpleGain Plugin for Chameleon Audio Processing System
Generated plugin template
"""

from typing import List, Dict, Any
from plugin_system import AudioEffectPlugin, PluginMetadata

class SimpleGainPlugin(AudioEffectPlugin):
    """
    SimpleGain - A Chameleon audio processing plugin
    """

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="SimpleGain",
            version="1.0.0",
            author="Plugin Developer",
            description="Description of SimpleGain plugin",
            category="effect",
            tags=["effect", "audio"],
            parameters={
                "gain": {
                    "type": "float",
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "description": "Gain level"
                }
            }
        )

    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin"""
        self.logger.info(f"Initializing {self.get_metadata().name} plugin")
        # TODO: Add initialization code here
        return True

    def cleanup(self):
        """Cleanup plugin resources"""
        self.logger.info(f"Cleaning up {self.get_metadata().name} plugin")
        # TODO: Add cleanup code here
        pass

    def process_audio(self, audio_data: List[float], sample_rate: int, **params) -> List[float]:
        """Process audio data"""
        # TODO: Implement your audio effect here
        # Example: simple gain
        # The metadata advertises gain 0.0..2.0 but the value used to be
        # applied unchecked: gain=100 overdrove the signal, gain=-1
        # silently phase-inverted it, and a non-number died on TypeError.
        gain = params.get('gain', 1.0)
        if not isinstance(gain, (int, float)):
            raise ValueError(f"gain must be a number, got {gain!r}")
        if not 0.0 <= gain <= 2.0:
            raise ValueError(f"gain {gain} outside advertised range 0.0-2.0")
        return [sample * gain for sample in audio_data]

# Plugin entry point
def create_plugin():
    return SimpleGainPlugin()
