"""
Integration and Unit Tests for V-SHIELD Authentication & Session Security (SIH 2026).
Verifies:
1. HTTP login endpoint (/api/v1/auth/login) issues valid HMAC-SHA256 JWT tokens.
2. HTTP /api/v1/auth/me enforces Bearer token authentication and rejects invalid/expired tokens.
3. WebSocket rejects unauthenticated connections and arbitrary unauthenticated binary audio.
4. WebSocket rejects binary audio sent during an inactive session (without 'start' or after 'stop').
5. WebSocket rejects binary audio sent when an analysis session has expired.
6. In-band authentication via control frame ({ "type": "auth", "token": "..." }).
7. Successful authenticated live analysis streaming.
8. Security log sanitizer masks passwords, secrets, tokens, cookies, and raw voice audio.
"""

import json
import time
from datetime import timedelta

import numpy as np
import pytest
from app.config import settings
from app.core.auth import (
    USERS_DB,
    AnalysisSession,
    InvalidTokenError,
    TokenExpiredError,
    authenticate_user,
    create_access_token,
    get_default_operator_token,
    mask_secret,
    sanitize_log_dict,
    sanitize_url_for_logging,
    verify_access_token,
)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


# =====================================================================
# 1. HTTP Authentication Tests
# =====================================================================


def test_auth_login_success_and_token_generation():
    """Verify operator login returns valid HMAC-SHA256 JWT access token."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.DEMO_OPERATOR_USERNAME,
            "password": settings.DEMO_OPERATOR_PASSWORD,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == settings.DEMO_OPERATOR_USERNAME
    assert data["user"]["role"] == "analyst"

    # Cryptographically verify the generated access token
    payload = verify_access_token(data["access_token"])
    assert payload["username"] == settings.DEMO_OPERATOR_USERNAME
    assert payload["role"] == "analyst"


def test_auth_login_invalid_credentials_rejected():
    """Verify incorrect password returns HTTP 401 unauthenticated."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.DEMO_OPERATOR_USERNAME,
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthenticated"


def test_auth_me_endpoint_requires_valid_bearer_token():
    """Verify /api/v1/auth/me enforces Bearer token and rejects unauthenticated requests."""
    # 1. No Authorization header
    resp_no_auth = client.get("/api/v1/auth/me")
    assert resp_no_auth.status_code == 401
    assert resp_no_auth.json()["detail"] == "unauthenticated"

    # 2. Invalid Bearer token
    resp_bad_auth = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"}
    )
    assert resp_bad_auth.status_code == 401
    assert resp_bad_auth.json()["detail"] == "unauthenticated"

    # 3. Valid Bearer token
    token = get_default_operator_token()
    resp_valid = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_valid.status_code == 200
    user_data = resp_valid.json()
    assert user_data["username"] == settings.DEMO_OPERATOR_USERNAME


def test_auth_expired_token_rejected():
    """Verify expired token returns HTTP 401 with 'expired session' detail."""
    expired_token = create_access_token(
        data={"sub": "usr_test", "username": "expired_analyst"},
        expires_delta=timedelta(seconds=-10),  # expired in past
    )
    with pytest.raises(TokenExpiredError):
        verify_access_token(expired_token)

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "expired session"


# =====================================================================
# 2. WebSocket Unauthenticated Rejection Tests
# =====================================================================


def test_websocket_reject_invalid_token_on_connect():
    """Verify WebSocket rejects connection with invalid token with explicit unauthenticated message."""
    with client.websocket_connect("/ws/live-call?token=invalid.tampered.token") as ws:
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "auth_error"
        assert msg["code"] in ("UNAUTHORIZED", "UNAUTHENTICATED")


def test_websocket_reject_expired_token_on_connect():
    """Verify WebSocket rejects connection with expired token with explicit expired session message."""
    expired_token = create_access_token(
        data={"sub": "usr_expired", "username": "old_user"},
        expires_delta=timedelta(seconds=-60),
    )
    with client.websocket_connect(f"/ws/live-call?token={expired_token}") as ws:
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "auth_error"
        assert msg["error"] == "expired session"
        assert msg["code"] == "EXPIRED_SESSION"


def test_websocket_reject_unauthenticated_binary_audio():
    """Verify arbitrary unauthenticated binary audio is rejected with explicit WebSocket message."""
    with client.websocket_connect("/ws/live-call") as ws:
        # Stream raw audio bytes without authenticating
        dummy_audio = np.zeros(1600, dtype=np.float32).tobytes()
        ws.send_bytes(dummy_audio)

        msg = json.loads(ws.receive_text())
        assert msg["type"] == "auth_error"
        assert msg["code"] in ("UNAUTHORIZED", "UNAUTHENTICATED")


def test_websocket_reject_unauthenticated_control_frame():
    """Verify control commands from unauthenticated clients are rejected."""
    with client.websocket_connect("/ws/live-call") as ws:
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "auth_error"
        assert msg["code"] in ("UNAUTHORIZED", "UNAUTHENTICATED")


def test_websocket_in_band_authentication():
    """Verify client connecting without query param can authenticate via in-band JSON message."""
    valid_token = get_default_operator_token()
    with client.websocket_connect("/ws/live-call") as ws:
        # Send auth message
        ws.send_text(json.dumps({"type": "auth", "token": valid_token}))
        auth_ack = json.loads(ws.receive_text())
        assert auth_ack["type"] == "authenticated"
        assert auth_ack["user"]["username"] == settings.DEMO_OPERATOR_USERNAME

        # Now start session
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001"}))
        start_ack = json.loads(ws.receive_text())
        assert start_ack["type"] == "session_started"


# =====================================================================
# 3. WebSocket Inactive Session Rejection Tests
# =====================================================================


def test_websocket_reject_audio_during_inactive_session():
    """Verify binary audio sent before 'start' is rejected with 'inactive session' error."""
    token = get_default_operator_token()
    with client.websocket_connect(f"/ws/live-call?token={token}") as ws:
        # Client is authenticated, but has NOT started a session!
        dummy_audio = (0.2 * np.ones(1600, dtype=np.float32)).tobytes()
        ws.send_bytes(dummy_audio)

        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "session_error"
        assert err_msg["code"] in ("SESSION_NOT_ACTIVE", "INACTIVE_SESSION")


def test_websocket_reject_audio_after_session_stopped():
    """Verify binary audio sent after 'stop' is rejected with 'inactive session' error."""
    token = get_default_operator_token()
    with client.websocket_connect(f"/ws/live-call?token={token}") as ws:
        # 1. Start session
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001", "format": "float32"}))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"

        # 2. Stop session
        ws.send_text(json.dumps({"type": "stop"}))
        stopped = json.loads(ws.receive_text())
        assert stopped["type"] == "session_stopped"

        # 3. Send binary audio after stop -> must reject with inactive session
        dummy_audio = (0.1 * np.ones(1600, dtype=np.float32)).tobytes()
        ws.send_bytes(dummy_audio)

        err_msg = json.loads(ws.receive_text())
        assert err_msg["type"] == "session_error"
        assert err_msg["code"] in ("SESSION_NOT_ACTIVE", "INACTIVE_SESSION")


# =====================================================================
# 4. WebSocket Expired Session Rejection Tests
# =====================================================================


def test_analysis_session_tracker_idle_timeout():
    """Verify AnalysisSession tracker marks idle sessions as expired."""
    session = AnalysisSession(
        session_id="sess_test",
        user_id="usr_01",
        username="analyst",
        idle_timeout_sec=0.05,  # 50ms timeout for test
    )
    session.start()
    assert session.validate_can_accept_audio() == (True, "OK")

    # Sleep past idle timeout
    time.sleep(0.06)
    can_accept, reason = session.validate_can_accept_audio()
    assert can_accept is False
    assert reason == "expired session"


def test_analysis_session_tracker_max_duration():
    """Verify AnalysisSession tracker marks sessions exceeding max duration as expired."""
    session = AnalysisSession(
        session_id="sess_test2",
        user_id="usr_01",
        username="analyst",
        max_duration_sec=0.05,  # 50ms max lifetime
        idle_timeout_sec=10.0,
    )
    session.start()
    time.sleep(0.06)
    can_accept, reason = session.validate_can_accept_audio()
    assert can_accept is False
    assert reason == "expired session"


# =====================================================================
# 5. Authenticated Live Analysis Streaming Flow
# =====================================================================


def test_websocket_authenticated_live_analysis_flow():
    """Verify end-to-end streaming when authenticated and active."""
    token = get_default_operator_token()
    with client.websocket_connect(f"/ws/live-call?token={token}") as ws:
        # 1. Start active session
        ws.send_text(json.dumps({"type": "start", "speaker_id": "exec-001", "format": "float32"}))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"
        assert started["user_id"] == USERS_DB[settings.DEMO_OPERATOR_USERNAME]["user_id"]

        # 2. Stream primed audio
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        f32_audio = (0.35 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        ws.send_bytes(f32_audio.tobytes())

        telemetry = json.loads(ws.receive_text())
        assert telemetry["type"] == "analysis"
        assert "risk_score" in telemetry
        assert "metrics" in telemetry


# =====================================================================
# 6. Security Log Sanitization Tests
# =====================================================================


def test_security_log_sanitization():
    """Verify log sanitizer redacts passwords, tokens, secrets, cookies, and raw audio."""
    dirty_log = {
        "user": "analyst@vshield.internal",
        "password": "TopSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.sig",
        "cookie": "session_id=12345; auth=secret_cookie_val",
        "raw_chunk": b"\x00\x01\x02\x03\x04" * 100,
        "telemetry": {
            "risk_score": 12.5,
            "secret_key": "super_secret_jwt_key",
        },
    }

    sanitized = sanitize_log_dict(dirty_log)
    assert sanitized["user"] == "analyst@vshield.internal"
    assert "TopSecretPassword123!" not in str(sanitized)
    assert "eyJhbGci" not in str(sanitized["access_token"])
    assert sanitized["telemetry"]["risk_score"] == 12.5
    assert "super_secret_jwt_key" not in str(sanitized)
    assert "[REDACTED" in sanitized["password"]
    assert "[REDACTED" in sanitized["cookie"]
    assert "[REDACTED_BYTES" in sanitized["raw_chunk"]


def test_sanitize_url_for_logging():
    """Verify URL query tokens are completely stripped from log lines."""
    url = "/ws/live-call?token=secret_token_12345&speaker_id=exec-001"
    clean = sanitize_url_for_logging(url)
    assert clean == "/ws/live-call"
    assert "secret_token_12345" not in clean


def test_authenticate_user_and_mask_secret():
    """Verify direct user authentication and secret masking helper."""
    # Successful authentication
    user = authenticate_user(settings.DEMO_OPERATOR_USERNAME, settings.DEMO_OPERATOR_PASSWORD)
    assert user is not None
    assert user["username"] == settings.DEMO_OPERATOR_USERNAME

    # Non-existent user
    assert authenticate_user("nonexistent_user", "wrongpass") is None

    # Secret masking
    assert mask_secret("") == "[EMPTY]"
    assert mask_secret("short") == "[REDACTED]"
    assert mask_secret("long_secret_string_12345") == "long...[REDACTED]"

    # Invalid token error raise
    with pytest.raises(InvalidTokenError):
        verify_access_token("completely_invalid_token")


# =====================================================================
# Google OAuth 2.0 & Logout Endpoint Tests
# =====================================================================


def test_auth_logout_endpoint():
    """Verify POST /api/v1/auth/logout clears session cookies."""
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_google_login_unconfigured(monkeypatch):
    """Verify /google/login gracefully redirects with error parameter when unconfigured."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    resp = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert resp.status_code == 307
    assert "error=google_not_configured" in resp.headers["location"]


def test_google_login_configured(monkeypatch):
    """Verify /google/login redirects to Google OAuth consent screen with CSRF state."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    resp = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "accounts.google.com/o/oauth2/v2/auth" in location
    assert "client_id=test-client-id.apps.googleusercontent.com" in location
    assert "state=" in location


def test_google_callback_error_handling():
    """Verify Google callback properly forwards error query parameter."""
    resp = client.get(
        "/api/v1/auth/google/callback?error=access_denied",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=access_denied" in resp.headers["location"]


def test_google_callback_invalid_csrf_state():
    """Verify Google callback rejects invalid or tampered CSRF state."""
    resp = client.get(
        "/api/v1/auth/google/callback?code=mock_code&state=tampered.state.123",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=invalid_oauth_state" in resp.headers["location"]


def test_google_callback_successful_flow(monkeypatch):
    """Verify Google OAuth token exchange, tokeninfo verification, and user session creation."""
    from app.core.auth import create_oauth_state

    valid_state = create_oauth_state()
    client_id = "test-google-client-id.apps.googleusercontent.com"
    client_secret = "test-google-secret"

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", client_secret)

    # Mock httpx.AsyncClient responses
    import httpx

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, data=None):
            return httpx.Response(
                200,
                json={"access_token": "mock_google_access", "id_token": "mock_id_token"},
            )

        async def get(self, url, params=None):
            return httpx.Response(
                200,
                json={
                    "sub": "109876543210123456789",
                    "email": "analyst.google@vshield.internal",
                    "email_verified": True,
                    "name": "Dr. Google Analyst",
                    "picture": "https://lh3.googleusercontent.com/a/mock_avatar",
                    "aud": client_id,
                    "iss": "https://accounts.google.com",
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    resp = client.get(
        f"/api/v1/auth/google/callback?code=valid_auth_code&state={valid_state}",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "auth_token=" in location

    # Extract issued token from redirect URL and verify
    import urllib.parse

    parsed = urllib.parse.urlparse(location)
    query_params = urllib.parse.parse_qs(parsed.query)
    issued_token = query_params["auth_token"][0]

    payload = verify_access_token(issued_token)
    assert payload["username"] == "analyst.google@vshield.internal"
    assert payload["role"] == "analyst"
