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


class TestLoopAndConditionalWorkflows:
    """The remaining workflow-type surfaces: a LOOP must not silently
    run nothing, and a CONDITIONAL guard must not be treated as met when
    its referenced task never produced a result."""

    def _engine(self):
        return ba.WorkflowEngine()

    def _task(self, task_id, fn=None):
        return ba.BatchTask(id=task_id, name=task_id,
                            function=fn or (lambda: task_id), inputs={})

    @pytest.mark.parametrize("bad", [0, -2, "3", True, 2.5])
    def test_loop_rejects_nonpositive_or_noint_iterations(self, bad):
        workflow = ba.Workflow(
            id="l", name="loop", type=ba.WorkflowType.LOOP,
            tasks=[self._task("x")], metadata={"iterations": bad})
        with pytest.raises(ValueError, match="iterations"):
            self._engine().execute_workflow(workflow)

    def test_loop_runs_each_task_per_iteration(self):
        workflow = ba.Workflow(
            id="l", name="loop", type=ba.WorkflowType.LOOP,
            tasks=[self._task("x")], metadata={"iterations": 3})
        results = self._engine().execute_workflow(workflow)
        assert set(results) == {"x_iter_0", "x_iter_1", "x_iter_2"}

    def test_conditional_on_nonexistent_task_skips(self):
        # "run b only if ghost succeeded" -- ghost can never succeed, so
        # b must be skipped, not run as though the guard were satisfied.
        ran = []
        workflow = ba.Workflow(
            id="c", name="cond", type=ba.WorkflowType.CONDITIONAL,
            tasks=[ba.BatchTask(id="a", name="a",
                                function=lambda: ran.append("a"), inputs={}),
                   ba.BatchTask(id="b", name="b",
                                function=lambda: ran.append("b"), inputs={})],
            conditions={"b": {"type": "simple", "task_id": "ghost"}})
        results = self._engine().execute_workflow(workflow)
        assert ran == ["a"]
        assert "b" not in results

    def test_conditional_on_failed_task_skips(self):
        def boom():
            raise RuntimeError("nope")
        ran = []
        workflow = ba.Workflow(
            id="c", name="cond", type=ba.WorkflowType.CONDITIONAL,
            tasks=[self._task("f", boom),
                   ba.BatchTask(id="g", name="g",
                                function=lambda: ran.append("g"), inputs={})],
            conditions={"g": {"type": "simple", "task_id": "f"}})
        results = self._engine().execute_workflow(workflow)
        assert results["f"].status == ba.TaskStatus.FAILED
        assert ran == []
        assert "g" not in results

    def test_conditional_on_completed_task_runs(self):
        ran = []
        workflow = ba.Workflow(
            id="c", name="cond", type=ba.WorkflowType.CONDITIONAL,
            tasks=[ba.BatchTask(id="a", name="a",
                                function=lambda: ran.append("a"), inputs={}),
                   ba.BatchTask(id="b", name="b",
                                function=lambda: ran.append("b"), inputs={})],
            conditions={"b": {"type": "simple", "task_id": "a"}})
        self._engine().execute_workflow(workflow)
        assert ran == ["a", "b"]
