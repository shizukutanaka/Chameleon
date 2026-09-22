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


def test_retry_count_is_a_real_budget_not_decorative_metadata():
    # retry_count was accepted from config and echoed in result metadata as
    # "retry_allowed" -- but execute() ran the function exactly once, so a
    # transient failure on attempt 1 was final despite the declared budget.
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) <= 2:
            raise RuntimeError("transient")
        return "ok"

    executor = ba.TaskExecutor()
    task = ba.BatchTask(id="t", name="t", function=flaky, inputs={},
                        retry_count=3)
    result = executor.execute(task)

    assert result.status is ba.TaskStatus.COMPLETED
    assert result.output == "ok"
    assert result.error is None          # cleared on the winning attempt
    assert len(calls) == 3               # 1 initial + 2 retries used
    assert result.metadata["attempts"] == 3


def test_retry_budget_exhausted_reports_last_error():
    calls = []

    def always_fails():
        calls.append(1)
        raise RuntimeError(f"boom {len(calls)}")

    executor = ba.TaskExecutor()
    task = ba.BatchTask(id="t", name="t", function=always_fails, inputs={},
                        retry_count=2)
    result = executor.execute(task)

    assert result.status is ba.TaskStatus.FAILED
    assert result.error == "boom 3"      # 1 + 2 retries, last error kept
    assert len(calls) == 3


def test_zero_retry_means_single_attempt():
    calls = []

    def fails():
        calls.append(1)
        raise RuntimeError("nope")

    executor = ba.TaskExecutor()
    task = ba.BatchTask(id="t", name="t", function=fails, inputs={},
                        retry_count=0)
    result = executor.execute(task)

    assert result.status is ba.TaskStatus.FAILED
    assert len(calls) == 1


def test_simple_condition_on_unknown_task_id_does_not_run_guarded_task():
    # A 'simple' condition whose task_id was missing from results fell
    # through to `return True` -- the guard silently disabled itself and
    # the guarded task ran unconditionally. Unknown, misspelled, or
    # later-ordered ids cannot satisfy a guard, so the task must skip.
    ran = []
    engine = ba.WorkflowEngine()
    workflow = ba.Workflow(
        id="w", name="w", type=ba.WorkflowType.CONDITIONAL,
        tasks=[ba.BatchTask(id="guarded", name="g",
                            function=lambda: ran.append(1), inputs={})],
        conditions={"guarded": {"type": "simple",
                                "task_id": "does_not_exist"}},
    )

    results = engine.execute_workflow(workflow)

    assert ran == []
    assert "guarded" not in results


def test_simple_condition_still_honours_a_completed_task():
    ran = []
    engine = ba.WorkflowEngine()
    workflow = ba.Workflow(
        id="w", name="w", type=ba.WorkflowType.CONDITIONAL,
        tasks=[
            ba.BatchTask(id="a", name="a",
                         function=lambda: ran.append("a"), inputs={}),
            ba.BatchTask(id="b", name="b",
                         function=lambda: ran.append("b"), inputs={}),
        ],
        conditions={"b": {"type": "simple", "task_id": "a"}},
    )

    results = engine.execute_workflow(workflow)

    assert ran == ["a", "b"]
    assert results["b"].status is ba.TaskStatus.COMPLETED
