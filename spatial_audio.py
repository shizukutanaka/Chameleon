#!/usr/bin/env python3
"""
Chameleon Audio System - Spatial Audio and 3D Processing Module

プロフェッショナル空間音声・3D音響処理
- バイノーラル録音・再生
- HRTF (Head-Related Transfer Function)
- 3Dポジショニング・パニング
- アンビソニックス (Ambisonics)
- リバーブ・エコー空間効果
- バーチャルスピーカー配置
"""

import math
import struct
import wave
import array
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum

class SpatialMode(Enum):
    STEREO = "stereo"
    BINAURAL = "binaural"
    SURROUND_5_1 = "surround_5_1"
    SURROUND_7_1 = "surround_7_1"
    AMBISONICS = "ambisonics"

class Position3D:
    """3D空間座標"""
    
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        self.x = x  # 左右 (-1.0 ~ 1.0)
        self.y = y  # 前後 (-1.0 ~ 1.0)
        self.z = z  # 上下 (-1.0 ~ 1.0)
        
    def distance_to(self, other: 'Position3D') -> float:
        """距離計算"""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx*dx + dy*dy + dz*dz)
        
    def angle_to(self, other: 'Position3D') -> float:
        """角度計算 (ラジアン)"""
        dx = other.x - self.x
        dy = other.y - self.y
        return math.atan2(dy, dx)

class SimpleHRTF:
    """簡易HRTF (Head-Related Transfer Function)"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        
    def get_delays(self, azimuth: float) -> Tuple[float, float]:
        """左右耳の遅延時間計算"""
        # 簡易モデル: 頭部半径約8.75cm
        head_radius = 0.0875  # meters
        sound_speed = 343.0   # m/s
        
        # 角度による遅延差計算
        max_delay = head_radius / sound_speed
        delay_factor = math.sin(azimuth)
        
        left_delay = max_delay * (1 + delay_factor) * 0.5
        right_delay = max_delay * (1 - delay_factor) * 0.5
        
        return left_delay, right_delay
        
    def get_gains(self, azimuth: float, elevation: float = 0.0) -> Tuple[float, float]:
        """左右耳のゲイン計算"""
        # 簡易頭部遮蔽モデル
        azimuth_normalized = azimuth / math.pi  # -1 to 1
        
        # 左耳ゲイン
        if azimuth_normalized < 0:
            left_gain = 1.0 + azimuth_normalized * 0.3
        else:
            left_gain = 1.0 - azimuth_normalized * 0.7
            
        # 右耳ゲイン
        if azimuth_normalized > 0:
            right_gain = 1.0 - azimuth_normalized * 0.3
        else:
            right_gain = 1.0 + azimuth_normalized * 0.7
            
        # 仰角による減衰
        elevation_factor = math.cos(elevation)
        left_gain *= elevation_factor
        right_gain *= elevation_factor
        
        return max(0.0, min(1.0, left_gain)), max(0.0, min(1.0, right_gain))

class DelayLine:
    """遅延ライン"""
    
    def __init__(self, max_delay_samples: int):
        self.buffer = [0.0] * max_delay_samples
        self.write_pos = 0
        self.max_delay = max_delay_samples
        
    def write_sample(self, sample: float):
        """サンプル書き込み"""
        self.buffer[self.write_pos] = sample
        self.write_pos = (self.write_pos + 1) % self.max_delay
        
    def read_sample(self, delay_samples: int) -> float:
        """遅延サンプル読み出し"""
        delay_samples = max(0, min(self.max_delay - 1, delay_samples))
        read_pos = (self.write_pos - delay_samples - 1) % self.max_delay
        return self.buffer[read_pos]

class SpatialPanner:
    """空間パナー"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.hrtf = SimpleHRTF(sample_rate)
        
        # 遅延ライン (最大10ms)
        max_delay_samples = int(0.01 * sample_rate)
        self.left_delay = DelayLine(max_delay_samples)
        self.right_delay = DelayLine(max_delay_samples)
        
    def pan_sample(self, input_sample: float, position: Position3D, 
                   listener_pos: Position3D = Position3D()) -> Tuple[float, float]:
        """サンプルの空間パニング"""
        # 相対位置計算
        rel_x = position.x - listener_pos.x
        rel_y = position.y - listener_pos.y
        rel_z = position.z - listener_pos.z
        
        # 極座標変換
        distance = math.sqrt(rel_x*rel_x + rel_y*rel_y + rel_z*rel_z)
        if distance < 0.001:
            distance = 0.001
            
        azimuth = math.atan2(rel_y, rel_x)
        elevation = math.atan2(rel_z, math.sqrt(rel_x*rel_x + rel_y*rel_y))
        
        # 距離による減衰
        distance_gain = 1.0 / (1.0 + distance * 2.0)
        
        # HRTF適用
        left_delay_time, right_delay_time = self.hrtf.get_delays(azimuth)
        left_gain, right_gain = self.hrtf.get_gains(azimuth, elevation)
        
        # 遅延サンプル数計算
        left_delay_samples = int(left_delay_time * self.sample_rate)
        right_delay_samples = int(right_delay_time * self.sample_rate)
        
        # 遅延ライン処理
        self.left_delay.write_sample(input_sample)
        self.right_delay.write_sample(input_sample)
        
        left_output = self.left_delay.read_sample(left_delay_samples) * left_gain * distance_gain
        right_output = self.right_delay.read_sample(right_delay_samples) * right_gain * distance_gain
        
        return left_output, right_output

class ReverbProcessor:
    """空間リバーブ処理"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        
        # コムフィルター (並列)
        self.comb_delays = [
            DelayLine(int(0.0297 * sample_rate)),  # 29.7ms
            DelayLine(int(0.0371 * sample_rate)),  # 37.1ms
            DelayLine(int(0.0411 * sample_rate)),  # 41.1ms
            DelayLine(int(0.0437 * sample_rate)),  # 43.7ms
        ]
        self.comb_gains = [0.773, 0.802, 0.753, 0.733]
        
        # オールパスフィルター (直列)
        self.allpass_delays = [
            DelayLine(int(0.0050 * sample_rate)),  # 5.0ms
            DelayLine(int(0.0017 * sample_rate)),  # 1.7ms
        ]
        self.allpass_gains = [0.7, 0.5]
        
        self.wet_level = 0.3
        self.decay = 0.5
        
    def process_sample(self, input_sample: float) -> float:
        """リバーブ処理"""
        # コムフィルター処理 (並列)
        comb_output = 0.0
        for i, (delay_line, gain) in enumerate(zip(self.comb_delays, self.comb_gains)):
            delayed = delay_line.read_sample(delay_line.max_delay - 1)
            feedback = delayed * gain * self.decay
            delay_line.write_sample(input_sample + feedback)
            comb_output += delayed
            
        comb_output /= len(self.comb_delays)
        
        # オールパスフィルター処理 (直列)
        allpass_input = comb_output
        for delay_line, gain in zip(self.allpass_delays, self.allpass_gains):
            delayed = delay_line.read_sample(delay_line.max_delay - 1)
            output = -gain * allpass_input + delayed
            delay_line.write_sample(allpass_input + gain * delayed)
            allpass_input = output
            
        # ウェット/ドライミックス
        return input_sample * (1.0 - self.wet_level) + allpass_input * self.wet_level

class AmbisonicsEncoder:
    """アンビソニックス・エンコーダー"""
    
    def __init__(self, order: int = 1):
        self.order = order
        self.num_channels = (order + 1) ** 2  # 1次: 4ch, 2次: 9ch, 3次: 16ch
        
    def encode_position(self, position: Position3D) -> List[float]:
        """位置をアンビソニックス信号にエンコード"""
        # 球面座標変換
        x, y, z = position.x, position.y, position.z
        distance = math.sqrt(x*x + y*y + z*z)
        if distance < 0.001:
            distance = 0.001
            
        azimuth = math.atan2(y, x)
        elevation = math.atan2(z, math.sqrt(x*x + y*y))
        
        # 1次アンビソニックス (B-format)
        if self.order >= 1:
            w = 1.0 / math.sqrt(2)  # W (無指向性)
            x_ch = math.cos(elevation) * math.cos(azimuth)  # X (前後)
            y_ch = math.cos(elevation) * math.sin(azimuth)  # Y (左右)
            z_ch = math.sin(elevation)  # Z (上下)
            
            channels = [w, x_ch, y_ch, z_ch]
            
        # より高次の実装は省略 (2次, 3次...)
        
        return channels[:self.num_channels]

class SpatialAudioProcessor:
    """統合空間音声処理システム"""
    
    def __init__(self, sample_rate: int = 44100, mode: SpatialMode = SpatialMode.BINAURAL):
        self.sample_rate = sample_rate
        self.mode = mode
        self.panner = SpatialPanner(sample_rate)
        self.reverb = ReverbProcessor(sample_rate)
        self.ambisonics = AmbisonicsEncoder(order=1)
        
        # バーチャルスピーカー配置 (5.1サラウンド)
        self.speaker_positions = {
            'front_left': Position3D(-0.5, 1.0, 0.0),
            'front_right': Position3D(0.5, 1.0, 0.0),
            'center': Position3D(0.0, 1.0, 0.0),
            'lfe': Position3D(0.0, 0.0, -0.5),  # Low Frequency Effects
            'rear_left': Position3D(-0.5, -1.0, 0.0),
            'rear_right': Position3D(0.5, -1.0, 0.0),
        }
        
    def process_positioned_audio(self, audio_data, 
                                position: Position3D,
                                listener_pos: Position3D = Position3D()) -> Tuple[List[float], List[float]]:
        """位置指定音声処理"""
        # bytes型の場合はfloatリストに変換
        if isinstance(audio_data, bytes):
            # 16bit PCMと仮定して変換
            audio_list = []
            for i in range(0, len(audio_data), 2):
                if i + 1 < len(audio_data):
                    sample = struct.unpack('<h', audio_data[i:i+2])[0]
                    audio_list.append(sample / 32767.0)
            audio_data = audio_list
        
        left_output = [0.0] * len(audio_data)
        right_output = [0.0] * len(audio_data)
        
        for i, sample in enumerate(audio_data):
            # 空間パニング
            left_sample, right_sample = self.panner.pan_sample(sample, position, listener_pos)
            
            # リバーブ適用
            left_reverb = self.reverb.process_sample(left_sample)
            right_reverb = self.reverb.process_sample(right_sample)
            
            left_output[i] = left_reverb
            right_output[i] = right_reverb
            
        return left_output, right_output
        
    def create_surround_mix(self, sources: Dict[str, Tuple[List[float], Position3D]]) -> Dict[str, List[float]]:
        """サラウンドミックス作成"""
        if not sources:
            return {}
            
        # 出力チャンネル数決定
        if self.mode == SpatialMode.STEREO:
            channels = ['left', 'right']
        elif self.mode == SpatialMode.SURROUND_5_1:
            channels = ['front_left', 'front_right', 'center', 'lfe', 'rear_left', 'rear_right']
        elif self.mode == SpatialMode.SURROUND_7_1:
            channels = ['front_left', 'front_right', 'center', 'lfe', 
                       'side_left', 'side_right', 'rear_left', 'rear_right']
        else:
            channels = ['left', 'right']  # デフォルト
            
        # サンプル数決定
        max_samples = max(len(audio) for audio, _ in sources.values())
        
        # 出力チャンネル初期化
        output_channels = {ch: [0.0] * max_samples for ch in channels}
        
        # 各ソースを処理
        for source_name, (audio_data, position) in sources.items():
            if self.mode == SpatialMode.STEREO or self.mode == SpatialMode.BINAURAL:
                # ステレオ/バイノーラル処理
                left, right = self.process_positioned_audio(audio_data, position)
                
                for i in range(len(audio_data)):
                    if i < max_samples:
                        output_channels['left'][i] += left[i] if 'left' in output_channels else left[i]
                        output_channels['right'][i] += right[i] if 'right' in output_channels else right[i]
                        
            else:
                # サラウンド処理 - 各スピーカーへの距離ベースパニング
                for i, sample in enumerate(audio_data):
                    if i >= max_samples:
                        break
                        
                    for speaker_name, speaker_pos in self.speaker_positions.items():
                        if speaker_name in output_channels:
                            # スピーカーまでの距離計算
                            distance = position.distance_to(speaker_pos)
                            gain = 1.0 / (1.0 + distance * 3.0)  # 距離減衰
                            
                            # 角度による減衰
                            angle = position.angle_to(speaker_pos)
                            angle_gain = (math.cos(angle) + 1.0) * 0.5
                            
                            final_gain = gain * angle_gain
                            output_channels[speaker_name][i] += sample * final_gain
                            
        return output_channels
        
    def apply_room_simulation(self, audio_data, 
                             room_size: float = 10.0,
                             damping: float = 0.3) -> List[float]:
        """ルームシミュレーション"""
        # bytes型の場合はfloatリストに変換
        if isinstance(audio_data, bytes):
            # 16bit PCMと仮定して変換
            audio_list = []
            for i in range(0, len(audio_data), 2):
                if i + 1 < len(audio_data):
                    sample = struct.unpack('<h', audio_data[i:i+2])[0]
                    audio_list.append(sample / 32767.0)
            audio_data = audio_list
        
        # ルームサイズに基づく遅延時間
        delay_time = room_size / 343.0  # 音速
        delay_samples = int(delay_time * self.sample_rate)
        
        if delay_samples > len(audio_data):
            delay_samples = len(audio_data) // 2
            
        output = audio_data[:]  # リスト作成
        
        # 初期反射音追加
        for i in range(delay_samples, len(audio_data)):
            reflection_gain = (1.0 - damping) * 0.3
            output[i] += audio_data[i - delay_samples] * reflection_gain
            
        # 後期残響 (簡易)
        for i in range(len(output)):
            output[i] = self.reverb.process_sample(output[i])
            
        return output
        
    def save_multichannel_audio(self, channels: Dict[str, List[float]], filename: str):
        """マルチチャンネル音声保存"""
        if not channels:
            return
            
        # チャンネル数とサンプル数決定
        channel_names = list(channels.keys())
        num_channels = len(channel_names)
        num_samples = len(channels[channel_names[0]])
        
        # インターリーブ形式でデータ作成
        interleaved_data = []
        for i in range(num_samples):
            for ch_name in channel_names:
                if i < len(channels[ch_name]):
                    sample = int(max(-32767, min(32767, channels[ch_name][i] * 32767)))
                    interleaved_data.append(sample)
                else:
                    interleaved_data.append(0)
                    
        # array.arrayを使用
        audio_array = array.array('h', interleaved_data)
        
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(num_channels)
            wav_file.setsampwidth(2)  # 16bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_array.tobytes())

def demo_spatial_audio():
    """空間音声デモ"""
    processor = SpatialAudioProcessor(mode=SpatialMode.BINAURAL)
    
    print("🎵 Spatial Audio Demo")
    
    # テスト音源生成 (440Hz正弦波)
    duration = 3.0
    samples = int(duration * processor.sample_rate)
    frequency = 440.0
    
    test_audio = []
    for i in range(samples):
        t = i / processor.sample_rate
        sample = math.sin(2 * math.pi * frequency * t) * 0.5
        # エンベロープ適用
        envelope = math.exp(-t * 2.0)  # 減衰
        test_audio.append(sample * envelope)
    
    # 様々な位置でテスト
    positions = {
        'center': Position3D(0.0, 0.0, 0.0),
        'left': Position3D(-1.0, 0.0, 0.0),
        'right': Position3D(1.0, 0.0, 0.0),
        'front': Position3D(0.0, 1.0, 0.0),
        'back': Position3D(0.0, -1.0, 0.0),
        'above': Position3D(0.0, 0.0, 1.0),
        'moving': Position3D(0.0, 0.0, 0.0)  # 動的位置
    }
    
    results = {}
    
    for pos_name, position in positions.items():
        print(f"Processing position: {pos_name}")
        
        if pos_name == 'moving':
            # 移動する音源
            left_output = [0.0] * samples
            right_output = [0.0] * samples
            
            for i, sample in enumerate(test_audio):
                # 円運動
                t = i / processor.sample_rate
                angle = t * math.pi  # 半円
                pos = Position3D(math.cos(angle), math.sin(angle), 0.0)
                
                left_sample, right_sample = processor.panner.pan_sample(sample, pos)
                left_output[i] = left_sample
                right_output[i] = right_sample
                
        else:
            # 固定位置
            left_output, right_output = processor.process_positioned_audio(test_audio, position)
        
        results[pos_name] = (left_output, right_output)
    
    # サラウンドミックスデモ
    print("Creating surround mix...")
    sources = {
        'lead': (test_audio, Position3D(0.0, 1.0, 0.0)),    # 前方中央
        'bass': (test_audio, Position3D(0.0, 0.0, -0.5)),   # 下方 (LFE的)
        'ambient': (test_audio, Position3D(-0.5, -0.5, 0.2)) # 左後上方
    }
    
    processor.mode = SpatialMode.SURROUND_5_1
    surround_mix = processor.create_surround_mix(sources)
    
    # ルームシミュレーション
    print("Applying room simulation...")
    room_audio = processor.apply_room_simulation(test_audio, room_size=15.0, damping=0.4)
    
    return {
        'positioned': results,
        'surround': surround_mix,
        'room': room_audio
    }

if __name__ == "__main__":
    demo_spatial_audio()