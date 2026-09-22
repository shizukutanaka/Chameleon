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

import time
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


@pytest.mark.parametrize("bogus_type", ["expresion", "always", "complex", None])
def test_conditional_workflow_with_unrecognised_condition_type_runs_nothing(
        bogus_type):
    # 'expresion' is a typo for 'expression'. A guard the engine cannot
    # evaluate cannot be satisfied -- until now the fall-through returned
    # True and the task ran unconditionally with its guard silently dropped.
    res = _run_dict({
        "id": "w", "name": "d", "type": "conditional",
        "conditions": {"t": {"type": bogus_type}},
        "tasks": [{
            "id": "t", "name": "pow",
            "function": {"type": "builtin", "module": "math", "name": "pow"},
            "inputs": {"x": 2, "y": 3},
        }],
    })
    assert res == {}


def test_conditional_workflow_recognised_conditions_unchanged():
    # 'simple' on a completed dependency still runs the guarded task --
    # tightening the unknown-type fall-through must not break the real
    # condition kinds.
    res = _run_dict({
        "id": "w", "name": "d", "type": "conditional",
        "conditions": {"b": {"type": "simple", "task_id": "a"}},
        "tasks": [
            {"id": "a", "name": "pow",
             "function": {"type": "builtin", "module": "math", "name": "pow"},
             "inputs": {"x": 2, "y": 3}},
            {"id": "b", "name": "sqrt",
             "function": {"type": "builtin", "module": "math", "name": "sqrt"},
             "inputs": {"x": 16}},
        ],
    })
    assert res["a"].status is ba.TaskStatus.COMPLETED
    assert res["b"].status is ba.TaskStatus.COMPLETED
    assert res["b"].output == 4.0


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


def _install_fake_schedule(monkeypatch, run_pending):
    monkeypatch.setattr(ba, "HAS_SCHEDULE", True)
    monkeypatch.setattr(
        ba, "schedule", types.SimpleNamespace(run_pending=run_pending),
        raising=False)
    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda s: real_sleep(0.005))
    return real_sleep


def test_scheduler_loop_survives_a_raising_job(monkeypatch):
    # A scheduled workflow that raises (an invalid definition, an
    # engine-level error) used to kill the scheduler thread outright --
    # 'running' stayed True while every scheduled job was silently dead.
    ticks = []

    def run_pending():
        ticks.append(1)
        if len(ticks) == 2:
            raise ValueError("bad workflow")

    real_sleep = _install_fake_schedule(monkeypatch, run_pending)
    scheduler = ba.BatchScheduler()
    scheduler.start()
    try:
        deadline = time.time() + 2
        while len(ticks) < 6 and time.time() < deadline:
            real_sleep(0.01)
        assert len(ticks) >= 6  # ticking continued past the raise
        assert scheduler.thread.is_alive()
        assert scheduler.running
    finally:
        scheduler.stop()
    assert not scheduler.running


def test_scheduler_refuses_a_second_start(monkeypatch):
    # start() had no guard: a second call spawned another loop thread, so
    # every pending job ran twice per interval and stop() could only join
    # the latest thread.
    _install_fake_schedule(monkeypatch, lambda: None)
    scheduler = ba.BatchScheduler()
    scheduler.start()
    try:
        with pytest.raises(RuntimeError, match="already running"):
            scheduler.start()
    finally:
        scheduler.stop()
    assert not scheduler.thread.is_alive()

    # Restartable after a clean stop.
    scheduler.start()
    scheduler.stop()


def test_template_expression_arithmetic_errors_are_typed():
    # 1/0, 'a'-1 and -'a' used to leak raw ZeroDivisionError/TypeError
    # where every other malformed template raises TemplateEvaluationError.
    import pytest
    from batch_automation import (
        _evaluate_template_expression,
        TemplateEvaluationError,
    )

    for bad in ('1 / 0', '"a" - 1', '"a" + 1', '- "a"', '+ "a"'):
        with pytest.raises(TemplateEvaluationError):
            _evaluate_template_expression(bad, {})

    assert _evaluate_template_expression('10 / 4', {}) == 2.5
    assert _evaluate_template_expression('-5', {}) == -5


def test_condition_expression_in_on_non_iterable_is_typed():
    # '"x" in results["t"].success' evaluated 'x' in a bool -- a raw
    # TypeError where the evaluator's contract is ConditionEvaluationError.
    import pytest
    from batch_automation import (
        _evaluate_condition_expression,
        ConditionEvaluationError,
    )

    for bad in ('"x" in results["t"].success', '"x" not in results["t"].error'):
        with pytest.raises(ConditionEvaluationError):
            _evaluate_condition_expression(bad, {})

    assert _evaluate_condition_expression('"x" in results["t"].status', {}) is False


def test_from_dict_rejects_non_mapping_configs():
    # A YAML/JSON file whose top level is a scalar or list parses cleanly
    # and then died inside from_dict on `.get` with a bare AttributeError --
    # for an empty file the message named 'NoneType', not the real mistake.
    # Same malformed-config class as the task-field validation: ValueError.
    from batch_automation import WorkflowBuilder

    for bad in (None, "daily", 5, [1, 2]):
        with pytest.raises(ValueError, match="must be a mapping"):
            WorkflowBuilder().from_dict(bad)
