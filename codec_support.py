#!/usr/bin/env python3
"""
Multi-format Audio Codec Support for Chameleon
Support for MP3, FLAC, OGG, M4A, and other popular audio formats
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
import warnings
import logging

# Audio codec libraries
try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    warnings.warn("soundfile not installed. Limited format support.")

try:
    from pydub import AudioSegment
    from pydub.utils import which
    HAS_PYDUB = True
    # Check for ffmpeg
    HAS_FFMPEG = which("ffmpeg") is not None
except ImportError:
    HAS_PYDUB = False
    HAS_FFMPEG = False
    warnings.warn("pydub not installed. MP3/M4A support limited.")

try:
    import mutagen
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    warnings.warn("mutagen not installed. Metadata support limited.")

try:
    import ffmpeg
    HAS_FFMPEG_PYTHON = True
except ImportError:
    HAS_FFMPEG_PYTHON = False

import numpy as np

@dataclass
class CodecInfo:
    """Information about an audio codec"""
    name: str
    extensions: List[str]
    supports_read: bool
    supports_write: bool
    quality_levels: List[str]
    max_sample_rate: int
    max_channels: int
    description: str

@dataclass
class ConversionConfig:
    """Configuration for audio format conversion"""
    target_format: str = "wav"
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    quality: str = "high"  # low, medium, high, lossless
    normalize: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    trim_start: float = 0.0
    trim_end: float = 0.0

class AudioCodecManager:
    """Manage audio codecs and format conversion"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supported_codecs = self._detect_codecs()
        self.temp_dir = tempfile.mkdtemp(prefix="chameleon_codec_")

    def _detect_codecs(self) -> Dict[str, CodecInfo]:
        """Detect available audio codecs"""
        codecs = {}

        # WAV (always supported)
        codecs["wav"] = CodecInfo(
            name="WAV",
            extensions=[".wav", ".wave"],
            supports_read=True,
            supports_write=True,
            quality_levels=["lossless"],
            max_sample_rate=192000,
            max_channels=32,
            description="Uncompressed PCM audio"
        )

        # FLAC
        if HAS_SOUNDFILE:
            codecs["flac"] = CodecInfo(
                name="FLAC",
                extensions=[".flac"],
                supports_read=True,
                supports_write=True,
                quality_levels=["lossless"],
                max_sample_rate=655350,
                max_channels=8,
                description="Free Lossless Audio Codec"
            )

        # OGG Vorbis
        if HAS_SOUNDFILE or HAS_PYDUB:
            codecs["ogg"] = CodecInfo(
                name="OGG Vorbis",
                extensions=[".ogg", ".oga"],
                supports_read=True,
                supports_write=HAS_PYDUB,
                quality_levels=["low", "medium", "high"],
                max_sample_rate=96000,
                max_channels=8,
                description="Open source lossy codec"
            )

        # MP3
        if HAS_PYDUB:
            codecs["mp3"] = CodecInfo(
                name="MP3",
                extensions=[".mp3"],
                supports_read=True,
                supports_write=True,
                quality_levels=["low", "medium", "high"],
                max_sample_rate=48000,
                max_channels=2,
                description="MPEG-1 Audio Layer III"
            )

        # M4A/AAC
        if HAS_PYDUB and HAS_FFMPEG:
            codecs["m4a"] = CodecInfo(
                name="M4A/AAC",
                extensions=[".m4a", ".aac", ".mp4"],
                supports_read=True,
                supports_write=True,
                quality_levels=["low", "medium", "high"],
                max_sample_rate=96000,
                max_channels=8,
                description="Advanced Audio Coding"
            )

        # AIFF
        if HAS_SOUNDFILE:
            codecs["aiff"] = CodecInfo(
                name="AIFF",
                extensions=[".aiff", ".aif"],
                supports_read=True,
                supports_write=True,
                quality_levels=["lossless"],
                max_sample_rate=192000,
                max_channels=32,
                description="Audio Interchange File Format"
            )

        return codecs

    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        formats = []
        for codec_info in self.supported_codecs.values():
            formats.extend(codec_info.extensions)
        return formats

    def detect_format(self, file_path: str) -> Optional[str]:
        """Detect audio format from file"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()

        for codec_name, codec_info in self.supported_codecs.items():
            if extension in codec_info.extensions:
                return codec_name

        return None

    def load_audio(self, file_path: str) -> Tuple[np.ndarray, int, Dict[str, Any]]:
        """Load audio file in any supported format"""
        file_path = str(file_path)
        format_type = self.detect_format(file_path)

        if not format_type:
            raise ValueError(f"Unsupported audio format: {file_path}")

        metadata = self.get_metadata(file_path)

        # Try different loading methods based on format
        if format_type in ["wav", "flac", "aiff"] and HAS_SOUNDFILE:
            return self._load_with_soundfile(file_path, metadata)
        elif format_type in ["mp3", "m4a", "ogg"] and HAS_PYDUB:
            return self._load_with_pydub(file_path, metadata)
        elif HAS_FFMPEG_PYTHON:
            return self._load_with_ffmpeg(file_path, metadata)
        else:
            raise RuntimeError(f"No suitable decoder for {format_type}")

    def _load_with_soundfile(self, file_path: str, metadata: Dict) -> Tuple[np.ndarray, int, Dict]:
        """Load audio using soundfile"""
        try:
            audio, sample_rate = sf.read(file_path, always_2d=True)
            # Convert to standard format (channels, samples)
            if audio.ndim == 2:
                audio = audio.T
            return audio, sample_rate, metadata
        except Exception as e:
            self.logger.error(f"Soundfile loading failed: {e}")
            raise

    def _load_with_pydub(self, file_path: str, metadata: Dict) -> Tuple[np.ndarray, int, Dict]:
        """Load audio using pydub"""
        try:
            # Load with pydub
            audio_segment = AudioSegment.from_file(file_path)

            # Convert to numpy array
            audio_data = np.array(audio_segment.get_array_of_samples())

            # Handle stereo
            if audio_segment.channels == 2:
                audio_data = audio_data.reshape((-1, 2)).T
            else:
                audio_data = audio_data.reshape((1, -1))

            # Normalize to float32
            if audio_segment.sample_width == 1:
                audio_data = audio_data.astype(np.float32) / 128.0
            elif audio_segment.sample_width == 2:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif audio_segment.sample_width == 4:
                audio_data = audio_data.astype(np.float32) / 2147483648.0

            return audio_data, audio_segment.frame_rate, metadata

        except Exception as e:
            self.logger.error(f"Pydub loading failed: {e}")
            raise

    def _load_with_ffmpeg(self, file_path: str, metadata: Dict) -> Tuple[np.ndarray, int, Dict]:
        """Load audio using ffmpeg-python"""
        try:
            # Probe file to get info
            probe = ffmpeg.probe(file_path)
            audio_info = next(stream for stream in probe['streams']
                            if stream['codec_type'] == 'audio')

            sample_rate = int(audio_info['sample_rate'])
            channels = int(audio_info['channels'])

            # Read audio data
            out, _ = (
                ffmpeg
                .input(file_path)
                .output('pipe:', format='f32le', acodec='pcm_f32le')
                .run(capture_stdout=True, quiet=True)
            )

            # Convert to numpy array
            audio_data = np.frombuffer(out, np.float32)

            # Reshape for channels
            if channels > 1:
                audio_data = audio_data.reshape((-1, channels)).T
            else:
                audio_data = audio_data.reshape((1, -1))

            return audio_data, sample_rate, metadata

        except Exception as e:
            self.logger.error(f"FFmpeg loading failed: {e}")
            raise

    def save_audio(self, audio: np.ndarray, file_path: str, sample_rate: int,
                  config: ConversionConfig = None) -> bool:
        """Save audio in specified format"""
        if config is None:
            config = ConversionConfig()

        file_path = str(file_path)
        format_type = self.detect_format(file_path) or config.target_format

        # Apply preprocessing
        processed_audio = self._preprocess_audio(audio, sample_rate, config)

        # Choose save method
        if format_type in ["wav", "flac", "aiff"] and HAS_SOUNDFILE:
            return self._save_with_soundfile(processed_audio, file_path, sample_rate, config)
        elif format_type in ["mp3", "m4a", "ogg"] and HAS_PYDUB:
            return self._save_with_pydub(processed_audio, file_path, sample_rate, config)
        elif HAS_FFMPEG_PYTHON:
            return self._save_with_ffmpeg(processed_audio, file_path, sample_rate, config)
        else:
            raise RuntimeError(f"No suitable encoder for {format_type}")

    def _preprocess_audio(self, audio: np.ndarray, sample_rate: int,
                         config: ConversionConfig) -> np.ndarray:
        """Apply preprocessing steps before saving"""
        processed = audio.copy()

        # Resample if needed
        if config.sample_rate and config.sample_rate != sample_rate:
            processed = self._resample_audio(processed, sample_rate, config.sample_rate)
            sample_rate = config.sample_rate

        # Convert channels
        if config.channels:
            processed = self._convert_channels(processed, config.channels)

        # Apply fades
        if config.fade_in > 0:
            processed = self._apply_fade_in(processed, sample_rate, config.fade_in)
        if config.fade_out > 0:
            processed = self._apply_fade_out(processed, sample_rate, config.fade_out)

        # Trim audio
        if config.trim_start > 0 or config.trim_end > 0:
            processed = self._trim_audio(processed, sample_rate, config.trim_start, config.trim_end)

        # Normalize
        if config.normalize:
            processed = self._normalize_audio(processed)

        return processed

    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate"""
        if orig_sr == target_sr:
            return audio

        # Simple resampling (for production use librosa.resample)
        ratio = target_sr / orig_sr
        new_length = int(audio.shape[-1] * ratio)

        if audio.ndim == 1:
            indices = np.linspace(0, len(audio) - 1, new_length)
            return np.interp(indices, np.arange(len(audio)), audio)
        else:
            resampled = np.zeros((audio.shape[0], new_length))
            for ch in range(audio.shape[0]):
                indices = np.linspace(0, audio.shape[1] - 1, new_length)
                resampled[ch] = np.interp(indices, np.arange(audio.shape[1]), audio[ch])
            return resampled

    def _convert_channels(self, audio: np.ndarray, target_channels: int) -> np.ndarray:
        """Convert number of channels"""
        current_channels = 1 if audio.ndim == 1 else audio.shape[0]

        if current_channels == target_channels:
            return audio

        if target_channels == 1:
            # Convert to mono
            if audio.ndim == 1:
                return audio
            else:
                return np.mean(audio, axis=0, keepdims=True)
        elif target_channels == 2 and current_channels == 1:
            # Convert mono to stereo
            if audio.ndim == 1:
                return np.array([audio, audio])
            else:
                return np.repeat(audio, 2, axis=0)
        else:
            # More complex channel conversion
            if current_channels > target_channels:
                # Downmix
                return audio[:target_channels]
            else:
                # Upmix by duplicating channels
                additional_channels = target_channels - current_channels
                if audio.ndim == 1:
                    audio = audio.reshape(1, -1)
                repeated = np.repeat(audio[-1:], additional_channels, axis=0)
                return np.vstack([audio, repeated])

    def _apply_fade_in(self, audio: np.ndarray, sample_rate: int, duration: float) -> np.ndarray:
        """Apply fade-in effect"""
        fade_samples = int(duration * sample_rate)
        if fade_samples >= audio.shape[-1]:
            return audio

        fade_curve = np.linspace(0, 1, fade_samples)

        if audio.ndim == 1:
            audio[:fade_samples] *= fade_curve
        else:
            audio[:, :fade_samples] *= fade_curve

        return audio

    def _apply_fade_out(self, audio: np.ndarray, sample_rate: int, duration: float) -> np.ndarray:
        """Apply fade-out effect"""
        fade_samples = int(duration * sample_rate)
        if fade_samples >= audio.shape[-1]:
            return audio

        fade_curve = np.linspace(1, 0, fade_samples)

        if audio.ndim == 1:
            audio[-fade_samples:] *= fade_curve
        else:
            audio[:, -fade_samples:] *= fade_curve

        return audio

    def _trim_audio(self, audio: np.ndarray, sample_rate: int,
                   start_time: float, end_time: float) -> np.ndarray:
        """Trim audio to specified time range"""
        start_sample = int(start_time * sample_rate)
        if end_time > 0:
            end_sample = int(end_time * sample_rate)
        else:
            end_sample = audio.shape[-1]

        if audio.ndim == 1:
            return audio[start_sample:end_sample]
        else:
            return audio[:, start_sample:end_sample]

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to prevent clipping"""
        peak = np.abs(audio).max()
        if peak > 0:
            return audio / peak * 0.95
        return audio

    def _save_with_soundfile(self, audio: np.ndarray, file_path: str,
                           sample_rate: int, config: ConversionConfig) -> bool:
        """Save audio using soundfile"""
        try:
            # Convert to format expected by soundfile
            if audio.ndim > 1:
                audio = audio.T  # soundfile expects (samples, channels)

            # Determine subtype based on quality
            subtype_map = {
                "low": "PCM_16",
                "medium": "PCM_24",
                "high": "PCM_24",
                "lossless": "PCM_32"
            }

            subtype = subtype_map.get(config.quality, "PCM_24")

            sf.write(file_path, audio, sample_rate, subtype=subtype)
            return True

        except Exception as e:
            self.logger.error(f"Soundfile save failed: {e}")
            return False

    def _save_with_pydub(self, audio: np.ndarray, file_path: str,
                        sample_rate: int, config: ConversionConfig) -> bool:
        """Save audio using pydub"""
        try:
            # Convert to pydub format
            if audio.ndim == 1:
                channels = 1
                audio_data = audio
            else:
                channels = audio.shape[0]
                audio_data = audio.T.flatten()  # Interleave channels

            # Convert to int16
            audio_int16 = (audio_data * 32767).astype(np.int16)

            # Create AudioSegment
            audio_segment = AudioSegment(
                audio_int16.tobytes(),
                frame_rate=sample_rate,
                sample_width=2,
                channels=channels
            )

            # Get export parameters based on format and quality
            export_params = self._get_export_parameters(file_path, config)

            # Export
            audio_segment.export(file_path, **export_params)
            return True

        except Exception as e:
            self.logger.error(f"Pydub save failed: {e}")
            return False

    def _save_with_ffmpeg(self, audio: np.ndarray, file_path: str,
                         sample_rate: int, config: ConversionConfig) -> bool:
        """Save audio using ffmpeg-python"""
        try:
            # Convert audio to bytes
            if audio.ndim > 1:
                audio_data = audio.T.flatten()  # Interleave channels
                channels = audio.shape[0]
            else:
                audio_data = audio
                channels = 1

            audio_bytes = audio_data.astype(np.float32).tobytes()

            # Build ffmpeg command
            input_stream = ffmpeg.input(
                'pipe:',
                format='f32le',
                acodec='pcm_f32le',
                ac=channels,
                ar=sample_rate
            )

            # Get output parameters
            output_params = self._get_ffmpeg_parameters(file_path, config)

            output_stream = ffmpeg.output(input_stream, file_path, **output_params)

            # Run ffmpeg
            ffmpeg.run(output_stream, input=audio_bytes, quiet=True, overwrite_output=True)
            return True

        except Exception as e:
            self.logger.error(f"FFmpeg save failed: {e}")
            return False

    def _get_export_parameters(self, file_path: str, config: ConversionConfig) -> Dict[str, Any]:
        """Get export parameters for pydub based on format and quality"""
        format_type = self.detect_format(file_path)
        params = {"format": format_type}

        if format_type == "mp3":
            bitrate_map = {
                "low": "128k",
                "medium": "192k",
                "high": "320k"
            }
            params["bitrate"] = bitrate_map.get(config.quality, "192k")

        elif format_type == "ogg":
            quality_map = {
                "low": "3",
                "medium": "6",
                "high": "9"
            }
            params["parameters"] = ["-q:a", quality_map.get(config.quality, "6")]

        elif format_type == "m4a":
            bitrate_map = {
                "low": "128k",
                "medium": "256k",
                "high": "320k"
            }
            params["bitrate"] = bitrate_map.get(config.quality, "256k")

        return params

    def _get_ffmpeg_parameters(self, file_path: str, config: ConversionConfig) -> Dict[str, Any]:
        """Get ffmpeg output parameters"""
        format_type = self.detect_format(file_path)
        params = {}

        if format_type == "mp3":
            bitrate_map = {
                "low": "128k",
                "medium": "192k",
                "high": "320k"
            }
            params.update({
                "acodec": "mp3",
                "audio_bitrate": bitrate_map.get(config.quality, "192k")
            })

        elif format_type == "flac":
            params.update({
                "acodec": "flac",
                "compression_level": 8 if config.quality == "high" else 5
            })

        elif format_type == "ogg":
            quality_map = {
                "low": "3",
                "medium": "6",
                "high": "9"
            }
            params.update({
                "acodec": "libvorbis",
                "q:a": quality_map.get(config.quality, "6")
            })

        return params

    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from audio file"""
        if not HAS_MUTAGEN:
            return {}

        try:
            file_path = str(file_path)
            audio_file = mutagen.File(file_path)

            if audio_file is None:
                return {}

            metadata = {
                "duration": getattr(audio_file.info, 'length', 0),
                "bitrate": getattr(audio_file.info, 'bitrate', 0),
                "sample_rate": getattr(audio_file.info, 'sample_rate', 0),
                "channels": getattr(audio_file.info, 'channels', 0)
            }

            # Extract common tags
            tag_mapping = {
                "title": ["TIT2", "TITLE", "\xa9nam"],
                "artist": ["TPE1", "ARTIST", "\xa9ART"],
                "album": ["TALB", "ALBUM", "\xa9alb"],
                "date": ["TDRC", "DATE", "\xa9day"],
                "genre": ["TCON", "GENRE", "\xa9gen"],
                "track": ["TRCK", "TRACKNUMBER", "trkn"]
            }

            for field, tags in tag_mapping.items():
                for tag in tags:
                    if tag in audio_file:
                        value = audio_file[tag]
                        if isinstance(value, list):
                            value = value[0]
                        metadata[field] = str(value)
                        break

            return metadata

        except Exception as e:
            self.logger.warning(f"Metadata extraction failed: {e}")
            return {}

    def convert_format(self, input_path: str, output_path: str,
                      config: ConversionConfig = None) -> bool:
        """Convert audio file from one format to another"""
        try:
            # Load audio
            audio, sample_rate, metadata = self.load_audio(input_path)

            # Save in new format
            success = self.save_audio(audio, output_path, sample_rate, config)

            if success:
                self.logger.info(f"Converted {input_path} -> {output_path}")

            return success

        except Exception as e:
            self.logger.error(f"Format conversion failed: {e}")
            return False

    def batch_convert(self, input_dir: str, output_dir: str,
                     target_format: str, config: ConversionConfig = None) -> Dict[str, bool]:
        """Batch convert audio files"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if config is None:
            config = ConversionConfig(target_format=target_format)
        else:
            config.target_format = target_format

        results = {}
        supported_extensions = self.get_supported_formats()

        for file_path in input_path.rglob("*"):
            if file_path.suffix.lower() in supported_extensions:
                # Create output filename
                output_file = output_path / f"{file_path.stem}.{target_format}"

                # Convert file
                success = self.convert_format(str(file_path), str(output_file), config)
                results[str(file_path)] = success

        return results

    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

def demo_codec_support():
    """Demonstrate codec support capabilities"""
    print("🎵 Chameleon Codec Support Demo")
    print("=" * 40)

    # Initialize codec manager
    codec_manager = AudioCodecManager()

    # Show supported formats
    print("Supported Audio Formats:")
    for codec_name, codec_info in codec_manager.supported_codecs.items():
        status = "✓" if codec_info.supports_read and codec_info.supports_write else "⚠"
        print(f"  {status} {codec_info.name}: {', '.join(codec_info.extensions)}")
        print(f"    {codec_info.description}")

    # Show available libraries
    print(f"\nAvailable Libraries:")
    print(f"  soundfile: {'✓' if HAS_SOUNDFILE else '✗'}")
    print(f"  pydub: {'✓' if HAS_PYDUB else '✗'}")
    print(f"  ffmpeg: {'✓' if HAS_FFMPEG else '✗'}")
    print(f"  mutagen: {'✓' if HAS_MUTAGEN else '✗'}")

    # Cleanup
    codec_manager.cleanup()

if __name__ == "__main__":
    demo_codec_support()