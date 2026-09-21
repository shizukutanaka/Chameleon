"""A batch job's files list must be length-bounded -- otherwise a job
naming one registered file a million times grows job_data['results']
without bound while occupying a worker slot."""
import hashlib
import io
import math
import struct
import wave

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402

DEV_USERNAME = "batchcap_user"
DEV_PASSWORD = "batchcap_pass_chameleon_2024"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_DEV_USERNAME", DEV_USERNAME)
    monkeypatch.setattr(
        api_server, "_DEV_PASSWORD_HASH",
        hashlib.sha256(DEV_PASSWORD.encode("utf-8")).hexdigest(),
    )
    api_server.api_state._rate_limit_windows.clear()
    api_server.api_state.job_failures_window.clear()
    api_server.api_state.circuit_breaker_open = False
    monkeypatch.setattr(api_server, "UPLOAD_DIRECTORY", tmp_path)
    with TestClient(api_server.app, base_url="http://localhost") as c:
        yield c
    api_server.api_state.audit_log.clear()
    api_server.api_state.uploaded_files.clear()
    api_server.api_state.active_jobs.clear()
    api_server.api_state.job_queue.clear()


def _auth(client):
    login = client.post(
        "/auth/login",
        json={"username": DEV_USERNAME, "password": DEV_PASSWORD,
              "clearance_level": "UNCLASSIFIED"},
    )
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _wav_bytes():
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


def test_oversized_files_list_rejected(client, monkeypatch):
    """len(files) > max_batch_files must be refused at submit time."""
    auth = _auth(client)
    up = client.post(
        "/audio/upload",
        files={"file": ("x.wav", _wav_bytes(), "audio/wav")},
        headers=auth,
    )
    stored = up.json()["stored_name"]

    monkeypatch.setitem(api_server.SECURITY_CONFIG, "max_batch_files", 3)
    r = client.post(
        "/batch/submit",
        json={"files": [stored] * 4, "operation": "analyze"},
        headers=auth,
    )
    assert r.status_code == 413


def test_zero_cap_disables_bound(client, monkeypatch):
    """max_batch_files=0 means unbounded -- the submit must proceed."""
    auth = _auth(client)
    up = client.post(
        "/audio/upload",
        files={"file": ("x.wav", _wav_bytes(), "audio/wav")},
        headers=auth,
    )
    stored = up.json()["stored_name"]

    monkeypatch.setitem(api_server.SECURITY_CONFIG, "max_batch_files", 0)
    r = client.post(
        "/batch/submit",
        json={"files": [stored] * 4, "operation": "analyze"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_files_within_cap_accepted(client, monkeypatch):
    """A list at exactly the cap is accepted -- boundary, not cap-1."""
    auth = _auth(client)
    up = client.post(
        "/audio/upload",
        files={"file": ("x.wav", _wav_bytes(), "audio/wav")},
        headers=auth,
    )
    stored = up.json()["stored_name"]

    monkeypatch.setitem(api_server.SECURITY_CONFIG, "max_batch_files", 3)
    r = client.post(
        "/batch/submit",
        json={"files": [stored] * 3, "operation": "analyze"},
        headers=auth,
    )
    assert r.status_code == 200
