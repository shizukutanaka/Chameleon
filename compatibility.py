#!/usr/bin/env python3
"""
Compatibility layer for missing dependencies
Provides fallback implementations when numpy, scipy, etc. are not available
"""

import array
import math
from typing import List, Union, Any

# Check for numpy availability
try:
    import numpy as np
    HAS_NUMPY = True
    
    # Re-export numpy functions
    def as_array(data, dtype=None):
        return np.array(data, dtype=dtype)
    
    def frombuffer(buffer, dtype):
        return np.frombuffer(buffer, dtype=dtype)
        
    def zeros(shape, dtype=None):
        return np.zeros(shape, dtype=dtype)
        
    def max_abs(arr):
        return np.max(np.abs(arr))
        
    def mean(arr):
        return np.mean(arr)
        
    def sqrt(x):
        return np.sqrt(x)
        
    def sin(x):
        return np.sin(x)
        
    def clip(arr, min_val, max_val):
        return np.clip(arr, min_val, max_val)
        
except ImportError:
    HAS_NUMPY = False
    
    # Fallback implementations using pure Python
    def as_array(data, dtype=None):
        """Convert to array-like object"""
        if isinstance(data, list):
            return data
        elif isinstance(data, bytes):
            arr = array.array('h')
            arr.frombytes(data)
            return list(arr)
        else:
            return list(data)
    
    def frombuffer(buffer, dtype):
        """Convert buffer to array"""
        if dtype == 'int16' or dtype == 'h':
            arr = array.array('h')
            arr.frombytes(buffer)
            return list(arr)
        else:
            # Generic fallback
            return list(buffer)
    
    def zeros(shape, dtype=None):
        """Create array of zeros"""
        if isinstance(shape, int):
            return [0] * shape
        else:
            return [0] * shape[0]  # Simplified for 1D
    
    def max_abs(arr):
        """Maximum absolute value"""
        return max(abs(x) for x in arr) if arr else 0
    
    def mean(arr):
        """Mean value"""
        return sum(arr) / len(arr) if arr else 0
    
    def sqrt(x):
        """Square root"""
        if isinstance(x, list):
            return [math.sqrt(val) for val in x]
        return math.sqrt(x)
    
    def sin(x):
        """Sine function"""
        if isinstance(x, list):
            return [math.sin(val) for val in x]
        return math.sin(x)
    
    def clip(arr, min_val, max_val):
        """Clip values to range"""
        return [max(min_val, min(max_val, x)) for x in arr]

# Check for scipy availability
try:
    from scipy import signal, stats
    HAS_SCIPY = True
    
except ImportError:
    HAS_SCIPY = False
    
    # Fallback signal processing
    class signal:
        @staticmethod
        def butter(n, wn, btype='low'):
            # Very simple fallback - just return identity coefficients
            return ([1.0], [1.0])
        
        @staticmethod
        def filtfilt(b, a, x):
            # Simple identity filter fallback
            return x
    
    class stats:
        @staticmethod
        def skew(arr):
            # Simple skewness approximation
            if not arr:
                return 0.0
            m = mean(arr)
            var = sum((x - m)**2 for x in arr) / len(arr)
            if var == 0:
                return 0.0
            std = math.sqrt(var)
            skew_sum = sum(((x - m) / std)**3 for x in arr)
            return skew_sum / len(arr)
        
        @staticmethod
        def kurtosis(arr):
            # Simple kurtosis approximation
            if not arr:
                return 0.0
            m = mean(arr)
            var = sum((x - m)**2 for x in arr) / len(arr)
            if var == 0:
                return 0.0
            std = math.sqrt(var)
            kurt_sum = sum(((x - m) / std)**4 for x in arr)
            return (kurt_sum / len(arr)) - 3  # Excess kurtosis

# Check for numba availability
try:
    import numba
    HAS_NUMBA = True
    
    # Use numba decorators
    def jit(nopython=True, cache=True):
        return numba.jit(nopython=nopython, cache=cache)
        
except ImportError:
    HAS_NUMBA = False
    
    # Fallback decorator that does nothing
    def jit(nopython=True, cache=True):
        def decorator(func):
            return func  # Return function unchanged
        return decorator

# Utility functions that work with or without dependencies
def safe_normalize(samples: Union[List, Any], target_max: float = 0.95) -> List:
    """Normalize audio samples with fallback implementation"""
    if HAS_NUMPY and hasattr(samples, 'dtype'):
        # Use numpy if available
        max_val = max_abs(samples)
        if max_val == 0:
            return samples
        scale = (32767 * target_max) / max_val
        return (samples * scale).astype('int16')
    else:
        # Pure Python fallback
        if isinstance(samples, bytes):
            arr = array.array('h')
            arr.frombytes(samples)
            samples = list(arr)
        
        if not samples:
            return []
        
        max_val = max(abs(s) for s in samples)
        if max_val == 0:
            return samples
        
        scale = (32767 * target_max) / max_val
        return [int(s * scale) for s in samples]

def safe_tone_generation(frequency: float, duration: float, sample_rate: int = 44100) -> bytes:
    """Generate tone with fallback implementation"""
    num_samples = int(duration * sample_rate)
    samples = []
    phase_increment = 2 * math.pi * frequency / sample_rate
    
    for i in range(num_samples):
        phase = i * phase_increment
        value = math.sin(phase) * 32767 * 0.5
        samples.append(int(value))
    
    arr = array.array('h', samples)
    return arr.tobytes()

def safe_rms_calculation(samples: Union[List, Any]) -> float:
    """Calculate RMS with fallback implementation"""
    if isinstance(samples, bytes):
        arr = array.array('h')
        arr.frombytes(samples)
        samples = list(arr)
    
    if not samples:
        return 0.0
    
    sum_squares = sum(s * s for s in samples)
    return math.sqrt(sum_squares / len(samples))

# Feature flags for conditional functionality
FEATURES = {
    'numpy': HAS_NUMPY,
    'scipy': HAS_SCIPY,
    'numba': HAS_NUMBA,
    'advanced_analysis': HAS_NUMPY and HAS_SCIPY,
    'fast_processing': HAS_NUMBA,
    'basic_processing': True  # Always available
}

def get_available_features():
    """Get list of available features"""
    return {name: available for name, available in FEATURES.items()}

def require_feature(feature_name: str):
    """Decorator to require a specific feature"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not FEATURES.get(feature_name, False):
                raise RuntimeError(f"Feature '{feature_name}' not available. Missing dependencies.")
            return func(*args, **kwargs)
        return wrapper
    return decorator