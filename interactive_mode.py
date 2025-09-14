#!/usr/bin/env python3
"""
Interactive Mode - Real-time parameter adjustment with keyboard controls
Pure Python implementation with terminal UI
"""

import sys
import time
import threading
import queue
import os
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import termios
import tty
import select

@dataclass
class Parameter:
    """Audio parameter definition"""
    name: str
    value: float
    min_val: float
    max_val: float
    step: float
    unit: str = ""
    
    def increase(self) -> float:
        """Increase parameter value"""
        self.value = min(self.max_val, self.value + self.step)
        return self.value
    
    def decrease(self) -> float:
        """Decrease parameter value"""
        self.value = max(self.min_val, self.value - self.step)
        return self.value
    
    def set_value(self, value: float) -> float:
        """Set parameter to specific value"""
        self.value = max(self.min_val, min(self.max_val, value))
        return self.value
    
    def get_display(self) -> str:
        """Get display string for parameter"""
        if self.unit == "%":
            return f"{self.value*100:.0f}{self.unit}"
        elif self.unit == "Hz":
            return f"{self.value:.1f}{self.unit}"
        else:
            return f"{self.value:.2f}{self.unit}"


class InteractiveController:
    """Interactive parameter controller with terminal UI"""
    
    def __init__(self):
        self.parameters = {}
        self.selected_param = 0
        self.is_running = False
        self.update_callback = None
        self.command_queue = queue.Queue()
        
        # UI settings
        self.clear_screen = True
        self.show_help = True
        self.show_meters = True
        
        # Audio levels for visualization
        self.input_level = 0.0
        self.output_level = 0.0
        
        # Initialize default parameters
        self._init_default_parameters()
    
    def _init_default_parameters(self):
        """Initialize default audio parameters"""
        self.parameters = {
            'pitch': Parameter('Pitch', 1.0, 0.5, 2.0, 0.05, 'x'),
            'formant': Parameter('Formant', 1.0, 0.5, 2.0, 0.05, 'x'),
            'speed': Parameter('Speed', 1.0, 0.5, 2.0, 0.05, 'x'),
            'volume': Parameter('Volume', 1.0, 0.0, 2.0, 0.1, 'x'),
            'reverb': Parameter('Reverb', 0.0, 0.0, 1.0, 0.1, '%'),
            'delay': Parameter('Delay', 0.0, 0.0, 1.0, 0.1, 's'),
            'distortion': Parameter('Distortion', 0.0, 0.0, 1.0, 0.1, '%'),
            'noise_gate': Parameter('Noise Gate', 0.01, 0.0, 0.1, 0.01, ''),
        }
        
        self.param_list = list(self.parameters.keys())
    
    def add_parameter(self, key: str, param: Parameter):
        """Add custom parameter"""
        self.parameters[key] = param
        self.param_list = list(self.parameters.keys())
    
    def set_update_callback(self, callback: Callable):
        """Set callback for parameter updates"""
        self.update_callback = callback
    
    def start(self):
        """Start interactive mode"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start input thread
        input_thread = threading.Thread(target=self._input_loop)
        input_thread.daemon = True
        input_thread.start()
        
        # Start UI update loop
        self._ui_loop()
    
    def stop(self):
        """Stop interactive mode"""
        self.is_running = False
        # Restore terminal settings
        self._restore_terminal()
    
    def _setup_terminal(self):
        """Setup terminal for raw input"""
        if sys.platform != 'win32':
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
    
    def _restore_terminal(self):
        """Restore terminal settings"""
        if sys.platform != 'win32' and hasattr(self, 'old_settings'):
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
    
    def _input_loop(self):
        """Handle keyboard input"""
        self._setup_terminal()
        
        try:
            while self.is_running:
                if sys.platform == 'win32':
                    # Windows input handling
                    import msvcrt
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8', errors='ignore')
                        self._process_key(key)
                else:
                    # Unix/Linux input handling
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)
                        self._process_key(key)
                
                time.sleep(0.01)
        finally:
            self._restore_terminal()
    
    def _process_key(self, key: str):
        """Process keyboard input"""
        if key in ['q', 'Q', '\x03']:  # q or Ctrl+C
            self.stop()
        elif key in ['w', 'W']:  # Up
            self.selected_param = max(0, self.selected_param - 1)
        elif key in ['s', 'S']:  # Down
            self.selected_param = min(len(self.param_list) - 1, self.selected_param + 1)
        elif key in ['a', 'A']:  # Decrease
            self._adjust_parameter(-1)
        elif key in ['d', 'D']:  # Increase
            self._adjust_parameter(1)
        elif key in ['r', 'R']:  # Reset
            self._reset_parameter()
        elif key == ' ':  # Space - toggle parameter
            self._toggle_parameter()
        elif key in ['h', 'H']:  # Help
            self.show_help = not self.show_help
        elif key in ['m', 'M']:  # Meters
            self.show_meters = not self.show_meters
        elif key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            # Quick select parameter
            index = int(key) - 1
            if index < len(self.param_list):
                self.selected_param = index
        elif key in ['p', 'P']:  # Load preset
            self._load_preset_menu()
    
    def _adjust_parameter(self, direction: int):
        """Adjust selected parameter"""
        param_key = self.param_list[self.selected_param]
        param = self.parameters[param_key]
        
        if direction > 0:
            param.increase()
        else:
            param.decrease()
        
        # Trigger callback
        if self.update_callback:
            self.update_callback(param_key, param.value)
    
    def _reset_parameter(self):
        """Reset selected parameter to default"""
        param_key = self.param_list[self.selected_param]
        param = self.parameters[param_key]
        
        # Reset to midpoint or zero
        if param.min_val >= 0:
            default = param.min_val
        else:
            default = (param.min_val + param.max_val) / 2
        
        param.set_value(default)
        
        if self.update_callback:
            self.update_callback(param_key, param.value)
    
    def _toggle_parameter(self):
        """Toggle parameter on/off"""
        param_key = self.param_list[self.selected_param]
        param = self.parameters[param_key]
        
        # Toggle between min and previous value
        if param.value > param.min_val:
            param._prev_value = param.value
            param.set_value(param.min_val)
        else:
            param.set_value(getattr(param, '_prev_value', param.max_val / 2))
        
        if self.update_callback:
            self.update_callback(param_key, param.value)
    
    def _ui_loop(self):
        """Main UI update loop"""
        while self.is_running:
            self._draw_ui()
            time.sleep(0.1)  # 10 FPS update rate
    
    def _draw_ui(self):
        """Draw terminal UI"""
        if self.clear_screen:
            os.system('cls' if sys.platform == 'win32' else 'clear')
        
        # Header
        print("╔" + "═" * 58 + "╗")
        print("║" + " CHAMELEON AUDIO - INTERACTIVE MODE ".center(58) + "║")
        print("╠" + "═" * 58 + "╣")
        
        # Parameters
        for i, param_key in enumerate(self.param_list):
            param = self.parameters[param_key]
            
            # Selection indicator
            if i == self.selected_param:
                selector = "▶"
                highlight = "\033[1;32m"  # Green bold
                reset = "\033[0m"
            else:
                selector = " "
                highlight = ""
                reset = ""
            
            # Parameter bar
            bar_width = 20
            filled = int((param.value - param.min_val) / (param.max_val - param.min_val) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            # Format line
            name = param.name.ljust(12)
            value = param.get_display().rjust(8)
            
            print(f"║ {selector} {highlight}{i+1}. {name} [{bar}] {value}{reset}".ljust(67) + "║")
        
        print("╠" + "═" * 58 + "╣")
        
        # Audio meters
        if self.show_meters:
            self._draw_meters()
            print("╠" + "═" * 58 + "╣")
        
        # Controls help
        if self.show_help:
            print("║ CONTROLS:                                                ║")
            print("║   W/S: Select  A/D: Adjust  R: Reset  Space: Toggle     ║")
            print("║   1-9: Quick Select  P: Presets  M: Meters  H: Help     ║")
            print("║   Q: Quit                                                ║")
            print("╠" + "═" * 58 + "╣")
        
        # Status
        print("║ Status: " + "● ACTIVE".ljust(49) + "║")
        print("╚" + "═" * 58 + "╝")
    
    def _draw_meters(self):
        """Draw audio level meters"""
        meter_width = 40
        
        # Input level
        in_filled = int(self.input_level * meter_width)
        in_bar = "█" * in_filled + "░" * (meter_width - in_filled)
        
        # Output level
        out_filled = int(self.output_level * meter_width)
        out_bar = "█" * out_filled + "░" * (meter_width - out_filled)
        
        # Color coding for levels
        if self.input_level > 0.9:
            in_color = "\033[1;31m"  # Red
        elif self.input_level > 0.7:
            in_color = "\033[1;33m"  # Yellow
        else:
            in_color = "\033[1;32m"  # Green
        
        if self.output_level > 0.9:
            out_color = "\033[1;31m"  # Red
        elif self.output_level > 0.7:
            out_color = "\033[1;33m"  # Yellow
        else:
            out_color = "\033[1;32m"  # Green
        
        reset = "\033[0m"
        
        print(f"║ INPUT:  {in_color}[{in_bar}]{reset} ".ljust(67) + "║")
        print(f"║ OUTPUT: {out_color}[{out_bar}]{reset} ".ljust(67) + "║")
    
    def update_levels(self, input_level: float, output_level: float):
        """Update audio level meters"""
        self.input_level = max(0.0, min(1.0, input_level))
        self.output_level = max(0.0, min(1.0, output_level))
    
    def _load_preset_menu(self):
        """Show preset loading menu"""
        # This would show a preset selection menu
        # For now, just cycle through some presets
        presets = {
            'normal': {'pitch': 1.0, 'formant': 1.0, 'speed': 1.0},
            'robot': {'pitch': 1.0, 'formant': 0.8, 'distortion': 0.3},
            'deep': {'pitch': 0.7, 'formant': 0.8, 'speed': 0.9},
            'child': {'pitch': 1.5, 'formant': 1.3, 'speed': 1.1},
        }
        
        # Simple preset cycling
        if not hasattr(self, '_preset_index'):
            self._preset_index = 0
        
        preset_names = list(presets.keys())
        self._preset_index = (self._preset_index + 1) % len(preset_names)
        preset_name = preset_names[self._preset_index]
        preset_values = presets[preset_name]
        
        # Apply preset
        for key, value in preset_values.items():
            if key in self.parameters:
                self.parameters[key].set_value(value)
                if self.update_callback:
                    self.update_callback(key, value)
    
    def get_parameters(self) -> Dict[str, float]:
        """Get current parameter values"""
        return {key: param.value for key, param in self.parameters.items()}
    
    def save_preset(self, name: str) -> Dict[str, float]:
        """Save current parameters as preset"""
        preset = self.get_parameters()
        # Could save to file here
        return preset


class InteractiveAudioProcessor:
    """Audio processor with interactive control"""
    
    def __init__(self, audio_processor=None, voice_processor=None):
        self.audio_processor = audio_processor
        self.voice_processor = voice_processor
        self.controller = InteractiveController()
        
        # Set up parameter update callback
        self.controller.set_update_callback(self.on_parameter_change)
        
        # Processing thread
        self.processing_thread = None
        self.is_processing = False
        
    def on_parameter_change(self, param_name: str, value: float):
        """Handle parameter changes from controller"""
        # Update audio processors
        if param_name in ['pitch', 'formant', 'speed'] and self.voice_processor:
            if param_name == 'pitch':
                self.voice_processor.profile.pitch = value
            elif param_name == 'formant':
                self.voice_processor.profile.formant = value
            elif param_name == 'speed':
                self.voice_processor.profile.speed = value
        
        elif self.audio_processor:
            # Update audio effect parameters
            if param_name == 'reverb':
                self.audio_processor.reverb_amount = value
            elif param_name == 'delay':
                self.audio_processor.delay_time = value
            elif param_name == 'distortion':
                self.audio_processor.distortion = value
    
    def start_interactive_mode(self, input_file: Optional[str] = None):
        """Start interactive processing mode"""
        print("Starting Interactive Mode...")
        print("Loading audio processors...")
        
        # Initialize processors if not provided
        if not self.audio_processor:
            import audio_processor
            self.audio_processor = audio_processor.AudioProcessor()
        
        if not self.voice_processor:
            import voice_processor
            self.voice_processor = voice_processor.VoiceProcessor()
        
        # Start controller
        try:
            self.controller.start()
        except KeyboardInterrupt:
            print("\nInteractive mode stopped.")
        finally:
            self.controller.stop()
    
    def process_with_interactive_params(self, audio_data: bytes) -> bytes:
        """Process audio with current interactive parameters"""
        params = self.controller.get_parameters()
        
        # Apply voice processing
        if self.voice_processor:
            audio_data = self.voice_processor.process_chunk(audio_data)
        
        # Apply audio effects
        if self.audio_processor:
            effect_params = {
                'reverb': params.get('reverb', 0),
                'delay': params.get('delay', 0),
                'gain': 1.0 + params.get('distortion', 0) * 2
            }
            audio_data = self.audio_processor.process_audio(audio_data, effect_params)
        
        return audio_data


def run_interactive_mode(input_file: Optional[str] = None):
    """High-level function to run interactive mode"""
    processor = InteractiveAudioProcessor()
    processor.start_interactive_mode(input_file)


if __name__ == '__main__':
    import sys
    
    # Check for input file
    input_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("Chameleon Audio - Interactive Mode")
    print("==================================")
    
    if input_file:
        print(f"Input: {input_file}")
    else:
        print("No input file - parameter adjustment only")
    
    print("\nStarting in 2 seconds...")
    time.sleep(2)
    
    # Run interactive mode
    run_interactive_mode(input_file)