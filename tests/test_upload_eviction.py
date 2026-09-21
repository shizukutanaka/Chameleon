"""The upload registry + UPLOAD_DIRECTORY must be bounded in aggregate:
beyond max_uploaded_files the least-recently-touched file is evicted
(registry entry AND its on-disk copy)."""
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

DEV_USERNAME = "evict_user"
DEV_PASSWORD = "evict_pass_chameleon_2024"


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


def _upload(client, auth, name):
    r = client.post(
        "/audio/upload",
        files={"file": (name, _wav_bytes(), "audio/wav")},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    return r.json()["stored_name"]


def test_overflow_evicts_oldest_file_and_disk_copy(client, monkeypatch, tmp_path):
    """With cap=2, the third upload must evict the first — registry AND
    on-disk file — so the store can't grow past the cap."""
    monkeypatch.setitem(api_server.SECURITY_CONFIG, "max_uploaded_files", 2)
    auth = _auth(client)
    first = _upload(client, auth, "a.wav")
    second = _upload(client, auth, "b.wav")
    third = _upload(client, auth, "c.wav")

    registry = api_server.api_state.uploaded_files
    assert len(registry) == 2
    assert first not in registry
    assert second in registry and third in registry
    # The disk copy went with the registry entry — an evicted file must
    # not remain fetchable on the filesystem.
    assert not (tmp_path / first).exists()
    assert (tmp_path / second).exists() and (tmp_path / third).exists()
    # Evicted name is no longer downloadable.
    assert client.get(f"/audio/download/{first}", headers=auth).status_code == 404


def test_zero_cap_disables_eviction(client, monkeypatch, tmp_path):
    """CHAMELEON_MAX_UPLOADED_FILES=0 keeps every tracked file."""
    monkeypatch.setitem(api_server.SECURITY_CONFIG, "max_uploaded_files", 0)
    auth = _auth(client)
    names = [_upload(client, auth, f"f{i}.wav") for i in range(3)]
    registry = api_server.api_state.uploaded_files
    assert len(registry) == 3
    for n in names:
        assert (tmp_path / n).exists()


def test_recently_touched_file_survives_eviction(client, monkeypatch, tmp_path):
    """LRU order follows last_modified: touching the oldest file before
    overflow makes the second-oldest the eviction victim."""
    monkeypatch.setitem(api_server.SECURITY_CONFIG, "max_uploaded_files", 2)
    auth = _auth(client)
    first = _upload(client, auth, "a.wav")
    second = _upload(client, auth, "b.wav")
    time.sleep(0.01)
    api_server.api_state.touch_file_metadata(first)
    third = _upload(client, auth, "c.wav")

    registry = api_server.api_state.uploaded_files
    assert len(registry) == 2
    assert second not in registry
    assert first in registry and third in registry
