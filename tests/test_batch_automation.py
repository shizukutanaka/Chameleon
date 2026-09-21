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


@pytest.mark.parametrize("bad", [-3, 0, "abc", 2.0, True])
def test_loop_workflow_rejects_impossible_iterations(bad):
    """metadata.iterations drove range() unchecked: -3 returned zero
    results as a silent success, "abc" died on a bare TypeError, True ran
    once (bool is an int). A loop that cannot iterate is bad config --
    name it."""
    import pytest
    cfg = {
        "id": "w", "type": "loop",
        "tasks": [{"id": "t1",
                   "function": {"type": "lambda", "expression": "1"}}],
        "metadata": {"iterations": bad},
    }
    workflow = ba.WorkflowBuilder().from_dict(cfg)
    with pytest.raises(ValueError, match="iterations"):
        ba.WorkflowEngine().execute_workflow(workflow)


def test_loop_workflow_still_runs_positive_iterations():
    res = _run_dict({
        "id": "w", "type": "loop",
        "tasks": [{"id": "t1",
                   "function": {"type": "lambda", "expression": "1"}}],
        "metadata": {"iterations": 3},
    })
    assert len(res) == 3
    assert all(r.status is ba.TaskStatus.COMPLETED for r in res.values())


@pytest.mark.parametrize("expr", ["every_0", "every_-5", "every_abc"])
def test_scheduler_rejects_impossible_every_intervals(monkeypatch, expr):
    """'every_<N>' fed int() straight into schedule.every(): every_0 and
    every_-5 produced a nonsensical interval, every_abc a bare ValueError
    with no naming. Reject before touching the scheduler."""
    class FakeJob:
        def do(self, fn, wf):
            pass

    fake_schedule = types.SimpleNamespace(
        every=lambda *a: types.SimpleNamespace(
            day=FakeJob(), hour=FakeJob(), minutes=FakeJob()))
    monkeypatch.setattr(ba, "HAS_SCHEDULE", True)
    monkeypatch.setattr(ba, "schedule", fake_schedule, raising=False)

    scheduler = ba.BatchScheduler()
    workflow = ba.Workflow(id="w", name="n", type=ba.WorkflowType.SEQUENTIAL,
                           tasks=[])
    with pytest.raises(ValueError, match="Unsupported schedule|interval"):
        scheduler.schedule_workflow(workflow, expr)
    assert not scheduler.scheduled_jobs  # never registered
