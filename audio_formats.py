#!/usr/bin/env python3
"""
Chameleon Audio Formats - Extended Format Support
Professional audio I/O for multiple formats without heavy dependencies
Direct implementation following Carmack's principles
"""

import os
import struct
import array
import subprocess
import tempfile
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

# Import our audio format detector
import audio_detector

# Use centralized error handling
from error_handler import AudioError as AudioFormatError

class AudioFormatHandler:
    """Lightweight audio format handler with minimal dependencies"""
    
    def __init__(self):
        # Supported formats
        self.supported_formats = {
            '.wav': self._load_wav,
            '.aiff': self._load_aiff,
            '.au': self._load_au,
            '.raw': self._load_raw,
            # Extended formats (require ffmpeg)
            '.mp3': self._load_with_ffmpeg,
            '.flac': self._load_with_ffmpeg,
            '.ogg': self._load_with_ffmpeg,
            '.m4a': self._load_with_ffmpeg,
            '.aac': self._load_with_ffmpeg,
            '.wma': self._load_with_ffmpeg
        }
        
        self.export_formats = {
            '.wav': self._save_wav,
            '.aiff': self._save_aiff,
            '.flac': self._save_with_ffmpeg,
            '.ogg': self._save_with_ffmpeg,
            '.mp3': self._save_with_ffmpeg,
            '.m4a': self._save_with_ffmpeg
        }
        
        # Check for ffmpeg availability
        self.has_ffmpeg = self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    def load_audio(self, file_path: str, auto_detect: bool = True) -> Tuple[bytes, Dict[str, Any]]:
        """
        Load audio from file, return raw PCM data and metadata
        Auto-detects format when enabled
        Returns: (audio_data, metadata)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise AudioFormatError(f"File not found: {file_path}")
        
        extension = file_path.suffix.lower()
        detected_format = None
        
        # Use auto-detection if enabled or if extension is unsupported
        if auto_detect or extension not in self.supported_formats:
            detection_result = audio_detector.detect_audio_format(str(file_path))
            
            if detection_result['confidence'] > 0.6:
                detected_format = f".{detection_result['format']}"
                print(f"Auto-detected format: {detection_result['format']} (confidence: {detection_result['confidence']:.2f})")
                
                # Use detected format if supported
                if detected_format in self.supported_formats:
                    extension = detected_format
                else:
                    print(f"Warning: Detected format {detected_format} not supported, trying extension-based loading")
        
        # Final check for supported format
        if extension not in self.supported_formats:
            if detected_format:
                raise AudioFormatError(f"Detected format {detected_format} is not supported")
            else:
                raise AudioFormatError(f"Unsupported format: {extension}")
        
        # Check if format requires ffmpeg
        if extension in ['.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma'] and not self.has_ffmpeg:
            raise AudioFormatError(f"Format {extension} requires ffmpeg (not found)")
        
        loader = self.supported_formats[extension]
        return loader(str(file_path))
    
    def save_audio(self, audio_data: bytes, file_path: str, 
                   sample_rate: int = 44100, channels: int = 1, 
                   bit_depth: int = 16, **kwargs) -> bool:
        """
        Save audio data to file
        Returns True if successful
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        if extension not in self.export_formats:
            raise AudioFormatError(f"Export format not supported: {extension}")
        
        # Check if format requires ffmpeg
        if extension in ['.flac', '.ogg', '.mp3', '.m4a'] and not self.has_ffmpeg:
            raise AudioFormatError(f"Export format {extension} requires ffmpeg (not found)")
        
        saver = self.export_formats[extension]
        return saver(audio_data, str(file_path), sample_rate, channels, bit_depth, **kwargs)
    
    def _load_wav(self, file_path: str) -> Tuple[bytes, Dict[str, Any]]:
        """Load WAV file with full header parsing"""
        with open(file_path, 'rb') as f:
            # Read and validate RIFF header
            riff_header = f.read(12)
            if len(riff_header) < 12 or riff_header[:4] != b'RIFF' or riff_header[8:12] != b'WAVE':
                raise AudioFormatError("Invalid WAV file format")
            
            # Parse chunks
            metadata = {'format': 'WAV'}
            audio_data = b''
            
            while True:
                chunk_header = f.read(8)
                if len(chunk_header) < 8:
                    break
                
                chunk_id = chunk_header[:4]
                chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
                
                if chunk_id == b'fmt ':
                    fmt_data = f.read(chunk_size)
                    if len(fmt_data) >= 16:
                        format_tag, channels, sample_rate, byte_rate, block_align, bits_per_sample = \
                            struct.unpack('<HHIIHH', fmt_data[:16])
                        
                        metadata.update({
                            'format_tag': format_tag,
                            'channels': channels,
                            'sample_rate': sample_rate,
                            'bits_per_sample': bits_per_sample,
                            'byte_rate': byte_rate,
                            'block_align': block_align
                        })
                
                elif chunk_id == b'data':
                    audio_data = f.read(chunk_size)
                    break
                else:
                    # Skip unknown chunks
                    f.seek(chunk_size, 1)
                
                # Align to even byte boundary
                if chunk_size % 2:
                    f.read(1)
            
            return audio_data, metadata
    
    def _load_aiff(self, file_path: str) -> Tuple[bytes, Dict[str, Any]]:
        """Load AIFF file"""
        with open(file_path, 'rb') as f:
            # Read FORM header
            form_header = f.read(12)
            if len(form_header) < 12 or form_header[:4] != b'FORM' or form_header[8:12] != b'AIFF':
                raise AudioFormatError("Invalid AIFF file format")
            
            metadata = {'format': 'AIFF'}
            audio_data = b''
            
            while True:
                chunk_header = f.read(8)
                if len(chunk_header) < 8:
                    break
                
                chunk_id = chunk_header[:4]
                chunk_size = struct.unpack('>I', chunk_header[4:8])[0]
                
                if chunk_id == b'COMM':
                    comm_data = f.read(min(chunk_size, 18))
                    if len(comm_data) >= 18:
                        channels, num_frames, bits_per_sample = struct.unpack('>HI H', comm_data[:8])
                        # IEEE 754 extended precision (80-bit) sample rate
                        sample_rate = self._ieee754_to_int(comm_data[8:18])
                        
                        metadata.update({
                            'channels': channels,
                            'sample_rate': sample_rate,
                            'bits_per_sample': bits_per_sample,
                            'num_frames': num_frames
                        })
                
                elif chunk_id == b'SSND':
                    ssnd_header = f.read(8)
                    if len(ssnd_header) == 8:
                        offset, block_size = struct.unpack('>II', ssnd_header)
                        f.seek(offset, 1)  # Skip offset bytes
                        audio_data = f.read(chunk_size - 8 - offset)
                    break
                else:
                    f.seek(chunk_size, 1)
                
                # AIFF chunks are word-aligned
                if chunk_size % 2:
                    f.read(1)
            
            return audio_data, metadata
    
    def _load_au(self, file_path: str) -> Tuple[bytes, Dict[str, Any]]:
        """Load AU/SND file (Sun Audio)"""
        with open(file_path, 'rb') as f:
            # Read AU header (24 bytes minimum)
            header = f.read(24)
            if len(header) < 24 or header[:4] != b'.snd':
                raise AudioFormatError("Invalid AU file format")
            
            header_size, data_size, encoding, sample_rate, channels = \
                struct.unpack('>IIIII', header[4:24])
            
            # Skip annotation if header is larger
            if header_size > 24:
                f.seek(header_size - 24, 1)
            
            # Read audio data
            audio_data = f.read(data_size) if data_size != 0xFFFFFFFF else f.read()
            
            metadata = {
                'format': 'AU',
                'encoding': encoding,
                'sample_rate': sample_rate,
                'channels': channels,
                'data_size': data_size
            }
            
            return audio_data, metadata
    
    def _load_raw(self, file_path: str) -> Tuple[bytes, Dict[str, Any]]:
        """Load raw PCM file (assume 44.1kHz, 16-bit, mono)"""
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        
        metadata = {
            'format': 'RAW',
            'sample_rate': 44100,
            'channels': 1,
            'bits_per_sample': 16
        }
        
        return audio_data, metadata
    
    def _load_with_ffmpeg(self, file_path: str) -> Tuple[bytes, Dict[str, Any]]:
        """Load audio using ffmpeg for unsupported formats"""
        if not self.has_ffmpeg:
            raise AudioFormatError("ffmpeg not available for format conversion")
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
        
        try:
            # Convert to WAV using ffmpeg
            cmd = [
                'ffmpeg', '-y', '-i', file_path,
                '-ar', '44100',  # Sample rate
                '-ac', '1',      # Mono
                '-f', 'wav',     # Output format
                temp_wav_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise AudioFormatError(f"ffmpeg conversion failed: {result.stderr}")
            
            # Load converted WAV file
            audio_data, wav_metadata = self._load_wav(temp_wav_path)
            
            # Update metadata with original format info
            metadata = wav_metadata.copy()
            metadata['original_format'] = Path(file_path).suffix.lower()
            metadata['converted_via'] = 'ffmpeg'
            
            return audio_data, metadata
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_wav_path)
            except OSError:
                pass
    
    def _save_wav(self, audio_data: bytes, file_path: str, 
                  sample_rate: int, channels: int, bit_depth: int, **kwargs) -> bool:
        """Save as WAV file"""
        try:
            with open(file_path, 'wb') as f:
                # WAV header
                data_size = len(audio_data)
                
                # RIFF header
                f.write(b'RIFF')
                f.write(struct.pack('<I', data_size + 36))
                f.write(b'WAVE')
                
                # Format chunk
                f.write(b'fmt ')
                f.write(struct.pack('<I', 16))  # Chunk size
                f.write(struct.pack('<H', 1))   # PCM format
                f.write(struct.pack('<H', channels))
                f.write(struct.pack('<I', sample_rate))
                f.write(struct.pack('<I', sample_rate * channels * bit_depth // 8))  # Byte rate
                f.write(struct.pack('<H', channels * bit_depth // 8))  # Block align
                f.write(struct.pack('<H', bit_depth))
                
                # Data chunk
                f.write(b'data')
                f.write(struct.pack('<I', data_size))
                f.write(audio_data)
            
            return True
            
        except Exception:
            return False
    
    def _save_aiff(self, audio_data: bytes, file_path: str,
                   sample_rate: int, channels: int, bit_depth: int, **kwargs) -> bool:
        """Save as AIFF file"""
        try:
            with open(file_path, 'wb') as f:
                data_size = len(audio_data)
                num_frames = data_size // (channels * bit_depth // 8)
                
                # FORM header
                f.write(b'FORM')
                f.write(struct.pack('>I', data_size + 46))
                f.write(b'AIFF')
                
                # Common chunk
                f.write(b'COMM')
                f.write(struct.pack('>I', 18))  # Chunk size
                f.write(struct.pack('>H', channels))
                f.write(struct.pack('>I', num_frames))
                f.write(struct.pack('>H', bit_depth))
                f.write(self._int_to_ieee754(sample_rate))
                
                # Sound data chunk
                f.write(b'SSND')
                f.write(struct.pack('>I', data_size + 8))
                f.write(struct.pack('>II', 0, 0))  # Offset and block size
                f.write(audio_data)
            
            return True
            
        except Exception:
            return False
    
    def _save_with_ffmpeg(self, audio_data: bytes, file_path: str,
                         sample_rate: int, channels: int, bit_depth: int, **kwargs) -> bool:
        """Save audio using ffmpeg"""
        if not self.has_ffmpeg:
            return False
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
        
        try:
            # First save as WAV
            if not self._save_wav(audio_data, temp_wav_path, sample_rate, channels, bit_depth):
                return False
            
            # Convert to target format using ffmpeg
            extension = Path(file_path).suffix.lower()
            
            cmd = ['ffmpeg', '-y', '-i', temp_wav_path]
            
            # Format-specific options
            if extension == '.flac':
                cmd.extend(['-compression_level', '8'])  # Maximum compression
            elif extension == '.ogg':
                cmd.extend(['-c:a', 'libvorbis', '-q:a', '5'])  # Good quality Vorbis
            elif extension == '.mp3':
                cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])  # 192 kbps MP3
            elif extension == '.m4a':
                cmd.extend(['-c:a', 'aac', '-b:a', '128k'])  # 128 kbps AAC
            
            cmd.append(file_path)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
            
        except Exception:
            return False
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_wav_path)
            except OSError:
                pass
    
    def _ieee754_to_int(self, ieee_bytes: bytes) -> int:
        """Convert IEEE 754 extended precision (80-bit) to integer"""
        if len(ieee_bytes) < 10:
            return 44100  # Default fallback
        
        # Simple approximation for sample rates
        # This is not a full IEEE 754 implementation
        exponent = struct.unpack('>H', ieee_bytes[:2])[0]
        mantissa = struct.unpack('>Q', ieee_bytes[2:10])[0]
        
        if exponent == 0:
            return 0
        
        # Rough conversion
        exp_bias = exponent - 16383
        if exp_bias < 0:
            return int(mantissa >> (63 - exp_bias))
        else:
            return int(mantissa << exp_bias) if exp_bias < 32 else 44100
    
    def _int_to_ieee754(self, value: int) -> bytes:
        """Convert integer to IEEE 754 extended precision (80-bit)"""
        # Simplified conversion for common sample rates
        if value == 44100:
            return b'\x40\x0e\xac\x44\x00\x00\x00\x00\x00\x00'
        elif value == 48000:
            return b'\x40\x0e\xbb\x80\x00\x00\x00\x00\x00\x00'
        elif value == 22050:
            return b'\x40\x0d\xac\x44\x00\x00\x00\x00\x00\x00'
        else:
            # Default to 44100 format
            return b'\x40\x0e\xac\x44\x00\x00\x00\x00\x00\x00'
    
    def get_format_info(self, file_path: str) -> Dict[str, Any]:
        """Get format information without loading full audio data"""
        try:
            extension = Path(file_path).suffix.lower()
            
            if extension == '.wav':
                with open(file_path, 'rb') as f:
                    f.seek(0)
                    riff_header = f.read(12)
                    if riff_header[:4] != b'RIFF':
                        return {'error': 'Invalid WAV file'}
                    
                    # Find fmt chunk
                    while True:
                        chunk_header = f.read(8)
                        if len(chunk_header) < 8:
                            break
                        
                        chunk_id = chunk_header[:4]
                        chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
                        
                        if chunk_id == b'fmt ':
                            fmt_data = f.read(chunk_size)
                            if len(fmt_data) >= 16:
                                format_tag, channels, sample_rate, byte_rate, block_align, bits_per_sample = \
                                    struct.unpack('<HHIIHH', fmt_data[:16])
                                
                                return {
                                    'format': 'WAV',
                                    'channels': channels,
                                    'sample_rate': sample_rate,
                                    'bits_per_sample': bits_per_sample,
                                    'duration_estimate': os.path.getsize(file_path) / byte_rate if byte_rate > 0 else 0
                                }
                        else:
                            f.seek(chunk_size, 1)
                            if chunk_size % 2:
                                f.read(1)
            
            # For other formats, provide basic info
            file_size = os.path.getsize(file_path)
            return {
                'format': extension.upper().lstrip('.'),
                'file_size': file_size,
                'ffmpeg_required': extension in ['.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma']
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def list_supported_formats(self) -> Dict[str, list]:
        """List all supported formats"""
        native_formats = [ext for ext in self.supported_formats.keys() 
                         if ext not in ['.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma']]
        
        ffmpeg_formats = [ext for ext in self.supported_formats.keys()
                         if ext in ['.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma']]
        
        return {
            'native': native_formats,
            'ffmpeg_required': ffmpeg_formats,
            'ffmpeg_available': self.has_ffmpeg
        }

# Convenience functions for backward compatibility
def load_audio_file(file_path: str) -> Tuple[bytes, Dict[str, Any]]:
    """Load audio file using the format handler"""
    handler = AudioFormatHandler()
    return handler.load_audio(file_path)

def save_audio_file(audio_data: bytes, file_path: str, **kwargs) -> bool:
    """Save audio file using the format handler"""
    handler = AudioFormatHandler()
    return handler.save_audio(audio_data, file_path, **kwargs)

def test_formats():
    """Test audio format support"""
    handler = AudioFormatHandler()
    
    print("🎵 Chameleon Audio Format Support Test")
    print("=" * 50)
    
    formats = handler.list_supported_formats()
    print(f"Native formats: {', '.join(formats['native'])}")
    print(f"FFmpeg formats: {', '.join(formats['ffmpeg_required'])}")
    print(f"FFmpeg available: {'✅ Yes' if formats['ffmpeg_available'] else '❌ No'}")
    
    # Test with a generated tone
    print("\nTesting WAV export...")
    import audio_utils
    test_audio = audio_utils.generate_tone_cached(440.0, 0.5)  # 0.5 second test tone
    
    if handler.save_audio(test_audio, "test_output.wav"):
        print("✅ WAV export successful")
        
        # Test loading it back
        try:
            loaded_audio, metadata = handler.load_audio("test_output.wav")
            print(f"✅ WAV loading successful: {len(loaded_audio)} bytes")
            print(f"   Metadata: {metadata}")
            
            # Cleanup
            os.unlink("test_output.wav")
        except Exception as e:
            print(f"❌ WAV loading failed: {e}")
    else:
        print("❌ WAV export failed")

if __name__ == "__main__":
    test_formats()