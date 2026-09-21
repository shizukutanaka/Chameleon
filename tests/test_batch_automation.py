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


class TestExecutorRetryAndQueueHonesty:
    """TaskExecutor advertised retry_count/RETRYING but never retried,
    TaskQueue.remove_task lied (the task still ran -- and after the
    removal get_task crashed KeyError), dep_graph state leaked between
    workflows on a reused engine, and execute_async bypassed the
    max_workers pool bound."""

    def _task(self, task_id, fn, **kw):
        return ba.BatchTask(id=task_id, name=task_id, function=fn,
                            inputs={}, **kw)

    def test_transient_failure_retries_until_success(self):
        calls = []
        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("transient")
            return "ok"
        engine = ba.WorkflowEngine()
        workflow = ba.Workflow(
            id="r", name="retry", type=ba.WorkflowType.SEQUENTIAL,
            tasks=[self._task("f", flaky, retry_count=3)])
        results = engine.execute_workflow(workflow)
        assert results["f"].status == ba.TaskStatus.COMPLETED
        assert results["f"].output == "ok"
        assert len(calls) == 3
        assert results["f"].metadata["attempts"] == 3

    def test_retry_exhaustion_still_fails_honestly(self):
        def always():
            raise RuntimeError("always")
        engine = ba.WorkflowEngine()
        workflow = ba.Workflow(
            id="r", name="retry", type=ba.WorkflowType.SEQUENTIAL,
            tasks=[self._task("g", always, retry_count=2)])
        results = engine.execute_workflow(workflow)
        assert results["g"].status == ba.TaskStatus.FAILED
        assert results["g"].metadata["attempts"] == 3
        assert "always" in results["g"].error

    def test_no_retry_means_single_attempt(self):
        calls = []
        def fail():
            calls.append(1)
            raise RuntimeError("x")
        engine = ba.WorkflowEngine()
        workflow = ba.Workflow(
            id="r", name="r", type=ba.WorkflowType.SEQUENTIAL,
            tasks=[self._task("h", fail, retry_count=0)])
        engine.execute_workflow(workflow)
        assert len(calls) == 1

    def test_removed_task_is_not_run_and_no_crash(self):
        q = ba.TaskQueue()
        q.add_task(self._task("x", lambda: "x"))
        q.add_task(self._task("y", lambda: "y"))
        assert q.remove_task("x") is True
        assert q.get_task().id == "y"
        assert q.get_task() is None

    def test_engine_is_reusable_across_dag_workflows(self):
        engine = ba.WorkflowEngine()
        def wf(wf_id, value):
            return ba.Workflow(
                id=wf_id, name=wf_id, type=ba.WorkflowType.DAG,
                tasks=[self._task("a", lambda: value)])
        r1 = engine.execute_workflow(wf("w1", 1))
        r2 = engine.execute_workflow(wf("w2", 2))
        assert [v.output for v in r1.values()] == [1]
        assert [v.output for v in r2.values()] == [2]

    def test_execute_async_uses_bounded_pool(self):
        import asyncio
        executor = ba.TaskExecutor(max_workers=2)
        task = self._task("a", lambda: "done")
        result = asyncio.run(executor.execute_async(task))
        assert result.status == ba.TaskStatus.COMPLETED
        assert result.output == "done"
        executor.cleanup()
