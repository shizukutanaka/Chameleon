"""`PerformanceTracker.start_time` was one shared attribute.

The parallel batch path drives a *single* AudioProcessor from
run_in_executor worker threads, so N concurrent `perf.start()` calls
overwrote each other: every file reported the last starter's duration,
and an interleaved `end()` cleared the value so a later `end()` returned
0. The reported "processed in Xms" was not a measurement of that file.
start_time is now per-thread (threading.local()).
"""

import threading
import time

import core


def test_perf_tracker_start_time_is_per_thread():
    """A worker thread's own timing must not erase another thread's
    in-flight measurement."""
    tracker = core.PerformanceTracker()
    tracker.start()
    time.sleep(0.05)

    done = threading.Event()

    def worker():
        tracker.start()
        tracker.end("other_op")
        done.set()

    t = threading.Thread(target=worker)
    t.start()
    done.wait(timeout=5)
    t.join()

    # At HEAD the worker's end() zeroed the shared start_time, so this
    # returned 0 for an op that demonstrably ran >=50ms.
    duration = tracker.end("main_op")
    assert duration >= 40, f"shared start_time race zeroed the measurement: {duration}ms"


def test_perf_tracker_thread_sees_own_duration():
    """A thread's end() returns its own elapsed time, not the last
    starter's."""
    tracker = core.PerformanceTracker()
    tracker.start()  # main thread's long-running op
    results = {}

    def worker():
        tracker.start()
        time.sleep(0.02)
        results["worker_ms"] = tracker.end("w")

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    time.sleep(0.06)
    main_ms = tracker.end("m")
    assert results["worker_ms"] >= 15
    # Worker's 20ms window must not be reported as >=60ms borrowed from main.
    assert results["worker_ms"] < main_ms
