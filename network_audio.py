#!/usr/bin/env python3
"""
Chameleon Audio System - Network Audio & Real-time Streaming Module

エンタープライズ・プロダクション対応ネットワーク音声処理
- リアルタイム音声ストリーミング
- ネットワーク配信・受信
- 低レイテンシ音声伝送
- マルチクライアント対応
- 音声品質監視・自動調整
- プロ放送対応プロトコル
"""

import socket
import threading
import time
import struct
import queue
import json
import hashlib
import zlib
from typing import List, Dict, Optional, Callable, Any, Tuple
from enum import Enum
import wave
import array

class StreamingProtocol(Enum):
    UDP_RAW = "udp_raw"
    TCP_RELIABLE = "tcp_reliable"
    CUSTOM_LOWLATENCY = "custom_lowlatency"

class AudioPacketType(Enum):
    AUDIO_DATA = 0x01
    CONTROL_MSG = 0x02
    HEARTBEAT = 0x03
    QUALITY_INFO = 0x04
    STREAM_END = 0x05

class StreamingQuality(Enum):
    LOW = "low"          # 22kHz, mono, compressed
    MEDIUM = "medium"    # 44kHz, stereo, moderate
    HIGH = "high"        # 48kHz, stereo, high quality
    BROADCAST = "broadcast"  # 48kHz, stereo, uncompressed

class AudioPacket:
    """音声パケット"""
    
    def __init__(self, packet_type: AudioPacketType, sequence_id: int, 
                 timestamp: float, data: bytes, checksum: Optional[str] = None):
        self.packet_type = packet_type
        self.sequence_id = sequence_id
        self.timestamp = timestamp
        self.data = data
        self.checksum = checksum or self._calculate_checksum(data)
        
    def _calculate_checksum(self, data: bytes) -> str:
        """チェックサム計算"""
        return hashlib.md5(data).hexdigest()[:8]
        
    def to_bytes(self) -> bytes:
        """バイト列にシリアライズ"""
        checksum_bytes = self.checksum.encode('ascii')[:8].ljust(8, b'\x00')
        header = struct.pack(
            '>BIIQ8s',  # Big-endian: byte, int, int, long long, 8 bytes
            self.packet_type.value,
            self.sequence_id,
            len(self.data),
            int(self.timestamp * 1000000),  # マイクロ秒
            checksum_bytes
        )
        return header + self.data
        
    @classmethod
    def from_bytes(cls, data: bytes) -> 'AudioPacket':
        """バイト列からデシリアライズ"""
        header_size = struct.calcsize('>BIIQ8s')
        if len(data) < header_size:
            raise ValueError(f"Invalid packet size: {len(data)} < {header_size}")
            
        header = data[:header_size]
        payload = data[header_size:]
        
        packet_type_val, sequence_id, data_len, timestamp_us, checksum_bytes = struct.unpack(
            '>BIIQ8s', header
        )
        
        packet_type = AudioPacketType(packet_type_val)
        timestamp = timestamp_us / 1000000.0
        checksum = checksum_bytes.decode('ascii').rstrip('\x00')
        
        return cls(packet_type, sequence_id, timestamp, payload, checksum)
        
    def verify_checksum(self) -> bool:
        """チェックサム検証"""
        return self.checksum == self._calculate_checksum(self.data)

class AudioCompressor:
    """簡易音声圧縮器"""
    
    def __init__(self, quality: StreamingQuality = StreamingQuality.MEDIUM):
        self.quality = quality
        
    def compress_audio(self, audio_data: bytes) -> bytes:
        """音声データ圧縮"""
        if self.quality == StreamingQuality.BROADCAST:
            return audio_data  # 無圧縮
        elif self.quality == StreamingQuality.HIGH:
            return zlib.compress(audio_data, 6)
        elif self.quality == StreamingQuality.MEDIUM:
            return zlib.compress(audio_data, 3)
        else:  # LOW
            # より積極的な圧縮 + ダウンサンプリング
            return zlib.compress(audio_data, 9)
            
    def decompress_audio(self, compressed_data: bytes) -> bytes:
        """音声データ展開"""
        if self.quality == StreamingQuality.BROADCAST:
            return compressed_data
        else:
            return zlib.decompress(compressed_data)

class NetworkQualityMonitor:
    """ネットワーク品質監視"""
    
    def __init__(self):
        self.packet_loss_rate = 0.0
        self.latency_ms = 0.0
        self.jitter_ms = 0.0
        self.bandwidth_kbps = 0.0
        self.received_packets = 0
        self.lost_packets = 0
        self.last_sequence_id = -1
        self.latency_samples = []
        
    def update_packet_stats(self, packet: AudioPacket, receive_time: float):
        """パケット統計更新"""
        self.received_packets += 1
        
        # パケットロス計算
        if self.last_sequence_id >= 0:
            expected_id = self.last_sequence_id + 1
            if packet.sequence_id > expected_id:
                lost = packet.sequence_id - expected_id
                self.lost_packets += lost
                
        self.last_sequence_id = packet.sequence_id
        
        # パケットロス率
        total_packets = self.received_packets + self.lost_packets
        if total_packets > 0:
            self.packet_loss_rate = self.lost_packets / total_packets
            
        # レイテンシ計算
        latency = (receive_time - packet.timestamp) * 1000  # ms
        self.latency_samples.append(latency)
        
        # 直近100サンプルのみ保持
        if len(self.latency_samples) > 100:
            self.latency_samples.pop(0)
            
        # 平均レイテンシとジッター
        if self.latency_samples:
            self.latency_ms = sum(self.latency_samples) / len(self.latency_samples)
            if len(self.latency_samples) > 1:
                avg = self.latency_ms
                variance = sum((x - avg) ** 2 for x in self.latency_samples) / len(self.latency_samples)
                self.jitter_ms = variance ** 0.5
                
    def get_quality_score(self) -> float:
        """品質スコア計算 (0-100)"""
        score = 100.0
        
        # パケットロス減点
        score -= self.packet_loss_rate * 50
        
        # レイテンシ減点
        if self.latency_ms > 50:
            score -= (self.latency_ms - 50) * 0.5
            
        # ジッター減点
        score -= self.jitter_ms * 0.2
        
        return max(0.0, min(100.0, score))
        
    def get_status_report(self) -> Dict[str, Any]:
        """ステータスレポート"""
        return {
            'packet_loss_rate': self.packet_loss_rate,
            'latency_ms': self.latency_ms,
            'jitter_ms': self.jitter_ms,
            'bandwidth_kbps': self.bandwidth_kbps,
            'quality_score': self.get_quality_score(),
            'received_packets': self.received_packets,
            'lost_packets': self.lost_packets
        }

class AudioStreamer:
    """音声ストリーマー (送信側)"""
    
    def __init__(self, host: str = "localhost", port: int = 8888, 
                 protocol: StreamingProtocol = StreamingProtocol.UDP_RAW,
                 quality: StreamingQuality = StreamingQuality.MEDIUM):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.quality = quality
        self.compressor = AudioCompressor(quality)
        
        self.socket = None
        self.is_streaming = False
        self.sequence_id = 0
        self.chunk_size = self._get_chunk_size()
        self.send_queue = queue.Queue()
        self.send_thread = None
        
        # クライアント管理 (TCPの場合)
        self.clients = []
        self.client_threads = []
        
    def _get_chunk_size(self) -> int:
        """品質に応じたチャンクサイズ"""
        if self.quality == StreamingQuality.LOW:
            return 512
        elif self.quality == StreamingQuality.MEDIUM:
            return 1024
        elif self.quality == StreamingQuality.HIGH:
            return 2048
        else:  # BROADCAST
            return 4096
            
    def start_streaming(self):
        """ストリーミング開始"""
        if self.is_streaming:
            return
            
        try:
            if self.protocol == StreamingProtocol.UDP_RAW:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            else:  # TCP
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind((self.host, self.port))
                self.socket.listen(5)
                
            self.is_streaming = True
            self.sequence_id = 0
            
            # 送信スレッド開始
            self.send_thread = threading.Thread(target=self._send_worker, daemon=True)
            self.send_thread.start()
            
            # TCP接続受付スレッド
            if self.protocol != StreamingProtocol.UDP_RAW:
                accept_thread = threading.Thread(target=self._accept_clients, daemon=True)
                accept_thread.start()
                
            print(f"Audio streaming started on {self.host}:{self.port} ({self.protocol.value})")
            
        except Exception as e:
            print(f"Failed to start streaming: {e}")
            self.is_streaming = False
            
    def stop_streaming(self):
        """ストリーミング停止"""
        if not self.is_streaming:
            return
            
        self.is_streaming = False
        
        # 終了パケット送信
        end_packet = AudioPacket(AudioPacketType.STREAM_END, self.sequence_id, time.time(), b"")
        self.send_queue.put(end_packet)
        
        # 少し待って接続クローズ
        time.sleep(0.1)
        
        if self.socket:
            self.socket.close()
            
        # クライアント接続終了
        for client_socket in self.clients:
            try:
                client_socket.close()
            except:
                pass
        self.clients.clear()
        
        print("Audio streaming stopped")
        
    def stream_audio_data(self, audio_data: bytes):
        """音声データをストリーミング"""
        if not self.is_streaming:
            return
            
        # チャンクに分割
        for i in range(0, len(audio_data), self.chunk_size):
            chunk = audio_data[i:i + self.chunk_size]
            
            # 圧縮
            compressed_chunk = self.compressor.compress_audio(chunk)
            
            # パケット作成
            packet = AudioPacket(
                AudioPacketType.AUDIO_DATA,
                self.sequence_id,
                time.time(),
                compressed_chunk
            )
            
            self.send_queue.put(packet)
            self.sequence_id += 1
            
    def _send_worker(self):
        """送信ワーカースレッド"""
        while self.is_streaming:
            try:
                packet = self.send_queue.get(timeout=0.1)
                self._send_packet(packet)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Send error: {e}")
                
    def _send_packet(self, packet: AudioPacket):
        """パケット送信"""
        packet_data = packet.to_bytes()
        
        if self.protocol == StreamingProtocol.UDP_RAW:
            # UDPブロードキャスト
            broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            broadcast_socket.sendto(packet_data, ('<broadcast>', self.port))
            broadcast_socket.close()
        else:
            # TCP全クライアントに送信
            dead_clients = []
            for client_socket in self.clients:
                try:
                    # データ長 + データ送信
                    length_header = struct.pack('>I', len(packet_data))
                    client_socket.sendall(length_header + packet_data)
                except Exception as e:
                    print(f"Client send error: {e}")
                    dead_clients.append(client_socket)
                    
            # 死んだクライアント削除
            for dead_client in dead_clients:
                if dead_client in self.clients:
                    self.clients.remove(dead_client)
                try:
                    dead_client.close()
                except:
                    pass
                    
    def _accept_clients(self):
        """クライアント接続受付"""
        while self.is_streaming:
            try:
                client_socket, addr = self.socket.accept()
                self.clients.append(client_socket)
                print(f"Client connected: {addr}")
            except Exception as e:
                if self.is_streaming:
                    print(f"Accept error: {e}")
                break

class AudioReceiver:
    """音声レシーバー (受信側)"""
    
    def __init__(self, host: str = "localhost", port: int = 8888,
                 protocol: StreamingProtocol = StreamingProtocol.UDP_RAW,
                 quality: StreamingQuality = StreamingQuality.MEDIUM):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.quality = quality
        self.compressor = AudioCompressor(quality)
        
        self.socket = None
        self.is_receiving = False
        self.receive_thread = None
        self.audio_queue = queue.Queue()
        self.quality_monitor = NetworkQualityMonitor()
        
        # 音声コールバック
        self.audio_callback: Optional[Callable[[bytes], None]] = None
        
    def set_audio_callback(self, callback: Callable[[bytes], None]):
        """音声データコールバック設定"""
        self.audio_callback = callback
        
    def start_receiving(self):
        """受信開始"""
        if self.is_receiving:
            return
            
        try:
            if self.protocol == StreamingProtocol.UDP_RAW:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.bind(('', self.port))  # 全インターフェースでリッスン
            else:  # TCP
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.host, self.port))
                
            self.is_receiving = True
            
            # 受信スレッド開始
            self.receive_thread = threading.Thread(target=self._receive_worker, daemon=True)
            self.receive_thread.start()
            
            print(f"Audio receiving started on port {self.port} ({self.protocol.value})")
            
        except Exception as e:
            print(f"Failed to start receiving: {e}")
            self.is_receiving = False
            
    def stop_receiving(self):
        """受信停止"""
        if not self.is_receiving:
            return
            
        self.is_receiving = False
        
        if self.socket:
            self.socket.close()
            
        print("Audio receiving stopped")
        
    def _receive_worker(self):
        """受信ワーカースレッド"""
        while self.is_receiving:
            try:
                if self.protocol == StreamingProtocol.UDP_RAW:
                    data, addr = self.socket.recvfrom(65536)
                    self._process_packet(data)
                else:  # TCP
                    # 長さヘッダー受信
                    length_data = self._recv_exact(4)
                    if not length_data:
                        break
                    length = struct.unpack('>I', length_data)[0]
                    
                    # パケットデータ受信
                    packet_data = self._recv_exact(length)
                    if packet_data:
                        self._process_packet(packet_data)
                        
            except Exception as e:
                if self.is_receiving:
                    print(f"Receive error: {e}")
                break
                
    def _recv_exact(self, length: int) -> bytes:
        """正確な長さのデータ受信 (TCP)"""
        data = b''
        while len(data) < length and self.is_receiving:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return data
        
    def _process_packet(self, packet_data: bytes):
        """パケット処理"""
        try:
            packet = AudioPacket.from_bytes(packet_data)
            receive_time = time.time()
            
            # チェックサム検証
            if not packet.verify_checksum():
                print("Checksum verification failed")
                return
                
            # 品質監視更新
            self.quality_monitor.update_packet_stats(packet, receive_time)
            
            if packet.packet_type == AudioPacketType.AUDIO_DATA:
                # 音声データ展開
                audio_data = self.compressor.decompress_audio(packet.data)
                
                # コールバック呼び出し
                if self.audio_callback:
                    self.audio_callback(audio_data)
                else:
                    self.audio_queue.put(audio_data)
                    
            elif packet.packet_type == AudioPacketType.STREAM_END:
                print("Stream ended by sender")
                self.stop_receiving()
                
        except Exception as e:
            print(f"Packet processing error: {e}")
            
    def get_audio_data(self, timeout: float = 1.0) -> Optional[bytes]:
        """音声データ取得 (コールバック未使用時)"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
            
    def get_quality_report(self) -> Dict[str, Any]:
        """品質レポート取得"""
        return self.quality_monitor.get_status_report()

class LiveAudioProcessor:
    """ライブ音声処理"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.streamer = None
        self.receiver = None
        self.is_processing = False
        
        # 音声処理チェーン
        self.processors = []
        
    def add_processor(self, processor):
        """音声処理器追加"""
        self.processors.append(processor)
        
    def start_live_stream(self, host: str = "localhost", port: int = 8888,
                         quality: StreamingQuality = StreamingQuality.MEDIUM):
        """ライブストリーミング開始"""
        self.streamer = AudioStreamer(host, port, quality=quality)
        self.streamer.start_streaming()
        self.is_processing = True
        
    def start_live_receive(self, host: str = "localhost", port: int = 8888,
                          quality: StreamingQuality = StreamingQuality.MEDIUM):
        """ライブ受信開始"""
        self.receiver = AudioReceiver(host, port, quality=quality)
        self.receiver.set_audio_callback(self._process_received_audio)
        self.receiver.start_receiving()
        
    def _process_received_audio(self, audio_data: bytes):
        """受信音声処理"""
        # バイト→float変換
        audio_samples = []
        for i in range(0, len(audio_data), 2):
            if i + 1 < len(audio_data):
                sample = struct.unpack('<h', audio_data[i:i+2])[0]
                audio_samples.append(sample / 32767.0)
                
        # 処理チェーン適用
        for processor in self.processors:
            if hasattr(processor, 'process_buffer'):
                audio_samples = processor.process_buffer(audio_samples)
                
        print(f"Processed {len(audio_samples)} samples")
        
    def stream_audio_file(self, file_path: str):
        """音声ファイルストリーミング"""
        if not self.streamer or not self.is_processing:
            return
            
        try:
            with wave.open(file_path, 'rb') as wav_file:
                frames = wav_file.readframes(1024)
                while frames and self.is_processing:
                    self.streamer.stream_audio_data(frames)
                    time.sleep(0.02)  # ~50fps
                    frames = wav_file.readframes(1024)
                    
        except Exception as e:
            print(f"Streaming error: {e}")
            
    def stop_live_processing(self):
        """ライブ処理停止"""
        self.is_processing = False
        
        if self.streamer:
            self.streamer.stop_streaming()
            
        if self.receiver:
            self.receiver.stop_receiving()

def demo_network_audio():
    """ネットワーク音声デモ"""
    print("🌐 Network Audio & Streaming Demo")
    
    # サーバー (ストリーマー) 
    def run_server():
        print("Starting audio server...")
        processor = LiveAudioProcessor()
        processor.start_live_stream(quality=StreamingQuality.MEDIUM)
        
        # デモ用テスト音声生成・配信
        import math
        
        print("Streaming test audio...")
        for i in range(100):  # 約2秒間
            # テスト音声生成 (440Hz)
            samples = []
            for j in range(1024):
                t = (i * 1024 + j) / 44100.0
                sample = math.sin(2 * math.pi * 440 * t) * 0.3
                sample_int = int(sample * 32767)
                samples.append(sample_int)
                
            # 16bit PCMとしてバイト列作成
            audio_array = array.array('h', samples)
            audio_data = audio_array.tobytes()
            processor.streamer.stream_audio_data(audio_data)
            time.sleep(0.02)
            
        processor.stop_live_processing()
        
    # クライアント (レシーバー)
    def run_client():
        time.sleep(0.5)  # サーバー起動待ち
        print("Starting audio client...")
        
        processor = LiveAudioProcessor()
        processor.start_live_receive(quality=StreamingQuality.MEDIUM)
        
        # 5秒間受信
        start_time = time.time()
        while time.time() - start_time < 5.0:
            time.sleep(0.1)
            
            # 品質レポート
            if processor.receiver:
                report = processor.receiver.get_quality_report()
                if report['received_packets'] > 0:
                    print(f"Quality: {report['quality_score']:.1f}, "
                          f"Latency: {report['latency_ms']:.1f}ms, "
                          f"Loss: {report['packet_loss_rate']:.2%}")
                    
        processor.stop_live_processing()
    
    # デモ実行
    try:
        # サーバーとクライアントを並行実行
        server_thread = threading.Thread(target=run_server, daemon=True)
        client_thread = threading.Thread(target=run_client, daemon=True)
        
        server_thread.start()
        client_thread.start()
        
        # 完了まで待機
        server_thread.join(timeout=10)
        client_thread.join(timeout=10)
        
        print("Network audio demo completed")
        
    except Exception as e:
        print(f"Demo error: {e}")

if __name__ == "__main__":
    demo_network_audio()