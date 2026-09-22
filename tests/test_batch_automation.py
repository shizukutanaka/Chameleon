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


def _boom(**kw):
    raise RuntimeError("boom")


def _ok(**kw):
    return "ran"


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


def test_dag_failed_dependency_blocks_dependents():
    # A failed task must not unblock its dependents: running them means
    # "dependency" was order-only decoration and they execute on missing
    # upstream data (the old mark_completed fired on any status). Each
    # blocked task gets a SKIPPED result so nothing vanishes silently.
    workflow = ba.Workflow(id="w", name="n", type=ba.WorkflowType.DAG, tasks=[
        ba.BatchTask(id="a", name="a", function=_boom, inputs={}),
        ba.BatchTask(id="b", name="b", function=_ok, inputs={},
                     dependencies=["a"]),
        ba.BatchTask(id="c", name="c", function=_ok, inputs={},
                     dependencies=["b"]),
    ])
    res = ba.WorkflowEngine().execute_workflow(workflow)
    assert res["a"].status is ba.TaskStatus.FAILED
    assert res["b"].status is ba.TaskStatus.SKIPPED
    assert res["c"].status is ba.TaskStatus.SKIPPED
    assert "'a'" in res["b"].error


def test_dag_engine_is_reusable_across_runs():
    # dep_graph/task_queue used to be engine state: a second
    # execute_workflow call inherited the first run's `completed` set and
    # returned {} -- every task silently never ran.
    engine = ba.WorkflowEngine()
    workflow = ba.Workflow(id="w", name="n", type=ba.WorkflowType.DAG, tasks=[
        ba.BatchTask(id="t1", name="t1", function=_ok, inputs={}),
        ba.BatchTask(id="t2", name="t2", function=_ok, inputs={},
                     dependencies=["t1"]),
    ])
    first = engine.execute_workflow(workflow)
    second = engine.execute_workflow(workflow)
    for res in (first, second):
        assert res["t1"].status is ba.TaskStatus.COMPLETED
        assert res["t2"].status is ba.TaskStatus.COMPLETED
        assert res["t2"].output == "ran"


def test_dag_unknown_dependency_fails_loudly():
    # A dangling dependency id used to seed a phantom graph node and crash
    # the seeding loop with a bare KeyError -- or, worse, silently ignore
    # the unenforceable constraint.
    workflow = ba.Workflow(id="w", name="n", type=ba.WorkflowType.DAG, tasks=[
        ba.BatchTask(id="x", name="x", function=_ok, inputs={},
                     dependencies=["ghost"]),
    ])
    with pytest.raises(ValueError, match="unknown tasks"):
        ba.WorkflowEngine().execute_workflow(workflow)


def test_dag_skipped_dependent_is_not_resurrected():
    # `d` depends on a failing task and a slow succeeding one: the later
    # success must not decrement its in_degree back to ready.
    def slow(**kw):
        import time
        time.sleep(0.2)
        return "slow-ran"

    workflow = ba.Workflow(id="w", name="n", type=ba.WorkflowType.DAG, tasks=[
        ba.BatchTask(id="bad", name="bad", function=_boom, inputs={}),
        ba.BatchTask(id="slow", name="slow", function=slow, inputs={}),
        ba.BatchTask(id="d", name="d", function=_ok, inputs={},
                     dependencies=["bad", "slow"]),
    ])
    res = ba.WorkflowEngine().execute_workflow(workflow)
    assert res["bad"].status is ba.TaskStatus.FAILED
    assert res["slow"].status is ba.TaskStatus.COMPLETED
    assert res["d"].status is ba.TaskStatus.SKIPPED


def test_dag_zero_max_parallel_does_not_hang():
    # max_parallel=0 (a legal YAML value) used to busy-spin forever: the
    # submit loop never ran so the queue could never drain. It now falls
    # back to sequential execution.
    workflow = ba.Workflow(
        id="w", name="n", type=ba.WorkflowType.DAG, max_parallel=0, tasks=[
            ba.BatchTask(id="t", name="t", function=_ok, inputs={}),
        ])
    res = ba.WorkflowEngine().execute_workflow(workflow)
    assert res["t"].status is ba.TaskStatus.COMPLETED


def test_conditional_workflow_records_skipped_tasks():
    # A condition-false task used to leave no trace in results at all.
    workflow = ba.Workflow(
        id="w", name="n", type=ba.WorkflowType.CONDITIONAL, tasks=[
            ba.BatchTask(id="first", name="first", function=_boom, inputs={}),
            ba.BatchTask(id="second", name="second", function=_ok, inputs={}),
        ],
        conditions={"second": {"type": "simple", "task_id": "first"}},
    )
    res = ba.WorkflowEngine().execute_workflow(workflow)
    assert res["first"].status is ba.TaskStatus.FAILED
    assert res["second"].status is ba.TaskStatus.SKIPPED


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
