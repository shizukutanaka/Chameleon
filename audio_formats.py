#!/usr/bin/env python3
"""
Audio format conversion support for Chameleon.
Handles multiple audio formats with fallback mechanisms.
"""

import os
import sys
import struct
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union

# Import types and logger
try:
    from .types import AudioData, AudioConstants, get_fallback_logger
    from .logger import get_logger
    logger = get_logger()
except ImportError:
    # Fallback for standalone usage
    from types import AudioData, AudioConstants, get_fallback_logger
    logger = get_fallback_logger(__name__)
except ImportError:
    # Complete fallback
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    AudioData = Tuple[bytes, int, int, int]
    
    class AudioConstants:
        SUPPORTED_FORMATS = ['wav', 'mp3', 'flac', 'ogg', 'aac', 'm4a']
        FORMAT_WAV = 'wav'

class AudioFormat:
    """Audio format constants and detection"""
    WAV = AudioConstants.FORMAT_WAV
    MP3 = AudioConstants.FORMAT_MP3
    FLAC = AudioConstants.FORMAT_FLAC
    OGG = AudioConstants.FORMAT_OGG
    AAC = AudioConstants.FORMAT_AAC
    M4A = AudioConstants.FORMAT_M4A
    
    SUPPORTED_FORMATS = AudioConstants.SUPPORTED_FORMATS
    
    @classmethod
    def detect_format(cls, filepath: str) -> str:
        """Detect audio format from file extension"""
        ext = Path(filepath).suffix.lower().lstrip('.')
        return ext if ext in cls.SUPPORTED_FORMATS else cls.WAV

class AudioConverter:
    """Audio format converter with multiple backends"""
    
    def __init__(self):
        self.available_backends = self._detect_backends()
        logger.info(f"Audio converter initialized with backends: {list(self.available_backends.keys())}")
    
    def _detect_backends(self) -> Dict[str, bool]:
        """Detect available audio processing backends"""
        backends = {}
        
        # Check for FFmpeg
        backends['ffmpeg'] = self._check_command('ffmpeg')
        
        # Check for SoX (Sound eXchange)
        backends['sox'] = self._check_command('sox')
        
        # Check for Python libraries
        try:
            import soundfile
            backends['soundfile'] = True
        except ImportError:
            backends['soundfile'] = False
        
        try:
            import pydub
            backends['pydub'] = True
        except ImportError:
            backends['pydub'] = False
        
        return backends
    
    def _check_command(self, command: str) -> bool:
        """Check if external command is available"""
        try:
            result = subprocess.run([command, '-version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_conversion_info(self) -> Dict[str, Any]:
        """Get information about conversion capabilities"""
        return {
            'supported_formats': AudioFormat.SUPPORTED_FORMATS,
            'available_backends': self.available_backends,
            'recommended_backend': self._get_recommended_backend()
        }
    
    def _get_recommended_backend(self) -> Optional[str]:
        """Get the recommended backend based on availability"""
        preference_order = ['soundfile', 'ffmpeg', 'pydub', 'sox']
        
        for backend in preference_order:
            if self.available_backends.get(backend, False):
                return backend
        
        return None
    
    def convert_file(self, input_path: str, output_path: str, 
                    target_format: Optional[str] = None,
                    quality: str = 'high') -> bool:
        """Convert audio file to different format"""
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False
        
        input_format = AudioFormat.detect_format(input_path)
        if target_format is None:
            target_format = AudioFormat.detect_format(output_path)
        
        logger.info(f"Converting {input_format} to {target_format}: {input_path} -> {output_path}")
        
        # Try conversion with available backends
        backend = self._get_recommended_backend()
        
        if backend == 'soundfile':
            return self._convert_with_soundfile(input_path, output_path, target_format, quality)
        elif backend == 'ffmpeg':
            return self._convert_with_ffmpeg(input_path, output_path, target_format, quality)
        elif backend == 'pydub':
            return self._convert_with_pydub(input_path, output_path, target_format, quality)
        elif backend == 'sox':
            return self._convert_with_sox(input_path, output_path, target_format, quality)
        else:
            logger.error("No suitable conversion backend available")
            return False
    
    def _convert_with_soundfile(self, input_path: str, output_path: str, 
                               target_format: str, quality: str) -> bool:
        """Convert using soundfile library"""
        try:
            import soundfile as sf
            
            # Read input file
            data, sample_rate = sf.read(input_path)
            
            # Set output parameters based on quality and format
            subtype = self._get_soundfile_subtype(target_format, quality)
            
            # Write output file
            sf.write(output_path, data, sample_rate, subtype=subtype)
            
            logger.info(f"Successfully converted using soundfile: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Soundfile conversion failed: {e}")
            return False
    
    def _convert_with_ffmpeg(self, input_path: str, output_path: str,
                           target_format: str, quality: str) -> bool:
        """Convert using FFmpeg"""
        try:
            # Build FFmpeg command
            cmd = ['ffmpeg', '-i', input_path]
            
            # Add quality settings
            if target_format == AudioFormat.MP3:
                if quality == 'high':
                    cmd.extend(['-b:a', '320k'])
                elif quality == 'medium':
                    cmd.extend(['-b:a', '192k'])
                else:
                    cmd.extend(['-b:a', '128k'])
            elif target_format == AudioFormat.AAC:
                if quality == 'high':
                    cmd.extend(['-b:a', '256k'])
                else:
                    cmd.extend(['-b:a', '128k'])
            
            # Output settings
            cmd.extend(['-y', output_path])  # -y to overwrite
            
            # Run conversion
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"Successfully converted using FFmpeg: {output_path}")
                return True
            else:
                logger.error(f"FFmpeg conversion failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"FFmpeg conversion error: {e}")
            return False
    
    def _convert_with_pydub(self, input_path: str, output_path: str,
                          target_format: str, quality: str) -> bool:
        """Convert using pydub library"""
        try:
            from pydub import AudioSegment
            
            # Load audio file
            audio = AudioSegment.from_file(input_path)
            
            # Set export parameters based on quality
            export_params = {}
            if target_format == AudioFormat.MP3:
                if quality == 'high':
                    export_params['bitrate'] = '320k'
                elif quality == 'medium':
                    export_params['bitrate'] = '192k'
                else:
                    export_params['bitrate'] = '128k'
            
            # Export to target format
            audio.export(output_path, format=target_format, **export_params)
            
            logger.info(f"Successfully converted using pydub: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Pydub conversion failed: {e}")
            return False
    
    def _convert_with_sox(self, input_path: str, output_path: str,
                         target_format: str, quality: str) -> bool:
        """Convert using SoX"""
        try:
            cmd = ['sox', input_path]
            
            # Add quality settings for compressed formats
            if target_format in [AudioFormat.MP3, AudioFormat.OGG]:
                if quality == 'high':
                    cmd.extend(['-C', '9'])  # High compression quality
                elif quality == 'medium':
                    cmd.extend(['-C', '6'])
                else:
                    cmd.extend(['-C', '3'])
            
            cmd.append(output_path)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"Successfully converted using SoX: {output_path}")
                return True
            else:
                logger.error(f"SoX conversion failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"SoX conversion error: {e}")
            return False
    
    def _get_soundfile_subtype(self, format: str, quality: str) -> str:
        """Get soundfile subtype based on format and quality"""
        subtypes = {
            AudioFormat.FLAC: 'FLAC',
            AudioFormat.OGG: 'VORBIS',
            AudioFormat.WAV: 'PCM_16'
        }
        
        return subtypes.get(format, 'PCM_16')
    
    def batch_convert(self, input_files: List[str], output_dir: str,
                     target_format: str, quality: str = 'high') -> Dict[str, bool]:
        """Convert multiple files to target format"""
        results = {}
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        for input_file in input_files:
            if not os.path.exists(input_file):
                logger.warning(f"Input file not found: {input_file}")
                results[input_file] = False
                continue
            
            # Generate output filename
            input_name = Path(input_file).stem
            output_file = os.path.join(output_dir, f"{input_name}.{target_format}")
            
            # Convert file
            success = self.convert_file(input_file, output_file, target_format, quality)
            results[input_file] = success
        
        successful = sum(1 for success in results.values() if success)
        logger.info(f"Batch conversion completed: {successful}/{len(input_files)} successful")
        
        return results

class AudioInfo:
    """Audio file information extractor"""
    
    @staticmethod
    def get_file_info(filepath: str) -> Optional[Dict[str, Any]]:
        """Extract audio file information"""
        if not os.path.exists(filepath):
            return None
        
        try:
            # Try soundfile first (most reliable)
            try:
                import soundfile as sf
                info = sf.info(filepath)
                
                return {
                    'format': AudioFormat.detect_format(filepath),
                    'sample_rate': info.samplerate,
                    'channels': info.channels,
                    'duration': info.duration,
                    'frames': info.frames,
                    'file_size': os.path.getsize(filepath)
                }
            except ImportError:
                pass
            
            # Fallback to FFmpeg
            if AudioConverter()._check_command('ffmpeg'):
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                    '-show_format', '-show_streams', filepath
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    import json
                    probe_data = json.loads(result.stdout)
                    
                    audio_stream = None
                    for stream in probe_data.get('streams', []):
                        if stream.get('codec_type') == 'audio':
                            audio_stream = stream
                            break
                    
                    if audio_stream:
                        duration = float(probe_data['format']['duration'])
                        return {
                            'format': AudioFormat.detect_format(filepath),
                            'sample_rate': int(audio_stream['sample_rate']),
                            'channels': int(audio_stream['channels']),
                            'duration': duration,
                            'bit_rate': int(probe_data['format'].get('bit_rate', 0)),
                            'file_size': os.path.getsize(filepath)
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get audio info for {filepath}: {e}")
            return None

def convert_audio_file(input_path: str, output_path: str, 
                      target_format: Optional[str] = None,
                      quality: str = 'high') -> bool:
    """Convenience function to convert single audio file"""
    converter = AudioConverter()
    return converter.convert_file(input_path, output_path, target_format, quality)

def get_audio_info(filepath: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get audio file information"""
    return AudioInfo.get_file_info(filepath)

def get_supported_formats() -> List[str]:
    """Get list of supported audio formats"""
    return AudioFormat.SUPPORTED_FORMATS.copy()

def check_conversion_capability() -> Dict[str, Any]:
    """Check system's audio conversion capabilities"""
    converter = AudioConverter()
    return converter.get_conversion_info()

if __name__ == '__main__':
    # Test audio format functionality
    print("Audio Format Converter Test")
    print("=" * 40)
    
    # Check capabilities
    capabilities = check_conversion_capability()
    print(f"Supported formats: {capabilities['supported_formats']}")
    print(f"Available backends: {capabilities['available_backends']}")
    print(f"Recommended backend: {capabilities['recommended_backend']}")
    
    # Test with sample file if available
    test_files = ['test.wav', 'test.mp3', 'sample.wav']
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\nTesting with file: {test_file}")
            info = get_audio_info(test_file)
            if info:
                print(f"File info: {info}")
            else:
                print("Failed to get file information")
            break
    else:
        print("\nNo test files found for demonstration")