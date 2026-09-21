"""DAG workflow semantics.

At HEAD:
- A task that *failed* still called ``mark_completed``, releasing its
  dependents -- 'B depends on A' silently ran B on the wreckage.
- A dependency cycle (or a dependency on a task id that doesn't exist)
  left the task unscheduled forever, and the result set simply *omitted*
  it -- a workflow that returns without mentioning half its tasks
  reports success it never earned. A missing dep also crashed the
  scheduler on a phantom ``task_map[dep]`` lookup.
- ``dep_graph``/``task_queue`` lived on the engine across runs, so a
  second workflow inherited the first run's ``completed`` ids and
  silently dropped colliding tasks.
"""
import pytest

from batch_automation import (
    BatchTask,
    TaskStatus,
    Workflow,
    WorkflowEngine,
    WorkflowType,
)


def _task(tid, deps=(), fn=None):
    return BatchTask(
        id=tid, name=tid, function=fn or (lambda: "ok"),
        inputs={}, dependencies=list(deps),
    )


def _workflow(tasks):
    return Workflow(id="wf", name="wf", tasks=tasks, type=WorkflowType.DAG)


def test_failed_dependency_prevents_dependent_from_running():
    engine = WorkflowEngine()
    ran = []

    def boom():
        raise RuntimeError("A exploded")

    def b_fn():
        ran.append("B")
        return "b"

    def c_fn():
        ran.append("C")
        return "c"

    wf = _workflow([
        _task("A", fn=boom),
        _task("B", deps=["A"], fn=b_fn),
        _task("C", deps=["B"], fn=c_fn),
        _task("D", deps=[]),           # independent -- must still run
    ])
    results = engine.execute_workflow(wf)
    engine.executor.cleanup()

    assert results["A"].status == TaskStatus.FAILED
    # B never ran, and is visibly failed rather than silently missing.
    assert results["B"].status == TaskStatus.FAILED
    assert "dependency" in results["B"].error
    # The failure cascades: C depended on B.
    assert results["C"].status == TaskStatus.FAILED
    assert ran == []
    assert results["D"].status == TaskStatus.COMPLETED


def test_dependency_cycle_marks_tasks_unreachable():
    engine = WorkflowEngine()
    wf = _workflow([
        _task("A", deps=["B"]),
        _task("B", deps=["A"]),
        _task("C", deps=[]),
    ])
    results = engine.execute_workflow(wf)
    engine.executor.cleanup()

    assert results["C"].status == TaskStatus.COMPLETED
    for tid in ("A", "B"):
        assert results[tid].status == TaskStatus.FAILED
        assert "nreachable" in results[tid].error


def test_missing_dependency_marks_task_unreachable():
    engine = WorkflowEngine()
    wf = _workflow([_task("A", deps=["ghost"])])
    results = engine.execute_workflow(wf)
    engine.executor.cleanup()

    assert results["A"].status == TaskStatus.FAILED
    assert "nreachable" in results["A"].error


def test_engine_state_does_not_leak_between_workflows():
    engine = WorkflowEngine()
    ran_first = engine.execute_workflow(_workflow([_task("x")]))
    assert ran_first["x"].status == TaskStatus.COMPLETED

    # Same engine, new workflow, colliding task id: must run again.
    second_calls = []
    wf2 = _workflow([_task("x", fn=lambda: second_calls.append(1) or "ok")])
    results = engine.execute_workflow(wf2)
    engine.executor.cleanup()

    assert results["x"].status == TaskStatus.COMPLETED
    assert second_calls == [1]


def test_happy_dag_still_runs_in_order():
    engine = WorkflowEngine()
    order = []
    wf = _workflow([
        _task("A", fn=lambda: order.append("A")),
        _task("B", deps=["A"], fn=lambda: order.append("B")),
    ])
    results = engine.execute_workflow(wf)
    engine.executor.cleanup()

    assert all(r.status == TaskStatus.COMPLETED for r in results.values())
    assert order == ["A", "B"]
