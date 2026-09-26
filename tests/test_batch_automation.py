"""The batch_automation engine is an allowed orphan, but it still has to
do what it claims. Two of its public paths could never have worked:

* `WorkflowBuilder`'s 'builtin' function type resolved an allowlisted
  callable and handed it straight to an executor that invokes
  `function(**inputs)` -- every allowlisted function (len, math.pow,
  statistics.mean, ...) is positional-only, so every task ended
  TaskStatus.FAILED with 'takes no keyword arguments'.
* `BatchScheduler.schedule_workflow` recognized 'daily', 'hourly' and
  'every_<minutes>' but fell through to `pass` for anything else -- the
  job was then registered in scheduled_jobs and never ran.
"""

import types

import pytest

import batch_automation as ba


def _run_dict(cfg):
    workflow = ba.WorkflowBuilder().from_dict(cfg)
    return ba.WorkflowEngine().execute_workflow(workflow)


def test_builtin_function_runs_positionally():
    res = _run_dict({
        "id": "w", "name": "d", "type": "sequential",
        "tasks": [{
            "id": "t", "name": "pow",
            "function": {"type": "builtin", "module": "math", "name": "pow"},
            "inputs": {"x": 2, "y": 3},
        }],
    })
    assert res["t"].status is ba.TaskStatus.COMPLETED
    assert res["t"].output == 8.0


def test_scheduler_rejects_an_expression_it_cannot_parse(monkeypatch):
    calls = []

    class FakeJob:
        def do(self, fn, wf):
            calls.append("scheduled")

    fake_schedule = types.SimpleNamespace(
        every=lambda *a: types.SimpleNamespace(
            day=FakeJob(), hour=FakeJob(),
            minutes=FakeJob()))
    monkeypatch.setattr(ba, "HAS_SCHEDULE", True)
    monkeypatch.setattr(ba, "schedule", fake_schedule, raising=False)

    scheduler = ba.BatchScheduler()
    workflow = ba.Workflow(id="w", name="n", type=ba.WorkflowType.SEQUENTIAL,
                           tasks=[])

    scheduler.schedule_workflow(workflow, "daily")
    assert calls == ["scheduled"]
    assert scheduler.scheduled_jobs  # registered

    with pytest.raises(ValueError, match="Unsupported schedule"):
        scheduler.schedule_workflow(workflow, "0 9 * * *")
    assert len(scheduler.scheduled_jobs) == 1  # not silently registered


def test_template_expression_rejects_oversized_results():
    # "x" * 500_000_000 is a three-node expression that would allocate
    # half a gigabyte -- the node cap limits complexity, not size, so the
    # evaluator must bound the materialised result too.
    import pytest
    from batch_automation import (
        _evaluate_template_expression,
        TemplateEvaluationError,
    )

    with pytest.raises(TemplateEvaluationError):
        _evaluate_template_expression('"x" * 500_000_000', {})

    assert _evaluate_template_expression('"ab" * 3', {}) == "ababab"
    assert _evaluate_template_expression('[1, 2] + [3]', {}) == [1, 2, 3]


def test_scheduler_fails_loudly_without_schedule_package():
    # 'schedule' is in no installable extra, so HAS_SCHEDULE is always
    # False today -- a warning-and-return left callers believing the job
    # was queued. The scheduler must refuse loudly instead.
    import pytest
    from batch_automation import BatchScheduler, HAS_SCHEDULE

    if HAS_SCHEDULE:
        pytest.skip("schedule package installed")

    scheduler = BatchScheduler()
    with pytest.raises(ImportError):
        scheduler.start()


def test_remove_task_tombstones_the_queue_entry():
    # remove_task could only clear task_map -- PriorityQueue has no
    # delete -- leaving a stale item that crashed get_task with KeyError
    # (and, absent the crash, would still have run the "removed" task).
    q = ba.TaskQueue()
    for task_id in ("gone", "kept"):
        q.add_task(ba.BatchTask(
            id=task_id, name=task_id, function=lambda: None, inputs={},
            dependencies=[], retry_count=0, timeout=None, priority=0,
            tags=[]))

    assert q.remove_task("gone") is True

    first = q.get_task()
    assert first is not None and first.id == "kept"
    assert q.get_task() is None  # tombstone dropped, no KeyError


def test_duplicate_task_ids_are_rejected():
    # results are keyed by task id: in a DAG the map kept only the last
    # task object, so the first duplicate was never executed and the
    # workflow still "completed" with one fewer entry than declared.
    calls = []
    for tag in ("first", "second"):
        calls.append(tag)

    tasks = [
        ba.BatchTask(id="dup", name="first",
                     function=lambda: "first", inputs={},
                     dependencies=[], retry_count=0, timeout=None,
                     priority=0, tags=[]),
        ba.BatchTask(id="dup", name="second",
                     function=lambda: "second", inputs={},
                     dependencies=[], retry_count=0, timeout=None,
                     priority=0, tags=[]),
    ]
    workflow = ba.Workflow(
        id="w", name="w", tasks=tasks, type=ba.WorkflowType.DAG,
        schedule=None, max_parallel=1, conditions={}, metadata={})

    with pytest.raises(ValueError, match="duplicate task id"):
        ba.WorkflowEngine().execute_workflow(workflow)


def test_duplicate_task_ids_rejected_on_sequential_too():
    # The overwrite was silent on every engine type, not just DAG.
    tasks = [
        ba.BatchTask(id="dup", name="a", function=lambda: "a", inputs={},
                     dependencies=[], retry_count=0, timeout=None,
                     priority=0, tags=[]),
        ba.BatchTask(id="dup", name="b", function=lambda: "b", inputs={},
                     dependencies=[], retry_count=0, timeout=None,
                     priority=0, tags=[]),
    ]
    workflow = ba.Workflow(
        id="w", name="w", tasks=tasks, type=ba.WorkflowType.SEQUENTIAL,
        schedule=None, max_parallel=1, conditions={}, metadata={})

    with pytest.raises(ValueError, match="duplicate task id"):
        ba.WorkflowEngine().execute_workflow(workflow)
