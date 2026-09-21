"""A batch job whose per-file operation never completes must not sit in
'processing' forever -- the watchdog marks the file failed so the job
finishes and frees its worker permit."""
import asyncio
import hashlib
import io
import math
import struct
import time
import wave

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402

DEV_USERNAME = "dev_user"
DEV_PASSWORD = "dev_pass_chameleon_2024"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api_server, "_DEV_USERNAME", DEV_USERNAME)
    monkeypatch.setattr(
        api_server, "_DEV_PASSWORD_HASH",
        hashlib.sha256(DEV_PASSWORD.encode("utf-8")).hexdigest(),
    )
    api_server.api_state._rate_limit_windows.clear()
    # The circuit breaker is module-global: earlier tests' per-file
    # failures can leave it open, which would make this test's jobs fail
    # before any per-file work runs.
    api_server.api_state.job_failures_window.clear()
    api_server.api_state.circuit_breaker_open = False
    # Persistent portal: without `with` each request gets a fresh loop and
    # background job tasks are cancelled at request end (see
    # test_api_routes.py's client fixture comment).
    with TestClient(api_server.app, base_url="http://localhost") as c:
        yield c
    # The audit log is module-global and shared across test files;
    # entries this file writes must not outlive it.
    api_server.api_state.audit_log.clear()


def _login(client):
    return client.post(
        "/auth/login",
        json={"username": DEV_USERNAME, "password": DEV_PASSWORD,
              "clearance_level": "UNCLASSIFIED"},
    )


def _tone_wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack(
            "<4410h",
            *[int(0.3 * 32767 * math.sin(2 * math.pi * 220 * i / 44100))
              for i in range(4410)],
        ))
    return buf.getvalue()


def _upload(client, auth, tmp_path, monkeypatch):
    monkeypatch.setattr(api_server, "UPLOAD_DIRECTORY", tmp_path)
    up = client.post(
        "/audio/upload",
        files={"file": ("slow.wav", _tone_wav_bytes(), "audio/wav")},
        headers=auth,
    )
    assert up.status_code == 200
    return up.json()["stored_name"]


def _await_job(client, job_id, auth, budget=30):
    deadline = time.time() + budget
    while time.time() < deadline:
        s = client.get(f"/batch/status/{job_id}", headers=auth)
        if s.status_code == 429:
            time.sleep(0.5)
            continue
        assert s.status_code == 200
        status = s.json()
        if status["status"] in ("completed", "failed"):
            return status
        time.sleep(0.15)
    raise AssertionError(f"job never settled: {status}")


@pytest.mark.parametrize("operation", ["normalize", "analyze"])
def test_hung_file_marks_job_failed_not_stuck(client, tmp_path, monkeypatch, operation):
    """When a file's operation hangs, the watchdog records a per-file
    timeout failure and the job completes -- a hung await can never
    produce a final state, so leaving it unbounded leaves the job
    'processing' forever."""
    auth = {"Authorization": f"Bearer {_login(client).json()['token']}"}
    stored = _upload(client, auth, tmp_path, monkeypatch)

    async def _hang(*args, **kwargs):
        await asyncio.sleep(3600)
        return {"success": True}

    if operation == "normalize":
        monkeypatch.setattr(api_server, "normalize_audio_fast", _hang)
    else:
        monkeypatch.setattr(api_server, "analyze_audio_fast", _hang)
    monkeypatch.setitem(api_server.SECURITY_CONFIG,
                        "file_timeout_seconds", 1)

    sub = client.post(
        "/batch/submit",
        json={"files": [stored], "operation": operation},
        headers=auth,
    )
    assert sub.status_code == 200
    job_id = sub.json()["job_id"]

    status = _await_job(client, job_id, auth)
    assert status["status"] == "completed", status
    results = status["results"]
    assert len(results) == 1
    assert results[0]["result"]["success"] is False
    assert "timed out" in results[0]["result"]["error"]


def test_zero_timeout_disables_watchdog(client, tmp_path, monkeypatch):
    """CHAMELEON_FILE_TIMEOUT=0 must mean no bound (CHAMELEON_TIMEOUT
    convention): a slow-but-finishing op completes successfully."""
    auth = {"Authorization": f"Bearer {_login(client).json()['token']}"}
    stored = _upload(client, auth, tmp_path, monkeypatch)

    async def _slow(*args, **kwargs):
        await asyncio.sleep(0.3)
        return {"success": True}

    monkeypatch.setattr(api_server, "normalize_audio_fast", _slow)
    monkeypatch.setitem(api_server.SECURITY_CONFIG,
                        "file_timeout_seconds", 0)

    sub = client.post(
        "/batch/submit",
        json={"files": [stored], "operation": "normalize"},
        headers=auth,
    )
    job_id = sub.json()["job_id"]
    status = _await_job(client, job_id, auth)
    assert status["status"] == "completed", status
    assert status["results"][0]["result"]["success"] is True
