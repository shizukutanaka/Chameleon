#!/usr/bin/env python3
"""
Performance Enhancer - 高度なパフォーマンス最適化
メモリ使用量削減、並列処理最適化、キャッシュ改善
"""

import time
import threading
import weakref
import gc
import sys
from typing import Dict, Any, Optional, List, Callable, Union, Generator
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps, lru_cache
from collections import deque, defaultdict
import concurrent.futures
import asyncio
import queue

# Import error handling
try:
    from robust_error_handler import (
        with_error_handling, get_error_handler,
        ErrorSeverity, ErrorCategory
    )
    ERROR_HANDLING_AVAILABLE = True
except ImportError:
    def with_error_handling(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    ERROR_HANDLING_AVAILABLE = False

class OptimizationLevel(Enum):
    """最適化レベル"""
    BASIC = "basic"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    MAXIMUM = "maximum"

class MemoryStrategy(Enum):
    """メモリ最適化戦略"""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"

@dataclass
class PerformanceProfile:
    """パフォーマンスプロファイル"""
    cpu_bound: bool = False
    io_bound: bool = True
    memory_intensive: bool = False
    cache_friendly: bool = True
    parallel_safe: bool = True
    optimization_level: OptimizationLevel = OptimizationLevel.MODERATE

class MemoryOptimizer:
    """メモリ使用量最適化"""
    
    def __init__(self, strategy: MemoryStrategy = MemoryStrategy.BALANCED):
        self.strategy = strategy
        self.weak_refs = weakref.WeakValueDictionary()
        self.object_pools = {}
        self.memory_stats = {
            'allocations': 0,
            'deallocations': 0,
            'pool_hits': 0,
            'pool_misses': 0
        }
        
    def get_object_from_pool(self, object_type: str, factory: Callable):
        """オブジェクトプールから取得"""
        if object_type not in self.object_pools:
            self.object_pools[object_type] = queue.Queue(maxsize=100)
        
        pool = self.object_pools[object_type]
        
        try:
            obj = pool.get_nowait()
            self.memory_stats['pool_hits'] += 1
            return obj
        except queue.Empty:
            self.memory_stats['pool_misses'] += 1
            obj = factory()
            self.memory_stats['allocations'] += 1
            return obj
    
    def return_object_to_pool(self, object_type: str, obj: Any):
        """オブジェクトプールに返却"""
        if object_type in self.object_pools:
            pool = self.object_pools[object_type]
            
            try:
                # オブジェクトをリセット（可能な場合）
                if hasattr(obj, 'reset'):
                    obj.reset()
                elif hasattr(obj, 'clear'):
                    obj.clear()
                
                pool.put_nowait(obj)
            except queue.Full:
                # プールが満杯の場合は単純に破棄
                self.memory_stats['deallocations'] += 1
    
    def create_generator_from_list(self, data: List[Any]) -> Generator[Any, None, None]:
        """リストをジェネレーターに変換してメモリを節約"""
        for item in data:
            yield item
    
    def batch_process_generator(self, generator: Generator, 
                              batch_size: int = 1000) -> Generator[List[Any], None, None]:
        """ジェネレーターをバッチ処理"""
        batch = []
        for item in generator:
            batch.append(item)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        if batch:
            yield batch
    
    def force_gc_collection(self):
        """強制ガベージコレクション"""
        if self.strategy in [MemoryStrategy.AGGRESSIVE]:
            collected = gc.collect()
            return collected
        return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """メモリ使用量情報"""
        return {
            'stats': self.memory_stats.copy(),
            'pool_sizes': {
                obj_type: pool.qsize() 
                for obj_type, pool in self.object_pools.items()
            },
            'weak_refs_count': len(self.weak_refs),
            'gc_stats': gc.get_stats() if hasattr(gc, 'get_stats') else {}
        }

class ParallelProcessingOptimizer:
    """並列処理最適化"""
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_pool = None  # 必要時に初期化
        self.task_stats = defaultdict(int)
        
    def optimize_for_task_type(self, profile: PerformanceProfile) -> concurrent.futures.Executor:
        """タスクタイプに最適化されたエグゼキューター選択"""
        if profile.cpu_bound:
            if not self.process_pool:
                self.process_pool = concurrent.futures.ProcessPoolExecutor(
                    max_workers=min(self.max_workers, os.cpu_count() or 1)
                )
            return self.process_pool
        else:
            return self.thread_pool
    
    def parallel_map(self, func: Callable, 
                    iterable: List[Any],
                    profile: PerformanceProfile,
                    chunk_size: Optional[int] = None) -> List[Any]:
        """並列マッピング処理"""
        executor = self.optimize_for_task_type(profile)
        
        if chunk_size:
            # チャンク化して処理
            chunks = [iterable[i:i + chunk_size] 
                     for i in range(0, len(iterable), chunk_size)]
            
            def process_chunk(chunk):
                return [func(item) for item in chunk]
            
            results = list(executor.map(process_chunk, chunks))
            # フラット化
            return [item for chunk_result in results for item in chunk_result]
        else:
            return list(executor.map(func, iterable))
    
    def parallel_reduce(self, func: Callable, 
                       iterable: List[Any],
                       initializer=None,
                       profile: PerformanceProfile) -> Any:
        """並列リダクション処理"""
        if not iterable:
            return initializer
        
        # 分割統治法を使用
        def reduce_chunk(chunk):
            result = initializer
            for item in chunk:
                result = func(result, item)
            return result
        
        chunk_size = max(1, len(iterable) // self.max_workers)
        chunks = [iterable[i:i + chunk_size] 
                 for i in range(0, len(iterable), chunk_size)]
        
        executor = self.optimize_for_task_type(profile)
        chunk_results = list(executor.map(reduce_chunk, chunks))
        
        # 最終的な結果をまとめる
        final_result = initializer
        for chunk_result in chunk_results:
            final_result = func(final_result, chunk_result)
        
        return final_result
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """処理統計取得"""
        return {
            'max_workers': self.max_workers,
            'task_stats': dict(self.task_stats),
            'thread_pool_active': self.thread_pool._threads if hasattr(self.thread_pool, '_threads') else 0,
            'process_pool_active': bool(self.process_pool)
        }

class CacheOptimizer:
    """キャッシュ最適化"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.hit_stats = defaultdict(int)
        self.miss_stats = defaultdict(int)
        self.custom_caches = {}
        
    def adaptive_lru_cache(self, maxsize: Optional[int] = None, 
                          ttl: Optional[float] = None):
        """適応的LRUキャッシュデコレーター"""
        def decorator(func):
            # TTL対応キャッシュ
            if ttl:
                cache = {}
                cache_times = {}
                
                @wraps(func)
                def wrapper(*args, **kwargs):
                    key = str(args) + str(sorted(kwargs.items()))
                    current_time = time.time()
                    
                    # TTLチェック
                    if key in cache and key in cache_times:
                        if current_time - cache_times[key] < ttl:
                            self.hit_stats[func.__name__] += 1
                            return cache[key]
                        else:
                            # 期限切れエントリを削除
                            del cache[key]
                            del cache_times[key]
                    
                    # キャッシュミス
                    self.miss_stats[func.__name__] += 1
                    result = func(*args, **kwargs)
                    
                    # キャッシュサイズ管理
                    if len(cache) >= (maxsize or self.max_size):
                        # 最も古いエントリを削除
                        oldest_key = min(cache_times.items(), key=lambda x: x[1])[0]
                        del cache[oldest_key]
                        del cache_times[oldest_key]
                    
                    cache[key] = result
                    cache_times[key] = current_time
                    return result
                
                return wrapper
            else:
                # 標準LRUキャッシュ
                cached_func = lru_cache(maxsize=maxsize or self.max_size)(func)
                
                @wraps(func)
                def wrapper(*args, **kwargs):
                    try:
                        result = cached_func(*args, **kwargs)
                        self.hit_stats[func.__name__] += 1
                        return result
                    except TypeError:
                        # キャッシュできない引数の場合
                        self.miss_stats[func.__name__] += 1
                        return func(*args, **kwargs)
                
                return wrapper
        
        return decorator
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """キャッシュ統計"""
        total_hits = sum(self.hit_stats.values())
        total_misses = sum(self.miss_stats.values())
        total_requests = total_hits + total_misses
        
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_hits': total_hits,
            'total_misses': total_misses,
            'hit_rate_percent': hit_rate,
            'function_stats': {
                func_name: {
                    'hits': self.hit_stats[func_name],
                    'misses': self.miss_stats[func_name],
                    'hit_rate': (self.hit_stats[func_name] / 
                               (self.hit_stats[func_name] + self.miss_stats[func_name]) * 100)
                    if (self.hit_stats[func_name] + self.miss_stats[func_name]) > 0 else 0
                }
                for func_name in set(list(self.hit_stats.keys()) + list(self.miss_stats.keys()))
            }
        }

class PerformanceEnhancer:
    """統合パフォーマンス最適化システム"""
    
    def __init__(self, optimization_level: OptimizationLevel = OptimizationLevel.MODERATE):
        self.optimization_level = optimization_level
        
        # 各種最適化コンポーネント
        memory_strategy = {
            OptimizationLevel.BASIC: MemoryStrategy.CONSERVATIVE,
            OptimizationLevel.MODERATE: MemoryStrategy.BALANCED,
            OptimizationLevel.AGGRESSIVE: MemoryStrategy.AGGRESSIVE,
            OptimizationLevel.MAXIMUM: MemoryStrategy.AGGRESSIVE
        }[optimization_level]
        
        self.memory_optimizer = MemoryOptimizer(memory_strategy)
        self.parallel_optimizer = ParallelProcessingOptimizer()
        self.cache_optimizer = CacheOptimizer()
        
        # パフォーマンス監視
        self.performance_history = deque(maxlen=1000)
        self.optimization_applied = []
        
        if ERROR_HANDLING_AVAILABLE:
            self.error_handler = get_error_handler("PerformanceEnhancer")
    
    @with_error_handling("PerformanceEnhancer",
                        category=ErrorCategory.PERFORMANCE,
                        severity=ErrorSeverity.WARNING)
    def optimize_function(self, profile: PerformanceProfile):
        """関数最適化デコレーター"""
        def decorator(func):
            # キャッシュ最適化
            if profile.cache_friendly:
                func = self.cache_optimizer.adaptive_lru_cache(
                    maxsize=1000 if self.optimization_level == OptimizationLevel.MAXIMUM else 100
                )(func)
            
            # 並列処理最適化
            if profile.parallel_safe and hasattr(func, '__call__'):
                original_func = func
                
                @wraps(func)
                def parallel_wrapper(*args, **kwargs):
                    # 引数がリストで大量データの場合は並列処理
                    for arg in args:
                        if isinstance(arg, list) and len(arg) > 100:
                            return self.parallel_optimizer.parallel_map(
                                lambda item: original_func(item, **kwargs),
                                arg,
                                profile
                            )
                    
                    return original_func(*args, **kwargs)
                
                func = parallel_wrapper
            
            # メモリ最適化
            if profile.memory_intensive:
                original_func = func
                
                @wraps(func)
                def memory_wrapper(*args, **kwargs):
                    # 実行前にガベージコレクション
                    if self.optimization_level == OptimizationLevel.MAXIMUM:
                        self.memory_optimizer.force_gc_collection()
                    
                    result = original_func(*args, **kwargs)
                    
                    # 実行後にもガベージコレクション（アグレッシブモード）
                    if self.optimization_level == OptimizationLevel.AGGRESSIVE:
                        self.memory_optimizer.force_gc_collection()
                    
                    return result
                
                func = memory_wrapper
            
            # パフォーマンス測定
            @wraps(func)
            def performance_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                start_memory = sys.getsizeof(args) + sys.getsizeof(kwargs)
                
                try:
                    result = func(*args, **kwargs)
                    
                    end_time = time.perf_counter()
                    execution_time = end_time - start_time
                    end_memory = sys.getsizeof(result) if result else 0
                    
                    # パフォーマンス記録
                    perf_record = {
                        'function': func.__name__,
                        'execution_time': execution_time,
                        'memory_delta': end_memory - start_memory,
                        'timestamp': time.time(),
                        'optimization_level': self.optimization_level.value
                    }
                    
                    self.performance_history.append(perf_record)
                    
                    return result
                
                except Exception as e:
                    # エラーの場合もパフォーマンス記録
                    end_time = time.perf_counter()
                    execution_time = end_time - start_time
                    
                    perf_record = {
                        'function': func.__name__,
                        'execution_time': execution_time,
                        'error': str(e),
                        'timestamp': time.time(),
                        'optimization_level': self.optimization_level.value
                    }
                    
                    self.performance_history.append(perf_record)
                    raise
            
            return performance_wrapper
        
        return decorator
    
    def batch_optimize_data_processing(self, data: List[Any], 
                                     processor: Callable,
                                     batch_size: int = 1000) -> List[Any]:
        """バッチデータ処理最適化"""
        # メモリ効率的なジェネレーター使用
        data_gen = self.memory_optimizer.create_generator_from_list(data)
        batch_gen = self.memory_optimizer.batch_process_generator(data_gen, batch_size)
        
        results = []
        for batch in batch_gen:
            # 並列処理でバッチを処理
            batch_results = self.parallel_optimizer.parallel_map(
                processor,
                batch,
                PerformanceProfile(parallel_safe=True)
            )
            results.extend(batch_results)
            
            # メモリ圧迫時のガベージコレクション
            if len(results) % (batch_size * 10) == 0:
                self.memory_optimizer.force_gc_collection()
        
        return results
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """最適化レポート生成"""
        memory_stats = self.memory_optimizer.get_memory_usage()
        cache_stats = self.cache_optimizer.get_cache_statistics()
        parallel_stats = self.parallel_optimizer.get_processing_stats()
        
        # パフォーマンス統計
        if self.performance_history:
            execution_times = [record['execution_time'] for record in self.performance_history 
                             if 'execution_time' in record]
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            memory_deltas = [record.get('memory_delta', 0) for record in self.performance_history]
            avg_memory_delta = sum(memory_deltas) / len(memory_deltas) if memory_deltas else 0
        else:
            avg_execution_time = 0
            avg_memory_delta = 0
        
        return {
            'optimization_level': self.optimization_level.value,
            'memory_optimization': memory_stats,
            'cache_optimization': cache_stats,
            'parallel_processing': parallel_stats,
            'performance_metrics': {
                'total_function_calls': len(self.performance_history),
                'average_execution_time': avg_execution_time,
                'average_memory_delta': avg_memory_delta
            },
            'optimizations_applied': len(self.optimization_applied)
        }

# Convenience decorators
def high_performance(cache_size: int = 1000, 
                    parallel: bool = True,
                    memory_optimized: bool = True):
    """高パフォーマンス関数デコレーター"""
    enhancer = get_performance_enhancer()
    
    profile = PerformanceProfile(
        cache_friendly=True,
        parallel_safe=parallel,
        memory_intensive=memory_optimized
    )
    
    return enhancer.optimize_function(profile)

def memory_efficient(force_gc: bool = False):
    """メモリ効率化デコレーター"""
    def decorator(func):
        enhancer = get_performance_enhancer()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if force_gc:
                enhancer.memory_optimizer.force_gc_collection()
            
            # ジェネレーター化可能な引数をチェック
            new_args = []
            for arg in args:
                if isinstance(arg, list) and len(arg) > 1000:
                    new_args.append(enhancer.memory_optimizer.create_generator_from_list(arg))
                else:
                    new_args.append(arg)
            
            return func(*new_args, **kwargs)
        
        return wrapper
    return decorator

# Global performance enhancer
_global_performance_enhancer = None

def get_performance_enhancer() -> PerformanceEnhancer:
    """グローバルパフォーマンス最適化取得"""
    global _global_performance_enhancer
    if _global_performance_enhancer is None:
        _global_performance_enhancer = PerformanceEnhancer()
    return _global_performance_enhancer

if __name__ == "__main__":
    import os
    # パフォーマンス最適化のテスト
    print("⚡ Performance Enhancer Test")
    print("=" * 40)
    
    enhancer = get_performance_enhancer()
    
    # テスト関数
    @high_performance(cache_size=100, parallel=True)
    def expensive_calculation(n: int) -> int:
        """重い計算のテスト関数"""
        result = 0
        for i in range(n):
            result += i * i
        return result
    
    # パフォーマンステスト
    print("Running performance tests...")
    
    start_time = time.time()
    for i in range(10):
        result = expensive_calculation(1000)
    end_time = time.time()
    
    print(f"Test completed in {end_time - start_time:.3f} seconds")
    
    # 最適化レポート
    report = enhancer.get_optimization_report()
    print(f"Optimization Level: {report['optimization_level']}")
    print(f"Function Calls: {report['performance_metrics']['total_function_calls']}")
    print(f"Cache Hit Rate: {report['cache_optimization']['hit_rate_percent']:.1f}%")
    print(f"Memory Pool Hits: {report['memory_optimization']['stats']['pool_hits']}")