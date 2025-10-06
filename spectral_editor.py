#!/usr/bin/env python3
"""
Spectral Editing Module for Chameleon
Advanced frequency-domain audio editing and restoration
"""

import os
import sys
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
import logging
import warnings

# Advanced processing libraries
try:
    import scipy.signal as signal
    import scipy.ndimage as ndimage
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    warnings.warn("SciPy not available. Advanced spectral editing disabled.")

try:
    import librosa
    import librosa.display
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

@dataclass
class SpectralSelection:
    """Spectral selection region"""
    time_start: float
    time_end: float
    freq_start: float
    freq_end: float
    operation: str = "delete"  # delete, copy, paste, enhance, reduce

@dataclass
class SpectrogramConfig:
    """Configuration for spectrogram computation"""
    n_fft: int = 2048
    hop_length: int = 512
    win_length: int = None
    window: str = "hann"
    overlap: float = 0.75
    zero_padding: int = 0

@dataclass
class SpectralEditConfig:
    """Configuration for spectral editing operations"""
    precision: str = "high"  # low, medium, high
    interpolation: str = "cubic"  # linear, cubic, spectral
    edge_smoothing: bool = True
    preserve_phase: bool = True
    quality: str = "high"

class SpectrogramProcessor:
    """High-quality spectrogram computation and manipulation"""

    def __init__(self, config: SpectrogramConfig = None):
        self.config = config or SpectrogramConfig()
        self.logger = logging.getLogger(__name__)

    def compute_stft(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute Short-Time Fourier Transform"""
        if HAS_LIBROSA:
            return self._compute_stft_librosa(audio, sample_rate)
        else:
            return self._compute_stft_manual(audio, sample_rate)

    def _compute_stft_librosa(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute STFT using librosa (highest quality)"""
        if audio.ndim > 1:
            audio = np.mean(audio, axis=0)  # Convert to mono for spectral editing

        # Compute STFT
        stft = librosa.stft(
            audio,
            n_fft=self.config.n_fft,
            hop_length=self.config.hop_length,
            win_length=self.config.win_length,
            window=self.config.window
        )

        # Generate time and frequency axes
        times = librosa.frames_to_time(
            np.arange(stft.shape[1]),
            sr=sample_rate,
            hop_length=self.config.hop_length
        )

        freqs = librosa.fft_frequencies(
            sr=sample_rate,
            n_fft=self.config.n_fft
        )

        return stft, times, freqs

    def _compute_stft_manual(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Manual STFT computation when librosa not available"""
        if audio.ndim > 1:
            audio = np.mean(audio, axis=0)

        n_fft = self.config.n_fft
        hop_length = self.config.hop_length
        win_length = self.config.win_length or n_fft

        # Create window
        if self.config.window == "hann":
            window = np.hanning(win_length)
        elif self.config.window == "hamming":
            window = np.hamming(win_length)
        else:
            window = np.ones(win_length)

        # Zero-pad window if needed
        if win_length < n_fft:
            window = np.pad(window, (0, n_fft - win_length))

        # Compute STFT
        n_frames = 1 + (len(audio) - n_fft) // hop_length
        stft = np.zeros((n_fft // 2 + 1, n_frames), dtype=complex)

        for i in range(n_frames):
            start = i * hop_length
            frame = audio[start:start + n_fft]

            # Zero-pad if necessary
            if len(frame) < n_fft:
                frame = np.pad(frame, (0, n_fft - len(frame)))

            # Apply window
            windowed_frame = frame * window

            # FFT
            fft_frame = np.fft.fft(windowed_frame)
            stft[:, i] = fft_frame[:n_fft // 2 + 1]

        # Generate axes
        times = np.arange(n_frames) * hop_length / sample_rate
        freqs = np.fft.fftfreq(n_fft, 1/sample_rate)[:n_fft // 2 + 1]

        return stft, times, freqs

    def compute_istft(self, stft: np.ndarray, sample_rate: int, length: int = None) -> np.ndarray:
        """Inverse Short-Time Fourier Transform"""
        if HAS_LIBROSA:
            return librosa.istft(
                stft,
                hop_length=self.config.hop_length,
                win_length=self.config.win_length,
                window=self.config.window,
                length=length
            )
        else:
            return self._compute_istft_manual(stft, sample_rate, length)

    def _compute_istft_manual(self, stft: np.ndarray, sample_rate: int, length: int = None) -> np.ndarray:
        """Manual ISTFT computation"""
        n_fft = (stft.shape[0] - 1) * 2
        hop_length = self.config.hop_length
        win_length = self.config.win_length or n_fft

        # Create window
        if self.config.window == "hann":
            window = np.hanning(win_length)
        else:
            window = np.ones(win_length)

        if win_length < n_fft:
            window = np.pad(window, (0, n_fft - win_length))

        # Reconstruct signal
        n_frames = stft.shape[1]
        output_length = (n_frames - 1) * hop_length + n_fft
        output = np.zeros(output_length)
        norm = np.zeros(output_length)

        for i in range(n_frames):
            # Reconstruct full FFT
            full_fft = np.zeros(n_fft, dtype=complex)
            full_fft[:len(stft[:, i])] = stft[:, i]
            full_fft[len(stft[:, i]):] = np.conj(stft[-2:0:-1, i])

            # IFFT
            frame = np.fft.ifft(full_fft).real

            # Apply window and overlap-add
            start = i * hop_length
            end = start + n_fft
            output[start:end] += frame * window
            norm[start:end] += window

        # Normalize
        norm[norm == 0] = 1
        output = output / norm

        # Trim to specified length
        if length is not None:
            output = output[:length]

        return output

class SpectralEditor:
    """Advanced spectral editing operations"""

    def __init__(self, config: SpectralEditConfig = None):
        self.config = config or SpectralEditConfig()
        self.spectrogram_processor = SpectrogramProcessor()
        self.logger = logging.getLogger(__name__)

        # Edit history for undo/redo
        self.edit_history = []
        self.undo_stack = []

    def load_audio(self, audio: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Load audio for spectral editing"""
        self.original_audio = audio.copy()
        self.current_audio = audio.copy()
        self.sample_rate = sample_rate

        # Compute initial spectrogram
        self.stft, self.times, self.freqs = self.spectrogram_processor.compute_stft(audio, sample_rate)
        self.original_stft = self.stft.copy()

        return {
            "duration": len(audio) / sample_rate,
            "sample_rate": sample_rate,
            "spectrogram_shape": self.stft.shape,
            "frequency_range": (self.freqs[0], self.freqs[-1]),
            "time_range": (self.times[0], self.times[-1])
        }

    def select_region(self, time_start: float, time_end: float,
                     freq_start: float, freq_end: float) -> SpectralSelection:
        """Create spectral selection"""
        selection = SpectralSelection(
            time_start=max(0, time_start),
            time_end=min(self.times[-1], time_end),
            freq_start=max(self.freqs[0], freq_start),
            freq_end=min(self.freqs[-1], freq_end)
        )

        return selection

    def get_selection_mask(self, selection: SpectralSelection) -> np.ndarray:
        """Get boolean mask for spectral selection"""
        # Find time indices
        time_start_idx = np.searchsorted(self.times, selection.time_start)
        time_end_idx = np.searchsorted(self.times, selection.time_end)

        # Find frequency indices
        freq_start_idx = np.searchsorted(self.freqs, selection.freq_start)
        freq_end_idx = np.searchsorted(self.freqs, selection.freq_end)

        # Create mask
        mask = np.zeros(self.stft.shape, dtype=bool)
        mask[freq_start_idx:freq_end_idx, time_start_idx:time_end_idx] = True

        return mask

    def delete_selection(self, selection: SpectralSelection,
                        fade_edges: bool = True) -> bool:
        """Delete spectral content in selection"""
        try:
            # Save current state for undo
            self._save_state()

            mask = self.get_selection_mask(selection)

            if fade_edges and self.config.edge_smoothing:
                # Apply smooth edges to avoid artifacts
                mask = self._smooth_mask_edges(mask)

            # Delete by setting to zero or very small value
            self.stft[mask] *= 0.01  # Small value instead of zero to preserve some structure

            # Reconstruct audio
            self.current_audio = self.spectrogram_processor.compute_istft(
                self.stft, self.sample_rate, len(self.original_audio)
            )

            self._add_to_history("delete", selection)
            return True

        except Exception as e:
            self.logger.error(f"Delete operation failed: {e}")
            return False

    def copy_selection(self, selection: SpectralSelection) -> np.ndarray:
        """Copy spectral content from selection"""
        mask = self.get_selection_mask(selection)
        copied_stft = self.stft.copy()
        copied_stft[~mask] = 0  # Zero out everything except selection
        return copied_stft

    def paste_selection(self, copied_stft: np.ndarray,
                       target_selection: SpectralSelection) -> bool:
        """Paste spectral content to target location"""
        try:
            self._save_state()

            target_mask = self.get_selection_mask(target_selection)

            # Simple pasting - would need more sophisticated blending in practice
            self.stft[target_mask] = copied_stft[target_mask]

            # Reconstruct audio
            self.current_audio = self.spectrogram_processor.compute_istft(
                self.stft, self.sample_rate, len(self.original_audio)
            )

            self._add_to_history("paste", target_selection)
            return True

        except Exception as e:
            self.logger.error(f"Paste operation failed: {e}")
            return False

    def enhance_selection(self, selection: SpectralSelection,
                         gain_db: float = 6.0) -> bool:
        """Enhance (boost) spectral content in selection"""
        try:
            self._save_state()

            mask = self.get_selection_mask(selection)
            gain_linear = 10**(gain_db / 20)

            if self.config.edge_smoothing:
                mask = self._smooth_mask_edges(mask)

            # Apply gain
            self.stft[mask] *= gain_linear

            # Reconstruct audio
            self.current_audio = self.spectrogram_processor.compute_istft(
                self.stft, self.sample_rate, len(self.original_audio)
            )

            self._add_to_history("enhance", selection, {"gain_db": gain_db})
            return True

        except Exception as e:
            self.logger.error(f"Enhance operation failed: {e}")
            return False

    def reduce_selection(self, selection: SpectralSelection,
                        reduction_db: float = -12.0) -> bool:
        """Reduce spectral content in selection"""
        return self.enhance_selection(selection, reduction_db)

    def noise_reduce_selection(self, selection: SpectralSelection,
                              strength: float = 0.8) -> bool:
        """Apply noise reduction to selection using spectral subtraction"""
        try:
            self._save_state()

            mask = self.get_selection_mask(selection)

            # Estimate noise from selection
            noise_stft = self.stft[mask]
            noise_magnitude = np.median(np.abs(noise_stft))

            # Apply spectral subtraction to entire spectrogram
            magnitude = np.abs(self.stft)
            phase = np.angle(self.stft)

            # Spectral subtraction
            reduced_magnitude = magnitude - strength * noise_magnitude
            reduced_magnitude = np.maximum(reduced_magnitude, 0.1 * magnitude)

            # Reconstruct complex STFT
            if self.config.preserve_phase:
                self.stft = reduced_magnitude * np.exp(1j * phase)
            else:
                self.stft = reduced_magnitude * np.exp(1j * np.angle(self.stft))

            # Reconstruct audio
            self.current_audio = self.spectrogram_processor.compute_istft(
                self.stft, self.sample_rate, len(self.original_audio)
            )

            self._add_to_history("noise_reduce", selection, {"strength": strength})
            return True

        except Exception as e:
            self.logger.error(f"Noise reduction failed: {e}")
            return False

    def harmonic_enhance_selection(self, selection: SpectralSelection,
                                  harmonic_strength: float = 0.5) -> bool:
        """Enhance harmonics in selection"""
        try:
            self._save_state()

            mask = self.get_selection_mask(selection)

            # Simple harmonic enhancement by boosting harmonic frequencies
            magnitude = np.abs(self.stft)
            phase = np.angle(self.stft)

            # Find fundamental frequencies and boost harmonics
            for freq_idx in range(len(self.freqs)):
                if mask[freq_idx].any():
                    fundamental_freq = self.freqs[freq_idx]

                    # Boost 2nd and 3rd harmonics if present
                    for harmonic in [2, 3]:
                        harmonic_freq = fundamental_freq * harmonic
                        if harmonic_freq < self.freqs[-1]:
                            harmonic_idx = np.searchsorted(self.freqs, harmonic_freq)
                            if harmonic_idx < len(self.freqs):
                                magnitude[harmonic_idx] *= (1 + harmonic_strength)

            # Reconstruct
            self.stft = magnitude * np.exp(1j * phase)
            self.current_audio = self.spectrogram_processor.compute_istft(
                self.stft, self.sample_rate, len(self.original_audio)
            )

            self._add_to_history("harmonic_enhance", selection, {"strength": harmonic_strength})
            return True

        except Exception as e:
            self.logger.error(f"Harmonic enhancement failed: {e}")
            return False

    def interpolate_selection(self, selection: SpectralSelection) -> bool:
        """Interpolate missing spectral content"""
        try:
            self._save_state()

            mask = self.get_selection_mask(selection)

            if HAS_SCIPY:
                # Use scipy for advanced interpolation
                magnitude = np.abs(self.stft)
                phase = np.angle(self.stft)

                # Interpolate magnitude
                magnitude_interp = magnitude.copy()

                # Simple interpolation - replace with surrounding values
                if self.config.interpolation == "linear":
                    # Linear interpolation across time and frequency
                    coords = np.where(mask)
                    for i, (freq_idx, time_idx) in enumerate(zip(coords[0], coords[1])):
                        # Find neighboring values
                        neighbors = []

                        # Check surrounding pixels
                        for df, dt in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nf, nt = freq_idx + df, time_idx + dt
                            if (0 <= nf < magnitude.shape[0] and
                                0 <= nt < magnitude.shape[1] and
                                not mask[nf, nt]):
                                neighbors.append(magnitude[nf, nt])

                        if neighbors:
                            magnitude_interp[freq_idx, time_idx] = np.mean(neighbors)

                elif self.config.interpolation == "cubic":
                    # More sophisticated interpolation using scipy
                    from scipy import interpolate

                    # Create interpolation grid
                    y_grid, x_grid = np.mgrid[0:magnitude.shape[0], 0:magnitude.shape[1]]
                    points = np.column_stack([y_grid[~mask].ravel(), x_grid[~mask].ravel()])
                    values = magnitude[~mask].ravel()

                    # Interpolate missing values
                    interp_points = np.column_stack([y_grid[mask].ravel(), x_grid[mask].ravel()])

                    if len(points) > 0 and len(interp_points) > 0:
                        interp_values = interpolate.griddata(
                            points, values, interp_points,
                            method='cubic', fill_value=0
                        )
                        magnitude_interp[mask] = interp_values.reshape(-1)

                # Reconstruct
                self.stft = magnitude_interp * np.exp(1j * phase)
            else:
                # Simple averaging interpolation
                magnitude = np.abs(self.stft)
                phase = np.angle(self.stft)

                # Simple neighbor averaging
                kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]]) / 4
                if HAS_SCIPY:
                    smoothed = ndimage.convolve(magnitude, kernel, mode='reflect')
                else:
                    smoothed = magnitude  # Fallback to no interpolation

                magnitude[mask] = smoothed[mask]
                self.stft = magnitude * np.exp(1j * phase)

            # Reconstruct audio
            self.current_audio = self.spectrogram_processor.compute_istft(
                self.stft, self.sample_rate, len(self.original_audio)
            )

            self._add_to_history("interpolate", selection)
            return True

        except Exception as e:
            self.logger.error(f"Interpolation failed: {e}")
            return False

    def _smooth_mask_edges(self, mask: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """Smooth mask edges to reduce artifacts"""
        if not HAS_SCIPY:
            return mask

        # Create smoothing kernel
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size * kernel_size)

        # Apply smoothing
        smoothed = ndimage.convolve(mask.astype(float), kernel, mode='reflect')

        return smoothed

    def _save_state(self):
        """Save current state for undo"""
        state = {
            "stft": self.stft.copy(),
            "audio": self.current_audio.copy()
        }
        self.undo_stack.append(state)

        # Limit undo stack size
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def _add_to_history(self, operation: str, selection: SpectralSelection, params: Dict = None):
        """Add operation to edit history"""
        history_entry = {
            "operation": operation,
            "selection": selection,
            "parameters": params or {},
            "timestamp": __import__('time').time()
        }
        self.edit_history.append(history_entry)

    def undo(self) -> bool:
        """Undo last operation"""
        if not self.undo_stack:
            return False

        try:
            state = self.undo_stack.pop()
            self.stft = state["stft"]
            self.current_audio = state["audio"]
            return True
        except Exception as e:
            self.logger.error(f"Undo failed: {e}")
            return False

    def get_spectrogram_data(self, db_range: Tuple[float, float] = (-80, 0)) -> Dict[str, Any]:
        """Get spectrogram data for visualization"""
        magnitude_db = 20 * np.log10(np.abs(self.stft) + 1e-10)

        # Clip to display range
        magnitude_db = np.clip(magnitude_db, db_range[0], db_range[1])

        return {
            "magnitude_db": magnitude_db,
            "times": self.times,
            "frequencies": self.freqs,
            "sample_rate": self.sample_rate,
            "db_range": db_range
        }

    def export_current_audio(self) -> np.ndarray:
        """Export current edited audio"""
        return self.current_audio.copy()

    def reset_to_original(self):
        """Reset to original audio"""
        self.current_audio = self.original_audio.copy()
        self.stft = self.original_stft.copy()
        self.edit_history.clear()
        self.undo_stack.clear()

class SpectralVisualizer:
    """Visualization tools for spectral editing"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def plot_spectrogram(self, spectrogram_data: Dict[str, Any],
                        selections: List[SpectralSelection] = None,
                        figsize: Tuple[int, int] = (12, 8)) -> Any:
        """Plot spectrogram with optional selections"""
        if not HAS_MATPLOTLIB:
            self.logger.warning("Matplotlib not available for visualization")
            return None

        fig, ax = plt.subplots(figsize=figsize)

        # Plot spectrogram
        magnitude_db = spectrogram_data["magnitude_db"]
        times = spectrogram_data["times"]
        freqs = spectrogram_data["frequencies"]

        im = ax.pcolormesh(
            times, freqs, magnitude_db,
            shading='auto', cmap='viridis'
        )

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Magnitude (dB)')

        # Plot selections if provided
        if selections:
            for i, selection in enumerate(selections):
                rect = patches.Rectangle(
                    (selection.time_start, selection.freq_start),
                    selection.time_end - selection.time_start,
                    selection.freq_end - selection.freq_start,
                    linewidth=2, edgecolor=f'C{i}', facecolor='none',
                    label=f'Selection {i+1}'
                )
                ax.add_patch(rect)

        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Frequency (Hz)')
        ax.set_title('Spectral Editor')

        if selections:
            ax.legend()

        plt.tight_layout()
        return fig

    def plot_before_after(self, original_data: Dict, edited_data: Dict,
                         figsize: Tuple[int, int] = (15, 6)) -> Any:
        """Plot before/after comparison"""
        if not HAS_MATPLOTLIB:
            return None

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # Original
        im1 = ax1.pcolormesh(
            original_data["times"], original_data["frequencies"],
            original_data["magnitude_db"], shading='auto', cmap='viridis'
        )
        ax1.set_title('Original')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Frequency (Hz)')

        # Edited
        im2 = ax2.pcolormesh(
            edited_data["times"], edited_data["frequencies"],
            edited_data["magnitude_db"], shading='auto', cmap='viridis'
        )
        ax2.set_title('Edited')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Frequency (Hz)')

        # Shared colorbar
        cbar = plt.colorbar(im2, ax=[ax1, ax2])
        cbar.set_label('Magnitude (dB)')

        plt.tight_layout()
        return fig

def demo_spectral_editing():
    """Demonstrate spectral editing capabilities"""
    print("🎼 Chameleon Spectral Editor Demo")
    print("=" * 40)

    # Show available features
    features = [
        ("Spectrogram Computation", HAS_LIBROSA or True),
        ("Advanced Interpolation", HAS_SCIPY),
        ("Visualization", HAS_MATPLOTLIB),
        ("Noise Reduction", True),
        ("Harmonic Enhancement", True),
        ("Selection Tools", True),
        ("Undo/Redo", True)
    ]

    print("Available Features:")
    for feature, available in features:
        status = "✓" if available else "✗"
        print(f"  {status} {feature}")

    print(f"\nSpectral Editing Operations:")
    print(f"  🗑️ Delete Selection")
    print(f"  📋 Copy/Paste Selection")
    print(f"  🔊 Enhance/Reduce Selection")
    print(f"  🧹 Noise Reduction")
    print(f"  🎵 Harmonic Enhancement")
    print(f"  🔧 Spectral Interpolation")

    # Show recommended workflows
    print(f"\nRecommended Workflows:")
    print(f"  🎤 Vocal Isolation: Select and enhance vocal harmonics")
    print(f"  🔇 Noise Removal: Select noise regions and delete/reduce")
    print(f"  🎸 Instrument Separation: Enhance specific frequency ranges")
    print(f"  🔧 Audio Restoration: Interpolate missing spectral content")

if __name__ == "__main__":
    demo_spectral_editing()