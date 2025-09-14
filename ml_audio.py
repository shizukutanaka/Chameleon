#!/usr/bin/env python3
"""
Chameleon Audio System - Machine Learning Audio Features Module

純Python実装の機械学習音声処理
- 音声分類・パターン認識
- 自動セグメンテーション
- 感情認識・音声解析
- 異常検知・品質分析
- レコメンデーション・最適化
- スペクトラム機械学習
"""

import math
import struct
import wave
import array
import statistics
from typing import List, Tuple, Dict, Optional, Any, Union
from enum import Enum
import json

class MLFeatureType(Enum):
    MFCC = "mfcc"
    SPECTRAL_CENTROID = "spectral_centroid"
    SPECTRAL_ROLLOFF = "spectral_rolloff"
    ZERO_CROSSING_RATE = "zero_crossing_rate"
    ENERGY = "energy"
    TEMPO = "tempo"
    CHROMA = "chroma"

class AudioClassification(Enum):
    SPEECH = "speech"
    MUSIC = "music"
    NOISE = "noise"
    SILENCE = "silence"
    UNKNOWN = "unknown"

class EmotionType(Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    CALM = "calm"
    EXCITED = "excited"
    NEUTRAL = "neutral"

class AudioFeatureExtractor:
    """音声特徴量抽出器"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.frame_size = 512  # 高速化のため小さくする
        self.hop_size = 256
        
    def extract_mfcc(self, audio_data: List[float], num_coeffs: int = 13) -> List[List[float]]:
        """MFCC (Mel-Frequency Cepstral Coefficients) 抽出"""
        frames = self._frame_audio(audio_data)
        mfcc_features = []
        
        for frame in frames:
            # パワースペクトラム計算
            power_spectrum = self._compute_power_spectrum(frame)
            
            # メルフィルターバンク適用
            mel_energies = self._apply_mel_filterbank(power_spectrum)
            
            # 対数化
            log_mel = [math.log(max(energy, 1e-10)) for energy in mel_energies]
            
            # DCT変換 (簡易実装)
            mfcc = self._dct(log_mel)[:num_coeffs]
            mfcc_features.append(mfcc)
            
        return mfcc_features
        
    def extract_spectral_centroid(self, audio_data: List[float]) -> List[float]:
        """スペクトラル重心抽出"""
        frames = self._frame_audio(audio_data)
        centroids = []
        
        for frame in frames:
            spectrum = self._compute_power_spectrum(frame)
            
            # 重心計算
            numerator = sum(i * magnitude for i, magnitude in enumerate(spectrum))
            denominator = sum(spectrum)
            
            if denominator > 0:
                centroid = numerator / denominator
                # Hz単位に変換
                centroid_hz = (centroid * self.sample_rate) / (2 * len(spectrum))
                centroids.append(centroid_hz)
            else:
                centroids.append(0.0)
                
        return centroids
        
    def extract_spectral_rolloff(self, audio_data: List[float], rolloff_percent: float = 0.85) -> List[float]:
        """スペクトラルロールオフ抽出"""
        frames = self._frame_audio(audio_data)
        rolloffs = []
        
        for frame in frames:
            spectrum = self._compute_power_spectrum(frame)
            
            # 総エネルギー計算
            total_energy = sum(spectrum)
            target_energy = total_energy * rolloff_percent
            
            # ロールオフ点検索
            cumulative_energy = 0
            rolloff_bin = 0
            
            for i, magnitude in enumerate(spectrum):
                cumulative_energy += magnitude
                if cumulative_energy >= target_energy:
                    rolloff_bin = i
                    break
                    
            # Hz単位に変換
            rolloff_hz = (rolloff_bin * self.sample_rate) / (2 * len(spectrum))
            rolloffs.append(rolloff_hz)
            
        return rolloffs
        
    def extract_zero_crossing_rate(self, audio_data: List[float]) -> List[float]:
        """ゼロクロッシング率抽出"""
        frames = self._frame_audio(audio_data)
        zcr_values = []
        
        for frame in frames:
            crossings = 0
            for i in range(1, len(frame)):
                if (frame[i-1] >= 0) != (frame[i] >= 0):
                    crossings += 1
                    
            zcr = crossings / (2.0 * len(frame))
            zcr_values.append(zcr)
            
        return zcr_values
        
    def extract_energy(self, audio_data: List[float]) -> List[float]:
        """エネルギー抽出"""
        frames = self._frame_audio(audio_data)
        energies = []
        
        for frame in frames:
            energy = sum(sample * sample for sample in frame)
            energies.append(energy)
            
        return energies
        
    def extract_tempo(self, audio_data: List[float]) -> float:
        """テンポ推定 (BPM)"""
        # 簡易テンポ検出アルゴリズム
        onset_times = self._detect_onsets(audio_data)
        
        if len(onset_times) < 2:
            return 120.0  # デフォルトBPM
            
        # インターバル計算
        intervals = []
        for i in range(1, len(onset_times)):
            interval = onset_times[i] - onset_times[i-1]
            if 0.2 < interval < 2.0:  # 妥当な範囲のみ
                intervals.append(interval)
                
        if not intervals:
            return 120.0
            
        # 平均インターバルからBPM計算
        avg_interval = statistics.median(intervals)
        bpm = 60.0 / avg_interval
        
        # 妥当な範囲に制限
        return max(60.0, min(200.0, bpm))
        
    def _frame_audio(self, audio_data: List[float]) -> List[List[float]]:
        """音声をフレーム分割"""
        frames = []
        for i in range(0, len(audio_data) - self.frame_size, self.hop_size):
            frame = audio_data[i:i + self.frame_size]
            if len(frame) == self.frame_size:
                frames.append(frame)
        return frames
        
    def _compute_power_spectrum(self, frame: List[float]) -> List[float]:
        """パワースペクトラム計算 (簡易・高速版)"""
        n = len(frame)
        # より少ないビンで高速化
        num_bins = min(64, n // 8)  # 最大64ビン
        spectrum = []
        
        for k in range(num_bins):
            real = 0.0
            imag = 0.0
            
            # サンプリング間隔を増やして高速化
            step = max(1, n // 256)
            
            for n_idx in range(0, n, step):
                angle = -2 * math.pi * k * n_idx / n
                real += frame[n_idx] * math.cos(angle)
                imag += frame[n_idx] * math.sin(angle)
                
            magnitude = math.sqrt(real * real + imag * imag)
            spectrum.append(magnitude)
            
        return spectrum
        
    def _apply_mel_filterbank(self, power_spectrum: List[float], num_filters: int = 12) -> List[float]:
        """メルフィルターバンク適用"""
        # メル尺度変換
        def hz_to_mel(hz):
            return 2595 * math.log10(1 + hz / 700)
            
        def mel_to_hz(mel):
            return 700 * (10**(mel / 2595) - 1)
            
        # フィルター周波数設定
        low_mel = hz_to_mel(0)
        high_mel = hz_to_mel(self.sample_rate / 2)
        
        mel_points = [low_mel + i * (high_mel - low_mel) / (num_filters + 1) 
                     for i in range(num_filters + 2)]
        hz_points = [mel_to_hz(mel) for mel in mel_points]
        
        # ビン対応
        bin_points = [int((hz * len(power_spectrum) * 2) / self.sample_rate) 
                     for hz in hz_points]
        
        # フィルター適用
        filter_energies = []
        for i in range(num_filters):
            energy = 0.0
            
            for j in range(bin_points[i], bin_points[i + 2]):
                if j < len(power_spectrum):
                    if bin_points[i] <= j < bin_points[i + 1]:
                        weight = (j - bin_points[i]) / (bin_points[i + 1] - bin_points[i])
                    elif bin_points[i + 1] <= j < bin_points[i + 2]:
                        weight = (bin_points[i + 2] - j) / (bin_points[i + 2] - bin_points[i + 1])
                    else:
                        weight = 0.0
                    energy += power_spectrum[j] * weight
                    
            filter_energies.append(energy)
            
        return filter_energies
        
    def _dct(self, data: List[float]) -> List[float]:
        """離散コサイン変換 (DCT)"""
        n = len(data)
        dct_coeffs = []
        
        for k in range(n):
            coeff = 0.0
            for i in range(n):
                coeff += data[i] * math.cos(math.pi * k * (i + 0.5) / n)
            dct_coeffs.append(coeff)
            
        return dct_coeffs
        
    def _detect_onsets(self, audio_data: List[float]) -> List[float]:
        """オンセット検出"""
        frames = self._frame_audio(audio_data)
        onset_times = []
        
        prev_energy = 0.0
        threshold_factor = 1.5
        
        for i, frame in enumerate(frames):
            energy = sum(sample * sample for sample in frame)
            
            # エネルギー急増を検出
            if energy > prev_energy * threshold_factor and energy > 0.01:
                time = i * self.hop_size / self.sample_rate
                onset_times.append(time)
                
            prev_energy = energy
            
        return onset_times

class SimpleNeuralNetwork:
    """シンプルなニューラルネットワーク"""
    
    def __init__(self, input_size: int, hidden_size: int, output_size: int):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        # 重み初期化 (ランダム)
        import random
        random.seed(42)  # 再現性のため
        
        self.weights1 = [[random.uniform(-1, 1) for _ in range(input_size)] 
                        for _ in range(hidden_size)]
        self.weights2 = [[random.uniform(-1, 1) for _ in range(hidden_size)] 
                        for _ in range(output_size)]
        
        self.bias1 = [random.uniform(-1, 1) for _ in range(hidden_size)]
        self.bias2 = [random.uniform(-1, 1) for _ in range(output_size)]
        
    def sigmoid(self, x: float) -> float:
        """シグモイド活性化関数"""
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0
            
    def forward(self, inputs: List[float]) -> List[float]:
        """フォワードパス"""
        # 隠れ層
        hidden = []
        for i in range(self.hidden_size):
            weighted_sum = sum(inputs[j] * self.weights1[i][j] for j in range(len(inputs)))
            hidden.append(self.sigmoid(weighted_sum + self.bias1[i]))
            
        # 出力層
        outputs = []
        for i in range(self.output_size):
            weighted_sum = sum(hidden[j] * self.weights2[i][j] for j in range(len(hidden)))
            outputs.append(self.sigmoid(weighted_sum + self.bias2[i]))
            
        return outputs

class AudioClassifier:
    """音声分類器"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.feature_extractor = AudioFeatureExtractor(sample_rate)
        
        # 事前学習済みモデル (簡易版)
        self.speech_music_classifier = SimpleNeuralNetwork(26, 16, 2)  # MFCC 26次元
        self.emotion_classifier = SimpleNeuralNetwork(26, 20, 6)  # 6感情
        
        # 閾値設定
        self.silence_threshold = 0.001
        self.noise_threshold = 0.1
        
    def classify_audio_type(self, audio_data: List[float]) -> Dict[str, Any]:
        """音声タイプ分類 (音声/音楽/ノイズ/無音)"""
        # 基本統計
        energy = sum(sample * sample for sample in audio_data) / len(audio_data)
        
        # 無音判定
        if energy < self.silence_threshold:
            return {
                'classification': AudioClassification.SILENCE,
                'confidence': 0.95,
                'energy': energy
            }
            
        # 特徴量抽出
        zcr = statistics.mean(self.feature_extractor.extract_zero_crossing_rate(audio_data))
        spectral_centroid = statistics.mean(self.feature_extractor.extract_spectral_centroid(audio_data))
        
        # ルールベース分類
        if zcr > 0.3 and energy < self.noise_threshold:
            classification = AudioClassification.NOISE
            confidence = 0.8
        elif zcr > 0.15:
            classification = AudioClassification.SPEECH
            confidence = 0.7
        elif spectral_centroid < 2000:
            classification = AudioClassification.MUSIC
            confidence = 0.6
        else:
            classification = AudioClassification.UNKNOWN
            confidence = 0.5
            
        return {
            'classification': classification,
            'confidence': confidence,
            'energy': energy,
            'zero_crossing_rate': zcr,
            'spectral_centroid': spectral_centroid
        }
        
    def analyze_emotion(self, audio_data: List[float]) -> Dict[str, Any]:
        """感情分析"""
        # 特徴量抽出
        energy = statistics.mean(self.feature_extractor.extract_energy(audio_data))
        zcr = statistics.mean(self.feature_extractor.extract_zero_crossing_rate(audio_data))
        spectral_centroid = statistics.mean(self.feature_extractor.extract_spectral_centroid(audio_data))
        tempo = self.feature_extractor.extract_tempo(audio_data)
        
        # 簡易感情分析 (ルールベース)
        emotion_scores = {
            EmotionType.HAPPY: 0.0,
            EmotionType.SAD: 0.0,
            EmotionType.ANGRY: 0.0,
            EmotionType.CALM: 0.0,
            EmotionType.EXCITED: 0.0,
            EmotionType.NEUTRAL: 0.0
        }
        
        # エネルギーベース
        if energy > 0.1:
            emotion_scores[EmotionType.EXCITED] += 0.3
            emotion_scores[EmotionType.ANGRY] += 0.2
        else:
            emotion_scores[EmotionType.CALM] += 0.3
            emotion_scores[EmotionType.SAD] += 0.2
            
        # テンポベース
        if tempo > 140:
            emotion_scores[EmotionType.HAPPY] += 0.3
            emotion_scores[EmotionType.EXCITED] += 0.2
        elif tempo < 80:
            emotion_scores[EmotionType.SAD] += 0.3
            emotion_scores[EmotionType.CALM] += 0.2
            
        # スペクトラル重心ベース
        if spectral_centroid > 3000:
            emotion_scores[EmotionType.HAPPY] += 0.2
            emotion_scores[EmotionType.ANGRY] += 0.1
        else:
            emotion_scores[EmotionType.SAD] += 0.2
            emotion_scores[EmotionType.CALM] += 0.1
            
        # ZCRベース
        if zcr > 0.2:
            emotion_scores[EmotionType.ANGRY] += 0.2
            emotion_scores[EmotionType.EXCITED] += 0.1
        else:
            emotion_scores[EmotionType.CALM] += 0.2
            
        # ニュートラル調整
        emotion_scores[EmotionType.NEUTRAL] = 0.3
        
        # 正規化
        total_score = sum(emotion_scores.values())
        if total_score > 0:
            for emotion in emotion_scores:
                emotion_scores[emotion] /= total_score
                
        # 最も可能性の高い感情
        predicted_emotion = max(emotion_scores, key=emotion_scores.get)
        confidence = emotion_scores[predicted_emotion]
        
        return {
            'predicted_emotion': predicted_emotion,
            'confidence': confidence,
            'emotion_scores': emotion_scores,
            'features': {
                'energy': energy,
                'tempo': tempo,
                'spectral_centroid': spectral_centroid,
                'zero_crossing_rate': zcr
            }
        }

class AudioSegmenter:
    """音声セグメンテーション"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.feature_extractor = AudioFeatureExtractor(sample_rate)
        
    def segment_by_energy(self, audio_data: List[float], 
                         threshold: float = 0.01,
                         min_segment_length: float = 0.5) -> List[Dict[str, Any]]:
        """エネルギーベースセグメンテーション"""
        frame_size = 1024
        hop_size = 512
        min_frames = int(min_segment_length * self.sample_rate / hop_size)
        
        segments = []
        current_segment_start = None
        frames_in_segment = 0
        
        for i in range(0, len(audio_data) - frame_size, hop_size):
            frame = audio_data[i:i + frame_size]
            energy = sum(sample * sample for sample in frame) / len(frame)
            
            if energy > threshold:
                if current_segment_start is None:
                    current_segment_start = i / self.sample_rate
                    frames_in_segment = 1
                else:
                    frames_in_segment += 1
            else:
                if current_segment_start is not None and frames_in_segment >= min_frames:
                    segment_end = i / self.sample_rate
                    segments.append({
                        'start': current_segment_start,
                        'end': segment_end,
                        'duration': segment_end - current_segment_start,
                        'type': 'active'
                    })
                current_segment_start = None
                frames_in_segment = 0
                
        # 最後のセグメント処理
        if current_segment_start is not None and frames_in_segment >= min_frames:
            segment_end = len(audio_data) / self.sample_rate
            segments.append({
                'start': current_segment_start,
                'end': segment_end,
                'duration': segment_end - current_segment_start,
                'type': 'active'
            })
            
        return segments
        
    def segment_by_change_detection(self, audio_data: List[float]) -> List[Dict[str, Any]]:
        """変化点検出によるセグメンテーション"""
        frame_size = 2048
        hop_size = 1024
        
        spectral_centroids = self.feature_extractor.extract_spectral_centroid(audio_data)
        
        # 変化点検出
        change_points = []
        threshold = 500  # Hz
        
        for i in range(1, len(spectral_centroids)):
            if abs(spectral_centroids[i] - spectral_centroids[i-1]) > threshold:
                time = i * hop_size / self.sample_rate
                change_points.append(time)
                
        # セグメント作成
        segments = []
        start_time = 0.0
        
        for change_time in change_points:
            if change_time - start_time > 1.0:  # 最小1秒
                segments.append({
                    'start': start_time,
                    'end': change_time,
                    'duration': change_time - start_time,
                    'type': 'segment'
                })
            start_time = change_time
            
        # 最後のセグメント
        end_time = len(audio_data) / self.sample_rate
        if end_time - start_time > 1.0:
            segments.append({
                'start': start_time,
                'end': end_time,
                'duration': end_time - start_time,
                'type': 'segment'
            })
            
        return segments

class AudioAnomalyDetector:
    """音声異常検知"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.feature_extractor = AudioFeatureExtractor(sample_rate)
        
    def detect_clipping(self, audio_data: List[float], threshold: float = 0.99) -> Dict[str, Any]:
        """クリッピング検知"""
        clipped_samples = sum(1 for sample in audio_data if abs(sample) >= threshold)
        clipping_ratio = clipped_samples / len(audio_data)
        
        return {
            'has_clipping': clipping_ratio > 0.001,  # 0.1%以上
            'clipping_ratio': clipping_ratio,
            'clipped_samples': clipped_samples,
            'severity': 'high' if clipping_ratio > 0.01 else 'medium' if clipping_ratio > 0.001 else 'low'
        }
        
    def detect_dc_offset(self, audio_data: List[float]) -> Dict[str, Any]:
        """DCオフセット検知"""
        dc_offset = sum(audio_data) / len(audio_data)
        threshold = 0.1
        
        return {
            'has_dc_offset': abs(dc_offset) > threshold,
            'dc_offset': dc_offset,
            'severity': 'high' if abs(dc_offset) > 0.3 else 'medium' if abs(dc_offset) > threshold else 'low'
        }
        
    def detect_noise_level(self, audio_data: List[float]) -> Dict[str, Any]:
        """ノイズレベル検知"""
        # 高周波ノイズ検出 (簡易)
        high_freq_energy = 0.0
        total_energy = 0.0
        
        energies = self.feature_extractor.extract_energy(audio_data)
        spectral_centroids = self.feature_extractor.extract_spectral_centroid(audio_data)
        
        total_energy = sum(energies)
        high_freq_ratio = sum(1 for sc in spectral_centroids if sc > 8000) / len(spectral_centroids)
        
        noise_level = high_freq_ratio * 0.7 + (total_energy / len(audio_data)) * 0.3
        
        return {
            'noise_level': noise_level,
            'high_freq_ratio': high_freq_ratio,
            'is_noisy': noise_level > 0.3,
            'severity': 'high' if noise_level > 0.5 else 'medium' if noise_level > 0.3 else 'low'
        }

class MLAudioProcessor:
    """統合機械学習音声処理システム"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.feature_extractor = AudioFeatureExtractor(sample_rate)
        self.classifier = AudioClassifier(sample_rate)
        self.segmenter = AudioSegmenter(sample_rate)
        self.anomaly_detector = AudioAnomalyDetector(sample_rate)
        
    def analyze_audio_comprehensive(self, audio_data) -> Dict[str, Any]:
        """包括的音声分析"""
        # bytes型の場合はfloatリストに変換
        if isinstance(audio_data, bytes):
            audio_list = []
            for i in range(0, len(audio_data), 2):
                if i + 1 < len(audio_data):
                    sample = struct.unpack('<h', audio_data[i:i+2])[0]
                    audio_list.append(sample / 32767.0)
            audio_data = audio_list
        
        analysis_results = {
            'basic_stats': self._compute_basic_stats(audio_data),
            'classification': self.classifier.classify_audio_type(audio_data),
            'emotion_analysis': self.classifier.analyze_emotion(audio_data),
            'features': self._extract_all_features(audio_data),
            'segments': self.segmenter.segment_by_energy(audio_data),
            'anomalies': self._detect_all_anomalies(audio_data),
            'quality_score': self._compute_quality_score(audio_data)
        }
        
        return analysis_results
        
    def _compute_basic_stats(self, audio_data: List[float]) -> Dict[str, float]:
        """基本統計計算"""
        if not audio_data:
            return {}
            
        return {
            'duration': len(audio_data) / self.sample_rate,
            'samples': len(audio_data),
            'max_amplitude': max(abs(sample) for sample in audio_data),
            'rms': math.sqrt(sum(sample * sample for sample in audio_data) / len(audio_data)),
            'mean': sum(audio_data) / len(audio_data),
            'std_dev': math.sqrt(sum((sample - statistics.mean(audio_data))**2 
                                   for sample in audio_data) / len(audio_data))
        }
        
    def _extract_all_features(self, audio_data: List[float]) -> Dict[str, Any]:
        """全特徴量抽出"""
        features = {}
        
        try:
            features['energy'] = statistics.mean(self.feature_extractor.extract_energy(audio_data))
            features['zcr'] = statistics.mean(self.feature_extractor.extract_zero_crossing_rate(audio_data))
            features['spectral_centroid'] = statistics.mean(self.feature_extractor.extract_spectral_centroid(audio_data))
            features['spectral_rolloff'] = statistics.mean(self.feature_extractor.extract_spectral_rolloff(audio_data))
            features['tempo'] = self.feature_extractor.extract_tempo(audio_data)
            
            mfcc = self.feature_extractor.extract_mfcc(audio_data)
            if mfcc:
                features['mfcc_mean'] = [statistics.mean(coeff) for coeff in zip(*mfcc)]
                features['mfcc_std'] = [statistics.stdev(coeff) if len(set(coeff)) > 1 else 0.0 
                                       for coeff in zip(*mfcc)]
        except Exception as e:
            features['extraction_error'] = str(e)
            
        return features
        
    def _detect_all_anomalies(self, audio_data: List[float]) -> Dict[str, Any]:
        """全異常検知"""
        return {
            'clipping': self.anomaly_detector.detect_clipping(audio_data),
            'dc_offset': self.anomaly_detector.detect_dc_offset(audio_data),
            'noise': self.anomaly_detector.detect_noise_level(audio_data)
        }
        
    def _compute_quality_score(self, audio_data: List[float]) -> Dict[str, Any]:
        """品質スコア計算"""
        anomalies = self._detect_all_anomalies(audio_data)
        
        # スコア計算 (0-100)
        score = 100.0
        
        # クリッピング減点
        if anomalies['clipping']['has_clipping']:
            score -= anomalies['clipping']['clipping_ratio'] * 50
            
        # DCオフセット減点
        if anomalies['dc_offset']['has_dc_offset']:
            score -= abs(anomalies['dc_offset']['dc_offset']) * 20
            
        # ノイズ減点
        score -= anomalies['noise']['noise_level'] * 30
        
        score = max(0.0, min(100.0, score))
        
        return {
            'overall_score': score,
            'grade': 'A' if score >= 90 else 'B' if score >= 80 else 'C' if score >= 70 else 'D' if score >= 60 else 'F',
            'issues': self._identify_issues(anomalies)
        }
        
    def _identify_issues(self, anomalies: Dict[str, Any]) -> List[str]:
        """問題点特定"""
        issues = []
        
        if anomalies['clipping']['has_clipping']:
            issues.append(f"Audio clipping detected ({anomalies['clipping']['severity']} severity)")
            
        if anomalies['dc_offset']['has_dc_offset']:
            issues.append(f"DC offset detected ({anomalies['dc_offset']['severity']} severity)")
            
        if anomalies['noise']['is_noisy']:
            issues.append(f"High noise level detected ({anomalies['noise']['severity']} severity)")
            
        return issues

def demo_ml_audio():
    """機械学習音声処理デモ"""
    processor = MLAudioProcessor()
    
    print("🤖 Machine Learning Audio Processing Demo")
    
    # テスト音源生成
    duration = 3.0
    samples = int(duration * processor.sample_rate)
    
    # 音声風サンプル (変調音)
    speech_like = []
    for i in range(samples):
        t = i / processor.sample_rate
        freq = 150 + 50 * math.sin(2 * math.pi * 3 * t)  # 変調
        sample = math.sin(2 * math.pi * freq * t) * 0.3
        # エンベロープ
        envelope = math.exp(-t * 0.5) * (1 + 0.5 * math.sin(2 * math.pi * 5 * t))
        speech_like.append(sample * envelope)
    
    # 音楽風サンプル (和音)
    music_like = []
    frequencies = [220, 277, 330]  # A minor chord
    for i in range(samples):
        t = i / processor.sample_rate
        sample = sum(math.sin(2 * math.pi * freq * t) for freq in frequencies) / len(frequencies)
        sample *= 0.4 * math.exp(-t * 0.3)
        music_like.append(sample)
    
    # ノイズサンプル
    import random
    noise_like = [random.uniform(-0.2, 0.2) for _ in range(samples)]
    
    test_samples = {
        'speech_like': speech_like,
        'music_like': music_like,
        'noise_like': noise_like
    }
    
    results = {}
    
    for sample_name, audio_data in test_samples.items():
        print(f"\nAnalyzing {sample_name}...")
        analysis = processor.analyze_audio_comprehensive(audio_data)
        results[sample_name] = analysis
        
        print(f"  Classification: {analysis['classification']['classification'].value}")
        print(f"  Confidence: {analysis['classification']['confidence']:.2f}")
        print(f"  Emotion: {analysis['emotion_analysis']['predicted_emotion'].value}")
        print(f"  Quality Score: {analysis['quality_score']['overall_score']:.1f}")
        print(f"  Segments: {len(analysis['segments'])}")
        
    return results

if __name__ == "__main__":
    demo_ml_audio()