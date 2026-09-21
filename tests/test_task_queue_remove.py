"""TaskQueue.remove_task must actually remove the task.

At HEAD, remove_task deleted the id from task_map but left the entry in
the PriorityQueue (it can't delete arbitrary entries). The next get_task
popped the "removed" task and crashed on ``del task_map[id]`` with
KeyError -- so removal both lied (returned True while the task would
still run) and took the consumer down with it.
"""
from batch_automation import BatchTask, TaskQueue


def _task(tid, priority=0):
    return BatchTask(id=tid, name=tid, function=lambda: None,
                     inputs={}, priority=priority)


def test_removed_task_is_never_returned():
    q = TaskQueue()
    q.add_task(_task("A"))
    assert q.remove_task("A") is True
    assert q.get_task() is None


def test_removed_task_skipped_not_blocking_others():
    q = TaskQueue()
    q.add_task(_task("A"))
    q.add_task(_task("B"))
    q.remove_task("A")
    task = q.get_task()
    assert task is not None and task.id == "B"
    assert q.get_task() is None


def test_remove_unknown_or_popped_returns_false():
    q = TaskQueue()
    assert q.remove_task("nope") is False
    q.add_task(_task("A"))
    q.get_task()
    # Already running (popped): not removable, and no crash later.
    assert q.remove_task("A") is False


def test_normal_pop_order_unchanged():
    q = TaskQueue()
    q.add_task(_task("low", priority=1))
    q.add_task(_task("high", priority=9))
    assert q.get_task().id == "high"
    assert q.get_task().id == "low"
    assert q.get_task() is None
