"""
MyGenerator Plugin for Chameleon Audio Processing System
Generated plugin template
"""

from typing import List, Dict, Any
from plugin_system import AudioGeneratorPlugin, PluginMetadata

class MyGeneratorPlugin(AudioGeneratorPlugin):
    """
    MyGenerator - A Chameleon audio processing plugin
    """

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="MyGenerator",
            version="1.0.0",
            author="Plugin Developer",
            description="Description of MyGenerator plugin",
            category="generator",
            tags=["generator", "audio"],
            parameters={
                "frequency": {
                    "type": "float",
                    "default": 440.0,
                    "min": 20.0,
                    "max": 20000.0,
                    "description": "Tone frequency in Hz"
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

    def generate_audio(self, duration: float, sample_rate: int, **params) -> List[float]:
        """Generate audio data"""
        # TODO: Implement your audio generator here
        # Example: sine wave, enforcing the range it advertises
        import math
        frequency = params.get('frequency', 440.0)
        if not isinstance(frequency, (int, float)) or not 20.0 <= frequency <= 20000.0:
            raise ValueError(f"frequency must be in 20-20000 Hz, got {frequency!r}")
        samples = []
        for i in range(int(duration * sample_rate)):
            t = i / sample_rate
            sample = math.sin(2 * math.pi * frequency * t)
            samples.append(sample)
        return samples

# Plugin entry point
def create_plugin():
    return MyGeneratorPlugin()
