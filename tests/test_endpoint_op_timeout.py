"""Single-file /audio/analyze and /audio/normalize must honor
file_timeout_seconds just like the batch path -- a hung operation
cannot hold a request open forever."""
import asyncio
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

DEV_USERNAME = "timeout_user"
DEV_PASSWORD = "timeout_pass_chameleon_2024"


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


@pytest.mark.parametrize("endpoint,op", [
    ("/audio/analyze", "analyze_audio_fast"),
    ("/audio/normalize", "normalize_audio_fast"),
])
def test_endpoint_times_out_hung_operation(client, monkeypatch, endpoint, op):
    """A hung per-file op returns success=False with a timeout error
    instead of parking the request forever."""
    auth = _auth(client)
    up = client.post(
        "/audio/upload",
        files={"file": ("x.wav", _wav_bytes(), "audio/wav")},
        headers=auth,
    )
    stored = up.json()["stored_name"]

    async def _hang(*args, **kwargs):
        await asyncio.sleep(3600)
        return {"success": True}

    monkeypatch.setattr(api_server, op, _hang)
    monkeypatch.setitem(api_server.SECURITY_CONFIG,
                        "file_timeout_seconds", 1)

    r = client.post(endpoint, json={"file_name": stored}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "timed out" in body.get("error", "")
