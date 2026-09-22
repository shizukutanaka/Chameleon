"""StructuredLogger's payload fields must reach the emitted JSON.

`log_security_event` and `log_performance_metrics` attached their
`details`/`metrics` dicts as LogRecord attributes the StructuredFormatter
never read -- a security event logged its type but silently dropped the
detail dict, and a metrics call emitted "Performance metrics" with no
metrics at all. `log_operation` likewise dropped `success`.
"""

import io
import json
import logging

from core import StructuredLogger


def _capture(sl):
    buf = io.StringIO()
    sl.logger.handlers[0].stream = buf
    return buf


def _lines(buf):
    return [json.loads(line) for line in buf.getvalue().strip().splitlines()]


def test_security_event_carries_its_details():
    sl = StructuredLogger()
    buf = _capture(sl)

    sl.log_security_event("path_blocked", {"path": "/etc/passwd"})

    (entry,) = _lines(buf)
    assert entry["event_type"] == "path_blocked"
    assert entry["details"] == {"path": "/etc/passwd"}


def test_performance_metrics_carries_the_metrics():
    sl = StructuredLogger()
    buf = _capture(sl)

    sl.log_performance_metrics({"files": 3, "elapsed_s": 1.2})

    (entry,) = _lines(buf)
    assert entry["metrics"] == {"files": 3, "elapsed_s": 1.2}
    assert entry["metrics_type"] == "performance"


def test_operation_log_reports_success_flag():
    sl = StructuredLogger()
    buf = _capture(sl)

    sl.log_operation("analyze", 42, success=False)

    (entry,) = _lines(buf)
    assert entry["success"] is False
    assert entry["operation"] == "analyze"
    assert entry["duration_ms"] == 42
