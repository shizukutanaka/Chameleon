#!/usr/bin/env python3
"""
Distributed Cloud Processing System
Scalable cloud-based audio processing with distributed computing
"""

import logging
import threading
import time
import json
import asyncio
import hashlib
import uuid
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import concurrent.futures
import queue
import socket
import urllib.request
import urllib.parse
import base64

class ProcessingPriority(Enum):
    """Processing priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CloudProvider(Enum):
    """Supported cloud providers"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    LOCAL = "local"
    HYBRID = "hybrid"

@dataclass
class ProcessingTask:
    """Represents a processing task"""
    task_id: str
    task_type: str
    priority: ProcessingPriority
    input_data: Any
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    progress: float = 0.0
    estimated_duration: Optional[float] = None

@dataclass
class WorkerNode:
    """Represents a worker node"""
    worker_id: str
    node_type: str  # "local", "cloud", "edge"
    capabilities: List[str]
    max_concurrent_tasks: int
    current_load: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.now)
    status: str = "available"  # "available", "busy", "offline"
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    location: str = "unknown"
    cost_per_hour: float = 0.0

@dataclass
class ProcessingResult:
    """Processing task result"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    processing_time: float = 0.0
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class TaskQueue:
    """Priority-based task queue"""
    
    def __init__(self):
        self.queues = {
            ProcessingPriority.URGENT: queue.PriorityQueue(),
            ProcessingPriority.HIGH: queue.PriorityQueue(),
            ProcessingPriority.NORMAL: queue.PriorityQueue(),
            ProcessingPriority.LOW: queue.PriorityQueue()
        }
        self.lock = threading.RLock()
        self.task_count = 0
    
    def enqueue(self, task: ProcessingTask):
        """Add task to appropriate priority queue"""
        with self.lock:
            # Use negative timestamp for priority ordering (newer tasks first within same priority)
            priority_value = -time.time()
            self.queues[task.priority].put((priority_value, task))
            self.task_count += 1
            task.status = TaskStatus.QUEUED
    
    def dequeue(self) -> Optional[ProcessingTask]:
        """Get next task based on priority"""
        with self.lock:
            # Check queues in priority order
            for priority in [ProcessingPriority.URGENT, ProcessingPriority.HIGH, 
                           ProcessingPriority.NORMAL, ProcessingPriority.LOW]:
                try:
                    _, task = self.queues[priority].get_nowait()
                    self.task_count -= 1
                    return task
                except queue.Empty:
                    continue
            return None
    
    def size(self) -> int:
        """Get total queue size"""
        return self.task_count
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """Get size of each priority queue"""
        return {
            priority.value: self.queues[priority].qsize() 
            for priority in ProcessingPriority
        }

class WorkerManager:
    """Manages worker nodes and load balancing"""
    
    def __init__(self):
        self.workers = {}
        self.worker_assignments = defaultdict(list)  # task_id -> worker_id
        self.lock = threading.RLock()
        self.logger = logging.getLogger("WorkerManager")
        
        # Load balancing configuration
        self.load_balancing_strategy = "least_loaded"  # "round_robin", "least_loaded", "capability_based"
        self.heartbeat_timeout = timedelta(minutes=5)
        
        # Start worker monitoring
        self._start_monitoring()
    
    def register_worker(self, worker: WorkerNode):
        """Register a new worker node"""
        with self.lock:
            self.workers[worker.worker_id] = worker
            self.logger.info(f"Registered worker: {worker.worker_id} ({worker.node_type})")
    
    def unregister_worker(self, worker_id: str):
        """Unregister a worker node"""
        with self.lock:
            if worker_id in self.workers:
                del self.workers[worker_id]
                self.logger.info(f"Unregistered worker: {worker_id}")
    
    def update_worker_heartbeat(self, worker_id: str, metrics: Dict[str, float] = None):
        """Update worker heartbeat and metrics"""
        with self.lock:
            if worker_id in self.workers:
                self.workers[worker_id].last_heartbeat = datetime.now()
                if metrics:
                    self.workers[worker_id].performance_metrics.update(metrics)
    
    def find_available_worker(self, task: ProcessingTask) -> Optional[WorkerNode]:
        """Find best available worker for task"""
        with self.lock:
            available_workers = [
                worker for worker in self.workers.values()
                if (worker.status == "available" and 
                    worker.current_load < worker.max_concurrent_tasks and
                    self._worker_can_handle_task(worker, task))
            ]
            
            if not available_workers:
                return None
            
            if self.load_balancing_strategy == "least_loaded":
                return min(available_workers, key=lambda w: w.current_load / w.max_concurrent_tasks)
            elif self.load_balancing_strategy == "capability_based":
                # Score workers based on capabilities and performance
                scored_workers = []
                for worker in available_workers:
                    score = self._calculate_worker_score(worker, task)
                    scored_workers.append((score, worker))
                return max(scored_workers, key=lambda x: x[0])[1]
            else:  # round_robin
                return available_workers[0]
    
    def _worker_can_handle_task(self, worker: WorkerNode, task: ProcessingTask) -> bool:
        """Check if worker can handle the task type"""
        required_capabilities = task.metadata.get('required_capabilities', [])
        if not required_capabilities:
            return True
        return any(cap in worker.capabilities for cap in required_capabilities)
    
    def _calculate_worker_score(self, worker: WorkerNode, task: ProcessingTask) -> float:
        """Calculate worker suitability score for task"""
        score = 1.0
        
        # Load factor (prefer less loaded workers)
        load_factor = worker.current_load / worker.max_concurrent_tasks
        score *= (1.0 - load_factor)
        
        # Performance factor
        avg_processing_time = worker.performance_metrics.get('avg_processing_time', 1.0)
        if avg_processing_time > 0:
            score *= (1.0 / avg_processing_time)
        
        # Capability match
        required_caps = task.metadata.get('required_capabilities', [])
        if required_caps:
            matching_caps = len(set(required_caps) & set(worker.capabilities))
            score *= (1.0 + matching_caps / len(required_caps))
        
        # Cost factor (prefer cheaper workers for low priority tasks)
        if task.priority == ProcessingPriority.LOW and worker.cost_per_hour > 0:
            score *= (1.0 / (1.0 + worker.cost_per_hour))
        
        return score
    
    def assign_task(self, task: ProcessingTask, worker: WorkerNode):
        """Assign task to worker"""
        with self.lock:
            worker.current_load += 1
            if worker.current_load >= worker.max_concurrent_tasks:
                worker.status = "busy"
            
            self.worker_assignments[task.task_id] = worker.worker_id
            task.worker_id = worker.worker_id
            task.started_at = datetime.now()
            task.status = TaskStatus.PROCESSING
    
    def complete_task(self, task_id: str):
        """Mark task as completed and free worker"""
        with self.lock:
            if task_id in self.worker_assignments:
                worker_id = self.worker_assignments[task_id]
                if worker_id in self.workers:
                    worker = self.workers[worker_id]
                    worker.current_load = max(0, worker.current_load - 1)
                    if worker.current_load < worker.max_concurrent_tasks:
                        worker.status = "available"
                
                del self.worker_assignments[task_id]
    
    def get_worker_status(self) -> Dict[str, Any]:
        """Get status of all workers"""
        with self.lock:
            return {
                "total_workers": len(self.workers),
                "available_workers": len([w for w in self.workers.values() if w.status == "available"]),
                "busy_workers": len([w for w in self.workers.values() if w.status == "busy"]),
                "offline_workers": len([w for w in self.workers.values() if w.status == "offline"]),
                "total_capacity": sum(w.max_concurrent_tasks for w in self.workers.values()),
                "current_load": sum(w.current_load for w in self.workers.values()),
                "workers": {wid: {
                    "status": w.status,
                    "load": w.current_load,
                    "capacity": w.max_concurrent_tasks,
                    "node_type": w.node_type,
                    "capabilities": w.capabilities,
                    "last_heartbeat": w.last_heartbeat.isoformat()
                } for wid, w in self.workers.items()}
            }
    
    def _start_monitoring(self):
        """Start worker monitoring thread"""
        def monitor_workers():
            while True:
                try:
                    self._check_worker_health()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    self.logger.error(f"Worker monitoring error: {e}")
                    time.sleep(60)
        
        monitor_thread = threading.Thread(target=monitor_workers, daemon=True)
        monitor_thread.start()
    
    def _check_worker_health(self):
        """Check worker health and mark offline workers"""
        with self.lock:
            current_time = datetime.now()
            for worker in self.workers.values():
                if current_time - worker.last_heartbeat > self.heartbeat_timeout:
                    if worker.status != "offline":
                        worker.status = "offline"
                        self.logger.warning(f"Worker {worker.worker_id} marked offline")

class CloudProcessor:
    """Main cloud processing orchestrator"""
    
    def __init__(self, provider: CloudProvider = CloudProvider.LOCAL):
        self.provider = provider
        self.task_queue = TaskQueue()
        self.worker_manager = WorkerManager()
        self.active_tasks = {}
        self.completed_tasks = deque(maxlen=10000)
        self.task_history = deque(maxlen=100000)
        
        # Configuration
        self.config = {
            "max_retries": 3,
            "retry_delay": 5.0,
            "task_timeout": 3600.0,  # 1 hour
            "batch_processing": True,
            "auto_scaling": True,
            "cost_optimization": True
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Initialize logging
        self.logger = logging.getLogger("CloudProcessor")
        
        # Processing statistics
        self.stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0
        }
        
        # Initialize local worker
        self._initialize_local_workers()
        
        # Start processing
        self._start_processing()
    
    def _initialize_local_workers(self):
        """Initialize local worker nodes"""
        import multiprocessing
        
        # Create local workers based on CPU cores
        cpu_count = multiprocessing.cpu_count()
        for i in range(min(cpu_count, 4)):  # Limit to 4 local workers
            worker = WorkerNode(
                worker_id=f"local_worker_{i}",
                node_type="local",
                capabilities=["audio_processing", "basic_analysis", "format_conversion"],
                max_concurrent_tasks=2,
                location="local",
                cost_per_hour=0.0
            )
            self.worker_manager.register_worker(worker)
    
    def submit_task(self, task_type: str, input_data: Any, 
                   parameters: Dict[str, Any] = None,
                   priority: ProcessingPriority = ProcessingPriority.NORMAL,
                   metadata: Dict[str, Any] = None) -> str:
        """Submit a processing task"""
        
        task_id = str(uuid.uuid4())
        task = ProcessingTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            input_data=input_data,
            parameters=parameters or {},
            metadata=metadata or {}
        )
        
        with self.lock:
            self.task_queue.enqueue(task)
            self.active_tasks[task_id] = task
            self.stats["tasks_submitted"] += 1
        
        self.logger.info(f"Task submitted: {task_id} ({task_type}, {priority.value})")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task"""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                return {
                    "task_id": task_id,
                    "status": task.status.value,
                    "progress": task.progress,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "worker_id": task.worker_id,
                    "estimated_duration": task.estimated_duration,
                    "error": task.error
                }
            
            # Check completed tasks
            for task in self.completed_tasks:
                if task.task_id == task_id:
                    return {
                        "task_id": task_id,
                        "status": task.status.value,
                        "processing_time": task.processing_time,
                        "worker_id": task.worker_id,
                        "error": task.error,
                        "completed": True
                    }
        
        return None
    
    def get_task_result(self, task_id: str) -> Optional[ProcessingResult]:
        """Get result of a completed task"""
        with self.lock:
            # Check active tasks first
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status == TaskStatus.COMPLETED:
                    return ProcessingResult(
                        task_id=task_id,
                        status=task.status,
                        result=task.result,
                        processing_time=(task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else 0,
                        worker_id=task.worker_id,
                        metadata=task.metadata
                    )
            
            # Check completed tasks
            for task in self.completed_tasks:
                if task.task_id == task_id:
                    return task
        
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or processing task"""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status in [TaskStatus.PENDING, TaskStatus.QUEUED]:
                    task.status = TaskStatus.CANCELLED
                    self._complete_task(task)
                    return True
                elif task.status == TaskStatus.PROCESSING:
                    # Mark for cancellation - actual cancellation depends on worker
                    task.status = TaskStatus.CANCELLED
                    return True
        
        return False
    
    def _start_processing(self):
        """Start background task processing"""
        def process_tasks():
            while True:
                try:
                    self._process_next_task()
                    time.sleep(0.1)  # Small delay to prevent busy waiting
                except Exception as e:
                    self.logger.error(f"Task processing error: {e}")
                    time.sleep(1)
        
        # Start multiple processing threads
        for i in range(2):  # 2 processing threads
            process_thread = threading.Thread(target=process_tasks, daemon=True)
            process_thread.start()
    
    def _process_next_task(self):
        """Process the next task in queue"""
        task = self.task_queue.dequeue()
        if not task:
            return
        
        # Find available worker
        worker = self.worker_manager.find_available_worker(task)
        if not worker:
            # No available workers, re-queue the task
            self.task_queue.enqueue(task)
            return
        
        # Assign task to worker
        self.worker_manager.assign_task(task, worker)
        
        # Execute task
        self._execute_task(task, worker)
    
    def _execute_task(self, task: ProcessingTask, worker: WorkerNode):
        """Execute task on worker"""
        def run_task():
            try:
                start_time = time.time()
                
                # Simulate task execution based on type
                result = self._simulate_task_execution(task, worker)
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Update task
                task.result = result
                task.completed_at = datetime.now()
                task.status = TaskStatus.COMPLETED
                task.progress = 100.0
                
                # Update worker metrics
                worker.performance_metrics["avg_processing_time"] = (
                    worker.performance_metrics.get("avg_processing_time", processing_time) + processing_time
                ) / 2
                
                # Complete task
                self._complete_task(task, processing_time)
                
                self.logger.info(f"Task completed: {task.task_id} in {processing_time:.2f}s")
                
            except Exception as e:
                # Handle task failure
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                
                self._complete_task(task)
                
                self.logger.error(f"Task failed: {task.task_id} - {e}")
        
        # Run task in background thread
        task_thread = threading.Thread(target=run_task, daemon=True)
        task_thread.start()
    
    def _simulate_task_execution(self, task: ProcessingTask, worker: WorkerNode) -> Any:
        """Simulate task execution (placeholder for actual processing)"""
        
        # Simulate processing time based on task type
        base_time = {
            "audio_analysis": 2.0,
            "format_conversion": 1.0,
            "noise_reduction": 3.0,
            "audio_enhancement": 2.5,
            "transcription": 5.0,
            "music_separation": 8.0
        }.get(task.task_type, 1.0)
        
        # Adjust time based on worker performance
        worker_efficiency = worker.performance_metrics.get("efficiency", 1.0)
        actual_time = base_time / worker_efficiency
        
        # Simulate progress updates
        steps = 10
        for i in range(steps):
            time.sleep(actual_time / steps)
            task.progress = (i + 1) / steps * 100
            
            # Check for cancellation
            if task.status == TaskStatus.CANCELLED:
                raise Exception("Task cancelled")
        
        # Generate result based on task type
        if task.task_type == "audio_analysis":
            return {
                "duration": 180.5,
                "sample_rate": 44100,
                "channels": 2,
                "peak_amplitude": 0.95,
                "rms_level": 0.42,
                "zero_crossings": 12540,
                "spectral_centroid": 2341.2
            }
        elif task.task_type == "format_conversion":
            return {
                "output_format": task.parameters.get("target_format", "mp3"),
                "file_size_bytes": 2048576,
                "conversion_time": actual_time,
                "quality_retained": 0.98
            }
        elif task.task_type == "noise_reduction":
            return {
                "noise_reduction_db": 15.3,
                "signal_quality": 0.91,
                "artifacts_introduced": 0.02,
                "processing_method": "spectral_subtraction"
            }
        else:
            return {
                "task_type": task.task_type,
                "processed": True,
                "processing_time": actual_time,
                "worker_id": worker.worker_id
            }
    
    def _complete_task(self, task: ProcessingTask, processing_time: float = 0):
        """Complete task and update statistics"""
        with self.lock:
            # Remove from active tasks
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]
            
            # Create result record
            result = ProcessingResult(
                task_id=task.task_id,
                status=task.status,
                result=task.result,
                error=task.error,
                processing_time=processing_time,
                worker_id=task.worker_id,
                metadata=task.metadata
            )
            
            # Store in completed tasks
            self.completed_tasks.append(result)
            
            # Update statistics
            if task.status == TaskStatus.COMPLETED:
                self.stats["tasks_completed"] += 1
                self.stats["total_processing_time"] += processing_time
                self.stats["average_processing_time"] = (
                    self.stats["total_processing_time"] / self.stats["tasks_completed"]
                )
            elif task.status == TaskStatus.FAILED:
                self.stats["tasks_failed"] += 1
            
            # Free worker
            self.worker_manager.complete_task(task.task_id)
            
            # Add to history
            self.task_history.append({
                "task_id": task.task_id,
                "task_type": task.task_type,
                "priority": task.priority.value,
                "status": task.status.value,
                "processing_time": processing_time,
                "worker_id": task.worker_id,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            })
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        with self.lock:
            queue_sizes = self.task_queue.get_queue_sizes()
            worker_status = self.worker_manager.get_worker_status()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "provider": self.provider.value,
                "queue_status": {
                    "total_queued": self.task_queue.size(),
                    "by_priority": queue_sizes
                },
                "worker_status": worker_status,
                "active_tasks": len(self.active_tasks),
                "processing_statistics": self.stats.copy(),
                "system_health": self._calculate_system_health()
            }
    
    def _calculate_system_health(self) -> str:
        """Calculate overall system health"""
        # Simple health calculation based on various metrics
        worker_availability = len([w for w in self.worker_manager.workers.values() if w.status == "available"])
        total_workers = len(self.worker_manager.workers)
        
        if total_workers == 0:
            return "critical"
        
        availability_ratio = worker_availability / total_workers
        
        if availability_ratio > 0.8:
            return "healthy"
        elif availability_ratio > 0.5:
            return "degraded"
        else:
            return "critical"
    
    def add_cloud_worker(self, provider: str, instance_type: str, capabilities: List[str]):
        """Add cloud worker (placeholder for cloud integration)"""
        worker_id = f"{provider}_{instance_type}_{uuid.uuid4().hex[:8]}"
        
        # Cost estimates (placeholder)
        cost_map = {
            "aws_t3.micro": 0.0104,
            "aws_c5.large": 0.085,
            "azure_b1s": 0.0052,
            "gcp_e2-micro": 0.0035
        }
        
        worker = WorkerNode(
            worker_id=worker_id,
            node_type="cloud",
            capabilities=capabilities,
            max_concurrent_tasks=4,
            location=provider,
            cost_per_hour=cost_map.get(f"{provider}_{instance_type}", 0.05)
        )
        
        self.worker_manager.register_worker(worker)
        self.logger.info(f"Added cloud worker: {worker_id}")
        
        return worker_id
    
    def scale_workers(self, target_capacity: int):
        """Auto-scale workers based on demand"""
        current_capacity = sum(w.max_concurrent_tasks for w in self.worker_manager.workers.values())
        
        if target_capacity > current_capacity:
            # Scale up
            additional_capacity = target_capacity - current_capacity
            workers_needed = (additional_capacity + 3) // 4  # 4 tasks per worker
            
            for i in range(workers_needed):
                self.add_cloud_worker("aws", "t3.micro", ["audio_processing", "basic_analysis"])
                
        elif target_capacity < current_capacity * 0.7:  # Scale down when capacity is underutilized
            # Scale down (placeholder - would terminate cloud instances)
            self.logger.info("Scale down triggered (not implemented)")

# Global cloud processor instance
_global_cloud_processor = None

def get_global_cloud_processor() -> CloudProcessor:
    """Get or create global cloud processor"""
    global _global_cloud_processor
    if _global_cloud_processor is None:
        _global_cloud_processor = CloudProcessor()
    return _global_cloud_processor

if __name__ == "__main__":
    # Example usage
    processor = CloudProcessor()
    
    # Submit various tasks
    task_ids = []
    
    # Audio analysis task
    task1 = processor.submit_task(
        "audio_analysis",
        {"file_path": "test_audio.wav"},
        priority=ProcessingPriority.HIGH,
        metadata={"required_capabilities": ["audio_processing"]}
    )
    task_ids.append(task1)
    
    # Format conversion task
    task2 = processor.submit_task(
        "format_conversion",
        {"input_format": "wav", "audio_data": b"fake_audio_data"},
        {"target_format": "mp3", "bitrate": 192},
        priority=ProcessingPriority.NORMAL
    )
    task_ids.append(task2)
    
    # Noise reduction task
    task3 = processor.submit_task(
        "noise_reduction",
        {"audio_data": b"noisy_audio_data"},
        {"algorithm": "spectral_subtraction", "strength": 0.7},
        priority=ProcessingPriority.URGENT
    )
    task_ids.append(task3)
    
    print(f"Submitted {len(task_ids)} tasks")
    
    # Wait for tasks to complete
    time.sleep(10)
    
    # Check results
    for task_id in task_ids:
        status = processor.get_task_status(task_id)
        if status:
            print(f"Task {task_id}: {status['status']}")
            
            if status['status'] == 'completed':
                result = processor.get_task_result(task_id)
                if result:
                    print(f"  Result: {result.result}")
    
    # Get system status
    system_status = processor.get_system_status()
    print("\nSystem Status:")
    print(json.dumps(system_status, indent=2, default=str))