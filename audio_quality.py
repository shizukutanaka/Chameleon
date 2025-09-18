#!/usr/bin/env python3
"""
Audio Quality Assessment and Repair
Practical tools for audio quality analysis and improvement
"""

import array
import math
from typing import Dict, List, Tuple, Optional, Union
from chameleon import AudioProcessor
from audio_analyzer import AudioAnalyzer


class AudioQualityMetrics:
    """Assess audio quality with practical metrics"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.analyzer = AudioAnalyzer(sample_rate)
        self.processor = AudioProcessor(sample_rate)

    def analyze_quality(self, samples: array.array) -> Dict[str, Union[float, str, bool]]:
        """Comprehensive quality analysis"""
        if not samples:
            return {'error': 'No audio data'}

        metrics = {}

        # Basic measurements
        rms = self.analyzer.get_rms(samples)
        peak = self.analyzer.get_peak(samples)

        # Signal-to-noise ratio estimation
        metrics['snr_db'] = self._estimate_snr(samples)

        # Dynamic range
        metrics['dynamic_range_db'] = self.processor.linear_to_db(peak / max(rms, 1))

        # Clipping detection
        metrics['clipping_percent'] = self._detect_clipping_percentage(samples)

        # Silence detection
        metrics['silence_percent'] = self._detect_silence_percentage(samples)

        # Frequency range analysis
        freq_analysis = self._analyze_frequency_range(samples)
        metrics.update(freq_analysis)

        # Overall quality score (0-100)
        metrics['quality_score'] = self._calculate_quality_score(metrics)

        # Quality rating
        metrics['quality_rating'] = self._get_quality_rating(metrics['quality_score'])

        # Recommendations
        metrics['recommendations'] = self._generate_recommendations(metrics)

        return metrics

    def _estimate_snr(self, samples: array.array) -> float:
        """Estimate signal-to-noise ratio"""
        if len(samples) < 1000:
            return 0.0

        # Find quiet sections (bottom 10% of RMS values)
        window_size = 1024
        rms_values = []

        for i in range(0, len(samples) - window_size, window_size):
            window = samples[i:i + window_size]
            rms = self.analyzer.get_rms(window)
            rms_values.append(rms)

        if not rms_values:
            return 0.0

        # Estimate noise floor from quietest sections
        sorted_rms = sorted(rms_values)
        noise_floor = sum(sorted_rms[:len(sorted_rms)//10]) / max(1, len(sorted_rms)//10)

        # Estimate signal level from loudest sections
        signal_level = sum(sorted_rms[-len(sorted_rms)//10:]) / max(1, len(sorted_rms)//10)

        if noise_floor > 0:
            snr = self.processor.linear_to_db(signal_level / noise_floor)
            return max(0, min(snr, 80))  # Reasonable range

        return 0.0

    def _detect_clipping_percentage(self, samples: array.array) -> float:
        """Detect percentage of clipped samples"""
        if not samples:
            return 0.0

        clipped_count = sum(1 for s in samples if abs(s) >= 32700)
        return (clipped_count / len(samples)) * 100

    def _detect_silence_percentage(self, samples: array.array) -> float:
        """Detect percentage of silent samples"""
        if not samples:
            return 100.0

        silence_threshold = 100  # Very low threshold
        silent_count = sum(1 for s in samples if abs(s) < silence_threshold)
        return (silent_count / len(samples)) * 100

    def _analyze_frequency_range(self, samples: array.array) -> Dict[str, float]:
        """Analyze frequency content"""
        # Get spectrum in bands
        bands = self.analyzer.get_spectrum_bands(samples, 8)

        if not bands:
            return {'freq_low': 0, 'freq_mid': 0, 'freq_high': 0, 'freq_balance': 0}

        # Divide into frequency ranges
        low_freq = sum(bands[:2])    # ~0-5kHz
        mid_freq = sum(bands[2:6])   # ~5-15kHz
        high_freq = sum(bands[6:])   # ~15-22kHz

        total_energy = sum(bands)

        if total_energy > 0:
            return {
                'freq_low': (low_freq / total_energy) * 100,
                'freq_mid': (mid_freq / total_energy) * 100,
                'freq_high': (high_freq / total_energy) * 100,
                'freq_balance': self._calculate_frequency_balance(low_freq, mid_freq, high_freq)
            }

        return {'freq_low': 0, 'freq_mid': 0, 'freq_high': 0, 'freq_balance': 0}

    def _calculate_frequency_balance(self, low: float, mid: float, high: float) -> float:
        """Calculate frequency balance score (0-100)"""
        total = low + mid + high
        if total == 0:
            return 0

        # Ideal balance: roughly 40% low, 40% mid, 20% high for speech/music
        ideal_low, ideal_mid, ideal_high = 0.4, 0.4, 0.2
        actual_low, actual_mid, actual_high = low/total, mid/total, high/total

        # Calculate deviation from ideal
        deviation = (abs(actual_low - ideal_low) +
                    abs(actual_mid - ideal_mid) +
                    abs(actual_high - ideal_high)) / 2

        return max(0, (1 - deviation) * 100)

    def _calculate_quality_score(self, metrics: Dict) -> float:
        """Calculate overall quality score (0-100)"""
        score = 100.0

        # Penalize clipping
        clipping = metrics.get('clipping_percent', 0)
        if clipping > 1:
            score -= min(50, clipping * 10)

        # Penalize excessive silence
        silence = metrics.get('silence_percent', 0)
        if silence > 50:
            score -= min(30, (silence - 50) * 0.5)

        # Reward good SNR
        snr = metrics.get('snr_db', 0)
        if snr < 20:
            score -= (20 - snr) * 2

        # Reward good dynamic range
        dr = metrics.get('dynamic_range_db', 0)
        if dr < 6:
            score -= (6 - dr) * 5

        # Reward frequency balance
        freq_balance = metrics.get('freq_balance', 0)
        score = (score + freq_balance) / 2

        return max(0, min(100, score))

    def _get_quality_rating(self, score: float) -> str:
        """Convert score to rating"""
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 40:
            return "Poor"
        else:
            return "Very Poor"

    def _generate_recommendations(self, metrics: Dict) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []

        clipping = metrics.get('clipping_percent', 0)
        if clipping > 0.1:
            recommendations.append(f"Reduce input level - {clipping:.1f}% clipping detected")

        snr = metrics.get('snr_db', 0)
        if snr < 20:
            recommendations.append(f"Apply noise reduction - low SNR ({snr:.1f}dB)")

        silence = metrics.get('silence_percent', 0)
        if silence > 70:
            recommendations.append("Remove excessive silence periods")

        dr = metrics.get('dynamic_range_db', 0)
        if dr > 40:
            recommendations.append("Apply compression - very wide dynamic range")
        elif dr < 6:
            recommendations.append("Avoid over-compression")

        freq_balance = metrics.get('freq_balance', 0)
        if freq_balance < 50:
            recommendations.append("Check frequency balance - may need EQ")

        if not recommendations:
            recommendations.append("Audio quality is acceptable")

        return recommendations


class AudioRepair:
    """Simple audio repair functions"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.processor = AudioProcessor(sample_rate)

    def auto_repair(self, samples: array.array) -> Tuple[array.array, List[str]]:
        """Automatic audio repair with applied fixes list"""
        if not samples:
            return samples, ["No audio data"]

        repaired = samples
        applied_fixes = []

        # Check and fix clipping
        clipping_percent = self._get_clipping_percentage(repaired)
        if clipping_percent > 0.1:
            repaired = self._repair_clipping(repaired)
            applied_fixes.append(f"Repaired {clipping_percent:.1f}% clipping")

        # Check and remove DC offset
        dc_offset = self._get_dc_offset(repaired)
        if abs(dc_offset) > 100:
            repaired = self._remove_dc_offset(repaired)
            applied_fixes.append(f"Removed DC offset ({dc_offset:.0f})")

        # Check and trim silence
        silence_trimmed = self._trim_silence(repaired)
        if len(silence_trimmed) < len(repaired) * 0.9:
            repaired = silence_trimmed
            reduction = (1 - len(repaired)/len(samples)) * 100
            applied_fixes.append(f"Trimmed {reduction:.1f}% silence")

        # Normalize if needed
        peak = max(abs(min(repaired)), abs(max(repaired)))
        if peak < 16000 or peak > 32000:
            repaired = self.processor.normalize(repaired, 0.95)
            applied_fixes.append("Normalized levels")

        if not applied_fixes:
            applied_fixes.append("No repairs needed")

        return repaired, applied_fixes

    def _get_clipping_percentage(self, samples: array.array) -> float:
        """Get percentage of clipped samples"""
        if not samples:
            return 0.0
        clipped = sum(1 for s in samples if abs(s) >= 32700)
        return (clipped / len(samples)) * 100

    def _repair_clipping(self, samples: array.array) -> array.array:
        """Simple clipping repair using soft limiting"""
        repaired = array.array('h')
        threshold = 32000

        for i, sample in enumerate(samples):
            if abs(sample) > threshold:
                # Soft limiting
                sign = 1 if sample > 0 else -1
                limited = sign * (threshold + (abs(sample) - threshold) * 0.1)
                repaired.append(int(limited))
            else:
                repaired.append(sample)

        return repaired

    def _get_dc_offset(self, samples: array.array) -> float:
        """Calculate DC offset"""
        if not samples:
            return 0.0
        return sum(samples) / len(samples)

    def _remove_dc_offset(self, samples: array.array) -> array.array:
        """Remove DC offset"""
        if not samples:
            return samples

        offset = self._get_dc_offset(samples)
        return array.array('h', [int(s - offset) for s in samples])

    def _trim_silence(self, samples: array.array, threshold: int = 200) -> array.array:
        """Trim leading and trailing silence"""
        if not samples:
            return samples

        # Find first non-silent sample
        start = 0
        for i, sample in enumerate(samples):
            if abs(sample) > threshold:
                start = i
                break

        # Find last non-silent sample
        end = len(samples)
        for i in range(len(samples) - 1, -1, -1):
            if abs(samples[i]) > threshold:
                end = i + 1
                break

        # Keep some padding
        padding = min(1000, len(samples) // 100)
        start = max(0, start - padding)
        end = min(len(samples), end + padding)

        return samples[start:end]

    def repair_clicks(self, samples: array.array, sensitivity: float = 0.8) -> array.array:
        """Simple click and pop removal"""
        if len(samples) < 3:
            return samples

        repaired = array.array('h', samples)
        threshold = 32767 * sensitivity

        # Detect and repair sudden amplitude changes
        for i in range(1, len(samples) - 1):
            prev_sample = samples[i - 1]
            curr_sample = samples[i]
            next_sample = samples[i + 1]

            # Check for abnormal jump
            if (abs(curr_sample - prev_sample) > threshold and
                abs(curr_sample - next_sample) > threshold):
                # Replace with interpolated value
                repaired[i] = (prev_sample + next_sample) // 2

        return repaired


def demo():
    """Demo quality analysis and repair"""
    print("Audio Quality Assessment Demo")
    print("-" * 40)

    # Create test audio with some issues
    from audio_recorder import SimpleRecorder
    import os

    recorder = SimpleRecorder()

    # Generate test file with intentional issues
    test_file = "quality_test.wav"
    recorder.generate_test_tone(440, 2.0, test_file)

    # Load and add some problems
    processor = AudioProcessor()
    samples, info = processor.load_wav(test_file)

    if samples:
        # Add DC offset
        offset_samples = array.array('h', [s + 1000 for s in samples])

        # Add some clipping
        clipped_samples = array.array('h')
        for s in offset_samples:
            if abs(s) > 30000:
                clipped_samples.append(32767 if s > 0 else -32768)
            else:
                clipped_samples.append(s)

        # Save problematic version
        problem_file = "problem_audio.wav"
        processor.save_wav(problem_file, clipped_samples, info['sample_rate'])

        print("\n1. Quality Analysis:")
        quality = AudioQualityMetrics()
        metrics = quality.analyze_quality(clipped_samples)

        print(f"Quality Score: {metrics['quality_score']:.1f}/100 ({metrics['quality_rating']})")
        print(f"SNR: {metrics['snr_db']:.1f}dB")
        print(f"Clipping: {metrics['clipping_percent']:.1f}%")
        print(f"Dynamic Range: {metrics['dynamic_range_db']:.1f}dB")

        print("\nRecommendations:")
        for rec in metrics['recommendations']:
            print(f"  - {rec}")

        print("\n2. Auto Repair:")
        repair = AudioRepair()
        repaired, fixes = repair.auto_repair(clipped_samples)

        print("Applied fixes:")
        for fix in fixes:
            print(f"  - {fix}")

        # Test repaired quality
        repaired_metrics = quality.analyze_quality(repaired)
        print(f"\nAfter repair: {repaired_metrics['quality_score']:.1f}/100 ({repaired_metrics['quality_rating']})")

        # Save repaired version
        repaired_file = "repaired_audio.wav"
        processor.save_wav(repaired_file, repaired, info['sample_rate'])

        # Cleanup
        for file in [test_file, problem_file, repaired_file]:
            if os.path.exists(file):
                os.remove(file)
                print(f"Cleaned up: {file}")

    print("\nQuality demo complete!")


if __name__ == '__main__':
    demo()