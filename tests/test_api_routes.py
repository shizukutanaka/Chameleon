"""HTTP-level tests for api_server.py via FastAPI's TestClient.

Prior test coverage (test_api_fallback.py) only exercised the fallback
adapter functions at the Python level — zero HTTP routes were ever hit. This
file closes that gap and pins the regressions fixed in this pass: HTTPException
status codes must survive through handlers that also catch generic Exception
(they previously got flattened to 200/500), the FLAC output-format claim (the
stdlib core cannot write FLAC) is now rejected by request validation, and the
honesty-motivated wording changes (no more "government_grade"/"classification").

Requires fastapi + httpx; skips cleanly if either is unavailable, matching the
project's graceful-degradation convention.
"""

import hashlib

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402

DEV_USERNAME = "test-dev-user"
DEV_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def client(monkeypatch):
    # Dev-mode auth fallback (no secure modules in this environment) needs
    # both of these set; patched directly since they're read once at import.
    monkeypatch.setattr(api_server, "_DEV_USERNAME", DEV_USERNAME)
    monkeypatch.setattr(
        api_server, "_DEV_PASSWORD_HASH",
        hashlib.sha256(DEV_PASSWORD.encode("utf-8")).hexdigest(),
    )
    # TrustedHostMiddleware only allows localhost/127.0.0.1 by default;
    # TestClient's default Host is "testserver", which it correctly rejects.
    return TestClient(api_server.app, base_url="http://localhost")


def _login(client, username=DEV_USERNAME, password=DEV_PASSWORD):
    return client.post(
        "/auth/login",
        json={"username": username, "password": password, "clearance_level": "UNCLASSIFIED"},
    )


# ---------------------------------------------------------------- basics --

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "uptime_seconds" in body


def test_root_endpoint_has_no_unbacked_marketing_claims(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Chameleon Audio API"
    # These claims were removed: this API does not do government
    # classification handling, and calling it "government_grade" is an
    # unbacked capability claim (CHARTER §4).
    assert "classification" not in body
    assert body.get("security") != "government_grade"


# -------------------------------------------------------------------- auth --

def test_login_with_correct_credentials_succeeds(client):
    response = _login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["token"]


def test_login_with_wrong_password_fails_cleanly(client):
    response = _login(client, password="wrong-password")
    assert response.status_code == 200  # by design: auth failure, not a server error
    body = response.json()
    assert body["success"] is False


def test_login_rate_limit_returns_429_not_200(client, monkeypatch):
    """Regression: the rate-limit HTTPException(429) was previously caught by
    a bare `except Exception` in login() and silently turned into HTTP 200."""
    monkeypatch.setitem(api_server.SECURITY_CONFIG, "enable_rate_limiting", True)
    monkeypatch.setitem(api_server.SECURITY_CONFIG, "rate_limit_max_requests", 1)
    monkeypatch.setitem(api_server.SECURITY_CONFIG, "rate_limit_window_seconds", 60)

    # Unique username so this test's rate-limit bucket (keyed on
    # f"login:{ip}:{username}") doesn't collide with other tests sharing
    # api_state._rate_limit_windows, a module-level singleton.
    unique_user = "rate-limit-test-user"
    first = _login(client, username=unique_user, password="irrelevant")
    assert first.status_code == 200

    second = _login(client, username=unique_user, password="irrelevant")
    assert second.status_code == 429


def test_authenticated_endpoint_rejects_missing_token(client):
    response = client.get("/audit/log")
    assert response.status_code in (401, 403)


def test_authenticated_endpoint_rejects_garbage_token(client):
    response = client.get(
        "/audit/log", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


# ------------------------------------------------- error-contract regressions --

def test_download_missing_file_returns_404_not_500(client):
    """Regression: download_file's bare `except Exception` previously turned
    the 404 from _get_authorized_file_path into a 500 with the original
    "404: ..." detail leaked as the message."""
    login = _login(client)
    token = login.json()["token"]

    response = client.get(
        "/audio/download/does-not-exist.wav",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "500" not in str(response.status_code)


def test_batch_submit_missing_file_returns_404_not_200(client):
    """Regression: submit_batch_job's bare `except Exception` previously
    turned the 404 from a missing input file into HTTP 200 success=False."""
    login = _login(client)
    token = login.json()["token"]

    response = client.post(
        "/batch/submit",
        json={"files": ["does-not-exist.wav"], "operation": "analyze", "options": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ------------------------------------------------------- FLAC claim removed --

def test_normalize_rejects_flac_output_format(client):
    """Regression: output_format accepted 'flac' but the stdlib core can only
    write WAV — a file named .flac containing WAV bytes. Now rejected by
    request validation (422) instead of silently mislabeling the output."""
    login = _login(client)
    token = login.json()["token"]

    response = client.post(
        "/audio/normalize",
        json={"file_name": "whatever.wav", "target_peak": 0.9, "output_format": "flac"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_upload_rejects_flac_extension(client):
    login = _login(client)
    token = login.json()["token"]

    response = client.post(
        "/audio/upload",
        files={"file": ("test.flac", b"not really flac data", "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


# ----------------------------------------- golden path + authorization gaps --

def _wav_bytes() -> bytes:
    """Minimal valid mono WAV (0.05s silence) for upload tests."""
    import io
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack("<" + "h" * 2205, *([0] * 2205)))
    return buf.getvalue()


def test_upload_without_token_rejected(client):
    response = client.post(
        "/audio/upload",
        files={"file": ("x.wav", _wav_bytes(), "audio/wav")},
    )
    assert response.status_code in (401, 403)


def test_upload_rejects_exe_extension(client):
    login = _login(client)
    token = login.json()["token"]
    response = client.post(
        "/audio/upload",
        files={"file": ("evil.exe", b"MZ payload", "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_upload_analyze_download_roundtrip(client, tmp_path, monkeypatch):
    """The whole point of the API: upload a WAV, analyze it, download it back.
    Previously only verified by hand — now pinned."""
    monkeypatch.setattr(api_server, "UPLOAD_DIRECTORY", tmp_path)
    login = _login(client)
    token = login.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    up = client.post(
        "/audio/upload",
        files={"file": ("roundtrip.wav", _wav_bytes(), "audio/wav")},
        headers=auth,
    )
    assert up.status_code == 200
    stored = up.json()["stored_name"]

    an = client.post("/audio/analyze", json={"file_name": stored}, headers=auth)
    assert an.status_code == 200

    dl = client.get(f"/audio/download/{stored}", headers=auth)
    assert dl.status_code == 200
    assert dl.content[:4] == b"RIFF"


def test_download_unregistered_name_returns_404(client):
    """Traversal-style or invented names must not escape the upload registry:
    an unregistered file_name is a 404, never a path lookup."""
    login = _login(client)
    token = login.json()["token"]
    response = client.get(
        "/audio/download/..%2F..%2Fetc%2Fpasswd",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (400, 404)


def test_batch_normalize_job_produces_a_downloadable_output(client, tmp_path, monkeypatch):
    """submit → status → download: the generated file's name must reach the
    client in the job results, otherwise the output is registered for
    download but can never be fetched."""
    import io
    import math
    import struct
    import time
    import wave
    monkeypatch.setattr(api_server, "UPLOAD_DIRECTORY", tmp_path)
    login = _login(client)
    token = login.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Normalize refuses silence ("No audio signal found"), so this needs a
    # real tone, not the silent _wav_bytes() fixture.
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack(
            "<4410h",
            *[int(0.3 * 32767 * math.sin(2 * math.pi * 220 * i / 44100)) for i in range(4410)],
        ))

    up = client.post(
        "/audio/upload",
        files={"file": ("batchme.wav", buf.getvalue(), "audio/wav")},
        headers=auth,
    )
    assert up.status_code == 200
    stored = up.json()["stored_name"]

    sub = client.post(
        "/batch/submit",
        json={"files": [stored], "operation": "normalize"},
        headers=auth,
    )
    assert sub.status_code == 200
    job_id = sub.json()["job_id"]

    status = None
    for _ in range(120):  # under a full-suite run the worker thread may need >9s
        s = client.get(f"/batch/status/{job_id}", headers=auth)
        if s.status_code == 429:  # rate limiter: keep polling, the job still runs
            time.sleep(0.5)
            continue
        assert s.status_code == 200
        status = s.json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.15)
    assert status["status"] == "completed", status
    assert status["results"][0]["result"].get("success") is True

    output_name = status["results"][0]["result"].get("output_file")
    assert output_name, f"job result names no output file: {status['results']}"
    dl = client.get(f"/audio/download/{output_name}", headers=auth)
    assert dl.status_code == 200
    assert dl.content[:4] == b"RIFF"


def test_cross_owner_download_denied(client):
    """Registry-based authorization: a file owned by another user is 403
    for a non-privileged session, even with a valid token."""
    api_server.api_state.register_uploaded_file(
        "someone-elses.wav",
        owner="not-the-dev-user",
        size=1,
        original_name="victim.wav",
        session_id="other-session",
    )
    login = _login(client)  # dev user logs in with UNCLASSIFIED clearance
    token = login.json()["token"]
    response = client.get(
        "/audio/download/someone-elses.wav",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_batch_normalize_options_target_peak_reaches_the_output(client, tmp_path, monkeypatch):
    """options.target_peak was stored in job_data and then dropped -- the
    normalize call ran at the default 0.95 regardless. The option must
    reach the DSP call and land on the written file."""
    import io
    import math
    import struct
    import time
    import wave
    monkeypatch.setattr(api_server, "UPLOAD_DIRECTORY", tmp_path)
    login = _login(client)
    token = login.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack(
            "<4410h",
            *[int(0.3 * 32767 * math.sin(2 * math.pi * 220 * i / 44100)) for i in range(4410)],
        ))

    up = client.post(
        "/audio/upload",
        files={"file": ("peakme.wav", buf.getvalue(), "audio/wav")},
        headers=auth,
    )
    assert up.status_code == 200
    stored = up.json()["stored_name"]

    sub = client.post(
        "/batch/submit",
        json={"files": [stored], "operation": "normalize",
              "options": {"target_peak": 0.5}},
        headers=auth,
    )
    assert sub.status_code == 200
    job_id = sub.json()["job_id"]

    status = None
    for _ in range(120):  # under a full-suite run the worker thread may need >9s
        s = client.get(f"/batch/status/{job_id}", headers=auth)
        if s.status_code == 429:
            time.sleep(0.5)
            continue
        assert s.status_code == 200
        status = s.json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.15)
    assert status["status"] == "completed", status
    result = status["results"][0]["result"]
    assert result.get("success") is True
    # The option reached core.normalize: it reports the applied target.
    assert result.get("target_peak") == 0.5, result

    out_path = tmp_path / result["output_file"]
    with wave.open(str(out_path), "rb") as w:
        import array
        samples = array.array("h", w.readframes(w.getnframes()))
    peak = max(abs(x) for x in samples) / 32768.0
    assert abs(peak - 0.5) < 0.02  # 0.5, not the default 0.95


def test_batch_submit_rejects_options_the_operation_cannot_use(client, monkeypatch):
    """Unknown option keys used to be accepted, stored, and silently
    dropped. They are rejected at submit time (422) now."""
    login = _login(client)
    token = login.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    sub = client.post(
        "/batch/submit",
        json={"files": ["x.wav"], "operation": "analyze",
              "options": {"speed": 2}},
        headers=auth,
    )
    assert sub.status_code == 422


def test_system_status_reports_degraded_when_circuit_breaker_open(client, monkeypatch):
    """security_status is derived, not a constant: a hardcoded "secure"
    would claim health while the breaker is open."""
    login = _login(client)
    auth = {"Authorization": f"Bearer {login.json()['token']}"}
    monkeypatch.setattr(api_server.api_state, "circuit_breaker_open", True)
    r = client.get("/system/status", headers=auth)
    assert r.status_code == 200
    assert r.json()["security_status"] == "degraded"
    assert r.json()["circuit_breaker_open"] is True


def test_login_clearance_is_capped_at_the_configured_maximum(client, monkeypatch):
    """The request's clearance is self-declared; honoring it without a
    bound let any client claim TOP_SECRET. The deployment's cap wins."""
    monkeypatch.setattr(api_server, "_MAX_CLAIMABLE_CLEARANCE", "UNCLASSIFIED")
    login = client.post(
        "/auth/login",
        json={"username": DEV_USERNAME, "password": DEV_PASSWORD,
              "clearance_level": "TOP_SECRET"},
    )
    assert login.status_code == 200
    # Asked for TOP_SECRET, capped at UNCLASSIFIED -- and the response
    # reports what was granted, not what was claimed.
    assert login.json()["user_info"]["clearance_level"] == "UNCLASSIFIED"


def test_expired_session_is_rejected_and_removed(client, monkeypatch):
    """Expiry is enforced per-request, not just at cleanup time: a session
    whose expires_at is in the past must get 401 and be dropped."""
    from datetime import datetime, timedelta, timezone
    login = _login(client)
    token = login.json()["token"]
    session_id = login.json()["user_info"]["session_id"]
    session = api_server.api_state.active_sessions[session_id]
    monkeypatch.setitem(
        session, "expires_at",
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    r = client.get("/system/status",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert session_id not in api_server.api_state.active_sessions


def test_audit_log_records_real_operations(client, monkeypatch, tmp_path):
    """Every authenticated endpoint writes an audit event; /audit/log must
    return the real trail (not a fixture) with the operation names."""
    monkeypatch.setattr(api_server, "UPLOAD_DIRECTORY", tmp_path)
    login = _login(client)
    token = login.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    import io, math, struct, wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(struct.pack("<4410h",
            *[int(0.3 * 32767 * math.sin(2 * math.pi * 220 * i / 44100))
              for i in range(4410)]))
    up = client.post("/audio/upload",
                     files={"file": ("a.wav", buf.getvalue(), "audio/wav")},
                     headers=auth)
    assert up.status_code == 200

    r = client.get("/audit/log", headers=auth)
    assert r.status_code == 200
    ops = {e["operation"] for e in r.json()["entries"]}
    assert {"LOGIN", "UPLOAD"} <= ops, ops
    # Entries carry real fields, not placeholders
    entry = next(e for e in r.json()["entries"]
                 if e["operation"] == "UPLOAD" and e["result"] == "SUCCESS")
    assert entry["result"] == "SUCCESS" and entry["user"] == DEV_USERNAME
    # The read itself is logged too -- visible on the next fetch.
    r2 = client.get("/audit/log", headers=auth)
    assert "AUDIT_READ" in {e["operation"] for e in r2.json()["entries"]}


def test_denied_requests_are_audited(client):
    """Refused requests must land in the audit log -- a log that only
    records successes cannot reveal filename probing or escalation
    attempts."""
    login = _login(client)
    auth = {"Authorization": f"Bearer {login.json()['token']}"}

    r = client.get("/audio/download/does-not-exist.wav", headers=auth)
    assert r.status_code == 404

    log = client.get("/audit/log", headers=auth)
    denied = [e for e in log.json()["entries"]
              if e["operation"] == "DOWNLOAD" and e["result"] == "DENIED"]
    assert denied, "denied download was not audited"
    assert "404" in denied[-1]["details"]
