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
