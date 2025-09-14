#!/usr/bin/env python3
"""
Format Conversion Pipeline - Advanced audio format processing
Professional-grade conversion with quality preservation and metadata handling
"""

import os
import subprocess
import struct
import wave
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import tempfile
import shutil

@dataclass
class AudioMetadata:
    """Complete audio metadata structure"""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    track: Optional[int] = None
    duration: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    format: Optional[str] = None
    codec: Optional[str] = None
    custom_tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.custom_tags is None:
            self.custom_tags = {}

@dataclass
class ConversionProfile:
    """Audio conversion profile with quality settings"""
    name: str
    format: str
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    quality: Optional[str] = None  # 'low', 'medium', 'high', 'lossless'
    custom_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}

class FormatPipeline:
    """Advanced audio format conversion pipeline"""
    
    def __init__(self):
        self.temp_dir = None
        self.cleanup_files = []
        
        # Built-in conversion profiles
        self.profiles = {
            'podcast_mp3': ConversionProfile(
                name='Podcast MP3',
                format='mp3',
                codec='mp3',
                bitrate=128,
                sample_rate=44100,
                channels=2,
                quality='medium'
            ),
            'music_high_mp3': ConversionProfile(
                name='Music High Quality MP3',
                format='mp3',
                codec='mp3',
                bitrate=320,
                sample_rate=44100,
                channels=2,
                quality='high'
            ),
            'speech_optimized': ConversionProfile(
                name='Speech Optimized',
                format='mp3',
                codec='mp3',
                bitrate=64,
                sample_rate=22050,
                channels=1,
                quality='medium'
            ),
            'lossless_flac': ConversionProfile(
                name='Lossless FLAC',
                format='flac',
                codec='flac',
                sample_rate=44100,
                channels=2,
                quality='lossless'
            ),
            'cd_quality_wav': ConversionProfile(
                name='CD Quality WAV',
                format='wav',
                codec='pcm_s16le',
                sample_rate=44100,
                channels=2,
                quality='lossless'
            ),
            'broadcast_wav': ConversionProfile(
                name='Broadcast WAV',
                format='wav',
                codec='pcm_s24le',
                sample_rate=48000,
                channels=2,
                quality='lossless'
            )
        }
        
        # Format capabilities
        self.format_info = {
            'wav': {
                'codecs': ['pcm_s16le', 'pcm_s24le', 'pcm_s32le'],
                'max_bitrate': None,
                'lossless': True,
                'metadata_support': 'basic'
            },
            'mp3': {
                'codecs': ['mp3'],
                'max_bitrate': 320,
                'lossless': False,
                'metadata_support': 'id3v2'
            },
            'flac': {
                'codecs': ['flac'],
                'max_bitrate': None,
                'lossless': True,
                'metadata_support': 'vorbis_comment'
            },
            'ogg': {
                'codecs': ['vorbis', 'opus'],
                'max_bitrate': 500,
                'lossless': False,
                'metadata_support': 'vorbis_comment'
            },
            'm4a': {
                'codecs': ['aac'],
                'max_bitrate': 320,
                'lossless': False,
                'metadata_support': 'mp4'
            }
        }
    
    def __enter__(self):
        """Context manager entry"""
        self.temp_dir = tempfile.mkdtemp(prefix='chameleon_pipeline_')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()
    
    def cleanup(self):
        """Clean up temporary files"""
        for file_path in self.cleanup_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
    
    def convert_file(self, input_file: str, output_file: str,
                    profile: Union[str, ConversionProfile],
                    preserve_metadata: bool = True,
                    normalize_audio: bool = False,
                    apply_effects: Optional[Dict] = None) -> bool:
        """Convert audio file using specified profile"""
        
        # Resolve profile
        if isinstance(profile, str):
            if profile not in self.profiles:
                print(f"Unknown profile: {profile}")
                return False
            conv_profile = self.profiles[profile]
        else:
            conv_profile = profile
        
        try:
            # Extract input metadata
            input_metadata = None
            if preserve_metadata:
                input_metadata = self.extract_metadata(input_file)
            
            # Create working file
            working_file = input_file
            
            # Apply audio processing if requested
            if normalize_audio or apply_effects:
                working_file = self._apply_preprocessing(
                    input_file, normalize_audio, apply_effects
                )
            
            # Perform format conversion
            success = self._convert_format(working_file, output_file, conv_profile)
            
            # Restore metadata
            if success and preserve_metadata and input_metadata:
                self._apply_metadata(output_file, input_metadata)
            
            return success
            
        except Exception as e:
            print(f"Conversion error: {e}")
            return False
    
    def batch_convert(self, input_directory: str, output_directory: str,
                     profile: Union[str, ConversionProfile],
                     preserve_structure: bool = True,
                     file_pattern: str = "*") -> Dict[str, bool]:
        """Batch convert multiple files"""
        
        import glob
        
        # Find input files
        if preserve_structure:
            pattern = os.path.join(input_directory, "**", file_pattern)
            input_files = glob.glob(pattern, recursive=True)
        else:
            pattern = os.path.join(input_directory, file_pattern)
            input_files = glob.glob(pattern)
        
        # Filter for audio files
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
        audio_files = [f for f in input_files 
                      if any(f.lower().endswith(ext) for ext in audio_extensions)]
        
        if not audio_files:
            print(f"No audio files found in {input_directory}")
            return {}
        
        # Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)
        
        # Get output format from profile
        if isinstance(profile, str):
            conv_profile = self.profiles[profile]
        else:
            conv_profile = profile
        
        output_ext = f".{conv_profile.format}"
        
        results = {}
        
        print(f"Converting {len(audio_files)} files...")
        
        for i, input_file in enumerate(audio_files, 1):
            # Calculate output path
            if preserve_structure:
                rel_path = os.path.relpath(input_file, input_directory)
                output_file = os.path.join(output_directory, rel_path)
                output_file = os.path.splitext(output_file)[0] + output_ext
                
                # Ensure output subdirectory exists
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
            else:
                filename = os.path.basename(input_file)
                output_file = os.path.join(
                    output_directory,
                    os.path.splitext(filename)[0] + output_ext
                )
            
            print(f"[{i}/{len(audio_files)}] Converting: {os.path.basename(input_file)}")
            
            success = self.convert_file(input_file, output_file, profile)
            results[input_file] = success
            
            if success:
                print(f"  ✓ Success: {os.path.basename(output_file)}")
            else:
                print(f"  ✗ Failed: {os.path.basename(input_file)}")
        
        # Summary
        successful = sum(1 for success in results.values() if success)
        print(f"\nBatch conversion complete:")
        print(f"  Successful: {successful}/{len(audio_files)}")
        print(f"  Failed: {len(audio_files) - successful}/{len(audio_files)}")
        
        return results
    
    def _convert_format(self, input_file: str, output_file: str,
                       profile: ConversionProfile) -> bool:
        """Perform the actual format conversion"""
        
        # Check if we have ffmpeg available
        if self._has_ffmpeg():
            return self._convert_with_ffmpeg(input_file, output_file, profile)
        else:
            # Fallback to basic conversion
            return self._convert_basic(input_file, output_file, profile)
    
    def _has_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _convert_with_ffmpeg(self, input_file: str, output_file: str,
                            profile: ConversionProfile) -> bool:
        """Convert using ffmpeg"""
        cmd = ['ffmpeg', '-y', '-i', input_file]
        
        # Audio codec
        if profile.codec:
            cmd.extend(['-acodec', profile.codec])
        
        # Sample rate
        if profile.sample_rate:
            cmd.extend(['-ar', str(profile.sample_rate)])
        
        # Channels
        if profile.channels:
            cmd.extend(['-ac', str(profile.channels)])
        
        # Bitrate
        if profile.bitrate and profile.format != 'wav':
            cmd.extend(['-ab', f'{profile.bitrate}k'])
        
        # Quality settings
        if profile.quality == 'high' and profile.format == 'mp3':
            cmd.extend(['-q:a', '0'])
        elif profile.quality == 'medium' and profile.format == 'mp3':
            cmd.extend(['-q:a', '2'])
        elif profile.quality == 'low' and profile.format == 'mp3':
            cmd.extend(['-q:a', '5'])
        
        # Custom parameters
        for key, value in profile.custom_params.items():
            cmd.extend([f'-{key}', str(value)])
        
        cmd.append(output_file)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"FFmpeg conversion error: {e}")
            return False
    
    def _convert_basic(self, input_file: str, output_file: str,
                      profile: ConversionProfile) -> bool:
        """Basic conversion without ffmpeg"""
        
        # Only support WAV to WAV conversion in basic mode
        if not (input_file.lower().endswith('.wav') and 
                profile.format.lower() == 'wav'):
            print("Basic conversion only supports WAV format")
            return False
        
        try:
            # Read input WAV
            with wave.open(input_file, 'rb') as wav_in:
                frames = wav_in.readframes(wav_in.getnframes())
                input_params = wav_in.getparams()
            
            # Convert sample rate if needed
            if (profile.sample_rate and 
                profile.sample_rate != input_params.framerate):
                frames = self._resample_audio(
                    frames, input_params.framerate, profile.sample_rate
                )
            
            # Convert channels if needed
            if profile.channels and profile.channels != input_params.nchannels:
                frames = self._convert_channels(
                    frames, input_params.nchannels, profile.channels
                )
            
            # Write output WAV
            with wave.open(output_file, 'wb') as wav_out:
                wav_out.setnchannels(profile.channels or input_params.nchannels)
                wav_out.setsampwidth(input_params.sampwidth)
                wav_out.setframerate(profile.sample_rate or input_params.framerate)
                wav_out.writeframes(frames)
            
            return True
            
        except Exception as e:
            print(f"Basic conversion error: {e}")
            return False
    
    def _resample_audio(self, audio_data: bytes, 
                       from_rate: int, to_rate: int) -> bytes:
        """Simple audio resampling"""
        if from_rate == to_rate:
            return audio_data
        
        # Convert bytes to samples
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0]
            samples.append(sample)
        
        # Simple linear interpolation resampling
        ratio = to_rate / from_rate
        new_length = int(len(samples) * ratio)
        resampled = []
        
        for i in range(new_length):
            src_index = i / ratio
            src_index_int = int(src_index)
            fraction = src_index - src_index_int
            
            if src_index_int + 1 < len(samples):
                # Linear interpolation
                sample = (samples[src_index_int] * (1 - fraction) + 
                         samples[src_index_int + 1] * fraction)
            else:
                sample = samples[src_index_int] if src_index_int < len(samples) else 0
            
            resampled.append(int(sample))
        
        # Convert back to bytes
        output = b''
        for sample in resampled:
            output += struct.pack('<h', sample)
        
        return output
    
    def _convert_channels(self, audio_data: bytes, 
                         from_channels: int, to_channels: int) -> bytes:
        """Convert between mono and stereo"""
        if from_channels == to_channels:
            return audio_data
        
        samples = []
        sample_size = 2  # 16-bit samples
        
        for i in range(0, len(audio_data) - sample_size + 1, sample_size * from_channels):
            frame_samples = []
            for ch in range(from_channels):
                offset = i + ch * sample_size
                if offset + sample_size <= len(audio_data):
                    sample = struct.unpack('<h', audio_data[offset:offset + sample_size])[0]
                    frame_samples.append(sample)
            
            if to_channels == 1 and from_channels == 2:
                # Stereo to mono - average channels
                mono_sample = sum(frame_samples) // len(frame_samples)
                samples.append(mono_sample)
            elif to_channels == 2 and from_channels == 1:
                # Mono to stereo - duplicate channel
                samples.extend([frame_samples[0], frame_samples[0]])
        
        # Convert back to bytes
        output = b''
        for sample in samples:
            output += struct.pack('<h', sample)
        
        return output
    
    def _apply_preprocessing(self, input_file: str, 
                           normalize: bool, effects: Optional[Dict]) -> str:
        """Apply audio preprocessing"""
        temp_file = os.path.join(self.temp_dir, 'preprocessed.wav')
        self.cleanup_files.append(temp_file)
        
        # Start with original file
        working_file = input_file
        
        # Apply normalization
        if normalize:
            norm_file = os.path.join(self.temp_dir, 'normalized.wav')
            self.cleanup_files.append(norm_file)
            
            if self._normalize_audio(working_file, norm_file):
                working_file = norm_file
        
        # Apply effects
        if effects:
            fx_file = os.path.join(self.temp_dir, 'effects.wav')
            self.cleanup_files.append(fx_file)
            
            if self._apply_audio_effects(working_file, fx_file, effects):
                working_file = fx_file
        
        return working_file
    
    def _normalize_audio(self, input_file: str, output_file: str) -> bool:
        """Normalize audio to -1dB peak"""
        try:
            import audio_utils
            
            # Load audio
            with wave.open(input_file, 'rb') as wav:
                params = wav.getparams()
                audio_data = wav.readframes(params.nframes)
            
            # Normalize
            normalized_data = audio_utils.normalize_audio(audio_data, 0.95)
            
            # Save
            with wave.open(output_file, 'wb') as wav:
                wav.setparams(params)
                wav.writeframes(normalized_data)
            
            return True
        except Exception as e:
            print(f"Normalization error: {e}")
            return False
    
    def _apply_audio_effects(self, input_file: str, output_file: str,
                           effects: Dict) -> bool:
        """Apply audio effects"""
        try:
            import audio_processor
            
            # Load audio
            with wave.open(input_file, 'rb') as wav:
                params = wav.getparams()
                audio_data = wav.readframes(params.nframes)
                sample_rate = params.framerate
            
            # Apply effects
            processor = audio_processor.AudioProcessor(sample_rate)
            processed_data = processor.process_audio(audio_data, effects)
            
            # Save
            with wave.open(output_file, 'wb') as wav:
                wav.setparams(params)
                wav.writeframes(processed_data)
            
            return True
        except Exception as e:
            print(f"Effects error: {e}")
            return False
    
    def extract_metadata(self, audio_file: str) -> Optional[AudioMetadata]:
        """Extract metadata from audio file"""
        metadata = AudioMetadata()
        
        try:
            # Try with ffprobe first
            if self._has_ffmpeg():
                metadata = self._extract_metadata_ffprobe(audio_file)
            else:
                # Basic metadata extraction
                metadata = self._extract_metadata_basic(audio_file)
            
            return metadata
            
        except Exception as e:
            print(f"Metadata extraction error: {e}")
            return None
    
    def _extract_metadata_ffprobe(self, audio_file: str) -> AudioMetadata:
        """Extract metadata using ffprobe"""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', audio_file
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            metadata = AudioMetadata()
            
            # Format information
            if 'format' in data:
                fmt = data['format']
                metadata.duration = float(fmt.get('duration', 0))
                metadata.bitrate = int(fmt.get('bit_rate', 0))
                metadata.format = fmt.get('format_name', '')
                
                # Tags
                if 'tags' in fmt:
                    tags = fmt['tags']
                    metadata.title = tags.get('title') or tags.get('TITLE')
                    metadata.artist = tags.get('artist') or tags.get('ARTIST')
                    metadata.album = tags.get('album') or tags.get('ALBUM')
                    metadata.genre = tags.get('genre') or tags.get('GENRE')
                    
                    if 'date' in tags or 'DATE' in tags:
                        try:
                            year_str = tags.get('date') or tags.get('DATE')
                            metadata.year = int(year_str[:4])
                        except:
                            pass
            
            # Stream information
            if 'streams' in data:
                for stream in data['streams']:
                    if stream.get('codec_type') == 'audio':
                        metadata.sample_rate = int(stream.get('sample_rate', 0))
                        metadata.channels = int(stream.get('channels', 0))
                        metadata.codec = stream.get('codec_name', '')
                        break
            
            return metadata
            
        except Exception as e:
            print(f"FFprobe metadata error: {e}")
            return AudioMetadata()
    
    def _extract_metadata_basic(self, audio_file: str) -> AudioMetadata:
        """Basic metadata extraction for WAV files"""
        metadata = AudioMetadata()
        
        if audio_file.lower().endswith('.wav'):
            try:
                with wave.open(audio_file, 'rb') as wav:
                    params = wav.getparams()
                    metadata.sample_rate = params.framerate
                    metadata.channels = params.nchannels
                    metadata.duration = params.nframes / params.framerate
                    metadata.format = 'wav'
                    metadata.codec = 'pcm'
            except:
                pass
        
        return metadata
    
    def _apply_metadata(self, audio_file: str, metadata: AudioMetadata):
        """Apply metadata to audio file"""
        if not self._has_ffmpeg():
            return  # No metadata support without ffmpeg
        
        # Create temporary file with metadata
        temp_file = os.path.join(self.temp_dir, 'with_metadata.tmp')
        self.cleanup_files.append(temp_file)
        
        cmd = ['ffmpeg', '-y', '-i', audio_file]
        
        # Add metadata options
        if metadata.title:
            cmd.extend(['-metadata', f'title={metadata.title}'])
        if metadata.artist:
            cmd.extend(['-metadata', f'artist={metadata.artist}'])
        if metadata.album:
            cmd.extend(['-metadata', f'album={metadata.album}'])
        if metadata.year:
            cmd.extend(['-metadata', f'date={metadata.year}'])
        if metadata.genre:
            cmd.extend(['-metadata', f'genre={metadata.genre}'])
        
        # Custom tags
        for key, value in metadata.custom_tags.items():
            cmd.extend(['-metadata', f'{key}={value}'])
        
        cmd.extend(['-c', 'copy', temp_file])
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            shutil.move(temp_file, audio_file)
        except Exception as e:
            print(f"Metadata application error: {e}")
    
    def create_profile(self, name: str, format_type: str, **kwargs) -> ConversionProfile:
        """Create a custom conversion profile"""
        profile = ConversionProfile(name=name, format=format_type, **kwargs)
        self.profiles[name] = profile
        return profile
    
    def list_profiles(self) -> List[str]:
        """List available conversion profiles"""
        return list(self.profiles.keys())
    
    def get_profile_info(self, profile_name: str) -> Optional[Dict]:
        """Get information about a profile"""
        if profile_name in self.profiles:
            return asdict(self.profiles[profile_name])
        return None


def convert_with_pipeline(input_file: str, output_file: str, 
                         profile: str = 'cd_quality_wav') -> bool:
    """High-level conversion function"""
    with FormatPipeline() as pipeline:
        return pipeline.convert_file(input_file, output_file, profile)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python format_pipeline.py convert <input> <output> [profile]")
        print("  python format_pipeline.py batch <input_dir> <output_dir> [profile]")
        print("  python format_pipeline.py profiles")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "convert":
        if len(sys.argv) < 4:
            print("Usage: python format_pipeline.py convert <input> <output> [profile]")
            sys.exit(1)
        
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        profile = sys.argv[4] if len(sys.argv) > 4 else 'cd_quality_wav'
        
        success = convert_with_pipeline(input_file, output_file, profile)
        print("Conversion successful!" if success else "Conversion failed!")
    
    elif command == "batch":
        if len(sys.argv) < 4:
            print("Usage: python format_pipeline.py batch <input_dir> <output_dir> [profile]")
            sys.exit(1)
        
        input_dir = sys.argv[2]
        output_dir = sys.argv[3]
        profile = sys.argv[4] if len(sys.argv) > 4 else 'cd_quality_wav'
        
        with FormatPipeline() as pipeline:
            results = pipeline.batch_convert(input_dir, output_dir, profile)
    
    elif command == "profiles":
        pipeline = FormatPipeline()
        profiles = pipeline.list_profiles()
        
        print("Available conversion profiles:")
        for profile_name in profiles:
            info = pipeline.get_profile_info(profile_name)
            print(f"  {profile_name}:")
            print(f"    Format: {info['format']}")
            print(f"    Quality: {info['quality']}")
            if info['bitrate']:
                print(f"    Bitrate: {info['bitrate']} kbps")
            print(f"    Sample Rate: {info['sample_rate']} Hz")
            print(f"    Channels: {info['channels']}")
    
    else:
        print(f"Unknown command: {command}")