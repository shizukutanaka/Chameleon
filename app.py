#!/usr/bin/env python3
"""
Chameleon Voice Changer - Modern Desktop Application.

Cross-platform desktop application built with Tkinter for maximum compatibility.
Provides intuitive GUI interface for all voice processing functionality.

Author: Chameleon Development Team
License: MIT
"""

import os
import sys
import threading
import time
from typing import Dict, List, Optional, Callable, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum, auto
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter.font import Font

try:
    from core import (
        generate_sine_wave, write_wav_file, read_wav_file,
        get_system_capabilities, load_config
    )
    from perf import get_performance_stats
    from __init__ import __version__
    APP_VERSION = __version__
except ImportError as e:
    print(f"Failed to import core modules: {e}")
    print("Make sure core.py and perf.py are in the same directory")
    APP_VERSION = "2.0.0"
    if "version" not in str(e).lower():
        sys.exit(1)

# Application constants
APP_NAME = "Chameleon Voice Changer"
WINDOW_SIZE = "900x700"
MIN_WINDOW_SIZE = (800, 600)

# Simple logging setup
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Theme(Enum):
    """Application theme enumeration."""
    LIGHT = auto()
    DARK = auto()
    SYSTEM = auto()

class AppState(Enum):
    """Application state enumeration."""
    IDLE = auto()
    PROCESSING = auto()
    ERROR = auto()
    READY = auto()

@dataclass
class AudioSettings:
    """Audio processing settings data class."""
    frequency: float = 440.0
    duration: float = 1.0
    sample_rate: int = 44100
    amplitude: float = 0.8
    output_path: str = "output.wav"

class ProgressDialog:
    """Modal progress dialog for long-running operations."""
    
    def __init__(self, parent: tk.Tk, title: str, message: str):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        # Message label
        self.message_label = ttk.Label(
            self.dialog, 
            text=message, 
            font=('Arial', 10)
        )
        self.message_label.pack(pady=20)
        
        # Progress bar
        self.progress = ttk.Progressbar(
            self.dialog, 
            mode='indeterminate',
            length=300
        )
        self.progress.pack(pady=10)
        self.progress.start()
        
        # Cancel button
        self.cancel_button = ttk.Button(
            self.dialog,
            text="Cancel",
            command=self.cancel
        )
        self.cancel_button.pack(pady=10)
        
        self.cancelled = False
    
    def update_message(self, message: str):
        """Update progress message."""
        self.message_label.config(text=message)
        self.dialog.update_idletasks()
    
    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.close()
    
    def close(self):
        """Close the progress dialog."""
        self.progress.stop()
        self.dialog.grab_release()
        self.dialog.destroy()

class AudioControlPanel(ttk.Frame):
    """Audio parameter control panel."""
    
    def __init__(self, parent: tk.Widget, settings: AudioSettings, callback: Optional[Callable] = None):
        super().__init__(parent)
        self.settings = settings
        self.callback = callback
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create control widgets."""
        # Frequency control
        ttk.Label(self, text="Frequency (Hz):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.freq_var = tk.DoubleVar(value=self.settings.frequency)
        self.freq_scale = ttk.Scale(
            self, 
            from_=20, 
            to=2000,
            orient='horizontal',
            length=200,
            variable=self.freq_var,
            command=self._on_parameter_change
        )
        self.freq_scale.grid(row=0, column=1, padx=5, pady=5)
        self.freq_label = ttk.Label(self, text=f"{self.settings.frequency:.0f} Hz")
        self.freq_label.grid(row=0, column=2, padx=5, pady=5)
        
        # Duration control
        ttk.Label(self, text="Duration (sec):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.duration_var = tk.DoubleVar(value=self.settings.duration)
        self.duration_scale = ttk.Scale(
            self,
            from_=0.1,
            to=10.0,
            orient='horizontal',
            length=200,
            variable=self.duration_var,
            command=self._on_parameter_change
        )
        self.duration_scale.grid(row=1, column=1, padx=5, pady=5)
        self.duration_label = ttk.Label(self, text=f"{self.settings.duration:.1f} sec")
        self.duration_label.grid(row=1, column=2, padx=5, pady=5)
        
        # Amplitude control
        ttk.Label(self, text="Amplitude:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.amplitude_var = tk.DoubleVar(value=self.settings.amplitude)
        self.amplitude_scale = ttk.Scale(
            self,
            from_=0.1,
            to=1.0,
            orient='horizontal',
            length=200,
            variable=self.amplitude_var,
            command=self._on_parameter_change
        )
        self.amplitude_scale.grid(row=2, column=1, padx=5, pady=5)
        self.amplitude_label = ttk.Label(self, text=f"{self.settings.amplitude:.1f}")
        self.amplitude_label.grid(row=2, column=2, padx=5, pady=5)
        
        # Sample rate combobox
        ttk.Label(self, text="Sample Rate:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.sample_rate_var = tk.StringVar(value=str(self.settings.sample_rate))
        self.sample_rate_combo = ttk.Combobox(
            self,
            textvariable=self.sample_rate_var,
            values=["8000", "16000", "22050", "44100", "48000", "96000"],
            state="readonly",
            width=10
        )
        self.sample_rate_combo.grid(row=3, column=1, padx=5, pady=5, sticky='w')
        self.sample_rate_combo.bind('<<ComboboxSelected>>', self._on_parameter_change)
    
    def _on_parameter_change(self, event=None):
        """Handle parameter changes."""
        self.settings.frequency = self.freq_var.get()
        self.settings.duration = self.duration_var.get()
        self.settings.amplitude = self.amplitude_var.get()
        self.settings.sample_rate = int(self.sample_rate_var.get())
        
        # Update labels
        self.freq_label.config(text=f"{self.settings.frequency:.0f} Hz")
        self.duration_label.config(text=f"{self.settings.duration:.1f} sec")
        self.amplitude_label.config(text=f"{self.settings.amplitude:.1f}")
        
        # Notify callback
        if self.callback:
            self.callback(self.settings)

class LogPanel(ttk.Frame):
    """Application log display panel."""
    
    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self._create_widgets()
        self._setup_logging()
    
    def _create_widgets(self):
        """Create log display widgets."""
        # Log area with scrollbar
        self.log_text = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            height=10,
            font=('Consolas', 9),
            state='disabled'
        )
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Control buttons frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side='left')
        ttk.Button(button_frame, text="Save Log", command=self.save_log).pack(side='left', padx=5)
    
    def _setup_logging(self):
        """Setup logging to display in widget."""
        self.add_log("INFO", "Application started")
        self.add_log("INFO", f"Chameleon Voice Changer {APP_VERSION}")
    
    def add_log(self, level: str, message: str):
        """Add log entry to display."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)  # Auto-scroll to bottom
        self.log_text.config(state='disabled')
        
        # Color coding for different log levels
        if level == "ERROR":
            self.log_text.tag_add("error", "end-2l", "end-1l")
            self.log_text.tag_config("error", foreground="red")
        elif level == "WARNING":
            self.log_text.tag_add("warning", "end-2l", "end-1l")
            self.log_text.tag_config("warning", foreground="orange")
        elif level == "INFO":
            self.log_text.tag_add("info", "end-2l", "end-1l")
            self.log_text.tag_config("info", foreground="blue")
    
    def clear_log(self):
        """Clear log display."""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.add_log("INFO", "Log cleared")
    
    def save_log(self):
        """Save log to file."""
        file_path = filedialog.asksaveasfilename(
            title="Save Log File",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    log_content = self.log_text.get(1.0, tk.END)
                    f.write(log_content)
                self.add_log("INFO", f"Log saved to {file_path}")
            except OSError as e:
                self.add_log("ERROR", f"Failed to save log: {e}")
                messagebox.showerror("Error", f"Failed to save log file: {e}")

class ChameleonApp:
    """Main application class."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.config = load_config()
        self.settings = AudioSettings()
        self.state = AppState.IDLE
        self.capabilities = get_system_capabilities()
        
        self._setup_window()
        self._create_menu()
        self._create_main_interface()
        self._setup_styling()
        
        # Initialize with system check
        self._perform_system_check()
    
    def _setup_window(self):
        """Configure main window."""
        self.root.title(f"{APP_NAME}")
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(*MIN_WINDOW_SIZE)
        
        # Set application icon (if available)
        icon_path = Path("chameleon.ico")
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except tk.TclError:
                pass  # Icon loading failed, continue without it
        
        # Configure window closing behavior
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _create_menu(self):
        """Create application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Audio File...", command=self._open_file)
        file_menu.add_command(label="Save As...", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)
        
        # Audio menu
        audio_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Audio", menu=audio_menu)
        audio_menu.add_command(label="Generate Tone", command=self._generate_tone)
        audio_menu.add_command(label="System Check", command=self._perform_system_check)
        audio_menu.add_command(label="Benchmark", command=self._run_benchmark)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="System Info", command=self._show_system_info)
    
    def _create_main_interface(self):
        """Create main application interface."""
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Audio Generation Tab
        self.audio_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.audio_tab, text="Audio Generation")
        
        # Control panel frame
        control_frame = ttk.LabelFrame(self.audio_tab, text="Audio Parameters", padding=10)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        self.control_panel = AudioControlPanel(
            control_frame, 
            self.settings, 
            self._on_settings_change
        )
        self.control_panel.pack(fill='x')
        
        # Action buttons frame
        action_frame = ttk.Frame(self.audio_tab)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        self.generate_button = ttk.Button(
            action_frame,
            text="Generate Tone",
            command=self._generate_tone,
            style="Accent.TButton"
        )
        self.generate_button.pack(side='left', padx=5)
        
        self.play_button = ttk.Button(
            action_frame,
            text="Play",
            command=self._play_audio,
            state='disabled'
        )
        self.play_button.pack(side='left', padx=5)
        
        self.save_button = ttk.Button(
            action_frame,
            text="Save As...",
            command=self._save_as,
            state='disabled'
        )
        self.save_button.pack(side='left', padx=5)
        
        # Status frame
        status_frame = ttk.LabelFrame(self.audio_tab, text="Status", padding=10)
        status_frame.pack(fill='x', padx=10, pady=10)
        
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(anchor='w')
        
        # Log Tab
        self.log_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.log_tab, text="Log")
        
        self.log_panel = LogPanel(self.log_tab)
        self.log_panel.pack(fill='both', expand=True)
    
    def _setup_styling(self):
        """Setup custom styling for widgets."""
        style = ttk.Style()
        
        # Configure custom button style
        style.configure(
            "Accent.TButton",
            font=('Arial', 10, 'bold')
        )
    
    def _on_settings_change(self, settings: AudioSettings):
        """Handle settings changes."""
        self.log_panel.add_log("INFO", f"Parameters updated: {settings.frequency}Hz, {settings.duration}s")
    
    def _generate_tone(self):
        """Generate audio tone with current settings."""
        def generate_worker():
            try:
                self._update_status("Generating tone...")
                self._set_controls_state(False)
                
                # Generate audio using unified core
                audio_data = generate_sine_wave(
                    frequency=self.settings.frequency,
                    duration=self.settings.duration,
                    sample_rate=self.settings.sample_rate,
                    fast=True
                )
                
                # Save to temporary location
                temp_file = Path("temp_output.wav")
                success = write_wav_file(str(temp_file), audio_data)
                
                if success:
                    self.current_audio_file = str(temp_file)
                    self.root.after(0, lambda: self._generation_complete(True))
                else:
                    self.root.after(0, lambda: self._generation_complete(False))
                        
            except Exception as e:
                logger.error(f"Audio generation failed: {e}")
                self.root.after(0, lambda: self._generation_failed(str(e)))
        
        # Run generation in background thread
        threading.Thread(target=generate_worker, daemon=True).start()
    
    def _generation_complete(self, success: bool):
        """Handle audio generation completion."""
        if success:
            self._update_status("Tone generated successfully")
            self.log_panel.add_log("INFO", "Audio tone generated")
            self.play_button.config(state='normal')
            self.save_button.config(state='normal')
        else:
            self._update_status("Generation failed")
            self.log_panel.add_log("ERROR", "Audio generation failed")
        
        self._set_controls_state(True)
    
    def _generation_failed(self, error_message: str):
        """Handle audio generation failure."""
        self._update_status(f"Error: {error_message}")
        self.log_panel.add_log("ERROR", f"Generation failed: {error_message}")
        self._set_controls_state(True)
        
        messagebox.showerror("Error", f"Audio generation failed:\n{error_message}")
    
    def _play_audio(self):
        """Play generated audio with multiple fallback methods."""
        if not hasattr(self, 'current_audio_file') or not self.current_audio_file:
            messagebox.showwarning("Warning", "No audio file to play")
            return
            
        self.log_panel.add_log("INFO", f"Attempting to play: {self.current_audio_file}")
        
        def play_worker():
            """Background worker for audio playback."""
            success = False
            error_msg = ""
            
            try:
                # Method 1: Try sounddevice (professional audio)
                try:
                    import sounddevice as sd
                    import soundfile as sf
                    data, samplerate = sf.read(self.current_audio_file)
                    sd.play(data, samplerate)
                    sd.wait()
                    success = True
                    self.root.after(0, lambda: self.log_panel.add_log("INFO", "Playback complete (sounddevice)"))
                except ImportError:
                    error_msg += "sounddevice not available; "
                except Exception as e:
                    error_msg += f"sounddevice error: {e}; "
            
                # Method 2: Try pygame mixer
                if not success:
                    try:
                        import pygame.mixer
                        pygame.mixer.init()
                        pygame.mixer.music.load(self.current_audio_file)
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy():
                            time.sleep(0.1)
                        pygame.mixer.quit()
                        success = True
                        self.root.after(0, lambda: self.log_panel.add_log("INFO", "Playback complete (pygame)"))
                    except ImportError:
                        error_msg += "pygame not available; "
                    except Exception as e:
                        error_msg += f"pygame error: {e}; "
                
                # Method 3: System fallback
                if not success:
                    import subprocess
                    import platform
                    system = platform.system()
                    
                    try:
                        if system == "Windows":
                            subprocess.run([
                                "powershell", "-c", 
                                f"(New-Object Media.SoundPlayer '{self.current_audio_file}').PlaySync()"
                            ], check=True, capture_output=True)
                        elif system == "Darwin":  # macOS
                            subprocess.run(["afplay", self.current_audio_file], check=True, capture_output=True)
                        elif system == "Linux":
                            # Try multiple Linux audio players
                            for player in ["aplay", "paplay", "play"]:
                                try:
                                    subprocess.run([player, self.current_audio_file], check=True, capture_output=True)
                                    break
                                except FileNotFoundError:
                                    continue
                            else:
                                raise Exception("No compatible audio player found")
                        
                        success = True
                        self.root.after(0, lambda: self.log_panel.add_log("INFO", "Playback complete (system)"))
                    except Exception as e:
                        error_msg += f"system playback error: {e}"
                
                if not success:
                    self.root.after(0, lambda: self._playback_failed(error_msg))
                    
            except Exception as e:
                self.root.after(0, lambda: self._playback_failed(str(e)))
        
        # Run playback in background thread
        threading.Thread(target=play_worker, daemon=True).start()
    
    def _playback_failed(self, error_msg: str):
        """Handle playback failure."""
        self.log_panel.add_log("WARNING", f"Audio playback failed: {error_msg}")
        fallback_msg = "Audio playback failed. Try installing:\n"
        fallback_msg += "• sounddevice: pip install sounddevice soundfile\n"
        fallback_msg += "• pygame: pip install pygame\n"
        fallback_msg += f"Or open the file manually: {self.current_audio_file}"
        messagebox.showwarning("Playback Failed", fallback_msg)
    
    def _save_as(self):
        """Save audio to user-specified file."""
        if not hasattr(self, 'current_audio_file'):
            messagebox.showwarning("Warning", "No audio file to save")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Audio File",
            defaultextension=".wav",
            filetypes=[
                ("WAV files", "*.wav"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                import shutil
                shutil.copy2(self.current_audio_file, file_path)
                self.log_panel.add_log("INFO", f"Audio saved to {file_path}")
                messagebox.showinfo("Success", f"Audio saved to:\n{file_path}")
            except OSError as e:
                self.log_panel.add_log("ERROR", f"Save failed: {e}")
                messagebox.showerror("Error", f"Failed to save file:\n{e}")
    
    def _open_file(self):
        """Open audio file for analysis."""
        file_path = filedialog.askopenfilename(
            title="Open Audio File",
            filetypes=[
                ("WAV files", "*.wav"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.log_panel.add_log("INFO", f"Opening file: {file_path}")
            try:
                result = read_wav_file(file_path)
                if result:
                    audio_data, audio_info = result
                    self.current_audio_file = file_path
                    self.log_panel.add_log("INFO", f"File loaded: {audio_info['duration']:.2f}s, {audio_info['size_bytes']} bytes")
                    self.play_button.config(state='normal')
                    self.save_button.config(state='normal')
                    
                    # Update settings with file info
                    duration = audio_info['duration']
                    if duration > 0:
                        self.settings.duration = min(duration, 10.0)  # Cap at UI limit
                        self.control_panel.duration_var.set(self.settings.duration)
                        self.control_panel._on_parameter_change()
                    
                    messagebox.showinfo("Success", f"Audio file loaded:\n{file_path}\nDuration: {duration:.2f}s")
                else:
                    self.log_panel.add_log("ERROR", f"Failed to load file: {file_path}")
                    messagebox.showerror("Error", f"Could not load audio file:\n{file_path}")
            except Exception as e:
                self.log_panel.add_log("ERROR", f"Error loading file: {e}")
                messagebox.showerror("Error", f"Error loading file:\n{e}")
    
    def _perform_system_check(self):
        """Perform system capability check."""
        self.log_panel.add_log("INFO", "Performing system check...")
        
        # Update capabilities
        self.capabilities = get_system_capabilities()
        
        available_count = sum(1 for available in self.capabilities.values() if available)
        total_count = len(self.capabilities)
        
        self.log_panel.add_log("INFO", f"System capabilities: {available_count}/{total_count} available")
        
        # Update status
        if self.capabilities.get('advanced_audio_available', False):
            self._update_status("System ready - Advanced features available")
        else:
            self._update_status("System ready - Basic features only")
    
    def _run_benchmark(self):
        """Run performance benchmark."""
        self.log_panel.add_log("INFO", "Running benchmark...")
        
        def benchmark_worker():
            try:
                # Import performance functions
                from perf import benchmark_audio_generation
                
                # Run comprehensive benchmark
                results = benchmark_audio_generation(10)
                
                # Calculate overall performance metric
                lut_speedup = results.get('lut_speedup', 1.0)
                cache_speedup = results.get('cache_speedup', 1.0)
                overall_score = (lut_speedup + cache_speedup) / 2
                
                self.root.after(0, lambda: self._benchmark_complete(results, overall_score))
                
            except Exception as e:
                self.root.after(0, lambda: self._benchmark_failed(str(e)))
        
        threading.Thread(target=benchmark_worker, daemon=True).start()
    
    def _benchmark_complete(self, results: dict, overall_score: float):
        """Handle benchmark completion."""
        standard_time = results.get('standard_total_ms', 0)
        lut_time = results.get('lut_total_ms', 0)
        lut_speedup = results.get('lut_speedup', 1.0)
        
        message = f"Benchmark Results:\n"
        message += f"Standard: {standard_time:.1f}ms\n"
        message += f"Optimized: {lut_time:.1f}ms\n"
        message += f"Speedup: {lut_speedup:.2f}x\n"
        message += f"Overall Score: {overall_score:.2f}"
        
        self.log_panel.add_log("INFO", f"Benchmark complete - Overall score: {overall_score:.2f}")
        messagebox.showinfo("Benchmark Results", message)
    
    def _benchmark_failed(self, error: str):
        """Handle benchmark failure."""
        self.log_panel.add_log("ERROR", f"Benchmark failed: {error}")
        messagebox.showerror("Error", f"Benchmark failed:\n{error}")
    
    def _show_about(self):
        """Show about dialog."""
        about_text = f"""
{APP_NAME} v{APP_VERSION}

Professional voice processing application with clean architecture design.

Features:
• Audio tone generation
• Real-time processing
• Modern GUI interface
• Cross-platform compatibility

Built with Python and Tkinter
"""
        messagebox.showinfo("About", about_text.strip())
    
    def _show_system_info(self):
        """Show system information dialog."""
        info_lines = ["System Capabilities:"]
        
        for capability, available in self.capabilities.items():
            status = 'Yes' if available else 'No'
            info_lines.append(f"• {capability}: {status}")
        
        info_lines.extend([
            "",
            f"Python Version: {sys.version}",
            f"Platform: {sys.platform}",
            f"Available Capabilities: {sum(self.capabilities.values())}/{len(self.capabilities)}"
        ])
        
        info_text = "\n".join(info_lines)
        messagebox.showinfo("System Information", info_text)
    
    def _update_status(self, message: str):
        """Update status bar message."""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def _set_controls_state(self, enabled: bool):
        """Enable/disable control widgets."""
        state = 'normal' if enabled else 'disabled'
        self.generate_button.config(state=state)
    
    def _on_closing(self):
        """Handle application closing."""
        self.log_panel.add_log("INFO", "Application closing...")
        
        # Cleanup temporary files
        temp_file = Path("temp_output.wav")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Start the application main loop."""
        logger.info(f"Starting {APP_NAME}")
        self.log_panel.add_log("INFO", "Application ready")
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
        except Exception as e:
            logger.critical(f"Application crashed: {e}", exc_info=True)
            messagebox.showerror("Critical Error", f"Application error:\n{e}")
        finally:
            logger.info("Application terminated")

def main():
    """Application entry point."""
    try:
        app = ChameleonApp()
        app.run()
        return 0
    except Exception as e:
        print(f"Failed to start application: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())