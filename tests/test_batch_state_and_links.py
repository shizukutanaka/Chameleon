"""Audit-77 regression tests.

1. ``BatchProcessor.process_directory_async`` gathered candidates with only
   ``is_file()`` + suffix checks -- no ``is_symlink()`` gate, unlike the sync
   ``process_directory`` right above it. A ``.wav`` symlink pointing outside
   the scanned tree passed every pre-flight check (the target is a real WAV)
   and was processed; verified: ``analyze`` on a link to an out-of-tree file
   succeeded while the sync path refused it.

2. ``WorkflowEngine`` kept ``dep_graph`` and ``task_queue`` as instance state
   across ``execute_workflow`` calls. ``dep_graph.completed`` was never
   reset, so re-running a DAG workflow on the same engine silently executed
   zero tasks -- every task id was already completed (verified: second run
   returned ``{}``).

3. ``TaskQueue.remove_task`` deleted only from ``task_map``; the
   PriorityQueue entry still surfaced in ``get_task``, so a "removed" task
   ran anyway. ``get_task`` now lazily skips ids no longer in the map.
"""

import asyncio
import os
import wave
import struct
from pathlib import Path

import pytest

from batch_automation import (
    BatchTask, TaskQueue, Workflow, WorkflowEngine, WorkflowType,
)
from core import BatchProcessor


def _wav(path: Path) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<160h", *([1000] * 160)))


@pytest.fixture
def tree_with_escaping_link(tmp_path: Path) -> Path:
    tree = tmp_path / "scan_me"
    tree.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _wav(outside / "secret.wav")
    _wav(tree / "real.wav")
    try:
        (tree / "link.wav").symlink_to(outside / "secret.wav")
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    return tree


def test_async_batch_refuses_escaping_symlink(tree_with_escaping_link: Path) -> None:
    processor = BatchProcessor()
    results = asyncio.run(
        processor.process_directory_async(str(tree_with_escaping_link), "analyze")
    )
    # One file result (real.wav) plus the trailing summary row -- the link
    # must not appear as a processed file.
    file_results = results[:-1]
    assert len(file_results) == 1
    assert file_results[0].success


def test_sync_and_async_gather_the_same_file_set(tree_with_escaping_link: Path) -> None:
    processor = BatchProcessor()
    sync_results = processor.process_directory(str(tree_with_escaping_link), "analyze")
    async_results = asyncio.run(
        processor.process_directory_async(str(tree_with_escaping_link), "analyze")
    )
    assert len(sync_results) == len(async_results) == 2  # file + summary


def _dag() -> Workflow:
    return Workflow(
        id="w1", name="w1", type=WorkflowType.DAG,
        tasks=[
            BatchTask(id="a", name="a", function=lambda: 1, inputs={}),
            BatchTask(id="b", name="b", function=lambda: 2,
                      inputs={}, dependencies=["a"]),
        ],
    )


def test_dag_workflow_reruns_on_same_engine() -> None:
    engine = WorkflowEngine()
    first = engine.execute_workflow(_dag())
    second = engine.execute_workflow(_dag())
    assert sorted(first) == ["a", "b"]
    assert sorted(second) == ["a", "b"]


def test_removed_task_does_not_execute() -> None:
    queue_ = TaskQueue()
    queue_.add_task(BatchTask(id="x", name="x", function=lambda: 0, inputs={}))
    assert queue_.remove_task("x") is True
    assert queue_.get_task() is None

    # A live entry queued after a removal still surfaces.
    queue_.add_task(BatchTask(id="y", name="y", function=lambda: 0, inputs={}))
    assert queue_.get_task().id == "y"
