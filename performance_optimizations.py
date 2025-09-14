#!/usr/bin/env python3
"""
Chameleon Audio System - Performance Optimization Module

パフォーマンス最適化機能
- メモリ効率化
- CPU負荷軽減
- キャッシュ最適化
- 並列処理
- プロファイリング
"""

import time
import gc
import threading
import multiprocessing
import functools
from typing import Any, Dict, List, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import weakref

class MemoryPool:
    """メモリプール管理"""
    
    def __init__(self, initial_size: int = 1024 * 1024):
        self.pools = {}
        self.lock = threading.Lock()
        self.stats = {
            'allocated': 0,
            'reused': 0,
            'cache_hits': 0
        }
        
    def get_buffer(self, size: int, dtype: str = 'float') -> List[float]:
        """バッファ取得（再利用）"""
        with self.lock:
            pool_key = f"{dtype}_{size}"
            
            if pool_key in self.pools and self.pools[pool_key]:
                buffer = self.pools[pool_key].pop()
                self.stats['reused'] += 1
                self.stats['cache_hits'] += 1
                return buffer
                
            # 新規作成
            if dtype == 'float':
                buffer = [0.0] * size
            elif dtype == 'int':
                buffer = [0] * size
            else:
                buffer = [0.0] * size
                
            self.stats['allocated'] += 1
            return buffer
            
    def return_buffer(self, buffer: List, dtype: str = 'float'):
        """バッファ返却"""
        if not buffer:
            return
            
        with self.lock:
            size = len(buffer)
            pool_key = f"{dtype}_{size}"
            
            if pool_key not in self.pools:
                self.pools[pool_key] = []
                
            # プールサイズ制限
            if len(self.pools[pool_key]) < 10:
                # バッファクリア
                if dtype == 'float':
                    for i in range(len(buffer)):
                        buffer[i] = 0.0
                else:
                    for i in range(len(buffer)):
                        buffer[i] = 0
                        
                self.pools[pool_key].append(buffer)
                
    def clear_pools(self):
        """プールクリア"""
        with self.lock:
            self.pools.clear()
            gc.collect()

class SmartCache:
    """スマートキャッシュシステム"""
    
    def __init__(self, max_size: int = 100, ttl: float = 300.0):
        self.cache = {}
        self.access_times = {}
        self.creation_times = {}
        self.max_size = max_size
        self.ttl = ttl
        self.lock = threading.Lock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
    def get(self, key: str) -> Optional[Any]:
        """キャッシュ取得"""
        with self.lock:
            current_time = time.time()
            
            if key in self.cache:
                # TTLチェック
                if current_time - self.creation_times[key] > self.ttl:
                    self._evict_key(key)
                    self.stats['misses'] += 1
                    return None
                    
                # アクセス時間更新
                self.access_times[key] = current_time
                self.stats['hits'] += 1
                return self.cache[key]
                
            self.stats['misses'] += 1
            return None
            
    def set(self, key: str, value: Any):
        """キャッシュ設定"""
        with self.lock:
            current_time = time.time()
            
            # 容量チェック
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_lru()
                
            self.cache[key] = value
            self.access_times[key] = current_time
            self.creation_times[key] = current_time
            
    def _evict_key(self, key: str):
        """キー削除"""
        if key in self.cache:
            del self.cache[key]
            del self.access_times[key]
            del self.creation_times[key]
            self.stats['evictions'] += 1
            
    def _evict_lru(self):
        """LRU削除"""
        if not self.access_times:
            return
            
        lru_key = min(self.access_times.keys(), 
                     key=lambda k: self.access_times[k])
        self._evict_key(lru_key)
        
    def clear(self):
        """キャッシュクリア"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.creation_times.clear()

class ParallelProcessor:
    """並列処理マネージャー"""
    
    def __init__(self, max_workers: Optional[int] = None):
        self.cpu_count = multiprocessing.cpu_count()
        self.max_workers = max_workers or min(4, self.cpu_count)
        self.thread_pool = None
        self.process_pool = None
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        
    def shutdown(self):
        """プール終了"""
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
            self.thread_pool = None
            
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
            self.process_pool = None
            
    def map_threads(self, func: Callable, iterable, chunk_size: int = 1):
        """スレッド並列マップ"""
        if self.thread_pool is None:
            self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
            
        # チャンクサイズ調整
        items = list(iterable)
        if len(items) < chunk_size:
            chunk_size = len(items)
            
        return self.thread_pool.map(func, items)
        
    def map_processes(self, func: Callable, iterable, chunk_size: int = 1):
        """プロセス並列マップ"""
        if self.process_pool is None:
            self.process_pool = ProcessPoolExecutor(max_workers=self.max_workers)
            
        items = list(iterable)
        if len(items) < chunk_size:
            chunk_size = len(items)
            
        return self.process_pool.map(func, items, chunksize=chunk_size)
        
    def process_audio_parallel(self, audio_data: List[float], 
                              processor_func: Callable,
                              chunk_size: int = 4096) -> List[float]:
        """音声データ並列処理"""
        if len(audio_data) < chunk_size * 2:
            # 小さなデータはシーケンシャル処理
            return processor_func(audio_data)
            
        # チャンク分割
        chunks = []
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            if chunk:  # 空チャンク避け
                chunks.append(chunk)
                
        # 並列処理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            processed_chunks = list(executor.map(processor_func, chunks))
            
        # 結合
        result = []
        for chunk in processed_chunks:
            result.extend(chunk)
            
        return result

class PerformanceProfiler:
    """パフォーマンスプロファイラー"""
    
    def __init__(self):
        self.timers = {}
        self.memory_usage = {}
        self.call_counts = {}
        self.lock = threading.Lock()
        
    def start_timer(self, name: str):
        """タイマー開始"""
        with self.lock:
            self.timers[name] = time.perf_counter()
            
    def stop_timer(self, name: str) -> float:
        """タイマー停止"""
        with self.lock:
            if name not in self.timers:
                return 0.0
                
            duration = time.perf_counter() - self.timers[name]
            del self.timers[name]
            
            # 統計更新
            if name not in self.call_counts:
                self.call_counts[name] = {'total_time': 0.0, 'calls': 0}
                
            self.call_counts[name]['total_time'] += duration
            self.call_counts[name]['calls'] += 1
            
            return duration
            
    def get_stats(self) -> Dict[str, Dict]:
        """統計取得"""
        with self.lock:
            stats = {}
            for name, data in self.call_counts.items():
                stats[name] = {
                    'total_time': data['total_time'],
                    'calls': data['calls'],
                    'avg_time': data['total_time'] / data['calls'] if data['calls'] > 0 else 0.0
                }
            return stats
            
    def clear_stats(self):
        """統計クリア"""
        with self.lock:
            self.timers.clear()
            self.call_counts.clear()

def timed(profiler: PerformanceProfiler = None):
    """タイマーデコレータ"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            timer_name = func.__name__
            
            if profiler:
                profiler.start_timer(timer_name)
                
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                if profiler:
                    profiler.stop_timer(timer_name)
                    
        return wrapper
    return decorator

def memoize(maxsize: int = 128, ttl: float = 300.0):
    """メモ化デコレータ"""
    def decorator(func):
        cache = SmartCache(max_size=maxsize, ttl=ttl)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # キー生成
            key = f"{func.__name__}_{hash(args)}_{hash(tuple(sorted(kwargs.items())))}"
            
            # キャッシュチェック
            result = cache.get(key)
            if result is not None:
                return result
                
            # 関数実行
            result = func(*args, **kwargs)
            cache.set(key, result)
            
            return result
            
        wrapper.cache = cache
        return wrapper
    return decorator

class OptimizedAudioProcessor:
    """最適化された音声プロセッサー"""
    
    def __init__(self):
        self.memory_pool = MemoryPool()
        self.cache = SmartCache(max_size=50)
        self.profiler = PerformanceProfiler()
        self.parallel_processor = ParallelProcessor()
        
    @timed()
    @memoize(maxsize=32, ttl=600.0)
    def process_with_optimization(self, audio_data: List[float], 
                                 effect_type: str,
                                 parameters: Dict[str, Any]) -> List[float]:
        """最適化処理"""
        # メモリプール使用
        buffer = self.memory_pool.get_buffer(len(audio_data))
        
        try:
            if effect_type == "reverb":
                return self._apply_reverb_optimized(audio_data, parameters, buffer)
            elif effect_type == "delay":
                return self._apply_delay_optimized(audio_data, parameters, buffer)
            else:
                return audio_data.copy()
                
        finally:
            # バッファ返却
            self.memory_pool.return_buffer(buffer)
            
    def _apply_reverb_optimized(self, audio_data: List[float], 
                               parameters: Dict[str, Any],
                               buffer: List[float]) -> List[float]:
        """最適化リバーブ"""
        room_size = parameters.get('room_size', 0.5)
        damping = parameters.get('damping', 0.3)
        
        # 並列処理で効果適用
        def reverb_chunk(chunk):
            result = []
            for i, sample in enumerate(chunk):
                # 簡易リバーブ計算
                delayed_sample = sample * room_size * (1 - damping)
                result.append(sample + delayed_sample * 0.3)
            return result
            
        return self.parallel_processor.process_audio_parallel(
            audio_data, reverb_chunk, chunk_size=2048
        )
        
    def _apply_delay_optimized(self, audio_data: List[float],
                              parameters: Dict[str, Any],
                              buffer: List[float]) -> List[float]:
        """最適化ディレイ"""
        delay_time = parameters.get('delay_time', 0.3)
        feedback = parameters.get('feedback', 0.4)
        
        delay_samples = int(delay_time * 44100)  # 44.1kHz想定
        
        # インプレース処理で高速化
        result = audio_data.copy()
        
        for i in range(delay_samples, len(result)):
            delayed = result[i - delay_samples] * feedback
            result[i] += delayed
            
        return result
        
    def get_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポート"""
        return {
            'profiler_stats': self.profiler.get_stats(),
            'memory_stats': self.memory_pool.stats,
            'cache_stats': self.cache.stats,
            'cpu_count': self.parallel_processor.cpu_count,
            'max_workers': self.parallel_processor.max_workers
        }
        
    def cleanup(self):
        """クリーンアップ"""
        self.memory_pool.clear_pools()
        self.cache.clear()
        self.profiler.clear_stats()
        self.parallel_processor.shutdown()

# グローバル最適化プロセッサー
_global_processor = None

def get_optimized_processor() -> OptimizedAudioProcessor:
    """グローバル最適化プロセッサー取得"""
    global _global_processor
    if _global_processor is None:
        _global_processor = OptimizedAudioProcessor()
    return _global_processor

def optimize_memory_usage():
    """メモリ使用量最適化"""
    # ガベージコレクション強制実行
    gc.collect()
    
    # グローバルプロセッサークリーンアップ
    processor = get_optimized_processor()
    processor.cleanup()

if __name__ == "__main__":
    # テスト用
    processor = OptimizedAudioProcessor()
    
    # テストデータ
    test_audio = [0.5 * i / 1000 for i in range(1000)]
    
    # 最適化処理テスト
    start_time = time.time()
    
    result1 = processor.process_with_optimization(
        test_audio, "reverb", {"room_size": 0.7, "damping": 0.4}
    )
    
    result2 = processor.process_with_optimization(
        test_audio, "delay", {"delay_time": 0.2, "feedback": 0.5}
    )
    
    end_time = time.time()
    
    print(f"Processing time: {end_time - start_time:.4f}s")
    print("Performance report:")
    report = processor.get_performance_report()
    
    for category, stats in report.items():
        print(f"  {category}: {stats}")
        
    processor.cleanup()