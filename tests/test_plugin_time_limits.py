"""Time-limit enforcement in PluginSandbox.execute_with_limits.

Two limit paths exist: POSIX SIGALRM in the calling (main) thread, and a
worker-thread join everywhere else. Both must honor the configured bound
exactly -- including sub-second values, where signal.alarm(int(x)) used
to truncate 0.5 -> 0 = disarmed -- and from threads that cannot legally
install signal handlers at all.
"""
import logging
import threading
import time

import pytest

from plugin_system import PluginConfig, PluginSandbox


def _sandbox(max_time: float) -> PluginSandbox:
    return PluginSandbox(PluginConfig(
        sandbox_mode=True, max_execution_time=max_time, max_memory_mb=0))


def test_subsecond_timeout_is_enforced():
    """max_execution_time=0.2 must fire, not disarm.

    At HEAD the POSIX path did signal.alarm(int(0.2)) == alarm(0), which
    *cancels* the timer -- a plugin slept its full duration under an
    explicitly configured sub-second bound.
    """
    sb = _sandbox(0.2)
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        sb.execute_with_limits(time.sleep, 3)
    assert time.monotonic() - start < 2.0


def test_execute_with_limits_runs_off_main_thread():
    """A caller on a worker thread cannot install SIGALRM handlers;
    the sandbox must fall back to the worker-thread path, not crash."""
    sb = _sandbox(1.0)
    outcome = []

    def call():
        try:
            outcome.append(("ok", sb.execute_with_limits(lambda: 42)))
        except Exception as exc:  # noqa: BLE001 - captured for assertion
            outcome.append(("error", exc))

    t = threading.Thread(target=call)
    t.start()
    t.join(10)
    assert outcome and outcome[0] == ("ok", 42), f"got {outcome}"


def test_timeout_is_enforced_off_main_thread():
    sb = _sandbox(0.3)
    outcome = []

    def call():
        try:
            sb.execute_with_limits(time.sleep, 5)
            outcome.append("returned")
        except TimeoutError:
            outcome.append("timeout")
        except Exception as exc:  # noqa: BLE001
            outcome.append(exc)

    t = threading.Thread(target=call)
    t.start()
    t.join(10)
    assert outcome == ["timeout"], f"got {outcome}"


def test_timeout_reports_thread_still_running(caplog):
    """Python cannot kill a thread: after a worker-path timeout the plugin
    keeps executing. The log must say the thread survives rather than
    imply containment."""
    sb = _sandbox(0.2)
    with caplog.at_level(logging.ERROR, logger="plugin_sandbox"):
        # Run off-main so the worker-thread path (the one with the leak)
        # handles it deterministically on every platform.
        def call():
            with pytest.raises(TimeoutError):
                sb.execute_with_limits(time.sleep, 5)
        t = threading.Thread(target=call)
        t.start()
        t.join(10)
        assert not t.is_alive()
    assert any("still running" in r.getMessage() for r in caplog.records)


def test_normal_call_returns_value():
    assert _sandbox(5.0).execute_with_limits(lambda: "done") == "done"
