"""_rate_limit_windows must actually shrink under the opportunistic
cleanup.

At HEAD the cleanup deleted only *empty* deques -- but a deque is only
emptied by its own identifier's next call, so a one-shot identifier
(rotating usernames at /auth/login, distinct client IPs) left a live
entry of expired timestamps behind forever. The dict grew by one entry
per unique identifier, permanently. The fix drops every window whose
newest entry has aged out.
"""
from collections import deque
import time

import pytest

pytest.importorskip("fastapi")

import api_server


def _config(monkeypatch):
    monkeypatch.setitem(api_server.SECURITY_CONFIG, 'enable_rate_limiting', True)
    monkeypatch.setitem(api_server.SECURITY_CONFIG, 'rate_limit_window_seconds', 60)
    monkeypatch.setitem(api_server.SECURITY_CONFIG, 'rate_limit_max_requests', 120)


def test_stale_windows_are_dropped(monkeypatch):
    _config(monkeypatch)
    windows = api_server.api_state._rate_limit_windows
    windows.clear()
    try:
        now = time.time()
        # 250 stale identifiers, each holding an expired timestamp.
        for i in range(250):
            windows[f"stale:{i}"] = deque([now - 3600])
        # One fresh identifier that must survive cleanup.
        windows["live"] = deque([now])

        api_server._enforce_rate_limit("probe")

        assert "live" in windows
        assert all(not k.startswith("stale:") for k in windows)
        assert len(windows) <= 3  # 'live', 'probe', maybe none else
    finally:
        windows.clear()


def test_fresh_windows_survive_cleanup(monkeypatch):
    _config(monkeypatch)
    windows = api_server.api_state._rate_limit_windows
    windows.clear()
    try:
        now = time.time()
        for i in range(250):
            windows[f"fresh:{i}"] = deque([now])

        api_server._enforce_rate_limit("probe")
        # All entries are within the window -- nothing expired, so only
        # the new identifier should have been added.
        assert sum(1 for k in windows if k.startswith("fresh:")) == 250
        assert "probe" in windows
    finally:
        windows.clear()
