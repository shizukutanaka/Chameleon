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


def _loop_workflow(iterations):
    calls = []

    def fn(**kwargs):
        calls.append(1)
        return "done"

    cfg = {
        "id": "w", "name": "loop", "type": "loop",
        "metadata": {"iterations": iterations},
        "tasks": [{
            "id": "t", "name": "t",
            "function": {"type": "lambda", "expression": "'done'"},
            "inputs": {},
        }],
    }
    workflow = ba.WorkflowBuilder().from_dict(cfg)
    return workflow, calls, fn


def test_loop_workflow_rejects_a_negative_iteration_count():
    # Old behavior: range(-1) is empty, so the workflow reported success
    # having executed nothing -- a silently zero-run job.
    workflow, _, _ = _loop_workflow(-1)
    with pytest.raises(ValueError, match="iterations"):
        ba.WorkflowEngine().execute_workflow(workflow)


def test_loop_workflow_accepts_a_numeric_string():
    # Old behavior: range("2") crashed with TypeError. A numeric YAML value
    # quoted by accident should still work.
    workflow, _, _ = _loop_workflow("2")
    res = ba.WorkflowEngine().execute_workflow(workflow)
    assert sorted(res) == ["t_iter_0", "t_iter_1"]
    assert all(r.status is ba.TaskStatus.COMPLETED for r in res.values())


def test_loop_workflow_rejects_garbage_iterations():
    workflow, _, _ = _loop_workflow("often")
    with pytest.raises(ValueError, match="iterations"):
        ba.WorkflowEngine().execute_workflow(workflow)


def test_loop_workflow_zero_iterations_is_an_honest_noop():
    # Contract pin: asking for zero iterations legitimately runs nothing.
    workflow, _, _ = _loop_workflow(0)
    assert ba.WorkflowEngine().execute_workflow(workflow) == {}
