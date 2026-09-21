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


class TestDagWorkflowValidation:
    """A DAG whose dependencies can't be satisfied must fail loudly --
    a cyclic workflow used to 'complete' having run zero tasks, and an
    unknown dep used to crash the executor with a bare KeyError."""

    def _engine(self):
        return ba.WorkflowEngine()

    def _task(self, task_id, dependencies=()):
        return ba.BatchTask(id=task_id, name=task_id, function=lambda: task_id,
                            inputs={}, dependencies=list(dependencies))

    def test_cyclic_dependencies_raise_not_silently_skip(self):
        workflow = ba.Workflow(
            id="cyc", name="cyclic", type=ba.WorkflowType.DAG,
            tasks=[self._task("a", ["b"]), self._task("b", ["a"])])
        with pytest.raises(ValueError, match="unscheduled.*a.*b|cycle"):
            self._engine().execute_workflow(workflow)

    def test_self_dependency_is_a_cycle(self):
        workflow = ba.Workflow(
            id="self", name="self", type=ba.WorkflowType.DAG,
            tasks=[self._task("a", ["a"])])
        with pytest.raises(ValueError, match="unscheduled"):
            self._engine().execute_workflow(workflow)

    def test_unknown_dependency_names_it(self):
        workflow = ba.Workflow(
            id="miss", name="missing", type=ba.WorkflowType.DAG,
            tasks=[self._task("a", ["ghost"])])
        with pytest.raises(ValueError, match="undefined.*ghost"):
            self._engine().execute_workflow(workflow)

    def test_valid_dag_still_runs_in_order(self):
        order = []
        workflow = ba.Workflow(
            id="ok", name="ok", type=ba.WorkflowType.DAG,
            tasks=[ba.BatchTask(id="a", name="a",
                                function=lambda: order.append("a"), inputs={}),
                   ba.BatchTask(id="b", name="b",
                                function=lambda: order.append("b"), inputs={},
                                dependencies=["a"])])
        results = self._engine().execute_workflow(workflow)
        assert order == ["a", "b"]
        assert set(results) == {"a", "b"}
