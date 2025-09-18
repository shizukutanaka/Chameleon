#!/usr/bin/env python3
"""
Simple GUI for Audio Processing
Using tkinter (built-in with Python)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import array
import wave
import os
from pathlib import Path
import threading

# Import our modules
from chameleon import AudioProcessor
from audio_effects import AudioEffects
from audio_analyzer import AudioAnalyzer

class AudioGUI:
    """Simple GUI for common audio operations"""

    def __init__(self, root):
        self.root = root
        self.root.title("Chameleon Audio Processor")
        self.root.geometry("600x500")

        # Initialize processors
        self.processor = AudioProcessor()
        self.effects = AudioEffects()
        self.analyzer = AudioAnalyzer()

        # State
        self.current_file = None
        self.samples = None
        self.info = None

        # Create UI
        self.create_widgets()

    def create_widgets(self):
        """Create UI elements"""
        # File frame
        file_frame = ttk.Frame(self.root, padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

        ttk.Button(file_frame, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(file_frame, text="No file loaded")
        self.file_label.pack(side=tk.LEFT, padx=5)

        # Info frame
        info_frame = ttk.LabelFrame(self.root, text="File Information", padding="10")
        info_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10)

        self.info_text = tk.Text(info_frame, height=5, width=60)
        self.info_text.pack()

        # Operations notebook
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)

        # Basic operations tab
        basic_tab = ttk.Frame(notebook)
        notebook.add(basic_tab, text="Basic")
        self.create_basic_tab(basic_tab)

        # Effects tab
        effects_tab = ttk.Frame(notebook)
        notebook.add(effects_tab, text="Effects")
        self.create_effects_tab(effects_tab)

        # Analysis tab
        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="Analysis")
        self.create_analysis_tab(analysis_tab)

        # Status bar
        self.status = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN)
        self.status.grid(row=3, column=0, sticky=(tk.W, tk.E))

    def create_basic_tab(self, parent):
        """Create basic operations tab"""
        # Normalize
        ttk.Button(parent, text="Normalize", command=lambda: self.apply_operation('normalize')).grid(row=0, column=0, padx=5, pady=5)

        # Amplify
        amp_frame = ttk.Frame(parent)
        amp_frame.grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(amp_frame, text="Amplify", command=lambda: self.apply_amplify()).pack(side=tk.LEFT)
        ttk.Label(amp_frame, text="Gain (dB):").pack(side=tk.LEFT, padx=5)
        self.gain_var = tk.DoubleVar(value=0)
        ttk.Spinbox(amp_frame, from_=-20, to=20, textvariable=self.gain_var, width=10).pack(side=tk.LEFT)

        # Fade
        fade_frame = ttk.Frame(parent)
        fade_frame.grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(fade_frame, text="Fade", command=lambda: self.apply_fade()).pack(side=tk.LEFT)
        ttk.Label(fade_frame, text="In (ms):").pack(side=tk.LEFT, padx=5)
        self.fade_in_var = tk.IntVar(value=100)
        ttk.Spinbox(fade_frame, from_=0, to=5000, textvariable=self.fade_in_var, width=10).pack(side=tk.LEFT)
        ttk.Label(fade_frame, text="Out (ms):").pack(side=tk.LEFT, padx=5)
        self.fade_out_var = tk.IntVar(value=100)
        ttk.Spinbox(fade_frame, from_=0, to=5000, textvariable=self.fade_out_var, width=10).pack(side=tk.LEFT)

        # Trim silence
        ttk.Button(parent, text="Trim Silence", command=lambda: self.apply_operation('trim')).grid(row=3, column=0, padx=5, pady=5)

        # Reverse
        ttk.Button(parent, text="Reverse", command=lambda: self.apply_operation('reverse')).grid(row=4, column=0, padx=5, pady=5)

        # Speed
        speed_frame = ttk.Frame(parent)
        speed_frame.grid(row=5, column=0, padx=5, pady=5)
        ttk.Button(speed_frame, text="Change Speed", command=lambda: self.apply_speed()).pack(side=tk.LEFT)
        ttk.Label(speed_frame, text="Factor:").pack(side=tk.LEFT, padx=5)
        self.speed_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(speed_frame, from_=0.5, to=2.0, increment=0.1, textvariable=self.speed_var, width=10).pack(side=tk.LEFT)

    def create_effects_tab(self, parent):
        """Create effects tab"""
        # Echo
        echo_frame = ttk.Frame(parent)
        echo_frame.grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(echo_frame, text="Echo", command=lambda: self.apply_echo()).pack(side=tk.LEFT)
        ttk.Label(echo_frame, text="Delay (ms):").pack(side=tk.LEFT, padx=5)
        self.echo_delay_var = tk.IntVar(value=300)
        ttk.Spinbox(echo_frame, from_=50, to=2000, textvariable=self.echo_delay_var, width=10).pack(side=tk.LEFT)

        # Chorus
        ttk.Button(parent, text="Chorus", command=lambda: self.apply_effect('chorus')).grid(row=1, column=0, padx=5, pady=5)

        # Distortion
        dist_frame = ttk.Frame(parent)
        dist_frame.grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(dist_frame, text="Distortion", command=lambda: self.apply_distortion()).pack(side=tk.LEFT)
        ttk.Label(dist_frame, text="Drive:").pack(side=tk.LEFT, padx=5)
        self.drive_var = tk.DoubleVar(value=0.5)
        ttk.Scale(dist_frame, from_=0, to=1, variable=self.drive_var, length=200).pack(side=tk.LEFT)

        # Filters
        filter_frame = ttk.Frame(parent)
        filter_frame.grid(row=3, column=0, padx=5, pady=5)
        ttk.Button(filter_frame, text="Low-pass", command=lambda: self.apply_filter('lowpass')).pack(side=tk.LEFT)
        ttk.Button(filter_frame, text="High-pass", command=lambda: self.apply_filter('highpass')).pack(side=tk.LEFT, padx=5)
        ttk.Label(filter_frame, text="Cutoff (Hz):").pack(side=tk.LEFT, padx=5)
        self.cutoff_var = tk.IntVar(value=1000)
        ttk.Spinbox(filter_frame, from_=100, to=10000, textvariable=self.cutoff_var, width=10).pack(side=tk.LEFT)

        # Compressor
        ttk.Button(parent, text="Compressor", command=lambda: self.apply_effect('compressor')).grid(row=4, column=0, padx=5, pady=5)

        # Tremolo
        ttk.Button(parent, text="Tremolo", command=lambda: self.apply_effect('tremolo')).grid(row=5, column=0, padx=5, pady=5)

        # Auto Gain
        ttk.Button(parent, text="Auto Gain", command=lambda: self.apply_effect('autogain')).grid(row=6, column=0, padx=5, pady=5)

    def create_analysis_tab(self, parent):
        """Create analysis tab"""
        # Analyze button
        ttk.Button(parent, text="Analyze Audio", command=self.analyze_audio).grid(row=0, column=0, padx=5, pady=5)

        # Results text
        self.analysis_text = tk.Text(parent, height=15, width=60)
        self.analysis_text.grid(row=1, column=0, padx=5, pady=5)

    def open_file(self):
        """Open audio file"""
        filename = filedialog.askopenfilename(
            title="Open Audio File",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )

        if filename:
            try:
                self.samples, self.info = self.processor.load_wav(filename)
                self.current_file = filename
                self.file_label.config(text=Path(filename).name)
                self.update_info()
                self.status.config(text=f"Loaded: {Path(filename).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")

    def update_info(self):
        """Update file info display"""
        if self.info:
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, f"Sample Rate: {self.info['sample_rate']} Hz\n")
            self.info_text.insert(tk.END, f"Channels: {self.info['channels']}\n")
            self.info_text.insert(tk.END, f"Duration: {self.info['duration']:.2f} seconds\n")
            self.info_text.insert(tk.END, f"Samples: {self.info['samples']}\n")

    def apply_operation(self, operation):
        """Apply basic operation"""
        if not self.samples:
            messagebox.showwarning("Warning", "No audio loaded")
            return

        try:
            if operation == 'normalize':
                self.samples = self.processor.normalize(self.samples)
            elif operation == 'trim':
                self.samples = self.processor.trim_silence(self.samples)
            elif operation == 'reverse':
                self.samples = self.processor.reverse(self.samples)

            self.status.config(text=f"Applied: {operation}")
            self.save_result()
        except Exception as e:
            messagebox.showerror("Error", f"Operation failed: {e}")

    def apply_amplify(self):
        """Apply amplify with gain"""
        if not self.samples:
            return
        self.samples = self.processor.amplify(self.samples, self.gain_var.get())
        self.status.config(text=f"Amplified: {self.gain_var.get()} dB")
        self.save_result()

    def apply_fade(self):
        """Apply fade"""
        if not self.samples:
            return
        self.samples = self.processor.fade(self.samples, self.fade_in_var.get(), self.fade_out_var.get())
        self.status.config(text=f"Applied fade")
        self.save_result()

    def apply_speed(self):
        """Apply speed change"""
        if not self.samples:
            return
        self.samples = self.processor.speed_change(self.samples, self.speed_var.get())
        self.status.config(text=f"Speed changed: {self.speed_var.get()}x")
        self.save_result()

    def apply_echo(self):
        """Apply echo effect"""
        if not self.samples:
            return
        self.samples = self.effects.echo(self.samples, self.echo_delay_var.get())
        self.status.config(text="Applied echo")
        self.save_result()

    def apply_distortion(self):
        """Apply distortion"""
        if not self.samples:
            return
        self.samples = self.effects.distortion(self.samples, self.drive_var.get())
        self.status.config(text="Applied distortion")
        self.save_result()

    def apply_filter(self, filter_type):
        """Apply filter"""
        if not self.samples:
            return
        if filter_type == 'lowpass':
            self.samples = self.effects.low_pass_filter(self.samples, self.cutoff_var.get())
        else:
            self.samples = self.effects.high_pass_filter(self.samples, self.cutoff_var.get())
        self.status.config(text=f"Applied {filter_type} filter")
        self.save_result()

    def apply_effect(self, effect):
        """Apply other effects"""
        if not self.samples:
            return

        if effect == 'chorus':
            self.samples = self.effects.chorus(self.samples)
        elif effect == 'compressor':
            self.samples = self.effects.compressor(self.samples)
        elif effect == 'tremolo':
            self.samples = self.effects.tremolo(self.samples)
        elif effect == 'autogain':
            self.samples = self.effects.auto_gain(self.samples)

        self.status.config(text=f"Applied {effect}")
        self.save_result()

    def analyze_audio(self):
        """Analyze audio"""
        if not self.samples:
            messagebox.showwarning("Warning", "No audio loaded")
            return

        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, "Analyzing...\n")

        # Run analysis in thread to avoid blocking UI
        def analyze():
            results = []
            results.append(f"RMS Level: {self.analyzer.get_rms(self.samples):.2f}")
            results.append(f"Peak: {self.analyzer.get_peak(self.samples)}")
            results.append(f"Zero Crossings: {self.analyzer.get_zero_crossings(self.samples)}")
            results.append(f"Estimated Frequency: {self.analyzer.estimate_frequency(self.samples):.2f} Hz")
            results.append(f"Detected Pitch: {self.analyzer.detect_pitch(self.samples):.2f} Hz")
            results.append(f"Is Silence: {self.analyzer.detect_silence(self.samples)}")

            dynamics = self.analyzer.get_dynamics(self.samples)
            results.append(f"\nDynamics:")
            for key, value in dynamics.items():
                results.append(f"  {key}: {value:.2f}")

            clipping = self.analyzer.detect_clipping(self.samples)
            results.append(f"\nClipping points: {len(clipping)}")

            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(tk.END, "\n".join(results))

        thread = threading.Thread(target=analyze)
        thread.daemon = True
        thread.start()

    def save_result(self):
        """Save processed audio"""
        if not self.samples or not self.current_file:
            return

        # Auto-save with suffix
        base = Path(self.current_file).stem
        suffix = "_processed"
        output = Path(self.current_file).parent / f"{base}{suffix}.wav"

        try:
            self.processor.save_wav(str(output), self.samples)
            self.status.config(text=f"Saved: {output.name}")
        except:
            pass  # Silent fail for auto-save


def main():
    """Run GUI"""
    root = tk.Tk()
    app = AudioGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()