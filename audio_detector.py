#!/usr/bin/env python3
"""
Audio Format Auto-Detection System
Intelligent detection of audio formats based on content analysis
"""

import os
import struct
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

class AudioFormatDetector:
    """Automatic audio format detection"""
    
    # Format signatures (magic bytes)
    SIGNATURES = {
        'wav': [b'RIFF', b'WAVE'],
        'mp3': [b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'],
        'flac': [b'fLaC'],
        'ogg': [b'OggS'],
        'aac': [b'\xff\xf1', b'\xff\xf9'],
        'm4a': [b'ftypM4A'],
        'aiff': [b'FORM', b'AIFF'],
        'au': [b'.snd']
    }
    
    def __init__(self):
        self.detection_cache = {}
        self.max_cache_size = 100
    
    def detect_format(self, filepath: str) -> Dict[str, Any]:
        """
        Detect audio format from file content
        
        Returns:
            Dict with format info including:
            - format: detected format name
            - confidence: detection confidence (0-1)
            - sample_rate: if detectable
            - channels: if detectable
            - duration: if detectable
            - bitrate: if detectable
        """
        filepath = str(filepath)
        
        # Check cache first
        file_stat = os.stat(filepath)
        cache_key = f"{filepath}:{file_stat.st_mtime}:{file_stat.st_size}"
        
        if cache_key in self.detection_cache:
            return self.detection_cache[cache_key].copy()
        
        try:
            # Read file header
            with open(filepath, 'rb') as f:
                header = f.read(64)  # Read first 64 bytes
            
            result = self._analyze_header(header, filepath)
            
            # Try to get additional metadata if format detected
            if result['format'] != 'unknown':
                metadata = self._extract_metadata(filepath, result['format'])
                result.update(metadata)
            
            # Cache result
            self._cache_result(cache_key, result)
            
            return result
            
        except Exception as e:
            return {
                'format': 'unknown',
                'confidence': 0.0,
                'error': str(e),
                'sample_rate': None,
                'channels': None,
                'duration': None,
                'bitrate': None
            }
    
    def _analyze_header(self, header: bytes, filepath: str) -> Dict[str, Any]:
        """Analyze file header for format detection"""
        if len(header) < 4:
            return {'format': 'unknown', 'confidence': 0.0}
        
        # Check each known format
        for format_name, signatures in self.SIGNATURES.items():
            for signature in signatures:
                if self._check_signature(header, signature):
                    confidence = self._calculate_confidence(header, format_name)
                    return {
                        'format': format_name,
                        'confidence': confidence,
                        'detected_by': 'signature'
                    }
        
        # Try extension-based detection as fallback
        ext = Path(filepath).suffix.lower()
        if ext.startswith('.'):
            ext = ext[1:]
        
        if ext in self.SIGNATURES:
            return {
                'format': ext,
                'confidence': 0.3,  # Lower confidence for extension-based
                'detected_by': 'extension'
            }
        
        return {'format': 'unknown', 'confidence': 0.0}
    
    def _check_signature(self, header: bytes, signature: bytes) -> bool:
        """Check if header contains signature"""
        if len(signature) > len(header):
            return False
        
        # Check at beginning
        if header.startswith(signature):
            return True
        
        # For some formats, check at specific offsets
        if signature == b'WAVE':
            return signature in header[:20]
        elif signature == b'AIFF':
            return signature in header[:20]
        
        return False
    
    def _calculate_confidence(self, header: bytes, format_name: str) -> float:
        """Calculate detection confidence based on additional checks"""
        confidence = 0.8  # Base confidence for signature match
        
        if format_name == 'wav':
            # Additional WAV validation
            if len(header) >= 44:
                try:
                    # Check RIFF chunk structure
                    if header[8:12] == b'WAVE' and header[12:16] == b'fmt ':
                        confidence = 0.95
                except:
                    pass
        
        elif format_name == 'mp3':
            # Check MP3 frame sync
            if len(header) >= 4:
                if header[0] == 0xff and (header[1] & 0xe0) == 0xe0:
                    confidence = 0.9
        
        elif format_name == 'flac':
            # FLAC has very distinctive signature
            confidence = 0.95
        
        elif format_name == 'ogg':
            # Check OGG page structure
            if len(header) >= 27:
                if header[4] == 0 and header[5:9] == b'vorbis':
                    confidence = 0.95
        
        return confidence
    
    def _extract_metadata(self, filepath: str, format_name: str) -> Dict[str, Any]:
        """Extract audio metadata based on detected format"""
        metadata = {
            'sample_rate': None,
            'channels': None,
            'duration': None,
            'bitrate': None
        }
        
        try:
            if format_name == 'wav':
                metadata.update(self._extract_wav_metadata(filepath))
            elif format_name == 'mp3':
                metadata.update(self._extract_mp3_metadata(filepath))
            elif format_name == 'flac':
                metadata.update(self._extract_flac_metadata(filepath))
            # Add more formats as needed
        
        except Exception:
            pass  # Metadata extraction is optional
        
        return metadata
    
    def _extract_wav_metadata(self, filepath: str) -> Dict[str, Any]:
        """Extract WAV file metadata"""
        metadata = {}
        
        with open(filepath, 'rb') as f:
            # Skip RIFF header
            f.seek(12)
            
            # Find fmt chunk
            chunk_id = f.read(4)
            if chunk_id == b'fmt ':
                chunk_size = struct.unpack('<I', f.read(4))[0]
                
                if chunk_size >= 16:
                    # Read PCM format data
                    format_tag = struct.unpack('<H', f.read(2))[0]
                    channels = struct.unpack('<H', f.read(2))[0]
                    sample_rate = struct.unpack('<I', f.read(4))[0]
                    byte_rate = struct.unpack('<I', f.read(4))[0]
                    
                    metadata['channels'] = channels
                    metadata['sample_rate'] = sample_rate
                    metadata['bitrate'] = byte_rate * 8
                    
                    # Calculate duration
                    file_size = os.path.getsize(filepath)
                    if byte_rate > 0:
                        metadata['duration'] = (file_size - 44) / byte_rate
        
        return metadata
    
    def _extract_mp3_metadata(self, filepath: str) -> Dict[str, Any]:
        """Extract MP3 file metadata (simplified)"""
        metadata = {}
        
        with open(filepath, 'rb') as f:
            # Look for first MP3 frame
            data = f.read(4)
            if len(data) >= 4:
                # Parse MP3 frame header (simplified)
                if data[0] == 0xff and (data[1] & 0xe0) == 0xe0:
                    # Extract basic info from frame header
                    version = (data[1] >> 3) & 0x03
                    layer = (data[1] >> 1) & 0x03
                    bitrate_index = (data[2] >> 4) & 0x0f
                    freq_index = (data[2] >> 2) & 0x03
                    channel_mode = (data[3] >> 6) & 0x03
                    
                    # Approximate values (simplified)
                    if freq_index == 0:
                        metadata['sample_rate'] = 44100
                    elif freq_index == 1:
                        metadata['sample_rate'] = 48000
                    elif freq_index == 2:
                        metadata['sample_rate'] = 32000
                    
                    metadata['channels'] = 1 if channel_mode == 3 else 2
        
        return metadata
    
    def _extract_flac_metadata(self, filepath: str) -> Dict[str, Any]:
        """Extract FLAC file metadata (simplified)"""
        metadata = {}
        
        with open(filepath, 'rb') as f:
            # Skip fLaC signature
            f.seek(4)
            
            # Read STREAMINFO block
            block_header = f.read(4)
            if len(block_header) >= 4:
                block_type = block_header[0] & 0x7f
                if block_type == 0:  # STREAMINFO
                    # Skip to sample rate info
                    f.seek(10, 1)  # Skip minimum/maximum block size and frame size
                    
                    # Read sample rate and channel info
                    data = f.read(8)
                    if len(data) >= 8:
                        # Parse FLAC STREAMINFO (simplified)
                        sample_rate = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
                        channels = ((data[2] >> 1) & 0x07) + 1
                        
                        metadata['sample_rate'] = sample_rate
                        metadata['channels'] = channels
        
        return metadata
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache detection result"""
        if len(self.detection_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.detection_cache))
            del self.detection_cache[oldest_key]
        
        self.detection_cache[cache_key] = result.copy()
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported format names"""
        return list(self.SIGNATURES.keys())
    
    def is_audio_file(self, filepath: str) -> bool:
        """Check if file appears to be an audio file"""
        detection = self.detect_format(filepath)
        return detection['format'] != 'unknown' and detection['confidence'] > 0.5
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cache_size': len(self.detection_cache),
            'max_cache_size': self.max_cache_size
        }
    
    def clear_cache(self):
        """Clear detection cache"""
        self.detection_cache.clear()


# Global detector instance
audio_detector = AudioFormatDetector()


# Convenience functions
def detect_audio_format(filepath: str) -> Dict[str, Any]:
    """Detect audio format of file"""
    return audio_detector.detect_format(filepath)


def is_audio_file(filepath: str) -> bool:
    """Check if file is an audio file"""
    return audio_detector.is_audio_file(filepath)


def get_audio_info(filepath: str) -> Dict[str, Any]:
    """Get comprehensive audio file information"""
    return audio_detector.detect_format(filepath)


def get_supported_audio_formats() -> List[str]:
    """Get list of supported audio formats"""
    return audio_detector.get_supported_formats()