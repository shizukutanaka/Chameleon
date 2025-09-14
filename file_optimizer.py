#!/usr/bin/env python3
"""
File Compression and Optimization
Utilities for reducing file sizes and optimizing audio files
"""

import os
import struct
import array
import math
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import audio_utils


class AudioOptimizer:
    """Audio file optimization and compression utilities"""
    
    def __init__(self):
        self.compression_levels = {
            'none': 0,
            'low': 1,
            'medium': 2,
            'high': 3,
            'maximum': 4
        }
    
    def analyze_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze audio file for optimization opportunities"""
        path = Path(filepath)
        if not path.exists():
            return {}
        
        # Get basic file info
        info = audio_utils.get_file_info(filepath)
        
        # Try to load and analyze audio
        try:
            from audio_formats import AudioFormatHandler
            handler = AudioFormatHandler()
            audio_data, metadata = handler.load_audio(filepath)
            
            # Audio analysis
            peak = audio_utils.detect_peak(audio_data)
            rms = audio_utils.calculate_rms(audio_data)
            is_silent = audio_utils.detect_silence(audio_data)
            
            # Calculate compression potential
            dynamic_range = peak - rms if peak > rms else 0
            
            analysis = {
                'file_info': info,
                'audio_info': metadata,
                'peak_amplitude': peak,
                'rms_level': rms,
                'dynamic_range': dynamic_range,
                'is_mostly_silent': is_silent,
                'zero_crossings': audio_utils.count_zero_crossings(audio_data),
                'duration_seconds': len(audio_data) / (2 * metadata.get('sample_rate', 44100)),
                'compression_potential': self._assess_compression_potential(peak, rms, is_silent)
            }
            
            return analysis
            
        except Exception as e:
            return {'file_info': info, 'error': str(e)}
    
    def _assess_compression_potential(self, peak: float, rms: float, is_silent: bool) -> str:
        """Assess how much the file could benefit from compression"""
        if is_silent:
            return 'high'  # Silent parts can be heavily compressed
        
        dynamic_range = peak - rms if peak > rms else 0
        
        if dynamic_range > 0.5:
            return 'high'  # High dynamic range - good for compression
        elif dynamic_range > 0.2:
            return 'medium'
        else:
            return 'low'  # Already compressed or low dynamic range
    
    def optimize_audio_data(self, audio_data: bytes, level: str = 'medium') -> bytes:
        """Optimize audio data without changing format"""
        if level not in self.compression_levels:
            level = 'medium'
        
        # Convert to samples
        samples = audio_utils.bytes_to_samples(audio_data)
        
        # Apply optimizations based on level
        if self.compression_levels[level] >= 1:
            # Remove DC offset
            samples = audio_utils.remove_dc_offset(samples)
        
        if self.compression_levels[level] >= 2:
            # Normalize to use full range
            audio_data = audio_utils.normalize_audio(samples, 0.95)
            samples = audio_utils.bytes_to_samples(audio_data)
        
        if self.compression_levels[level] >= 3:
            # Apply gentle compression
            samples = self._apply_gentle_compression(samples)
        
        if self.compression_levels[level] >= 4:
            # Aggressive optimization
            samples = self._apply_aggressive_optimization(samples)
        
        return audio_utils.samples_to_bytes(samples)
    
    def _apply_gentle_compression(self, samples: List[int]) -> List[int]:
        """Apply gentle compression to reduce dynamic range"""
        if not samples:
            return samples
        
        # Simple compression: reduce peaks, boost quiet parts
        peak = max(abs(s) for s in samples)
        if peak == 0:
            return samples
        
        compressed = []
        threshold = peak * 0.7  # Compression threshold
        ratio = 2.0  # Compression ratio
        
        for sample in samples:
            abs_sample = abs(sample)
            if abs_sample > threshold:
                # Compress above threshold
                excess = abs_sample - threshold
                compressed_excess = excess / ratio
                new_abs = threshold + compressed_excess
                new_sample = int((new_abs / abs_sample) * sample)
            else:
                # Boost below threshold
                boost_factor = 1.1
                new_sample = int(sample * boost_factor)
            
            compressed.append(audio_utils.clamp(new_sample, -32768, 32767))
        
        return compressed
    
    def _apply_aggressive_optimization(self, samples: List[int]) -> List[int]:
        """Apply aggressive optimization for maximum file size reduction"""
        if not samples:
            return samples
        
        # Aggressive noise gate
        noise_floor = max(abs(s) for s in samples) * 0.01
        
        # Remove very quiet samples
        cleaned = []
        for sample in samples:
            if abs(sample) < noise_floor:
                cleaned.append(0)
            else:
                cleaned.append(sample)
        
        # Apply strong compression
        cleaned = self._apply_gentle_compression(cleaned)
        
        return cleaned
    
    def optimize_file(self, input_file: str, output_file: str, level: str = 'medium') -> bool:
        """Optimize an audio file and save the result"""
        try:
            from audio_formats import AudioFormatHandler
            handler = AudioFormatHandler()
            
            # Load audio
            audio_data, metadata = handler.load_audio(input_file)
            
            # Optimize
            optimized_data = self.optimize_audio_data(audio_data, level)
            
            # Save
            return handler.save_audio(optimized_data, output_file,
                                    sample_rate=metadata.get('sample_rate', 44100),
                                    channels=metadata.get('channels', 1))
            
        except Exception as e:
            print(f"Optimization failed: {e}")
            return False
    
    def batch_optimize(self, input_dir: str, output_dir: str, level: str = 'medium') -> Dict[str, Any]:
        """Optimize all audio files in a directory"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        if not input_path.exists():
            return {'error': 'Input directory not found'}
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Find audio files
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a']
        audio_files = []
        for ext in audio_extensions:
            audio_files.extend(input_path.glob(f'*{ext}'))
        
        if not audio_files:
            return {'error': 'No audio files found'}
        
        results = {
            'processed': 0,
            'failed': 0,
            'total_size_before': 0,
            'total_size_after': 0,
            'files': []
        }
        
        for audio_file in audio_files:
            try:
                # Get original size
                original_size = audio_file.stat().st_size
                results['total_size_before'] += original_size
                
                # Optimize
                output_file = output_path / audio_file.name
                success = self.optimize_file(str(audio_file), str(output_file), level)
                
                if success and output_file.exists():
                    new_size = output_file.stat().st_size
                    results['total_size_after'] += new_size
                    compression_ratio = (original_size - new_size) / original_size * 100
                    
                    results['files'].append({
                        'file': audio_file.name,
                        'original_size': original_size,
                        'new_size': new_size,
                        'compression_percent': compression_ratio,
                        'status': 'success'
                    })
                    results['processed'] += 1
                else:
                    results['files'].append({
                        'file': audio_file.name,
                        'status': 'failed'
                    })
                    results['failed'] += 1
                    
            except Exception as e:
                results['files'].append({
                    'file': audio_file.name,
                    'status': 'error',
                    'error': str(e)
                })
                results['failed'] += 1
        
        # Calculate overall compression
        if results['total_size_before'] > 0:
            overall_compression = (results['total_size_before'] - results['total_size_after']) / results['total_size_before'] * 100
            results['overall_compression_percent'] = overall_compression
        
        return results


class FileValidator:
    """Validate audio files for common issues"""
    
    def __init__(self):
        self.issues = []
    
    def validate_file(self, filepath: str) -> Dict[str, Any]:
        """Validate an audio file and return analysis"""
        path = Path(filepath)
        if not path.exists():
            return {'valid': False, 'error': 'File not found'}
        
        try:
            from audio_formats import AudioFormatHandler
            handler = AudioFormatHandler()
            audio_data, metadata = handler.load_audio(filepath)
            
            issues = []
            
            # Check for silence
            if audio_utils.detect_silence(audio_data):
                issues.append('File appears to be silent or very quiet')
            
            # Check for clipping
            peak = audio_utils.detect_peak(audio_data)
            if peak > 0.99:
                issues.append('Audio may be clipped (peak > 99%)')
            
            # Check for very low levels
            rms = audio_utils.calculate_rms(audio_data)
            if rms < 1000:  # Very quiet
                issues.append('Audio level is very low')
            
            # Check for DC offset
            samples = audio_utils.bytes_to_samples(audio_data)
            if samples:
                dc_offset = sum(samples) / len(samples)
                if abs(dc_offset) > 100:
                    issues.append(f'DC offset detected: {dc_offset:.1f}')
            
            # Check duration
            duration = len(audio_data) / (2 * metadata.get('sample_rate', 44100))
            if duration < 0.1:
                issues.append('Audio duration is very short (< 0.1 seconds)')
            
            return {
                'valid': True,
                'issues': issues,
                'metadata': metadata,
                'peak': peak,
                'rms': rms,
                'duration': duration,
                'file_size': path.stat().st_size
            }
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def repair_file(self, filepath: str, output_file: Optional[str] = None) -> bool:
        """Attempt to repair common audio file issues"""
        try:
            from audio_formats import AudioFormatHandler
            handler = AudioFormatHandler()
            
            audio_data, metadata = handler.load_audio(filepath)
            samples = audio_utils.bytes_to_samples(audio_data)
            
            # Apply repairs
            repaired = samples.copy()
            
            # Remove DC offset
            repaired = audio_utils.remove_dc_offset(repaired)
            
            # Normalize if very quiet
            rms = audio_utils.calculate_rms(repaired)
            if rms < 5000:
                audio_data = audio_utils.normalize_audio(repaired, 0.8)
                repaired = audio_utils.bytes_to_samples(audio_data)
            
            # Clip protection
            repaired = audio_utils.clip_audio(repaired, 0.95)
            
            # Save repaired file
            output_path = output_file or filepath
            repaired_data = audio_utils.samples_to_bytes(repaired)
            
            return handler.save_audio(repaired_data, output_path,
                                    sample_rate=metadata.get('sample_rate', 44100),
                                    channels=metadata.get('channels', 1))
            
        except Exception as e:
            print(f"Repair failed: {e}")
            return False


# Convenience functions
def optimize_audio_file(input_file: str, output_file: str, level: str = 'medium') -> bool:
    """Optimize a single audio file"""
    optimizer = AudioOptimizer()
    return optimizer.optimize_file(input_file, output_file, level)


def analyze_audio_file(filepath: str) -> Dict[str, Any]:
    """Analyze an audio file for optimization potential"""
    optimizer = AudioOptimizer()
    return optimizer.analyze_file(filepath)


def validate_audio_file(filepath: str) -> Dict[str, Any]:
    """Validate an audio file for issues"""
    validator = FileValidator()
    return validator.validate_file(filepath)