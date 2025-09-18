#!/usr/bin/env python3
"""
Audio Format Converter - Handles various audio format conversions
"""

import array
import struct
import wave
from pathlib import Path
from typing import Optional, Tuple, List

class AudioConverter:
    """Convert between different audio formats and parameters"""

    def __init__(self):
        self.supported_formats = ['.wav', '.raw', '.pcm']

    def change_channels(self, samples: array.array, orig_channels: int,
                       target_channels: int) -> array.array:
        """Convert between mono and stereo"""
        if orig_channels == target_channels:
            return samples

        result = array.array('h')

        if orig_channels == 1 and target_channels == 2:
            # Mono to stereo: duplicate channel
            for s in samples:
                result.append(s)
                result.append(s)

        elif orig_channels == 2 and target_channels == 1:
            # Stereo to mono: average channels
            for i in range(0, len(samples) - 1, 2):
                mono = (samples[i] + samples[i + 1]) // 2
                result.append(mono)

        return result

    def convert_bit_depth(self, samples: array.array, target_bits: int) -> array.array:
        """Convert between different bit depths"""
        if target_bits == 16:
            return samples

        result = array.array('h')

        if target_bits == 8:
            # 16-bit to 8-bit
            for s in samples:
                # Scale and shift to unsigned 8-bit
                s8 = ((s + 32768) >> 8)
                # Convert back to signed 16-bit for storage
                result.append((s8 - 128) << 8)

        elif target_bits == 24:
            # 16-bit to 24-bit (store as 16-bit with scaling info)
            # Note: array.array doesn't support 24-bit, so we scale
            for s in samples:
                result.append(s)  # Keep as 16-bit

        elif target_bits == 32:
            # 16-bit to 32-bit
            for s in samples:
                result.append(s)  # Keep as 16-bit

        return result

    def wav_to_raw(self, wav_path: str, raw_path: str) -> bool:
        """Convert WAV to raw PCM"""
        try:
            with wave.open(wav_path, 'rb') as wav:
                frames = wav.readframes(wav.getnframes())

            with open(raw_path, 'wb') as raw:
                raw.write(frames)

            return True
        except Exception as e:
            print(f"Error converting to raw: {e}")
            return False

    def raw_to_wav(self, raw_path: str, wav_path: str,
                   sample_rate: int = 44100, channels: int = 1,
                   sample_width: int = 2) -> bool:
        """Convert raw PCM to WAV"""
        try:
            with open(raw_path, 'rb') as raw:
                data = raw.read()

            with wave.open(wav_path, 'wb') as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(sample_width)
                wav.setframerate(sample_rate)
                wav.writeframes(data)

            return True
        except Exception as e:
            print(f"Error converting to WAV: {e}")
            return False

    def split_stereo(self, stereo_samples: array.array) -> Tuple[array.array, array.array]:
        """Split stereo audio into left and right channels"""
        left = array.array('h')
        right = array.array('h')

        for i in range(0, len(stereo_samples) - 1, 2):
            left.append(stereo_samples[i])
            right.append(stereo_samples[i + 1])

        return left, right

    def merge_channels(self, left: array.array, right: array.array) -> array.array:
        """Merge two mono channels into stereo"""
        stereo = array.array('h')
        min_len = min(len(left), len(right))

        for i in range(min_len):
            stereo.append(left[i])
            stereo.append(right[i])

        return stereo

    def normalize_format(self, input_path: str, output_path: str,
                        target_rate: int = 44100, target_channels: int = 1,
                        target_bits: int = 16) -> bool:
        """Normalize audio file to standard format"""
        try:
            # Load input
            with wave.open(input_path, 'rb') as wav:
                params = wav.getparams()
                frames = wav.readframes(params.nframes)
                samples = array.array('h', frames)

            # Skip resampling for now (would need to import from chameleon)
            # if params.framerate != target_rate:
            #     samples = self.resample(samples, params.framerate, target_rate)

            # Change channels if needed
            if params.nchannels != target_channels:
                samples = self.change_channels(samples, params.nchannels, target_channels)

            # Save output
            with wave.open(output_path, 'wb') as wav:
                wav.setnchannels(target_channels)
                wav.setsampwidth(target_bits // 8)
                wav.setframerate(target_rate)
                wav.writeframes(samples.tobytes())

            return True
        except Exception as e:
            print(f"Error normalizing format: {e}")
            return False

    def create_silence(self, duration_ms: int, sample_rate: int = 44100) -> array.array:
        """Create silence of specified duration"""
        num_samples = int((duration_ms / 1000) * sample_rate)
        return array.array('h', [0] * num_samples)

    def concatenate(self, audio_files: List[str], output_path: str,
                   gap_ms: int = 0) -> bool:
        """Concatenate multiple audio files"""
        try:
            result = array.array('h')
            target_rate = None
            target_channels = None

            gap_samples = None
            if gap_ms > 0:
                gap_samples = self.create_silence(gap_ms)

            for i, filepath in enumerate(audio_files):
                with wave.open(filepath, 'rb') as wav:
                    params = wav.getparams()

                    # Set target format from first file
                    if i == 0:
                        target_rate = params.framerate
                        target_channels = params.nchannels

                    frames = wav.readframes(params.nframes)
                    samples = array.array('h', frames)

                    # Convert to target format if needed
                    # Skip resampling for concatenation
                    # if params.framerate != target_rate:
                    #     samples = self.resample(samples, params.framerate, target_rate)
                    if params.nchannels != target_channels:
                        samples = self.change_channels(samples, params.nchannels, target_channels)

                    # Add to result
                    result.extend(samples)

                    # Add gap if not last file
                    if gap_samples and i < len(audio_files) - 1:
                        result.extend(gap_samples)

            # Save concatenated audio
            with wave.open(output_path, 'wb') as wav:
                wav.setnchannels(target_channels)
                wav.setsampwidth(2)
                wav.setframerate(target_rate)
                wav.writeframes(result.tobytes())

            return True
        except Exception as e:
            print(f"Error concatenating files: {e}")
            return False