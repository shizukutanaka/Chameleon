#!/usr/bin/env python3
"""
Audio Quality Monitor - Automatic quality validation and correction
Real-time monitoring and optimization for audio processing
"""

import array
import math
import time
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

import audio_utils


@dataclass
class QualityMetrics:
    """Audio quality metrics"""
    peak_level: float
    rms_level: float
    dynamic_range: float
    thd_estimate: float  # Total harmonic distortion estimate
    snr_estimate: float  # Signal-to-noise ratio estimate
    clipping_detected: bool
    dc_offset: float
    is_silent: bool
    quality_score: float  # 0-100 overall quality


class QualityMonitor:
    """Real-time audio quality monitoring"""
    
    def __init__(self):
        self.history = []
        self.max_history = 100
        self.quality_threshold = 70.0
        self.auto_correct = True
        
    def analyze_quality(self, audio_data: bytes) -> QualityMetrics:
        """Comprehensive quality analysis of audio data"""
        samples = audio_utils.bytes_to_samples(audio_data)
        if not samples:
            return QualityMetrics(0, 0, 0, 0, 0, False, 0, True, 0)
        
        # Basic measurements
        peak = max(abs(s) for s in samples) / audio_utils.MAX_INT16
        rms = audio_utils.calculate_rms(samples) / audio_utils.MAX_INT16
        dc_offset = sum(samples) / len(samples) if samples else 0
        is_silent = audio_utils.detect_silence(samples, threshold=0.01)
        
        # Dynamic range
        dynamic_range = peak - rms if peak > rms else 0
        
        # Clipping detection
        clipping_detected = peak > 0.99
        
        # THD estimation (simplified)
        thd_estimate = self._estimate_thd(samples)
        
        # SNR estimation (simplified)
        snr_estimate = self._estimate_snr(samples)
        
        # Overall quality score
        quality_score = self._calculate_quality_score(
            peak, rms, dynamic_range, thd_estimate, snr_estimate, 
            clipping_detected, abs(dc_offset), is_silent
        )
        
        metrics = QualityMetrics(
            peak_level=peak,
            rms_level=rms,
            dynamic_range=dynamic_range,
            thd_estimate=thd_estimate,
            snr_estimate=snr_estimate,
            clipping_detected=clipping_detected,
            dc_offset=dc_offset,
            is_silent=is_silent,
            quality_score=quality_score
        )
        
        # Update history
        self.history.append(metrics)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return metrics
    
    def _estimate_thd(self, samples: List[int]) -> float:
        """Estimate total harmonic distortion"""
        if len(samples) < 1024:
            return 0.0
        
        # Simplified THD estimation based on high-frequency content
        high_freq_energy = 0
        total_energy = 0
        
        for i in range(1, len(samples)):
            diff = abs(samples[i] - samples[i-1])
            high_freq_energy += diff * diff
            total_energy += samples[i] * samples[i]
        
        if total_energy == 0:
            return 0.0
        
        thd_ratio = high_freq_energy / total_energy
        return min(100.0, thd_ratio * 100)
    
    def _estimate_snr(self, samples: List[int]) -> float:
        """Estimate signal-to-noise ratio"""
        if len(samples) < 512:
            return 0.0
        
        # Find quiet sections (noise floor)
        window_size = 256
        noise_floors = []
        
        for i in range(0, len(samples) - window_size, window_size):
            window = samples[i:i + window_size]
            window_rms = math.sqrt(sum(s * s for s in window) / len(window))
            if window_rms < audio_utils.MAX_INT16 * 0.1:  # Quiet section
                noise_floors.append(window_rms)
        
        if not noise_floors:
            return 60.0  # Default reasonable SNR
        
        noise_floor = sum(noise_floors) / len(noise_floors)
        if noise_floor == 0:
            return 96.0  # Theoretical max for 16-bit
        
        signal_rms = audio_utils.calculate_rms(samples)
        snr_db = 20 * math.log10(signal_rms / noise_floor) if signal_rms > 0 else 0
        return max(0.0, min(96.0, snr_db))
    
    def _calculate_quality_score(self, peak: float, rms: float, dynamic_range: float,
                                thd: float, snr: float, clipping: bool, 
                                dc_offset: float, is_silent: bool) -> float:
        """Calculate overall quality score (0-100)"""
        if is_silent:
            return 0.0
        
        score = 100.0
        
        # Penalize clipping heavily
        if clipping:
            score -= 30
        
        # Penalize excessive DC offset
        if abs(dc_offset) > 1000:
            score -= 20
        
        # Penalize poor dynamic range
        if dynamic_range < 0.1:
            score -= 15
        elif dynamic_range < 0.2:
            score -= 10
        
        # Penalize high THD
        if thd > 5.0:
            score -= 20
        elif thd > 2.0:
            score -= 10
        
        # Penalize low SNR
        if snr < 40:
            score -= 25
        elif snr < 50:
            score -= 15
        elif snr < 60:
            score -= 5
        
        # Penalize extreme levels
        if peak < 0.1:
            score -= 15  # Too quiet
        elif peak > 0.95:
            score -= 10  # Too loud
        
        return max(0.0, min(100.0, score))
    
    def auto_enhance(self, audio_data: bytes) -> bytes:
        """Automatically enhance audio quality"""
        if not self.auto_correct:
            return audio_data
        
        metrics = self.analyze_quality(audio_data)
        samples = audio_utils.bytes_to_samples(audio_data)
        
        if not samples:
            return audio_data
        
        enhanced = samples.copy()
        
        # Fix DC offset
        if abs(metrics.dc_offset) > 100:
            enhanced = audio_utils.remove_dc_offset(enhanced)
        
        # Fix levels
        if metrics.peak_level < 0.1 and not metrics.is_silent:
            # Too quiet - normalize
            enhanced_bytes = audio_utils.normalize_audio(enhanced, 0.8)
            enhanced = audio_utils.bytes_to_samples(enhanced_bytes)
        elif metrics.clipping_detected:
            # Clipping - apply soft limiting
            enhanced = audio_utils.clip_audio(enhanced, 0.95)
        
        # Gentle noise reduction for very low SNR
        if metrics.snr_estimate < 30:
            enhanced = self._apply_gentle_nr(enhanced)
        
        return audio_utils.samples_to_bytes(enhanced)
    
    def _apply_gentle_nr(self, samples: List[int]) -> List[int]:
        """Apply gentle noise reduction"""
        # Simple noise gate
        threshold = max(abs(s) for s in samples) * 0.05
        
        result = []
        for sample in samples:
            if abs(sample) < threshold:
                result.append(int(sample * 0.3))  # Reduce noise
            else:
                result.append(sample)
        
        return result
    
    def get_quality_report(self) -> Dict[str, Any]:
        """Get comprehensive quality report"""
        if not self.history:
            return {'error': 'No quality data available'}
        
        recent = self.history[-10:]  # Last 10 measurements
        
        avg_quality = sum(m.quality_score for m in recent) / len(recent)
        avg_peak = sum(m.peak_level for m in recent) / len(recent)
        avg_rms = sum(m.rms_level for m in recent) / len(recent)
        avg_snr = sum(m.snr_estimate for m in recent) / len(recent)
        
        clipping_count = sum(1 for m in recent if m.clipping_detected)
        
        return {
            'average_quality_score': avg_quality,
            'average_peak_level': avg_peak,
            'average_rms_level': avg_rms,
            'average_snr_db': avg_snr,
            'clipping_incidents': clipping_count,
            'total_measurements': len(self.history),
            'quality_trend': self._calculate_trend(),
            'recommendations': self._get_recommendations(recent)
        }
    
    def _calculate_trend(self) -> str:
        """Calculate quality trend"""
        if len(self.history) < 5:
            return 'insufficient_data'
        
        recent_avg = sum(m.quality_score for m in self.history[-5:]) / 5
        older_avg = sum(m.quality_score for m in self.history[-10:-5]) / 5 if len(self.history) >= 10 else recent_avg
        
        if recent_avg > older_avg + 5:
            return 'improving'
        elif recent_avg < older_avg - 5:
            return 'declining'
        else:
            return 'stable'
    
    def _get_recommendations(self, recent_metrics: List[QualityMetrics]) -> List[str]:
        """Get quality improvement recommendations"""
        recommendations = []
        
        if any(m.clipping_detected for m in recent_metrics):
            recommendations.append("Reduce input gain to prevent clipping")
        
        avg_snr = sum(m.snr_estimate for m in recent_metrics) / len(recent_metrics)
        if avg_snr < 40:
            recommendations.append("Consider noise reduction or better recording environment")
        
        avg_peak = sum(m.peak_level for m in recent_metrics) / len(recent_metrics)
        if avg_peak < 0.2:
            recommendations.append("Increase recording level for better signal quality")
        
        avg_dc = sum(abs(m.dc_offset) for m in recent_metrics) / len(recent_metrics)
        if avg_dc > 500:
            recommendations.append("Check for DC offset in recording chain")
        
        avg_dr = sum(m.dynamic_range for m in recent_metrics) / len(recent_metrics)
        if avg_dr < 0.15:
            recommendations.append("Audio appears over-compressed - consider reducing compression")
        
        if not recommendations:
            recommendations.append("Audio quality is good")
        
        return recommendations


class AutoCorrector:
    """Automatic audio correction system"""
    
    def __init__(self):
        self.monitor = QualityMonitor()
        self.correction_history = []
        
    def process_with_correction(self, audio_data: bytes, 
                              target_quality: float = 80.0) -> Tuple[bytes, Dict[str, Any]]:
        """Process audio with automatic correction"""
        # Initial quality check
        initial_metrics = self.monitor.analyze_quality(audio_data)
        
        if initial_metrics.quality_score >= target_quality:
            # Quality is already good
            return audio_data, {
                'corrected': False,
                'initial_quality': initial_metrics.quality_score,
                'final_quality': initial_metrics.quality_score
            }
        
        # Apply corrections
        corrected_data = self.monitor.auto_enhance(audio_data)
        
        # Check final quality
        final_metrics = self.monitor.analyze_quality(corrected_data)
        
        correction_info = {
            'corrected': True,
            'initial_quality': initial_metrics.quality_score,
            'final_quality': final_metrics.quality_score,
            'improvement': final_metrics.quality_score - initial_metrics.quality_score,
            'corrections_applied': self._get_corrections_applied(initial_metrics, final_metrics)
        }
        
        self.correction_history.append(correction_info)
        
        return corrected_data, correction_info
    
    def _get_corrections_applied(self, initial: QualityMetrics, 
                               final: QualityMetrics) -> List[str]:
        """Determine what corrections were applied"""
        corrections = []
        
        if abs(initial.dc_offset) > abs(final.dc_offset):
            corrections.append("DC offset correction")
        
        if initial.clipping_detected and not final.clipping_detected:
            corrections.append("Clipping prevention")
        
        if abs(initial.peak_level - 0.8) > abs(final.peak_level - 0.8):
            corrections.append("Level normalization")
        
        if initial.snr_estimate < final.snr_estimate - 2:
            corrections.append("Noise reduction")
        
        return corrections or ["General enhancement"]


# Global instances
quality_monitor = QualityMonitor()
auto_corrector = AutoCorrector()


# Convenience functions
def check_quality(audio_data: bytes) -> QualityMetrics:
    """Quick quality check"""
    return quality_monitor.analyze_quality(audio_data)


def enhance_audio(audio_data: bytes) -> bytes:
    """Enhance audio quality automatically"""
    return quality_monitor.auto_enhance(audio_data)


def process_with_quality_control(audio_data: bytes, target_quality: float = 80.0) -> Tuple[bytes, Dict[str, Any]]:
    """Process audio with automatic quality control"""
    return auto_corrector.process_with_correction(audio_data, target_quality)