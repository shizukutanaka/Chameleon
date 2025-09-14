#!/usr/bin/env python3
"""
Chameleon Audio System - ML Training & Model Management Module

AI/機械学習トレーニング・モデル管理システム
- 音声データセット管理
- モデルトレーニング・評価
- 転移学習・ファインチューニング
- モデルバージョン管理
- オンライン学習・適応
- 推論最適化・デプロイ
"""

import os
import json
import math
import random
import statistics
from typing import List, Dict, Optional, Tuple, Any, Callable
from enum import Enum
import hashlib
import time

class ModelType(Enum):
    AUDIO_CLASSIFIER = "audio_classifier"
    EMOTION_DETECTOR = "emotion_detector"
    SPEECH_RECOGNITION = "speech_recognition"
    NOISE_REDUCER = "noise_reducer"
    QUALITY_ASSESSOR = "quality_assessor"

class TrainingPhase(Enum):
    PREPROCESSING = "preprocessing"
    TRAINING = "training"
    VALIDATION = "validation"
    EVALUATION = "evaluation"
    DEPLOYMENT = "deployment"

class DataAugmentation:
    """音声データ拡張"""
    
    def __init__(self):
        self.augmentation_methods = {
            'noise_injection': self._add_noise,
            'time_stretch': self._time_stretch,
            'pitch_shift': self._pitch_shift,
            'volume_adjustment': self._adjust_volume,
            'echo_effect': self._add_echo
        }
        
    def augment_audio(self, audio_data: List[float], 
                     method: str, intensity: float = 0.5) -> List[float]:
        """音声データ拡張"""
        if method not in self.augmentation_methods:
            return audio_data.copy()
            
        return self.augmentation_methods[method](audio_data, intensity)
        
    def _add_noise(self, audio_data: List[float], intensity: float) -> List[float]:
        """ノイズ注入"""
        augmented = []
        noise_level = intensity * 0.1
        
        for sample in audio_data:
            noise = random.uniform(-noise_level, noise_level)
            augmented.append(sample + noise)
            
        return augmented
        
    def _time_stretch(self, audio_data: List[float], intensity: float) -> List[float]:
        """時間伸縮"""
        stretch_factor = 1.0 + (intensity - 0.5) * 0.4  # 0.8-1.2x
        
        if stretch_factor == 1.0:
            return audio_data.copy()
            
        stretched = []
        for i in range(int(len(audio_data) * stretch_factor)):
            src_index = i / stretch_factor
            src_int = int(src_index)
            src_frac = src_index - src_int
            
            if src_int + 1 < len(audio_data):
                # 線形補間
                interpolated = audio_data[src_int] * (1 - src_frac) + \
                              audio_data[src_int + 1] * src_frac
                stretched.append(interpolated)
            elif src_int < len(audio_data):
                stretched.append(audio_data[src_int])
                
        return stretched
        
    def _pitch_shift(self, audio_data: List[float], intensity: float) -> List[float]:
        """ピッチシフト（簡易実装）"""
        # 実際のピッチシフトは複雑なため、簡易版として時間伸縮を使用
        pitch_factor = 1.0 + (intensity - 0.5) * 0.2  # ±10%
        return self._time_stretch(audio_data, pitch_factor)
        
    def _adjust_volume(self, audio_data: List[float], intensity: float) -> List[float]:
        """音量調整"""
        volume_factor = 0.5 + intensity * 1.0  # 0.5-1.5x
        return [sample * volume_factor for sample in audio_data]
        
    def _add_echo(self, audio_data: List[float], intensity: float) -> List[float]:
        """エコー効果"""
        delay_samples = int(intensity * 0.1 * 44100)  # 最大0.1秒
        echo_gain = intensity * 0.3
        
        echoed = audio_data.copy()
        
        for i in range(delay_samples, len(echoed)):
            echoed[i] += audio_data[i - delay_samples] * echo_gain
            
        return echoed

class AudioDataset:
    """音声データセット管理"""
    
    def __init__(self, dataset_path: str = "audio_dataset"):
        self.dataset_path = dataset_path
        self.samples = []
        self.labels = []
        self.metadata = {}
        self.augmentation = DataAugmentation()
        
        # データセットディレクトリ作成
        os.makedirs(dataset_path, exist_ok=True)
        
    def add_sample(self, audio_data: List[float], label: str, 
                   metadata: Optional[Dict] = None):
        """サンプル追加"""
        sample_id = len(self.samples)
        
        self.samples.append(audio_data)
        self.labels.append(label)
        
        if metadata:
            self.metadata[sample_id] = metadata
            
    def load_from_directory(self, directory: str, 
                           pattern_to_label: Dict[str, str]):
        """ディレクトリからデータセット読み込み"""
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            # ラベル推定
            label = "unknown"
            for pattern, pattern_label in pattern_to_label.items():
                if pattern in filename.lower():
                    label = pattern_label
                    break
                    
            try:
                # 音声ファイル読み込み（簡易版）
                if filename.endswith('.wav'):
                    audio_data = self._load_wav_simple(file_path)
                    self.add_sample(audio_data, label, {'filename': filename})
                    
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
                
    def _load_wav_simple(self, file_path: str) -> List[float]:
        """簡易WAV読み込み"""
        # 実際の実装では audio_formats を使用
        # ここでは簡易版
        try:
            import wave
            with wave.open(file_path, 'rb') as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                # 16bit PCM想定
                samples = []
                for i in range(0, len(frames), 2):
                    if i + 1 < len(frames):
                        sample = int.from_bytes(frames[i:i+2], 'little', signed=True)
                        samples.append(sample / 32767.0)
                return samples
        except:
            return []
            
    def augment_dataset(self, augmentation_factor: int = 2):
        """データセット拡張"""
        original_count = len(self.samples)
        
        for i in range(original_count):
            for _ in range(augmentation_factor):
                # ランダムな拡張手法選択
                method = random.choice(list(self.augmentation.augmentation_methods.keys()))
                intensity = random.uniform(0.3, 0.7)
                
                augmented_audio = self.augmentation.augment_audio(
                    self.samples[i], method, intensity
                )
                
                # 拡張サンプル追加
                self.add_sample(
                    augmented_audio, 
                    self.labels[i],
                    {
                        'original_id': i,
                        'augmentation': method,
                        'intensity': intensity
                    }
                )
                
        print(f"Dataset augmented: {original_count} → {len(self.samples)} samples")
        
    def split_dataset(self, train_ratio: float = 0.7, 
                     val_ratio: float = 0.2) -> Tuple[Dict, Dict, Dict]:
        """データセット分割"""
        n_samples = len(self.samples)
        indices = list(range(n_samples))
        random.shuffle(indices)
        
        train_end = int(n_samples * train_ratio)
        val_end = train_end + int(n_samples * val_ratio)
        
        train_indices = indices[:train_end]
        val_indices = indices[train_end:val_end]
        test_indices = indices[val_end:]
        
        def create_split(indices):
            return {
                'samples': [self.samples[i] for i in indices],
                'labels': [self.labels[i] for i in indices],
                'indices': indices
            }
            
        return (
            create_split(train_indices),
            create_split(val_indices), 
            create_split(test_indices)
        )
        
    def save_dataset(self, filename: str):
        """データセット保存 (JSON形式で安全に保存)"""
        # audio_dataは大きすぎるため、メタデータのみJSON保存
        dataset_data = {
            'labels': self.labels,
            'metadata': self.metadata,
            'version': '1.0',
            'created_at': time.time(),
            'sample_count': len(self.samples)
        }
        
        json_filename = filename.replace('.pkl', '.json')
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(dataset_data, f, indent=2, ensure_ascii=False)
            
    def load_dataset(self, filename: str):
        """データセット読み込み (JSON形式から安全に読み込み)"""
        json_filename = filename.replace('.pkl', '.json')
        
        try:
            with open(json_filename, 'r', encoding='utf-8') as f:
                dataset_data = json.load(f)
        except FileNotFoundError:
            print(f"Dataset file {json_filename} not found")
            return
            
        # メタデータのみ復元（サンプルは別途読み込み必要）
        self.labels = dataset_data.get('labels', [])
        self.metadata = dataset_data.get('metadata', {})
        self.samples = []  # サンプルは別途読み込み
        
        print(f"Loaded dataset metadata with {len(self.labels)} labels")

class NeuralNetworkTrainer:
    """ニューラルネットワーク訓練器"""
    
    def __init__(self, model_config: Dict):
        self.config = model_config
        self.model = None
        self.training_history = []
        self.feature_extractor = None
        
    def create_model(self, input_size: int, output_size: int) -> Dict:
        """モデル作成"""
        # 簡易ニューラルネットワーク構造
        hidden_size = self.config.get('hidden_size', 64)
        
        model = {
            'weights1': [[random.uniform(-1, 1) for _ in range(input_size)] 
                        for _ in range(hidden_size)],
            'bias1': [random.uniform(-1, 1) for _ in range(hidden_size)],
            'weights2': [[random.uniform(-1, 1) for _ in range(hidden_size)] 
                        for _ in range(output_size)],
            'bias2': [random.uniform(-1, 1) for _ in range(output_size)],
            'config': self.config.copy()
        }
        
        self.model = model
        return model
        
    def extract_features(self, audio_data: List[float]) -> List[float]:
        """特徴量抽出"""
        # 基本統計特徴量
        features = []
        
        # エネルギー
        energy = sum(x * x for x in audio_data) / len(audio_data)
        features.append(energy)
        
        # ゼロクロッシング率
        zero_crossings = sum(1 for i in range(1, len(audio_data)) 
                           if (audio_data[i-1] >= 0) != (audio_data[i] >= 0))
        zcr = zero_crossings / len(audio_data)
        features.append(zcr)
        
        # RMS
        rms = math.sqrt(energy)
        features.append(rms)
        
        # 平均・標準偏差
        mean = sum(audio_data) / len(audio_data)
        variance = sum((x - mean) ** 2 for x in audio_data) / len(audio_data)
        std_dev = math.sqrt(variance)
        features.append(mean)
        features.append(std_dev)
        
        # スペクトラル特徴量（簡易）
        if len(audio_data) >= 256:
            chunk_size = len(audio_data) // 4
            for i in range(4):
                start = i * chunk_size
                end = start + chunk_size
                chunk_energy = sum(x * x for x in audio_data[start:end]) / chunk_size
                features.append(chunk_energy)
        else:
            features.extend([0.0, 0.0, 0.0, 0.0])
            
        return features
        
    def forward_pass(self, inputs: List[float]) -> List[float]:
        """フォワードパス"""
        if not self.model:
            raise ValueError("Model not created")
            
        # 隠れ層
        hidden = []
        for i in range(len(self.model['weights1'])):
            weighted_sum = sum(inputs[j] * self.model['weights1'][i][j] 
                             for j in range(len(inputs)))
            hidden.append(self._sigmoid(weighted_sum + self.model['bias1'][i]))
            
        # 出力層
        outputs = []
        for i in range(len(self.model['weights2'])):
            weighted_sum = sum(hidden[j] * self.model['weights2'][i][j] 
                             for j in range(len(hidden)))
            outputs.append(self._sigmoid(weighted_sum + self.model['bias2'][i]))
            
        return outputs
        
    def _sigmoid(self, x: float) -> float:
        """シグモイド関数"""
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0
            
    def train_model(self, train_data: Dict, val_data: Dict, 
                   epochs: int = 100, learning_rate: float = 0.01) -> Dict:
        """モデル訓練"""
        # ラベルエンコーディング
        unique_labels = list(set(train_data['labels']))
        label_to_idx = {label: i for i, label in enumerate(unique_labels)}
        
        # 特徴量抽出
        train_features = [self.extract_features(sample) for sample in train_data['samples']]
        train_targets = [[1.0 if i == label_to_idx[label] else 0.0 
                         for i in range(len(unique_labels))] 
                        for label in train_data['labels']]
        
        val_features = [self.extract_features(sample) for sample in val_data['samples']]
        val_targets = [[1.0 if i == label_to_idx[label] else 0.0 
                       for i in range(len(unique_labels))] 
                      for label in val_data['labels']]
        
        # モデル作成
        input_size = len(train_features[0])
        output_size = len(unique_labels)
        self.create_model(input_size, output_size)
        
        # 訓練ループ
        for epoch in range(epochs):
            total_loss = 0.0
            correct_predictions = 0
            
            # 訓練データでの学習
            for i in range(len(train_features)):
                features = train_features[i]
                target = train_targets[i]
                
                # フォワードパス
                output = self.forward_pass(features)
                
                # 損失計算
                loss = sum((output[j] - target[j]) ** 2 for j in range(len(target))) / 2
                total_loss += loss
                
                # 予測精度
                predicted_idx = output.index(max(output))
                actual_idx = target.index(max(target))
                if predicted_idx == actual_idx:
                    correct_predictions += 1
                    
                # バックプロパゲーション（簡易版）
                self._backpropagate(features, output, target, learning_rate)
                
            # バリデーション評価
            val_accuracy = self._evaluate_model(val_features, val_targets)
            
            # 履歴記録
            epoch_stats = {
                'epoch': epoch + 1,
                'train_loss': total_loss / len(train_features),
                'train_accuracy': correct_predictions / len(train_features),
                'val_accuracy': val_accuracy
            }
            self.training_history.append(epoch_stats)
            
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs}: "
                      f"Loss={epoch_stats['train_loss']:.4f}, "
                      f"Train Acc={epoch_stats['train_accuracy']:.3f}, "
                      f"Val Acc={epoch_stats['val_accuracy']:.3f}")
                      
        return {
            'model': self.model,
            'label_mapping': label_to_idx,
            'training_history': self.training_history,
            'final_accuracy': self.training_history[-1]['val_accuracy']
        }
        
    def _backpropagate(self, inputs: List[float], outputs: List[float], 
                      targets: List[float], learning_rate: float):
        """簡易バックプロパゲーション"""
        # 出力層エラー
        output_errors = [outputs[i] - targets[i] for i in range(len(outputs))]
        
        # 重み更新（簡易版）
        for i in range(len(self.model['weights2'])):
            for j in range(len(self.model['weights2'][i])):
                gradient = output_errors[i] * inputs[j] if j < len(inputs) else 0
                self.model['weights2'][i][j] -= learning_rate * gradient
                
    def _evaluate_model(self, features: List[List[float]], 
                       targets: List[List[float]]) -> float:
        """モデル評価"""
        correct = 0
        total = len(features)
        
        for i in range(total):
            output = self.forward_pass(features[i])
            predicted_idx = output.index(max(output))
            actual_idx = targets[i].index(max(targets[i]))
            
            if predicted_idx == actual_idx:
                correct += 1
                
        return correct / total if total > 0 else 0.0

class ModelManager:
    """モデル管理システム"""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
        self.models_registry = {}
        self.load_registry()
        
    def save_model(self, model: Dict, model_name: str, 
                   model_type: ModelType, metadata: Optional[Dict] = None) -> str:
        """モデル保存"""
        timestamp = int(time.time())
        version = f"v{timestamp}"
        model_id = f"{model_name}_{version}"
        
        model_info = {
            'model': model,
            'name': model_name,
            'type': model_type.value,
            'version': version,
            'created_at': timestamp,
            'metadata': metadata or {},
            'checksum': self._calculate_checksum(model)
        }
        
        # モデルファイル保存 (JSON形式で安全に保存)
        model_path = os.path.join(self.models_dir, f"{model_id}.json")
        
        # JSON互換形式に変換
        json_model_info = {
            'model': self._serialize_model(model),
            'name': model_name,
            'type': model_type.value,
            'version': version,
            'created_at': timestamp,
            'metadata': metadata or {},
            'checksum': self._calculate_checksum(model)
        }
        
        with open(model_path, 'w', encoding='utf-8') as f:
            json.dump(json_model_info, f, indent=2, ensure_ascii=False)
            
        # レジストリ更新
        if model_name not in self.models_registry:
            self.models_registry[model_name] = []
            
        self.models_registry[model_name].append({
            'model_id': model_id,
            'version': version,
            'type': model_type.value,
            'created_at': timestamp,
            'path': model_path,
            'metadata': metadata or {}
        })
        
        self.save_registry()
        
        print(f"Model saved: {model_id}")
        return model_id
        
    def load_model(self, model_name: str, version: Optional[str] = None) -> Dict:
        """モデル読み込み"""
        if model_name not in self.models_registry:
            raise ValueError(f"Model not found: {model_name}")
            
        models = self.models_registry[model_name]
        
        if version:
            # 特定バージョン
            target_model = None
            for model_info in models:
                if model_info['version'] == version:
                    target_model = model_info
                    break
                    
            if not target_model:
                raise ValueError(f"Version not found: {version}")
        else:
            # 最新バージョン
            target_model = max(models, key=lambda x: x['created_at'])
            
        # モデルファイル読み込み (JSON形式で安全に読み込み)
        try:
            with open(target_model['path'], 'r', encoding='utf-8') as f:
                model_data = json.load(f)
                
            # モデル構造をデシリアライズ
            model_data['model'] = self._deserialize_model(model_data['model'])
            return model_data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to load model: {e}")
        
    def list_models(self) -> Dict:
        """モデル一覧"""
        return self.models_registry.copy()
        
    def delete_model(self, model_name: str, version: Optional[str] = None):
        """モデル削除"""
        if model_name not in self.models_registry:
            return
            
        models = self.models_registry[model_name]
        
        if version:
            # 特定バージョン削除
            models_to_keep = []
            for model_info in models:
                if model_info['version'] == version:
                    try:
                        os.remove(model_info['path'])
                    except:
                        pass
                else:
                    models_to_keep.append(model_info)
            self.models_registry[model_name] = models_to_keep
        else:
            # 全バージョン削除
            for model_info in models:
                try:
                    os.remove(model_info['path'])
                except:
                    pass
            del self.models_registry[model_name]
            
        self.save_registry()
        
    def _serialize_model(self, model: Dict) -> Dict:
        """モデルをJSON互換形式にシリアライズ"""
        return {
            'weights1': model['weights1'],
            'bias1': model['bias1'], 
            'weights2': model['weights2'],
            'bias2': model['bias2'],
            'config': model['config']
        }
        
    def _deserialize_model(self, serialized_model: Dict) -> Dict:
        """シリアライズされたモデルを復元"""
        return {
            'weights1': serialized_model['weights1'],
            'bias1': serialized_model['bias1'],
            'weights2': serialized_model['weights2'], 
            'bias2': serialized_model['bias2'],
            'config': serialized_model['config']
        }
        
    def _calculate_checksum(self, model: Dict) -> str:
        """モデルチェックサム計算"""
        model_str = json.dumps(self._serialize_model(model), sort_keys=True)
        return hashlib.md5(model_str.encode()).hexdigest()
        
    def save_registry(self):
        """レジストリ保存"""
        registry_path = os.path.join(self.models_dir, "registry.json")
        with open(registry_path, 'w') as f:
            json.dump(self.models_registry, f, indent=2)
            
    def load_registry(self):
        """レジストリ読み込み"""
        registry_path = os.path.join(self.models_dir, "registry.json")
        if os.path.exists(registry_path):
            try:
                with open(registry_path, 'r') as f:
                    self.models_registry = json.load(f)
            except:
                self.models_registry = {}

def demo_ml_training():
    """ML訓練デモ"""
    print("🤖 ML Training & Model Management Demo")
    
    # データセット作成
    dataset = AudioDataset("demo_dataset")
    
    # サンプル音声データ生成
    print("Generating sample audio data...")
    sample_rate = 44100
    duration = 1.0
    samples = int(duration * sample_rate)
    
    # 異なるクラスの音声データ
    for class_name in ['tone', 'noise', 'silence']:
        for i in range(10):  # 各クラス10サンプル
            if class_name == 'tone':
                # トーン信号
                freq = 440 + i * 50
                audio = [math.sin(2 * math.pi * freq * t / sample_rate) * 0.5 
                        for t in range(samples)]
            elif class_name == 'noise':
                # ノイズ信号
                audio = [random.uniform(-0.3, 0.3) for _ in range(samples)]
            else:  # silence
                # 無音信号
                audio = [random.uniform(-0.01, 0.01) for _ in range(samples)]
                
            dataset.add_sample(audio, class_name, {'sample_id': i})
            
    print(f"Dataset created: {len(dataset.samples)} samples")
    
    # データ拡張
    dataset.augment_dataset(augmentation_factor=1)
    
    # データセット分割
    train_data, val_data, test_data = dataset.split_dataset()
    print(f"Data split: Train={len(train_data['samples'])}, "
          f"Val={len(val_data['samples'])}, Test={len(test_data['samples'])}")
    
    # モデル訓練
    print("\nTraining neural network...")
    trainer = NeuralNetworkTrainer({
        'hidden_size': 32,
        'model_type': 'audio_classifier'
    })
    
    training_result = trainer.train_model(
        train_data, val_data, epochs=50, learning_rate=0.1
    )
    
    print(f"Training completed. Final accuracy: {training_result['final_accuracy']:.3f}")
    
    # モデル管理
    model_manager = ModelManager("demo_models")
    
    model_id = model_manager.save_model(
        training_result['model'],
        "audio_classifier_demo",
        ModelType.AUDIO_CLASSIFIER,
        {
            'accuracy': training_result['final_accuracy'],
            'epochs': 50,
            'classes': list(training_result['label_mapping'].keys())
        }
    )
    
    # モデル一覧
    print(f"\nSaved models:")
    models = model_manager.list_models()
    for name, versions in models.items():
        print(f"  {name}: {len(versions)} versions")
        
    return {
        'dataset': dataset,
        'training_result': training_result,
        'model_manager': model_manager,
        'model_id': model_id
    }

if __name__ == "__main__":
    demo_ml_training()