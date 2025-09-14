#!/usr/bin/env python3
"""
Chameleon Audio System - Advanced Audio Codecs & Compression Module

プロフェッショナル音声コーデック・圧縮システム
- 高度音声圧縮アルゴリズム
- ロスレス・ロッシー圧縮
- 適応ビットレート制御
- 心理音響モデル
- プロフェッショナルコーデック実装
- リアルタイム圧縮・展開
"""

import math
import struct
import array
import zlib
import base64
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import json

class CompressionType(Enum):
    LOSSLESS = "lossless"
    LOSSY = "lossy"
    HYBRID = "hybrid"

class CodecType(Enum):
    PCM_UNCOMPRESSED = "pcm"
    ADPCM = "adpcm"
    DPCM = "dpcm"
    PSYCHOACOUSTIC = "psychoacoustic"
    WAVELET = "wavelet"
    SPECTRAL = "spectral"
    NEURAL = "neural"

class AudioCodec:
    """音声コーデック基底クラス"""
    
    def __init__(self, codec_type: CodecType, compression_type: CompressionType):
        self.codec_type = codec_type
        self.compression_type = compression_type
        self.sample_rate = 44100
        self.bit_depth = 16
        self.channels = 1
        
    def encode(self, audio_data: List[float]) -> bytes:
        """音声データエンコード"""
        raise NotImplementedError
        
    def decode(self, encoded_data: bytes) -> List[float]:
        """音声データデコード"""
        raise NotImplementedError
        
    def get_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """圧縮率計算"""
        if compressed_size == 0:
            return 0.0
        return original_size / compressed_size

class ADPCMCodec(AudioCodec):
    """ADPCM (Adaptive Differential Pulse Code Modulation) コーデック"""
    
    def __init__(self):
        super().__init__(CodecType.ADPCM, CompressionType.LOSSY)
        
        # ADPCM予測フィルタ
        self.predictor = 0
        self.step_index = 0
        
        # ステップサイズテーブル
        self.step_table = [
            7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
            19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
            50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
            130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
            337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
            876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
            2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
            5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
            15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
        ]
        
        # インデックステーブル
        self.index_table = [-1, -1, -1, -1, 2, 4, 6, 8]
        
    def encode(self, audio_data: List[float]) -> bytes:
        """ADPCMエンコード"""
        # float → 16bit PCM変換
        pcm_data = [int(max(-32768, min(32767, sample * 32767))) for sample in audio_data]
        
        encoded = []
        self.predictor = 0
        self.step_index = 0
        
        for i in range(0, len(pcm_data), 2):
            # 2サンプルを1バイトに圧縮
            sample1 = pcm_data[i] if i < len(pcm_data) else 0
            sample2 = pcm_data[i + 1] if i + 1 < len(pcm_data) else 0
            
            code1 = self._encode_sample(sample1)
            code2 = self._encode_sample(sample2)
            
            # 4bitずつパック
            encoded_byte = (code1 & 0xF) | ((code2 & 0xF) << 4)
            encoded.append(encoded_byte)
            
        return bytes(encoded)
        
    def decode(self, encoded_data: bytes) -> List[float]:
        """ADPCMデコード"""
        decoded = []
        self.predictor = 0
        self.step_index = 0
        
        for byte_val in encoded_data:
            # 4bitずつアンパック
            code1 = byte_val & 0xF
            code2 = (byte_val >> 4) & 0xF
            
            sample1 = self._decode_sample(code1)
            sample2 = self._decode_sample(code2)
            
            decoded.append(sample1 / 32767.0)
            decoded.append(sample2 / 32767.0)
            
        return decoded
        
    def _encode_sample(self, sample: int) -> int:
        """単一サンプルエンコード"""
        step = self.step_table[self.step_index]
        diff = sample - self.predictor
        
        code = 0
        if diff < 0:
            code = 8
            diff = -diff
            
        if diff >= step:
            code |= 4
            diff -= step
        if diff >= step // 2:
            code |= 2
            diff -= step // 2
        if diff >= step // 4:
            code |= 1
            
        # 予測値更新
        diff_quantized = self._decode_sample(code) - self.predictor
        self.predictor += diff_quantized
        self.predictor = max(-32768, min(32767, self.predictor))
        
        return code
        
    def _decode_sample(self, code: int) -> int:
        """単一サンプルデコード"""
        step = self.step_table[self.step_index]
        
        diff = step // 8
        if code & 4:
            diff += step
        if code & 2:
            diff += step // 2
        if code & 1:
            diff += step // 4
            
        if code & 8:
            diff = -diff
            
        self.predictor += diff
        self.predictor = max(-32768, min(32767, self.predictor))
        
        # ステップインデックス更新
        self.step_index += self.index_table[code & 7]
        self.step_index = max(0, min(len(self.step_table) - 1, self.step_index))
        
        return self.predictor

class PsychoacousticCodec(AudioCodec):
    """心理音響モデルベースコーデック"""
    
    def __init__(self, quality: float = 0.8):
        super().__init__(CodecType.PSYCHOACOUSTIC, CompressionType.LOSSY)
        self.quality = quality  # 0.0-1.0
        self.frame_size = 1024
        self.masking_threshold_db = -60.0  # マスキング閾値
        
    def encode(self, audio_data: List[float]) -> bytes:
        """心理音響エンコード"""
        encoded_frames = []
        
        # フレーム分割
        for i in range(0, len(audio_data), self.frame_size):
            frame = audio_data[i:i + self.frame_size]
            if len(frame) < self.frame_size:
                frame.extend([0.0] * (self.frame_size - len(frame)))
                
            encoded_frame = self._encode_frame(frame)
            encoded_frames.append(encoded_frame)
            
        # フレーム結合
        result = b""
        for frame_data in encoded_frames:
            frame_length = len(frame_data)
            result += struct.pack('>I', frame_length)  # フレーム長
            result += frame_data
            
        return result
        
    def decode(self, encoded_data: bytes) -> List[float]:
        """心理音響デコード"""
        decoded_audio = []
        pos = 0
        
        while pos < len(encoded_data):
            if pos + 4 > len(encoded_data):
                break
                
            # フレーム長読み取り
            frame_length = struct.unpack('>I', encoded_data[pos:pos + 4])[0]
            pos += 4
            
            if pos + frame_length > len(encoded_data):
                break
                
            # フレームデータ読み取り
            frame_data = encoded_data[pos:pos + frame_length]
            pos += frame_length
            
            # フレームデコード
            decoded_frame = self._decode_frame(frame_data)
            decoded_audio.extend(decoded_frame)
            
        return decoded_audio
        
    def _encode_frame(self, frame: List[float]) -> bytes:
        """フレームエンコード"""
        # FFT
        spectrum = self._fft(frame)
        
        # 心理音響マスキング計算
        masking_threshold = self._compute_masking_threshold(spectrum)
        
        # 量子化
        quantized_spectrum = self._quantize_spectrum(spectrum, masking_threshold)
        
        # 可変長エンコード
        return self._encode_spectrum(quantized_spectrum)
        
    def _decode_frame(self, frame_data: bytes) -> List[float]:
        """フレームデコード"""
        # スペクトラムデコード
        spectrum = self._decode_spectrum(frame_data)
        
        # IFFT
        return self._ifft(spectrum)
        
    def _fft(self, frame: List[float]) -> List[complex]:
        """簡易FFT実装"""
        n = len(frame)
        spectrum = []
        
        for k in range(n // 2):
            real = 0.0
            imag = 0.0
            
            for i in range(n):
                angle = -2 * math.pi * k * i / n
                real += frame[i] * math.cos(angle)
                imag += frame[i] * math.sin(angle)
                
            spectrum.append(complex(real, imag))
            
        return spectrum
        
    def _ifft(self, spectrum: List[complex]) -> List[float]:
        """簡易IFFT実装"""
        n = len(spectrum) * 2
        frame = []
        
        for i in range(n):
            sample = 0.0
            
            for k in range(len(spectrum)):
                angle = 2 * math.pi * k * i / n
                real_part = spectrum[k].real * math.cos(angle) - spectrum[k].imag * math.sin(angle)
                sample += real_part
                
            frame.append(sample / n)
            
        return frame
        
    def _compute_masking_threshold(self, spectrum: List[complex]) -> List[float]:
        """マスキング閾値計算"""
        n = len(spectrum)
        threshold = []
        
        for i in range(n):
            magnitude_db = 20 * math.log10(max(abs(spectrum[i]), 1e-10))
            
            # 簡易マスキング計算
            masked_threshold = self.masking_threshold_db
            
            # 近隣の強い成分によるマスキング
            for j in range(max(0, i - 10), min(n, i + 11)):
                if i != j:
                    neighbor_db = 20 * math.log10(max(abs(spectrum[j]), 1e-10))
                    distance = abs(i - j)
                    masking_effect = neighbor_db - 20 * math.log10(distance + 1)
                    masked_threshold = max(masked_threshold, masking_effect)
                    
            threshold.append(masked_threshold)
            
        return threshold
        
    def _quantize_spectrum(self, spectrum: List[complex], threshold: List[float]) -> List[Tuple[int, int]]:
        """スペクトラム量子化"""
        quantized = []
        quality_factor = int(8 * self.quality + 1)  # 1-8ビット
        
        for i, coeff in enumerate(spectrum):
            magnitude = abs(coeff)
            phase = math.atan2(coeff.imag, coeff.real)
            
            # マスキング閾値以下は0に
            magnitude_db = 20 * math.log10(max(magnitude, 1e-10))
            if magnitude_db < threshold[i]:
                quantized.append((0, 0))
                continue
                
            # 量子化
            max_val = 2 ** (quality_factor - 1) - 1
            quant_mag = int(magnitude * max_val)
            quant_phase = int((phase + math.pi) / (2 * math.pi) * 255)
            
            quantized.append((quant_mag, quant_phase))
            
        return quantized
        
    def _encode_spectrum(self, quantized_spectrum: List[Tuple[int, int]]) -> bytes:
        """スペクトラムエンコード"""
        data = []
        
        for mag, phase in quantized_spectrum:
            data.append(mag & 0xFF)
            data.append((mag >> 8) & 0xFF)
            data.append(phase & 0xFF)
            
        # 圧縮
        return zlib.compress(bytes(data))
        
    def _decode_spectrum(self, frame_data: bytes) -> List[complex]:
        """スペクトラムデコード"""
        # 展開
        data = zlib.decompress(frame_data)
        
        spectrum = []
        for i in range(0, len(data), 3):
            if i + 2 < len(data):
                mag = data[i] | (data[i + 1] << 8)
                phase = data[i + 2]
                
                # 非量子化
                magnitude = mag / 32767.0
                phase_rad = (phase / 255.0) * 2 * math.pi - math.pi
                
                real = magnitude * math.cos(phase_rad)
                imag = magnitude * math.sin(phase_rad)
                spectrum.append(complex(real, imag))
                
        return spectrum

class WaveletCodec(AudioCodec):
    """ウェーブレット変換ベースコーデック"""
    
    def __init__(self, levels: int = 6):
        super().__init__(CodecType.WAVELET, CompressionType.LOSSY)
        self.levels = levels
        
    def encode(self, audio_data: List[float]) -> bytes:
        """ウェーブレットエンコード"""
        # ウェーブレット変換
        coefficients = self._wavelet_transform(audio_data, self.levels)
        
        # 閾値処理
        thresholded = self._threshold_coefficients(coefficients)
        
        # 量子化・エンコード
        return self._encode_coefficients(thresholded)
        
    def decode(self, encoded_data: bytes) -> List[float]:
        """ウェーブレットデコード"""
        # 係数デコード
        coefficients = self._decode_coefficients(encoded_data)
        
        # 逆ウェーブレット変換
        return self._inverse_wavelet_transform(coefficients, self.levels)
        
    def _wavelet_transform(self, signal: List[float], levels: int) -> List[float]:
        """Haarウェーブレット変換"""
        coeffs = signal[:]
        
        for level in range(levels):
            length = len(coeffs) // (2 ** level)
            if length < 2:
                break
                
            # 低周波・高周波分離
            low_freq = []
            high_freq = []
            
            for i in range(0, length, 2):
                if i + 1 < length:
                    low = (coeffs[i] + coeffs[i + 1]) / math.sqrt(2)
                    high = (coeffs[i] - coeffs[i + 1]) / math.sqrt(2)
                    low_freq.append(low)
                    high_freq.append(high)
                else:
                    low_freq.append(coeffs[i])
                    
            # 結合
            coeffs[:len(low_freq)] = low_freq
            coeffs[len(low_freq):len(low_freq) + len(high_freq)] = high_freq
            
        return coeffs
        
    def _inverse_wavelet_transform(self, coeffs: List[float], levels: int) -> List[float]:
        """逆Haarウェーブレット変換"""
        signal = coeffs[:]
        
        for level in range(levels - 1, -1, -1):
            length = len(signal) // (2 ** level)
            if length < 2:
                continue
                
            half_length = length // 2
            low_freq = signal[:half_length]
            high_freq = signal[half_length:half_length * 2]
            
            # 再構成
            reconstructed = []
            for i in range(min(len(low_freq), len(high_freq))):
                val1 = (low_freq[i] + high_freq[i]) / math.sqrt(2)
                val2 = (low_freq[i] - high_freq[i]) / math.sqrt(2)
                reconstructed.extend([val1, val2])
                
            signal[:len(reconstructed)] = reconstructed
            
        return signal
        
    def _threshold_coefficients(self, coeffs: List[float]) -> List[float]:
        """係数閾値処理"""
        # エネルギーベース閾値
        energy = sum(coeff * coeff for coeff in coeffs)
        threshold = math.sqrt(energy / len(coeffs)) * 0.1
        
        return [coeff if abs(coeff) > threshold else 0.0 for coeff in coeffs]
        
    def _encode_coefficients(self, coeffs: List[float]) -> bytes:
        """係数エンコード"""
        # 量子化
        quantized = [int(coeff * 32767) for coeff in coeffs]
        
        # バイト列変換
        data = []
        for val in quantized:
            val = max(-32768, min(32767, val))
            data.extend(struct.pack('<h', val))
            
        # 圧縮
        return zlib.compress(bytes(data))
        
    def _decode_coefficients(self, encoded_data: bytes) -> List[float]:
        """係数デコード"""
        # 展開
        data = zlib.decompress(encoded_data)
        
        # 非量子化
        coeffs = []
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                val = struct.unpack('<h', data[i:i + 2])[0]
                coeffs.append(val / 32767.0)
                
        return coeffs

class AdaptiveBitrateController:
    """適応ビットレート制御"""
    
    def __init__(self):
        self.target_bitrate = 128000  # bps
        self.current_quality = 0.8
        self.buffer_level = 0.5  # 0.0-1.0
        self.network_bandwidth = 256000  # bps
        
    def update_network_conditions(self, bandwidth: float, latency: float, packet_loss: float):
        """ネットワーク状況更新"""
        self.network_bandwidth = bandwidth
        
        # 品質調整
        if packet_loss > 0.05:  # 5%以上のパケットロス
            self.current_quality = max(0.3, self.current_quality - 0.1)
        elif packet_loss < 0.01 and latency < 50:  # 良好な状況
            self.current_quality = min(1.0, self.current_quality + 0.05)
            
    def get_recommended_quality(self) -> float:
        """推奨品質取得"""
        # バッファレベル考慮
        if self.buffer_level < 0.3:
            return max(0.3, self.current_quality - 0.2)
        elif self.buffer_level > 0.8:
            return min(1.0, self.current_quality + 0.1)
        else:
            return self.current_quality
            
    def adjust_bitrate(self, content_complexity: float) -> int:
        """ビットレート調整"""
        base_bitrate = self.target_bitrate
        
        # コンテンツ複雑度による調整
        complexity_factor = 0.5 + content_complexity * 0.5
        
        # ネットワーク帯域による制限
        max_bitrate = int(self.network_bandwidth * 0.8)  # 80%利用
        
        adjusted_bitrate = int(base_bitrate * complexity_factor * self.current_quality)
        return min(adjusted_bitrate, max_bitrate)

class AdvancedAudioCodecManager:
    """高度音声コーデック管理システム"""
    
    def __init__(self):
        self.codecs = {
            'adpcm': ADPCMCodec(),
            'psychoacoustic': PsychoacousticCodec(),
            'wavelet': WaveletCodec()
        }
        
        self.bitrate_controller = AdaptiveBitrateController()
        
    def encode_audio(self, audio_data: List[float], codec_name: str, 
                    quality: float = 0.8) -> Dict[str, Any]:
        """音声エンコード"""
        if codec_name not in self.codecs:
            raise ValueError(f"Unknown codec: {codec_name}")
            
        codec = self.codecs[codec_name]
        
        # 品質設定
        if hasattr(codec, 'quality'):
            codec.quality = quality
            
        # エンコード
        start_size = len(audio_data) * 4  # float32として計算
        encoded_data = codec.encode(audio_data)
        
        # 統計情報
        compression_ratio = codec.get_compression_ratio(start_size, len(encoded_data))
        
        return {
            'codec': codec_name,
            'data': base64.b64encode(encoded_data).decode('ascii'),
            'original_size': start_size,
            'compressed_size': len(encoded_data),
            'compression_ratio': compression_ratio,
            'quality': quality,
            'sample_rate': codec.sample_rate,
            'channels': codec.channels
        }
        
    def decode_audio(self, encoded_info: Dict[str, Any]) -> List[float]:
        """音声デコード"""
        codec_name = encoded_info['codec']
        if codec_name not in self.codecs:
            raise ValueError(f"Unknown codec: {codec_name}")
            
        codec = self.codecs[codec_name]
        encoded_data = base64.b64decode(encoded_info['data'])
        
        return codec.decode(encoded_data)
        
    def compare_codecs(self, audio_data: List[float], quality: float = 0.8) -> Dict[str, Dict]:
        """コーデック比較"""
        results = {}
        
        for codec_name in self.codecs.keys():
            try:
                # エンコード
                encoded_info = self.encode_audio(audio_data, codec_name, quality)
                
                # デコード
                decoded_audio = self.decode_audio(encoded_info)
                
                # 品質測定 (MSE)
                mse = self._calculate_mse(audio_data, decoded_audio)
                snr = self._calculate_snr(audio_data, decoded_audio)
                
                results[codec_name] = {
                    'compression_ratio': encoded_info['compression_ratio'],
                    'compressed_size': encoded_info['compressed_size'],
                    'mse': mse,
                    'snr_db': snr,
                    'codec_type': self.codecs[codec_name].codec_type.value,
                    'compression_type': self.codecs[codec_name].compression_type.value
                }
                
            except Exception as e:
                results[codec_name] = {'error': str(e)}
                
        return results
        
    def _calculate_mse(self, original: List[float], decoded: List[float]) -> float:
        """平均二乗誤差計算"""
        min_len = min(len(original), len(decoded))
        if min_len == 0:
            return float('inf')
            
        mse = sum((original[i] - decoded[i]) ** 2 for i in range(min_len)) / min_len
        return mse
        
    def _calculate_snr(self, original: List[float], decoded: List[float]) -> float:
        """SNR計算"""
        min_len = min(len(original), len(decoded))
        if min_len == 0:
            return 0.0
            
        signal_power = sum(x ** 2 for x in original[:min_len]) / min_len
        noise_power = sum((original[i] - decoded[i]) ** 2 for i in range(min_len)) / min_len
        
        if noise_power == 0:
            return float('inf')
        if signal_power == 0:
            return 0.0
            
        snr = 10 * math.log10(signal_power / noise_power)
        return snr

def demo_advanced_codecs():
    """高度コーデックデモ"""
    print("🎵 Advanced Audio Codecs Demo")
    
    # テスト音声生成
    duration = 2.0
    sample_rate = 44100
    samples = int(duration * sample_rate)
    
    # 複雑な音声信号 (複数周波数)
    test_audio = []
    frequencies = [220, 440, 880, 1760]  # A3, A4, A5, A6
    
    for i in range(samples):
        t = i / sample_rate
        sample = 0.0
        
        for freq in frequencies:
            amplitude = 1.0 / len(frequencies)
            sample += amplitude * math.sin(2 * math.pi * freq * t)
            
        # エンベロープ適用
        envelope = math.exp(-t * 0.5)
        test_audio.append(sample * envelope * 0.5)
    
    print(f"Test audio: {len(test_audio)} samples, {duration:.1f}s")
    
    # コーデック管理
    codec_manager = AdvancedAudioCodecManager()
    
    # 各コーデック比較
    print("\n=== Codec Comparison ===")
    comparison = codec_manager.compare_codecs(test_audio, quality=0.8)
    
    for codec_name, stats in comparison.items():
        if 'error' in stats:
            print(f"{codec_name}: ERROR - {stats['error']}")
        else:
            print(f"{codec_name}:")
            print(f"  Compression: {stats['compression_ratio']:.1f}x")
            print(f"  Size: {stats['compressed_size']} bytes")
            print(f"  SNR: {stats['snr_db']:.1f} dB")
            print(f"  Type: {stats['codec_type']} ({stats['compression_type']})")
    
    # 品質別比較
    print("\n=== Quality Comparison (Psychoacoustic) ===")
    qualities = [0.3, 0.5, 0.8, 1.0]
    
    for quality in qualities:
        encoded = codec_manager.encode_audio(test_audio, 'psychoacoustic', quality)
        decoded = codec_manager.decode_audio(encoded)
        
        mse = codec_manager._calculate_mse(test_audio, decoded)
        snr = codec_manager._calculate_snr(test_audio, decoded)
        
        print(f"Quality {quality:.1f}: "
              f"Ratio {encoded['compression_ratio']:.1f}x, "
              f"SNR {snr:.1f} dB")
    
    return {
        'test_audio': test_audio,
        'comparison': comparison,
        'codec_manager': codec_manager
    }

if __name__ == "__main__":
    demo_advanced_codecs()