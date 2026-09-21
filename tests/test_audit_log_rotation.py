"""The durable audit file must be bounded: past max_audit_log_bytes the
current log rotates to <name>.1, so disk usage stays at ~2x cap instead
of growing forever. The in-memory deque was already bounded -- the file
it mirrors was not."""
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import api_server  # noqa: E402


def _emit(n=3):
    for i in range(n):
        api_server.log_audit_event(
            "u", "TEST_OP", f"res-{i}", "SUCCESS", "d" * 64, "127.0.0.1", "s",
        )


def test_audit_file_rotates_past_size_cap(monkeypatch, tmp_path):
    log_file = tmp_path / "api-audit.log"
    monkeypatch.setattr(api_server, "_resolve_audit_log_path",
                        lambda: log_file)
    monkeypatch.setitem(api_server.SECURITY_CONFIG,
                        "max_audit_log_bytes", 512)

    _emit(5)
    assert log_file.exists()
    first_size = log_file.stat().st_size
    assert first_size > 0
    # Writing more past the cap must rotate: the previous content moves
    # to .1 and the live file stays bounded (rotation is checked before
    # each write, so the live file holds at most cap + one entry).
    _emit(5)
    rotated = tmp_path / "api-audit.log.1"
    assert rotated.exists(), "expected rotation to api-audit.log.1"
    assert rotated.stat().st_size >= 512
    assert log_file.stat().st_size < 512 + 512
    # And it keeps rotating: more writes must not re-grow it forever.
    _emit(5)
    assert log_file.stat().st_size < 512 + 512


def test_zero_cap_never_rotates(monkeypatch, tmp_path):
    log_file = tmp_path / "api-audit.log"
    monkeypatch.setattr(api_server, "_resolve_audit_log_path",
                        lambda: log_file)
    monkeypatch.setitem(api_server.SECURITY_CONFIG,
                        "max_audit_log_bytes", 0)
    _emit(5)
    assert log_file.exists()
    assert not (tmp_path / "api-audit.log.1").exists()
