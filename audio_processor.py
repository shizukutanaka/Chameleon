#!/usr/bin/env python3
"""
Simple Audio Processor - Basic audio processing without heavy dependencies
Provides essential functionality using pure Python
"""

import array
import math
import logging
from functools import lru_cache
from typing import Dict, Any, Optional, List, Union
from collections import deque

# Import robust error handling
try:
    from robust_error_handler import (
        with_error_handling, get_error_handler, 
        ErrorSeverity, ErrorCategory
    )
    ERROR_HANDLING_AVAILABLE = True
except ImportError:
    # Fallback for basic error handling
    def with_error_handling(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    ERROR_HANDLING_AVAILABLE = False

# Audio constants
SAMPLE_RATE_DEFAULT = 44100
CHANNELS_DEFAULT = 1
CHUNK_SIZE_DEFAULT = 1024
MAX_INT16 = 32767
MIN_INT16 = -32768

class AudioProcessor:
    """Simple audio processor using basic Python operations"""
    
    def __init__(self, sample_rate: int = SAMPLE_RATE_DEFAULT, chunk_size: int = CHUNK_SIZE_DEFAULT):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # Initialize logging
        self.logger = logging.getLogger("AudioProcessor")
        
        # Error handler
        if ERROR_HANDLING_AVAILABLE:
            self.error_handler = get_error_handler("AudioProcessor")
        
        # Simple buffers
        self.working_buffer = [0] * (chunk_size * 2)
        
        # Processing cache for repeated operations
        self._cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Performance tracking
        self.processing_times = deque(maxlen=100)
        
        # Validation
        if sample_rate <= 0:
            raise ValueError(f"Sample rate must be positive, got {sample_rate}")
        if chunk_size <= 0:
            raise ValueError(f"Chunk size must be positive, got {chunk_size}")
        
    def _clip_sample(self, sample: float) -> int:
        """Clip single sample to int16 range"""
        return max(MIN_INT16, min(MAX_INT16, int(sample)))
    
    def _apply_gain(self, samples: List[int], gain: float) -> List[int]:
        """Apply gain to samples"""
        if gain == 1.0:
            return samples
        
        result = []
        for sample in samples:
            amplified = sample * gain
            # Soft clipping
            if amplified > MAX_INT16:
                amplified = MAX_INT16 - (amplified - MAX_INT16) * 0.1
            elif amplified < MIN_INT16:
                amplified = MIN_INT16 - (amplified - MIN_INT16) * 0.1
            result.append(self._clip_sample(amplified))
        
        return result
    
    def _apply_simple_filter(self, samples: List[int], filter_type: str, cutoff: float = 0.5) -> List[int]:
        """Apply simple filter"""
        if not samples or filter_type not in ['lowpass', 'highpass']:
            return samples
        
        # Simple single-pole filter
        alpha = cutoff
        result = []
        prev = 0
        
        for sample in samples:
            if filter_type == 'lowpass':
                filtered = alpha * sample + (1 - alpha) * prev
            else:  # highpass
                filtered = alpha * (sample - prev) + (1 - alpha) * prev
            
            result.append(self._clip_sample(filtered))
            prev = filtered
        
        return result
    
    def _apply_simple_reverb(self, samples: List[int], amount: float) -> List[int]:
        """Apply simple reverb effect"""
        if amount <= 0 or not samples:
            return samples
        
        # Simple delay-based reverb
        delay_samples = min(int(0.05 * self.sample_rate), len(samples) // 2)  # 50ms delay
        result = []
        
        for i, sample in enumerate(samples):
            delayed = 0
            if i >= delay_samples:
                delayed = samples[i - delay_samples] * 0.3
            
            mixed = sample * (1 - amount) + delayed * amount
            result.append(self._clip_sample(mixed))
        
        return result
    
    def _apply_simple_delay(self, samples: List[int], delay_time: float, feedback: float = 0.3) -> List[int]:
        """Apply simple delay effect"""
        if delay_time <= 0 or not samples:
            return samples
        
        delay_samples = min(int(delay_time * self.sample_rate), len(samples) // 2)
        result = []
        
        for i, sample in enumerate(samples):
            delayed = 0
            if i >= delay_samples:
                delayed = samples[i - delay_samples] * feedback
            
            mixed = sample + delayed
            result.append(self._clip_sample(mixed))
        
        return result
    
    @with_error_handling("AudioProcessor", 
                         category=ErrorCategory.LOGIC,
                         severity=ErrorSeverity.ERROR)
    def process_audio(self, samples: Union[bytes, List[int]], params: Dict[str, Any]) -> bytes:
        """Process audio with given parameters"""
        if not samples:
            self.logger.warning("Empty samples provided to process_audio")
            return b''
        
        if not isinstance(params, dict):
            raise TypeError(f"Parameters must be dict, got {type(params)}")
        
        # Convert input to samples list
        try:
            if isinstance(samples, bytes):
                if len(samples) % 2 != 0:
                    raise ValueError("Byte array length must be even for 16-bit samples")
                arr = array.array('h')
                arr.frombytes(samples)
                sample_list = list(arr)
            else:
                sample_list = list(samples)
        except Exception as e:
            self.logger.error(f"Failed to convert input samples: {e}")
            raise ValueError(f"Invalid input samples format: {e}")
        
        if not sample_list:
            return b''
        
        # Create cache key for parameters
        cache_key = str(sorted(params.items()))
        
        # Check cache for repeated operations
        if cache_key in self._cache and len(sample_list) == self._cache[cache_key]['input_len']:
            self._cache_hits += 1
            # Apply cached processing pattern to new data
            cached_ops = self._cache[cache_key]['operations']
            result = sample_list[:]
            for op, op_params in cached_ops:
                if op == 'gain':
                    result = self._apply_gain(result, op_params)
                elif op == 'filter':
                    result = self._apply_simple_filter(result, op_params['type'], op_params.get('cutoff', 0.5))
                elif op == 'reverb':
                    result = self._apply_simple_reverb(result, op_params)
                elif op == 'delay':
                    result = self._apply_simple_delay(result, op_params['time'], op_params.get('feedback', 0.3))
        else:
            self._cache_misses += 1
            result = sample_list[:]
            operations = []
            
            # Apply gain
            gain = params.get('gain', 1.0)
            if gain != 1.0:
                result = self._apply_gain(result, gain)
                operations.append(('gain', gain))
            
            # Apply filter
            filter_type = params.get('filter')
            if filter_type:
                cutoff = params.get('filter_cutoff', 0.5)
                result = self._apply_simple_filter(result, filter_type, cutoff)
                operations.append(('filter', {'type': filter_type, 'cutoff': cutoff}))
            
            # Apply reverb
            reverb = params.get('reverb', 0.0)
            if reverb > 0:
                result = self._apply_simple_reverb(result, reverb)
                operations.append(('reverb', reverb))
            
            # Apply delay
            delay_time = params.get('delay', 0.0)
            if delay_time > 0:
                feedback = params.get('delay_feedback', 0.3)
                result = self._apply_simple_delay(result, delay_time, feedback)
                operations.append(('delay', {'time': delay_time, 'feedback': feedback}))
            
            # Cache the operation sequence
            if len(self._cache) < 100:  # Limit cache size
                self._cache[cache_key] = {
                    'input_len': len(sample_list),
                    'operations': operations
                }
        
        # Convert back to bytes
        output_array = array.array('h', result)
        return output_array.tobytes()
    
    def process_streaming(self, chunk: bytes) -> bytes:
        """Process streaming audio with minimal latency"""
        if not chunk:
            return chunk
        
        # Basic normalization for streaming
        arr = array.array('h')
        arr.frombytes(chunk)
        samples = list(arr)
        
        # Simple gain adjustment
        normalized = [self._clip_sample(s * 1.0) for s in samples]
        
        result_array = array.array('h', normalized)
        return result_array.tobytes()
    
    def clear_cache(self):
        """Clear processing cache"""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'hit_rate': hit_rate,
            'size': len(self._cache)
        }
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics"""
        if not self.processing_times:
            return {'avg_time': 0.0, 'min_time': 0.0, 'max_time': 0.0}
        
        times = list(self.processing_times)
        return {
            'avg_time': sum(times) / len(times),
            'min_time': min(times),
            'max_time': max(times),
            'real_time_factor': (sum(times) / len(times)) / (self.chunk_size / self.sample_rate)
        }
    
    def process(self, audio_data: bytes, **kwargs) -> bytes:
        """Simple process interface for compatibility"""
        return self.process_audio(audio_data, kwargs)