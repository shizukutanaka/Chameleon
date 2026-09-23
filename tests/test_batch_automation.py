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


def test_dag_rejects_cyclic_dependencies():
    # A cycle can never reach in_degree 0: its tasks were simply never
    # queued, so `results` came back missing them and the workflow read
    # as a success (verified: 2 declared tasks -> {} returned).
    def f():
        return 1

    tasks = [
        ba.BatchTask(id="a", name="a", function=f, inputs={}, dependencies=["b"]),
        ba.BatchTask(id="b", name="b", function=f, inputs={}, dependencies=["a"]),
    ]
    workflow = ba.Workflow(id="w", name="w", tasks=tasks,
                           type=ba.WorkflowType.DAG)
    with pytest.raises(ValueError, match="[Cc]yclic|unschedulable"):
        ba.WorkflowEngine().execute_workflow(workflow)


def test_dag_rejects_self_loop():
    def f():
        return 1

    tasks = [ba.BatchTask(id="a", name="a", function=f, inputs={},
                          dependencies=["a"])]
    workflow = ba.Workflow(id="w", name="w", tasks=tasks,
                           type=ba.WorkflowType.DAG)
    with pytest.raises(ValueError, match="[Cc]yclic|unschedulable"):
        ba.WorkflowEngine().execute_workflow(workflow)


def test_loop_requires_positive_integer_iterations():
    def f():
        return 1

    for bad in ("many", 0, -3, 1.5):
        workflow = ba.Workflow(
            id="w", name="w",
            tasks=[ba.BatchTask(id="t", name="t", function=f, inputs={})],
            type=ba.WorkflowType.LOOP, metadata={"iterations": bad})
        with pytest.raises(ValueError, match="iterations"):
            ba.WorkflowEngine().execute_workflow(workflow)


def test_loop_runs_declared_iterations():
    def f():
        return 1

    workflow = ba.Workflow(
        id="w", name="w",
        tasks=[ba.BatchTask(id="t", name="t", function=f, inputs={})],
        type=ba.WorkflowType.LOOP, metadata={"iterations": 3})
    results = ba.WorkflowEngine().execute_workflow(workflow)
    assert set(results) == {"t_iter_0", "t_iter_1", "t_iter_2"}
    assert all(r.status is ba.TaskStatus.COMPLETED for r in results.values())


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
