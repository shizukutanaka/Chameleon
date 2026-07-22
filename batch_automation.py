#!/usr/bin/env python3
"""
Batch Automation Framework
Batch/workflow automation: a safe AST-based condition-expression evaluator
(no eval/exec; whitelisted node types) and optional scheduling. Standalone —
not currently wired into the CLI or REST API (main.py has its own batch
path); see PRODUCT_ANALYSIS.md for its orphaned status.
"""

import os
import json
import asyncio
import threading
import queue
import ast
import subprocess
import shlex
import time
from types import MappingProxyType
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import pickle
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging
from logging.handlers import RotatingFileHandler

from security_validator import SecurityValidator, SecurityError, SecurityConfig

try:
    import schedule
    HAS_SCHEDULE = True
except ImportError:
    HAS_SCHEDULE = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class WorkflowType(Enum):
    """Workflow execution types"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    DAG = "dag"  # Directed Acyclic Graph

@dataclass
class TaskResult:
    """Result of task execution"""
    task_id: str
    status: TaskStatus
    output: Any
    error: Optional[str] = None
    start_time: datetime = None
    end_time: datetime = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BatchTask:
    """Individual batch task"""
    id: str
    name: str
    function: Callable
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]] = None
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 3
    timeout: Optional[float] = None
    priority: int = 0
    tags: List[str] = field(default_factory=list)

@dataclass
class Workflow:
    """Workflow definition"""
    id: str
    name: str
    tasks: List[BatchTask]
    type: WorkflowType
    schedule: Optional[str] = None  # Cron expression
    max_parallel: int = 4
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


SAFE_MODULE_FUNCTIONS = MappingProxyType({
    'builtins': frozenset({
        'len', 'sum', 'min', 'max', 'sorted', 'any', 'all', 'abs',
        'round'
    }),
    'math': frozenset({
        'ceil', 'floor', 'sqrt', 'fabs', 'log', 'log10', 'pow'
    }),
    'statistics': frozenset({
        'mean', 'median', 'harmonic_mean'
    })
})

RESULT_ALLOWED_ATTRIBUTES = frozenset({'status', 'success', 'error'})
SAFE_LITERAL_ALLOWED_TYPES = (str, int, float, bool, type(None))


CONFIG_VALIDATOR = SecurityValidator(
    SecurityConfig(allowed_extensions={'.yaml', '.yml', '.json'})
)
SCRIPT_VALIDATOR = SecurityValidator(
    SecurityConfig(allowed_extensions={'.py', '.sh', '.bat', '.cmd', '.ps1'})
)


_LOGGING_CONFIGURED = False
_MODULE_LOGGER = logging.getLogger(__name__)


def _configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    validator = SecurityValidator()

    try:
        log_dir = validator.validate_directory(
            Path.home() / '.chameleon' / 'logs',
            require_exists=False,
            allow_create=True
        )
    except SecurityError:
        _MODULE_LOGGER.addHandler(logging.NullHandler())
        _LOGGING_CONFIGURED = True
        return

    log_file = log_dir / 'batch_automation.log'

    handler = RotatingFileHandler(
        str(log_file),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    _MODULE_LOGGER.setLevel(logging.INFO)
    _MODULE_LOGGER.addHandler(handler)
    _MODULE_LOGGER.propagate = False
    _LOGGING_CONFIGURED = True


_configure_logging()


class ResultProxy:
    """Read-only projection of task result data"""

    __slots__ = ('status', 'success', 'error')

    def __init__(self, status: str, success: bool, error: Optional[str]):
        self.status = status
        self.success = success
        self.error = (error[:256] if error else None)


class ConditionEvaluationError(Exception):
    """Raised when a condition expression is invalid"""


class TemplateEvaluationError(Exception):
    """Raised when a template expression is invalid"""


def _build_results_proxy(results: Dict[str, 'TaskResult']) -> MappingProxyType:
    proxy: Dict[str, ResultProxy] = {}

    for task_id, result in results.items():
        status_value = result.status.value if isinstance(result.status, TaskStatus) else str(result.status)
        proxy[task_id] = ResultProxy(
            status=status_value,
            success=result.status == TaskStatus.COMPLETED,
            error=str(result.error) if result.error else None
        )

    return MappingProxyType(proxy)


class _ConditionExpressionEvaluator(ast.NodeVisitor):
    """AST evaluator for safe condition expressions"""

    def __init__(self, results_proxy: MappingProxyType):
        self._results = results_proxy

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = result and bool(self.visit(value))
                if not result:
                    break
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value in node.values:
                result = result or bool(self.visit(value))
                if result:
                    break
            return result
        raise ConditionEvaluationError("Unsupported boolean operator")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> bool:
        if isinstance(node.op, ast.Not):
            return not bool(self.visit(node.operand))
        raise ConditionEvaluationError("Unsupported unary operator")

    def visit_Compare(self, node: ast.Compare) -> bool:
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if isinstance(op, ast.Eq):
                comparison = left == right
            elif isinstance(op, ast.NotEq):
                comparison = left != right
            elif isinstance(op, ast.In):
                comparison = left in right
            elif isinstance(op, ast.NotIn):
                comparison = left not in right
            elif isinstance(op, ast.Is):
                comparison = left is right
            elif isinstance(op, ast.IsNot):
                comparison = left is not right
            else:
                raise ConditionEvaluationError("Unsupported comparison operator")

            if not comparison:
                return False
            left = right

        return True

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id == 'results':
            return self._results
        if node.id in {'True', 'False'}:
            return node.id == 'True'
        if node.id == 'None':
            return None
        raise ConditionEvaluationError(f"Name '{node.id}' is not permitted")

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, SAFE_LITERAL_ALLOWED_TYPES):
            return node.value
        raise ConditionEvaluationError("Unsupported literal in condition")

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        base = self.visit(node.value)
        if base is self._results:
            key = self._extract_index(node.slice)
            if key not in self._results:
                return ResultProxy(status='unknown', success=False, error=None)
            return self._results[key]
        raise ConditionEvaluationError("Subscript only allowed on results")

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        value = self.visit(node.value)
        if isinstance(value, ResultProxy) and node.attr in RESULT_ALLOWED_ATTRIBUTES:
            return getattr(value, node.attr)
        raise ConditionEvaluationError("Attribute access not permitted")

    def generic_visit(self, node: ast.AST) -> Any:
        raise ConditionEvaluationError(f"Unsupported expression component: {type(node).__name__}")

    @staticmethod
    def _extract_index(slice_node: ast.slice) -> str:
        if isinstance(slice_node, ast.Index):
            target = slice_node.value
        else:
            target = slice_node

        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            return target.value
        raise ConditionEvaluationError("Only string indices are allowed")


def _evaluate_condition_expression(expression: str, results: Dict[str, 'TaskResult']) -> bool:
    try:
        parsed = ast.parse(expression, mode='eval')
    except SyntaxError as exc:
        raise ConditionEvaluationError("Invalid condition syntax") from exc

    if sum(1 for _ in ast.walk(parsed)) > 200:
        raise ConditionEvaluationError("Condition expression too complex")

    evaluator = _ConditionExpressionEvaluator(_build_results_proxy(results))
    return bool(evaluator.visit(parsed))


class _LiteralExpressionEvaluator(ast.NodeVisitor):
    """Evaluate safe literal expressions with variable support"""

    def __init__(self, variables: MappingProxyType):
        self._variables = variables

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, SAFE_LITERAL_ALLOWED_TYPES):
            return node.value
        raise TemplateEvaluationError("Unsupported literal type in template")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in self._variables:
            return self._variables[node.id]
        if node.id in {'True', 'False'}:
            return node.id == 'True'
        if node.id == 'None':
            return None
        raise TemplateEvaluationError(f"Name '{node.id}' not permitted in template")

    def visit_List(self, node: ast.List) -> List[Any]:
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> tuple:
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Set(self, node: ast.Set) -> set:
        return {self.visit(elt) for elt in node.elts}

    def visit_Dict(self, node: ast.Dict) -> Dict[Any, Any]:
        return {
            self.visit(key): self.visit(value)
            for key, value in zip(node.keys, node.values)
        }

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise TemplateEvaluationError("Unsupported unary operator in template")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        raise TemplateEvaluationError("Unsupported binary operator in template")

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        base = self.visit(node.value)
        index = self._extract_index(node.slice)
        try:
            return base[index]
        except Exception as exc:
            raise TemplateEvaluationError("Invalid subscript access") from exc

    def generic_visit(self, node: ast.AST) -> Any:
        raise TemplateEvaluationError(f"Unsupported template component: {type(node).__name__}")

    @staticmethod
    def _extract_index(slice_node: ast.slice) -> Any:
        if isinstance(slice_node, ast.Index):
            target = slice_node.value
        else:
            target = slice_node

        if isinstance(target, ast.Constant) and isinstance(target.value, (str, int)):
            return target.value
        raise TemplateEvaluationError("Only string or integer indices permitted")


def _evaluate_template_expression(expression: str, variables: Dict[str, Any]) -> Any:
    try:
        parsed = ast.parse(expression, mode='eval')
    except SyntaxError as exc:
        raise TemplateEvaluationError("Invalid template syntax") from exc

    if sum(1 for _ in ast.walk(parsed)) > 200:
        raise TemplateEvaluationError("Template expression too complex")

    evaluator = _LiteralExpressionEvaluator(MappingProxyType(variables))
    return evaluator.visit(parsed)


def _import_safe_function(module_name: str, func_name: str) -> Callable:
    if module_name not in SAFE_MODULE_FUNCTIONS:
        raise ValueError(f"Module '{module_name}' is not allowed")

    if func_name not in SAFE_MODULE_FUNCTIONS[module_name]:
        raise ValueError(f"Function '{func_name}' is not permitted")

    module = __import__(module_name)
    func = getattr(module, func_name)

    if not callable(func):
        raise ValueError(f"Attribute '{func_name}' is not callable")

    return func


def _validate_config_path(path: Union[str, Path]) -> Path:
    raw_path = Path(path).expanduser()
    if not raw_path.is_absolute():
        raise SecurityError("Configuration path must be absolute")

    validated = CONFIG_VALIDATOR.validate_file_path(str(raw_path), operation='read')

    if not validated.exists():
        raise SecurityError(f"Configuration file does not exist: {validated}")

    return validated


def _validate_script_path(path: Union[str, Path]) -> Path:
    raw_path = Path(path).expanduser()
    if not raw_path.is_absolute():
        raise SecurityError("Script path must be absolute")

    validated = SCRIPT_VALIDATOR.validate_file_path(str(raw_path), operation='read')
    if not validated.exists():
        raise SecurityError(f"Script path does not exist: {validated}")
    return validated

class TaskQueue:
    """Priority queue for tasks"""

    def __init__(self):
        self.queue = queue.PriorityQueue()
        self.task_map = {}
        self.lock = threading.Lock()

    def add_task(self, task: BatchTask) -> None:
        """Add task to queue"""
        with self.lock:
            # Priority queue uses negative priority for higher values first
            self.queue.put((-task.priority, task.id, task))
            self.task_map[task.id] = task

    def get_task(self) -> Optional[BatchTask]:
        """Get next task from queue"""
        try:
            _, _, task = self.queue.get_nowait()
            with self.lock:
                del self.task_map[task.id]
            return task
        except queue.Empty:
            return None

    def remove_task(self, task_id: str) -> bool:
        """Remove task from queue"""
        with self.lock:
            if task_id in self.task_map:
                del self.task_map[task_id]
                return True
        return False

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return self.queue.empty()

class DependencyGraph:
    """Manage task dependencies"""

    def __init__(self):
        self.graph = {}
        self.in_degree = {}
        self.completed = set()

    def add_task(self, task: BatchTask) -> None:
        """Add task to dependency graph"""
        if task.id not in self.graph:
            self.graph[task.id] = []
            self.in_degree[task.id] = 0

        for dep in task.dependencies:
            if dep not in self.graph:
                self.graph[dep] = []
                self.in_degree[dep] = 0

            self.graph[dep].append(task.id)
            self.in_degree[task.id] += 1

    def get_ready_tasks(self) -> List[str]:
        """Get tasks ready for execution"""
        ready = []
        for task_id, degree in self.in_degree.items():
            if degree == 0 and task_id not in self.completed:
                ready.append(task_id)
        return ready

    def mark_completed(self, task_id: str) -> List[str]:
        """Mark task as completed and return newly ready tasks"""
        self.completed.add(task_id)
        newly_ready = []

        for dependent in self.graph.get(task_id, []):
            self.in_degree[dependent] -= 1
            if self.in_degree[dependent] == 0:
                newly_ready.append(dependent)

        return newly_ready

class TaskExecutor:
    """Execute individual tasks"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=max_workers)
        self.results = {}
        self.logger = logging.getLogger(__name__)

    def execute(self, task: BatchTask) -> TaskResult:
        """Execute a single task"""
        result = TaskResult(
            task_id=task.id,
            status=TaskStatus.RUNNING,
            output=None,
            start_time=datetime.now()
        )

        start_clock = time.perf_counter()

        try:
            # Execute with timeout if specified
            if task.timeout:
                future = self.thread_pool.submit(task.function, **task.inputs)
                output = future.result(timeout=task.timeout)
            else:
                output = task.function(**task.inputs)

            result.status = TaskStatus.COMPLETED
            result.output = output
            result.end_time = datetime.now()

        except TimeoutError:
            result.status = TaskStatus.FAILED
            result.error = f"Task timed out after {task.timeout} seconds"
            result.end_time = datetime.now()

        except Exception as e:
            result.status = TaskStatus.FAILED
            error_message = str(e)
            if len(error_message) > 512:
                error_message = error_message[:509] + "..."
            result.error = error_message
            result.end_time = datetime.now()
            self.logger.error(f"Task {task.id} failed: {e}")

        duration_ms = (time.perf_counter() - start_clock) * 1000.0
        result.metadata.update({
            "duration_ms": round(duration_ms, 2),
            "retry_allowed": task.retry_count,
            "timeout_seconds": task.timeout,
            "tags": list(task.tags),
            "priority": task.priority,
        })

        self.results[task.id] = result
        return result

    async def execute_async(self, task: BatchTask) -> TaskResult:
        """Execute task asynchronously"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.execute, task)

    def cleanup(self) -> None:
        """Cleanup executor resources"""
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)

class WorkflowEngine:
    """Execute workflows"""

    def __init__(self, max_parallel: int = 4):
        self.max_parallel = max_parallel
        self.executor = TaskExecutor(max_parallel)
        self.task_queue = TaskQueue()
        self.dep_graph = DependencyGraph()
        self.results = {}
        self.logger = logging.getLogger(__name__)

    def execute_workflow(self, workflow: Workflow) -> Dict[str, TaskResult]:
        """Execute complete workflow"""
        if workflow.type == WorkflowType.SEQUENTIAL:
            return self._execute_sequential(workflow)
        elif workflow.type == WorkflowType.PARALLEL:
            return self._execute_parallel(workflow)
        elif workflow.type == WorkflowType.DAG:
            return self._execute_dag(workflow)
        elif workflow.type == WorkflowType.CONDITIONAL:
            return self._execute_conditional(workflow)
        elif workflow.type == WorkflowType.LOOP:
            return self._execute_loop(workflow)
        else:
            raise ValueError(f"Unknown workflow type: {workflow.type}")

    def _execute_sequential(self, workflow: Workflow) -> Dict[str, TaskResult]:
        """Execute tasks sequentially"""
        results = {}

        for task in workflow.tasks:
            result = self.executor.execute(task)
            results[task.id] = result

            if result.status == TaskStatus.FAILED:
                self.logger.error(f"Sequential workflow stopped at task {task.id}")
                break

        return results

    def _execute_parallel(self, workflow: Workflow) -> Dict[str, TaskResult]:
        """Execute tasks in parallel"""
        import concurrent.futures

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=workflow.max_parallel) as executor:
            futures = {executor.submit(self.executor.execute, task): task for task in workflow.tasks}

            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                result = future.result()
                results[task.id] = result

        return results

    def _execute_dag(self, workflow: Workflow) -> Dict[str, TaskResult]:
        """Execute DAG workflow"""
        # Build dependency graph
        for task in workflow.tasks:
            self.dep_graph.add_task(task)

        # Create task map
        task_map = {task.id: task for task in workflow.tasks}
        results = {}
        running_tasks = {}

        # Get initial ready tasks
        ready_tasks = self.dep_graph.get_ready_tasks()
        for task_id in ready_tasks:
            self.task_queue.add_task(task_map[task_id])

        # Execute tasks
        while not self.task_queue.is_empty() or running_tasks:
            # Start new tasks up to parallel limit
            while len(running_tasks) < workflow.max_parallel:
                task = self.task_queue.get_task()
                if task is None:
                    break

                # Start task execution
                future = self.executor.thread_pool.submit(self.executor.execute, task)
                running_tasks[task.id] = future

            # Check for completed tasks
            completed_tasks = []
            for task_id, future in running_tasks.items():
                if future.done():
                    result = future.result()
                    results[task_id] = result
                    completed_tasks.append(task_id)

                    # Mark as completed and get newly ready tasks
                    newly_ready = self.dep_graph.mark_completed(task_id)
                    for ready_id in newly_ready:
                        if ready_id in task_map:
                            self.task_queue.add_task(task_map[ready_id])

            # Remove completed tasks
            for task_id in completed_tasks:
                del running_tasks[task_id]

            # Small delay to prevent busy waiting
            if running_tasks:
                import time
                time.sleep(0.1)

        return results

    def _execute_conditional(self, workflow: Workflow) -> Dict[str, TaskResult]:
        """Execute conditional workflow"""
        results = {}

        for task in workflow.tasks:
            # Check condition
            condition = workflow.conditions.get(task.id)
            if condition:
                if not self._evaluate_condition(condition, results):
                    self.logger.info(f"Skipping task {task.id} due to condition")
                    continue

            result = self.executor.execute(task)
            results[task.id] = result

        return results

    def _execute_loop(self, workflow: Workflow) -> Dict[str, TaskResult]:
        """Execute loop workflow"""
        results = {}
        iterations = workflow.metadata.get('iterations', 1)

        for i in range(iterations):
            for task in workflow.tasks:
                # Create unique task ID for each iteration
                loop_task = BatchTask(
                    id=f"{task.id}_iter_{i}",
                    name=f"{task.name} (iteration {i})",
                    function=task.function,
                    inputs=task.inputs,
                    dependencies=task.dependencies,
                    retry_count=task.retry_count,
                    timeout=task.timeout,
                    priority=task.priority,
                    tags=task.tags
                )

                result = self.executor.execute(loop_task)
                results[loop_task.id] = result

                if result.status == TaskStatus.FAILED:
                    self.logger.error(f"Loop workflow stopped at iteration {i}")
                    return results

        return results

    def _evaluate_condition(self, condition: Dict[str, Any], results: Dict[str, TaskResult]) -> bool:
        """Evaluate workflow condition"""
        condition_type = condition.get('type', 'simple')

        if condition_type == 'simple':
            # Check if previous task succeeded
            task_id = condition.get('task_id')
            if task_id in results:
                return results[task_id].status == TaskStatus.COMPLETED

        elif condition_type == 'expression':
            # Evaluate expression
            expr = condition.get('expression', 'True')
            try:
                return _evaluate_condition_expression(expr, results)
            except ConditionEvaluationError as exc:
                self.logger.warning(f"Condition evaluation failed for expression '{expr}': {exc}")
                return False

        return True

class BatchScheduler:
    """Schedule batch jobs"""

    def __init__(self):
        self.scheduled_jobs = {}
        self.running = False
        self.thread = None
        self.logger = logging.getLogger(__name__)

    def schedule_workflow(self, workflow: Workflow, cron_expression: str) -> None:
        """Schedule workflow execution"""
        if not HAS_SCHEDULE:
            self.logger.warning("Schedule library not available")
            return

        job_id = f"{workflow.id}_{datetime.now().timestamp()}"

        # Parse cron expression and schedule
        if cron_expression == "daily":
            schedule.every().day.do(self._execute_scheduled, workflow)
        elif cron_expression == "hourly":
            schedule.every().hour.do(self._execute_scheduled, workflow)
        elif cron_expression.startswith("every_"):
            interval = int(cron_expression.split("_")[1])
            schedule.every(interval).minutes.do(self._execute_scheduled, workflow)
        else:
            # Custom cron parsing would go here
            pass

        self.scheduled_jobs[job_id] = workflow

    def _execute_scheduled(self, workflow: Workflow) -> None:
        """Execute scheduled workflow"""
        self.logger.info(f"Executing scheduled workflow: {workflow.name}")
        engine = WorkflowEngine()
        results = engine.execute_workflow(workflow)
        self.logger.info(f"Completed workflow: {workflow.name}")

    def start(self) -> None:
        """Start scheduler"""
        if not HAS_SCHEDULE:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler)
        self.thread.start()

    def _run_scheduler(self) -> None:
        """Run scheduler loop"""
        while self.running:
            schedule.run_pending()
            import time
            time.sleep(1)

    def stop(self) -> None:
        """Stop scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()

class WorkflowBuilder:
    """Build workflows from configurations"""

    def __init__(self):
        self.workflows = {}

    def from_yaml(self, yaml_path: str) -> Workflow:
        """Build workflow from YAML configuration"""
        if not HAS_YAML:
            raise ImportError("PyYAML not installed")

        validated_path = _validate_config_path(yaml_path)

        with open(validated_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return self.from_dict(config)

    def from_json(self, json_path: str) -> Workflow:
        """Build workflow from JSON configuration"""
        validated_path = _validate_config_path(json_path)

        with open(validated_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return self.from_dict(config)

    def from_dict(self, config: Dict[str, Any]) -> Workflow:
        """Build workflow from dictionary"""
        tasks = []

        for task_config in config.get('tasks', []):
            # Create task function from configuration
            func = self._create_function(task_config.get('function'))

            task = BatchTask(
                id=task_config['id'],
                name=task_config.get('name', task_config['id']),
                function=func,
                inputs=task_config.get('inputs', {}),
                dependencies=task_config.get('dependencies', []),
                retry_count=task_config.get('retry_count', 3),
                timeout=task_config.get('timeout'),
                priority=task_config.get('priority', 0),
                tags=task_config.get('tags', [])
            )
            tasks.append(task)

        workflow = Workflow(
            id=config['id'],
            name=config.get('name', config['id']),
            tasks=tasks,
            type=WorkflowType(config.get('type', 'sequential')),
            schedule=config.get('schedule'),
            max_parallel=config.get('max_parallel', 4),
            conditions=config.get('conditions', {}),
            metadata=config.get('metadata', {})
        )

        return workflow

    def _create_function(self, func_config: Dict[str, Any]) -> Callable:
        """Create function from configuration"""
        func_type = func_config.get('type', 'builtin')

        if func_type == 'builtin':
            # Use built-in function
            module_name = func_config.get('module', 'builtins')
            func_name = func_config['name']

            return _import_safe_function(module_name, func_name)

        elif func_type == 'lambda':
            # Create lambda function
            expr = func_config['expression']
            variables = MappingProxyType({'inputs': MappingProxyType({})})

            def lambda_executor(**kwargs):
                scoped_variables = {
                    'inputs': MappingProxyType(kwargs),
                }
                return _evaluate_template_expression(expr, scoped_variables)

            return lambda_executor

        elif func_type == 'script':
            # Execute external script
            script_path = func_config['path']
            validated_script = _validate_script_path(str(script_path))
            timeout = float(func_config.get('timeout', 300))
            shell = bool(func_config.get('shell', False))

            script_logger = logging.getLogger("batch_automation.script")
            script_hash = hashlib.sha256(validated_script.read_bytes()).hexdigest()

            def script_executor(**kwargs):
                args = [str(v) for v in kwargs.values()]
                command = [str(validated_script)] + args

                if shell:
                    command = [str(validated_script)] + args
                    command_str = " ".join(shlex.quote(item) for item in command)
                    exec_command = command_str
                else:
                    exec_command = command

                env = {**os.environ}
                env.pop("PYTHONPATH", None)
                env.pop("PYTHONHOME", None)

                start_time = time.perf_counter()
                completed = subprocess.run(
                    exec_command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    shell=shell,
                    check=False,
                    env=env
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                stdout = completed.stdout.strip()
                stderr = completed.stderr.strip()

                result = {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": completed.returncode,
                    "command": command,
                    "script_hash": script_hash,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "timeout_seconds": timeout,
                    "shell": shell,
                }

                if elapsed_ms > (timeout * 1000 * 0.9):
                    script_logger.warning(
                        "Script '%s' executed in %.2f ms (>=90%% of timeout %.2f s)",
                        validated_script,
                        elapsed_ms,
                        timeout
                    )

                if stderr:
                    script_logger.info(
                        "Script '%s' produced stderr output (%d chars)",
                        validated_script,
                        len(stderr)
                    )

                if completed.returncode != 0:
                    raise RuntimeError(
                        f"Script execution failed (code {completed.returncode}): {stderr}"  # pragma: no cover
                    )

                return result

            return script_executor

        else:
            raise ValueError(f"Unknown function type: {func_type}")

class BatchAutomation:
    """Main batch automation system"""

    def __init__(self):
        self.engine = WorkflowEngine()
        self.scheduler = BatchScheduler()
        self.builder = WorkflowBuilder()
        self.workflows = {}
        self.results_cache = {}

    def create_workflow(self, config: Union[str, Dict[str, Any]]) -> Workflow:
        """Create workflow from configuration"""
        if isinstance(config, str):
            validated = _validate_config_path(config)
            suffix = validated.suffix.lower()

            if suffix in {'.yaml', '.yml'}:
                workflow = self.builder.from_yaml(str(validated))
            elif suffix == '.json':
                workflow = self.builder.from_json(str(validated))
            else:
                raise ValueError("Unsupported configuration format")
        else:
            workflow = self.builder.from_dict(config)

        self.workflows[workflow.id] = workflow
        return workflow

    def execute(self, workflow_id: str) -> Dict[str, TaskResult]:
        """Execute workflow"""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self.workflows[workflow_id]
        results = self.engine.execute_workflow(workflow)
        self.results_cache[workflow_id] = results

        return results

    def schedule(self, workflow_id: str, cron_expression: str) -> None:
        """Schedule workflow execution"""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self.workflows[workflow_id]
        self.scheduler.schedule_workflow(workflow, cron_expression)

    def start_scheduler(self) -> None:
        """Start the scheduler"""
        self.scheduler.start()

    def stop_scheduler(self) -> None:
        """Stop the scheduler"""
        self.scheduler.stop()

    def get_results(self, workflow_id: str) -> Optional[Dict[str, TaskResult]]:
        """Get workflow results"""
        return self.results_cache.get(workflow_id)

# Example usage
if __name__ == "__main__":
    print("Batch Automation Framework")

    # Example workflow configuration
    config = {
        "id": "audio_processing_workflow",
        "name": "Audio Processing Pipeline",
        "type": "dag",
        "max_parallel": 4,
        "tasks": [
            {
                "id": "load_audio",
                "name": "Load Audio Files",
                "function": {
                    "type": "lambda",
                    "expression": "{'files': ['audio1.wav', 'audio2.wav']}"
                },
                "inputs": {},
                "dependencies": []
            },
            {
                "id": "enhance_audio",
                "name": "Enhance Audio Quality",
                "function": {
                    "type": "lambda",
                    "expression": "{'enhanced': True}"
                },
                "inputs": {},
                "dependencies": ["load_audio"]
            },
            {
                "id": "transcode",
                "name": "Transcode to Multiple Formats",
                "function": {
                    "type": "lambda",
                    "expression": "{'formats': ['mp3', 'flac', 'ogg']}"
                },
                "inputs": {},
                "dependencies": ["enhance_audio"]
            }
        ]
    }

    # Create and execute workflow
    automation = BatchAutomation()
    workflow = automation.create_workflow(config)
    print(f"Created workflow: {workflow.name}")

    results = automation.execute(workflow.id)
    print(f"Executed {len(results)} tasks")

    for task_id, result in results.items():
        print(f"  {task_id}: {result.status.value}")