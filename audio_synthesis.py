#!/usr/bin/env python3
"""
Chameleon Audio System - Audio Synthesis and Generation Module

プロフェッショナル音声合成・生成ツール
- オシレーター (正弦波、のこぎり波、矩形波、三角波、ノイズ)
- エンベロープ制御 (ADSR)
- LFO (低周波発振器)
- シンセサイザー (減算合成、FM合成、加算合成)
- ドラムマシン・リズムパターン
- シーケンサー・楽曲生成
"""

import struct
import wave
import math
import random
import array
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum
import json

class WaveformType(Enum):
    SINE = "sine"
    SAWTOOTH = "sawtooth"
    SQUARE = "square"
    TRIANGLE = "triangle"
    NOISE = "noise"

class FilterType(Enum):
    LOWPASS = "lowpass"
    HIGHPASS = "highpass"
    BANDPASS = "bandpass"

class Oscillator:
    """基本オシレーター - 各種波形生成"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.phase = 0.0
        self.frequency = 440.0
        self.amplitude = 1.0
        self.waveform = WaveformType.SINE
        
    def set_frequency(self, frequency: float):
        """周波数設定"""
        self.frequency = max(20.0, min(20000.0, frequency))
        
    def set_amplitude(self, amplitude: float):
        """振幅設定"""
        self.amplitude = max(0.0, min(1.0, amplitude))
        
    def set_waveform(self, waveform: WaveformType):
        """波形タイプ設定"""
        self.waveform = waveform
        
    def generate_sample(self) -> float:
        """単一サンプル生成"""
        if self.waveform == WaveformType.SINE:
            sample = math.sin(2 * math.pi * self.phase)
        elif self.waveform == WaveformType.SAWTOOTH:
            sample = 2 * (self.phase - math.floor(self.phase + 0.5))
        elif self.waveform == WaveformType.SQUARE:
            sample = 1.0 if self.phase % 1.0 < 0.5 else -1.0
        elif self.waveform == WaveformType.TRIANGLE:
            p = self.phase % 1.0
            sample = 4 * abs(p - 0.5) - 1
        elif self.waveform == WaveformType.NOISE:
            sample = random.uniform(-1.0, 1.0)
        else:
            sample = 0.0
            
        # フェーズ更新
        self.phase += self.frequency / self.sample_rate
        if self.phase >= 1.0:
            self.phase -= 1.0
            
        return sample * self.amplitude

class ADSR:
    """ADSR エンベロープ (Attack, Decay, Sustain, Release)"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.attack_time = 0.1   # 秒
        self.decay_time = 0.1    # 秒
        self.sustain_level = 0.7 # 0.0-1.0
        self.release_time = 0.3  # 秒
        
        self.phase = "off"  # off, attack, decay, sustain, release
        self.current_level = 0.0
        self.samples_in_phase = 0
        
    def note_on(self):
        """ノートオン - エンベロープ開始"""
        self.phase = "attack"
        self.samples_in_phase = 0
        
    def note_off(self):
        """ノートオフ - リリース開始"""
        if self.phase != "off":
            self.phase = "release"
            self.samples_in_phase = 0
            
    def get_level(self) -> float:
        """現在のエンベロープレベル取得"""
        if self.phase == "off":
            return 0.0
            
        elif self.phase == "attack":
            attack_samples = int(self.attack_time * self.sample_rate)
            if self.samples_in_phase < attack_samples:
                self.current_level = self.samples_in_phase / attack_samples
            else:
                self.current_level = 1.0
                self.phase = "decay"
                self.samples_in_phase = 0
                
        elif self.phase == "decay":
            decay_samples = int(self.decay_time * self.sample_rate)
            if self.samples_in_phase < decay_samples:
                progress = self.samples_in_phase / decay_samples
                self.current_level = 1.0 - progress * (1.0 - self.sustain_level)
            else:
                self.current_level = self.sustain_level
                self.phase = "sustain"
                self.samples_in_phase = 0
                
        elif self.phase == "sustain":
            self.current_level = self.sustain_level
            
        elif self.phase == "release":
            release_samples = int(self.release_time * self.sample_rate)
            if self.samples_in_phase < release_samples:
                progress = self.samples_in_phase / release_samples
                self.current_level = self.sustain_level * (1.0 - progress)
            else:
                self.current_level = 0.0
                self.phase = "off"
                self.samples_in_phase = 0
                
        self.samples_in_phase += 1
        return self.current_level

class LFO:
    """LFO (Low Frequency Oscillator) - 低周波発振器"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.frequency = 1.0  # Hz
        self.amplitude = 1.0
        self.waveform = WaveformType.SINE
        self.phase = 0.0
        
    def set_frequency(self, frequency: float):
        """LFO周波数設定 (通常0.1-20Hz)"""
        self.frequency = max(0.01, min(50.0, frequency))
        
    def get_value(self) -> float:
        """LFO値取得 (-amplitude ~ +amplitude)"""
        if self.waveform == WaveformType.SINE:
            value = math.sin(2 * math.pi * self.phase)
        elif self.waveform == WaveformType.TRIANGLE:
            p = self.phase % 1.0
            value = 4 * abs(p - 0.5) - 1
        elif self.waveform == WaveformType.SAWTOOTH:
            value = 2 * (self.phase - math.floor(self.phase + 0.5))
        elif self.waveform == WaveformType.SQUARE:
            value = 1.0 if self.phase % 1.0 < 0.5 else -1.0
        else:
            value = 0.0
            
        self.phase += self.frequency / self.sample_rate
        if self.phase >= 1.0:
            self.phase -= 1.0
            
        return value * self.amplitude

class SimpleFilter:
    """シンプルなデジタルフィルター"""
    
    def __init__(self, filter_type: FilterType = FilterType.LOWPASS):
        self.filter_type = filter_type
        self.cutoff = 1000.0  # Hz
        self.resonance = 1.0
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0
        
    def set_cutoff(self, cutoff: float):
        """カットオフ周波数設定"""
        self.cutoff = max(20.0, min(20000.0, cutoff))
        
    def process_sample(self, input_sample: float, sample_rate: int) -> float:
        """フィルター処理"""
        # 簡易IIRフィルター実装
        omega = 2 * math.pi * self.cutoff / sample_rate
        sin_omega = math.sin(omega)
        cos_omega = math.cos(omega)
        
        alpha = sin_omega / (2 * self.resonance)
        
        if self.filter_type == FilterType.LOWPASS:
            b0 = (1 - cos_omega) / 2
            b1 = 1 - cos_omega
            b2 = (1 - cos_omega) / 2
            a0 = 1 + alpha
            a1 = -2 * cos_omega
            a2 = 1 - alpha
        elif self.filter_type == FilterType.HIGHPASS:
            b0 = (1 + cos_omega) / 2
            b1 = -(1 + cos_omega)
            b2 = (1 + cos_omega) / 2
            a0 = 1 + alpha
            a1 = -2 * cos_omega
            a2 = 1 - alpha
        else:  # BANDPASS
            b0 = alpha
            b1 = 0
            b2 = -alpha
            a0 = 1 + alpha
            a1 = -2 * cos_omega
            a2 = 1 - alpha
            
        # 係数正規化
        b0 /= a0
        b1 /= a0
        b2 /= a0
        a1 /= a0
        a2 /= a0
        
        # フィルター計算
        output = b0 * input_sample + b1 * self.x1 + b2 * self.x2 - a1 * self.y1 - a2 * self.y2
        
        # 遅延要素更新
        self.x2 = self.x1
        self.x1 = input_sample
        self.y2 = self.y1
        self.y1 = output
        
        return output

class SubtractiveSynth:
    """減算合成シンセサイザー"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.oscillator1 = Oscillator(sample_rate)
        self.oscillator2 = Oscillator(sample_rate)
        self.filter = SimpleFilter(FilterType.LOWPASS)
        self.envelope = ADSR(sample_rate)
        self.lfo = LFO(sample_rate)
        
        # パラメータ
        self.osc1_level = 0.7
        self.osc2_level = 0.3
        self.osc2_detune = 0.0  # セント
        self.filter_envelope_amount = 0.5
        self.lfo_to_pitch = 0.0
        self.lfo_to_filter = 0.0
        
    def note_on(self, frequency: float, velocity: float = 1.0):
        """ノートオン"""
        self.oscillator1.set_frequency(frequency)
        self.oscillator2.set_frequency(frequency * (2 ** (self.osc2_detune / 1200)))
        self.oscillator1.set_amplitude(velocity * self.osc1_level)
        self.oscillator2.set_amplitude(velocity * self.osc2_level)
        self.envelope.note_on()
        
    def note_off(self):
        """ノートオフ"""
        self.envelope.note_off()
        
    def generate_sample(self) -> float:
        """サンプル生成"""
        # LFO値取得
        lfo_value = self.lfo.get_value()
        
        # ピッチモジュレーション
        if self.lfo_to_pitch > 0:
            pitch_mod = 1.0 + (lfo_value * self.lfo_to_pitch * 0.1)
            current_freq1 = self.oscillator1.frequency * pitch_mod
            current_freq2 = self.oscillator2.frequency * pitch_mod
            self.oscillator1.set_frequency(current_freq1)
            self.oscillator2.set_frequency(current_freq2)
        
        # オシレーター出力
        osc1_out = self.oscillator1.generate_sample()
        osc2_out = self.oscillator2.generate_sample()
        mixed = osc1_out + osc2_out
        
        # フィルター処理
        envelope_level = self.envelope.get_level()
        filter_mod = self.filter_envelope_amount * envelope_level
        if self.lfo_to_filter > 0:
            filter_mod += lfo_value * self.lfo_to_filter * 0.3
        
        filter_cutoff = self.filter.cutoff * (1.0 + filter_mod)
        self.filter.set_cutoff(filter_cutoff)
        filtered = self.filter.process_sample(mixed, self.sample_rate)
        
        # エンベロープ適用
        return filtered * envelope_level

class FMSynth:
    """FM合成シンセサイザー"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.carrier = Oscillator(sample_rate)
        self.modulator = Oscillator(sample_rate)
        self.envelope = ADSR(sample_rate)
        
        # FMパラメータ
        self.fm_ratio = 2.0     # モジュレーター周波数比
        self.fm_depth = 1.0     # FM深度
        
    def note_on(self, frequency: float, velocity: float = 1.0):
        """ノートオン"""
        self.carrier.set_frequency(frequency)
        self.modulator.set_frequency(frequency * self.fm_ratio)
        self.carrier.set_amplitude(velocity)
        self.envelope.note_on()
        
    def note_off(self):
        """ノートオフ"""
        self.envelope.note_off()
        
    def generate_sample(self) -> float:
        """FM合成サンプル生成"""
        # モジュレーター出力
        mod_out = self.modulator.generate_sample()
        
        # キャリア周波数をモジュレート
        modulated_freq = self.carrier.frequency * (1.0 + mod_out * self.fm_depth)
        self.carrier.set_frequency(modulated_freq)
        
        # キャリア出力
        carrier_out = self.carrier.generate_sample()
        
        # エンベロープ適用
        envelope_level = self.envelope.get_level()
        return carrier_out * envelope_level

class DrumMachine:
    """ドラムマシン - リズムパターン生成"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.patterns = {
            "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
            "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "hihat": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
            "openhat": [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1]
        }
        self.bpm = 120
        self.current_step = 0
        self.samples_per_step = 0
        self.step_counter = 0
        self.update_timing()
        
    def update_timing(self):
        """タイミング更新"""
        steps_per_second = (self.bpm / 60) * 4  # 16分音符
        self.samples_per_step = int(self.sample_rate / steps_per_second)
        
    def set_bpm(self, bpm: int):
        """BPM設定"""
        self.bpm = max(60, min(200, bpm))
        self.update_timing()
        
    def set_pattern(self, drum: str, pattern: List[int]):
        """パターン設定"""
        if drum in self.patterns:
            self.patterns[drum] = pattern[:16]  # 最大16ステップ
            
    def generate_drum_sound(self, drum_type: str) -> float:
        """ドラム音色生成"""
        if drum_type == "kick":
            # キック: 低周波ノイズ + 短いエンベロープ
            freq = 60 + random.uniform(-10, 10)
            return math.sin(2 * math.pi * freq * self.step_counter / self.sample_rate) * \
                   max(0, 1 - self.step_counter / (self.samples_per_step * 0.3))
        elif drum_type == "snare":
            # スネア: ホワイトノイズ + 短いエンベロープ
            noise = random.uniform(-1, 1)
            tone = math.sin(2 * math.pi * 200 * self.step_counter / self.sample_rate)
            envelope = max(0, 1 - self.step_counter / (self.samples_per_step * 0.2))
            return (noise * 0.7 + tone * 0.3) * envelope
        elif drum_type == "hihat":
            # ハイハット: 高周波ノイズ + 短いエンベロープ
            noise = random.uniform(-1, 1)
            envelope = max(0, 1 - self.step_counter / (self.samples_per_step * 0.1))
            return noise * envelope * 0.3
        elif drum_type == "openhat":
            # オープンハイハット: 高周波ノイズ + 長いエンベロープ
            noise = random.uniform(-1, 1)
            envelope = max(0, 1 - self.step_counter / (self.samples_per_step * 0.5))
            return noise * envelope * 0.5
        return 0.0
        
    def generate_sample(self) -> float:
        """ドラムマシンサンプル生成"""
        output = 0.0
        
        # 現在のステップでアクティブなドラムをチェック
        for drum, pattern in self.patterns.items():
            if pattern[self.current_step]:
                output += self.generate_drum_sound(drum)
                
        # ステップ進行
        self.step_counter += 1
        if self.step_counter >= self.samples_per_step:
            self.step_counter = 0
            self.current_step = (self.current_step + 1) % 16
            
        return max(-1.0, min(1.0, output))

class AudioSynthesizer:
    """統合音声合成システム"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.subtractive_synth = SubtractiveSynth(sample_rate)
        self.fm_synth = FMSynth(sample_rate)
        self.drum_machine = DrumMachine(sample_rate)
        
    def generate_tone(self, frequency: float, duration: float, 
                     waveform: WaveformType = WaveformType.SINE,
                     amplitude: float = 0.5) -> List[float]:
        """基本トーン生成"""
        samples = int(duration * self.sample_rate)
        audio = [0.0] * samples
        
        osc = Oscillator(self.sample_rate)
        osc.set_frequency(frequency)
        osc.set_amplitude(amplitude)
        osc.set_waveform(waveform)
        
        envelope = ADSR(self.sample_rate)
        envelope.attack_time = 0.1
        envelope.release_time = 0.2
        envelope.note_on()
        
        for i in range(samples):
            if i > samples - int(0.2 * self.sample_rate):
                if envelope.phase != "release":
                    envelope.note_off()
            
            sample = osc.generate_sample()
            env_level = envelope.get_level()
            audio[i] = sample * env_level
            
        return audio
        
    def generate_chord(self, frequencies: List[float], duration: float,
                      waveform: WaveformType = WaveformType.SINE,
                      amplitude: float = 0.3) -> List[float]:
        """コード生成"""
        samples = int(duration * self.sample_rate)
        audio = [0.0] * samples
        
        # 各音程を生成して合成
        for freq in frequencies:
            tone = self.generate_tone(freq, duration, waveform, amplitude)
            for i in range(min(len(audio), len(tone))):
                audio[i] += tone[i]
                
        # 正規化
        for i in range(len(audio)):
            audio[i] = max(-1.0, min(1.0, audio[i]))
        return audio
        
    def generate_arpeggio(self, frequencies: List[float], duration: float,
                         note_duration: float = 0.25) -> List[float]:
        """アルペジオ生成"""
        total_samples = int(duration * self.sample_rate)
        audio = [0.0] * total_samples
        
        note_samples = int(note_duration * self.sample_rate)
        pos = 0
        
        while pos < total_samples:
            for freq in frequencies:
                if pos >= total_samples:
                    break
                    
                tone = self.generate_tone(freq, note_duration, amplitude=0.4)
                end_pos = min(pos + note_samples, total_samples)
                copy_len = end_pos - pos
                for i in range(copy_len):
                    if i < len(tone):
                        audio[pos + i] = tone[i]
                pos += note_samples
                
        return audio
        
    def generate_sequence(self, sequence: List[Dict], total_duration: float) -> List[float]:
        """音楽シーケンス生成"""
        samples = int(total_duration * self.sample_rate)
        audio = [0.0] * samples
        
        for note_data in sequence:
            start_time = note_data.get('start', 0.0)
            duration = note_data.get('duration', 0.5)
            frequency = note_data.get('frequency', 440.0)
            synth_type = note_data.get('synth', 'subtractive')
            velocity = note_data.get('velocity', 0.7)
            
            start_sample = int(start_time * self.sample_rate)
            note_samples = int(duration * self.sample_rate)
            
            if start_sample >= samples:
                continue
                
            # シンセタイプに応じて音を生成
            if synth_type == 'subtractive':
                self.subtractive_synth.note_on(frequency, velocity)
                for i in range(note_samples):
                    if start_sample + i >= samples:
                        break
                    sample = self.subtractive_synth.generate_sample()
                    audio[start_sample + i] += sample
                self.subtractive_synth.note_off()
                
            elif synth_type == 'fm':
                self.fm_synth.note_on(frequency, velocity)
                for i in range(note_samples):
                    if start_sample + i >= samples:
                        break
                    sample = self.fm_synth.generate_sample()
                    audio[start_sample + i] += sample
                self.fm_synth.note_off()
                
        # クリッピング
        for i in range(len(audio)):
            audio[i] = max(-1.0, min(1.0, audio[i]))
        return audio
        
    def generate_drum_pattern(self, duration: float, bpm: int = 120,
                            patterns: Optional[Dict] = None) -> List[float]:
        """ドラムパターン生成"""
        samples = int(duration * self.sample_rate)
        audio = [0.0] * samples
        
        self.drum_machine.set_bpm(bpm)
        if patterns:
            for drum, pattern in patterns.items():
                self.drum_machine.set_pattern(drum, pattern)
                
        for i in range(samples):
            audio[i] = self.drum_machine.generate_sample()
            
        return audio
        
    def save_audio(self, audio_data: List[float], filename: str):
        """音声ファイル保存"""
        # 16bit整数に変換
        audio_int = [int(max(-32767, min(32767, sample * 32767))) for sample in audio_data]
        
        # array.arrayを使用してバイトデータに変換
        audio_array = array.array('h', audio_int)  # 'h' = signed short (16bit)
        
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)  # モノラル
            wav_file.setsampwidth(2)  # 16bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_array.tobytes())

def demo_synthesis():
    """シンセサイザーデモ"""
    synth = AudioSynthesizer()
    
    print("🎵 Audio Synthesis Demo")
    
    # 基本トーン生成
    print("Basic tone generation...")
    tone_sine = synth.generate_tone(440.0, 2.0, WaveformType.SINE)
    tone_saw = synth.generate_tone(440.0, 2.0, WaveformType.SAWTOOTH)
    
    # コード生成 (Cメジャー)
    print("Chord generation...")
    c_major = [261.63, 329.63, 392.00]  # C, E, G
    chord = synth.generate_chord(c_major, 3.0)
    
    # アルペジオ生成
    print("Arpeggio generation...")
    arpeggio = synth.generate_arpeggio(c_major, 4.0)
    
    # ドラムパターン
    print("Drum pattern generation...")
    drums = synth.generate_drum_pattern(8.0, bpm=120)
    
    # シーケンス生成
    print("Musical sequence generation...")
    sequence = [
        {'start': 0.0, 'duration': 0.5, 'frequency': 261.63, 'synth': 'subtractive'},
        {'start': 0.5, 'duration': 0.5, 'frequency': 329.63, 'synth': 'subtractive'},
        {'start': 1.0, 'duration': 0.5, 'frequency': 392.00, 'synth': 'fm'},
        {'start': 1.5, 'duration': 1.0, 'frequency': 523.25, 'synth': 'fm'},
    ]
    music = synth.generate_sequence(sequence, 4.0)
    
    return {
        'tone_sine': tone_sine,
        'tone_saw': tone_saw,
        'chord': chord,
        'arpeggio': arpeggio,
        'drums': drums,
        'music': music
    }

if __name__ == "__main__":
    demo_synthesis()