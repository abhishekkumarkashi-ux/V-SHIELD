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
    client.cookies.clear()


def test_oauth_state_generation_and_validation():
    """Verify create_oauth_state creates valid cryptographic CSRF tokens."""
    from app.core.auth import create_oauth_state, verify_oauth_state

    state = create_oauth_state(expires_in_sec=300)
    assert isinstance(state, str)
    assert "." in state
    assert verify_oauth_state(state) is True


def test_oauth_state_expiration():
    """Verify expired OAuth states are rejected."""
    from app.core.auth import create_oauth_state, verify_oauth_state

    expired_state = create_oauth_state(expires_in_sec=-10)
    assert verify_oauth_state(expired_state) is False


def test_oauth_state_tampering_rejected():
    """Verify tampered payloads or signatures in OAuth states are rejected."""
    from app.core.auth import create_oauth_state, verify_oauth_state

    state = create_oauth_state(expires_in_sec=300)
    parts = state.split(".")
    assert len(parts) == 2

    # 1. Tamper signature
    tampered_sig = parts[0] + ".tampered_signature_bytes"
    assert verify_oauth_state(tampered_sig) is False

    # 2. Tamper payload
    tampered_payload = "tampered_payload." + parts[1]
    assert verify_oauth_state(tampered_payload) is False

    # 3. Invalid format
    assert verify_oauth_state("no_dot_in_state") is False
    assert verify_oauth_state("") is False
    assert verify_oauth_state("too.many.dots.here") is False


def test_google_callback_missing_code_or_state():
    """Verify callback rejects requests with missing code or state parameters."""
    local_client = TestClient(app)
    resp1 = local_client.get("/api/v1/auth/google/callback", follow_redirects=False)
    assert resp1.status_code == 307
    assert "error=missing_oauth_parameters" in resp1.headers["location"]

    resp2 = local_client.get("/api/v1/auth/google/callback?code=some_code", follow_redirects=False)
    assert resp2.status_code == 307
    assert "error=missing_oauth_parameters" in resp2.headers["location"]


def test_google_callback_missing_server_credentials(monkeypatch):
    """Verify callback safely rejects when Google client secret is unconfigured."""
    from app.core.auth import create_oauth_state

    local_client = TestClient(app)
    valid_state = create_oauth_state()

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "configured-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", None)

    resp = local_client.get(
        f"/api/v1/auth/google/callback?code=mock_code&state={valid_state}",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=server_oauth_unconfigured" in resp.headers["location"]


def test_find_or_create_google_user_lifecycle():
    """Verify provisioning new Google users, existing lookup, and profile linking."""
    from app.core.auth import find_or_create_google_user

    test_sub = "test_sub_9988776655"
    test_email = "new.engineer@vshield.internal"
    test_name = "New Engineer"
    test_pic = "https://lh3.googleusercontent.com/avatar_test"

    # 1. Provision new Google user
    user = find_or_create_google_user(
        google_sub=test_sub,
        email=test_email,
        name=test_name,
        picture=test_pic,
    )
    assert user["user_id"].startswith("usr_google_")
    assert user["username"] == test_email
    assert user["name"] == test_name
    assert user["role"] == "analyst"
    assert user["picture"] == test_pic

    # 2. Lookup existing user by google_sub
    existing = find_or_create_google_user(
        google_sub=test_sub,
        email=test_email,
    )
    assert existing["user_id"] == user["user_id"]
    assert existing["username"] == test_email

    # 3. Link Google sub to existing pre-configured operator
    linked_op = find_or_create_google_user(
        google_sub="linked_sub_12345",
        email=settings.DEMO_OPERATOR_USERNAME,
        name="Linked Analyst",
    )
    assert linked_op["username"] == settings.DEMO_OPERATOR_USERNAME


def test_google_callback_invalid_audience_rejected(monkeypatch):
    """Verify callback rejects Google token with mismatched audience claim."""
    from app.core.auth import create_oauth_state
    import httpx

    local_client = TestClient(app)
    valid_state = create_oauth_state()
    client_id = "vshield-official-client-id"

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-secret")

    class MockAsyncClientAudienceMismatch:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, data=None):
            return httpx.Response(200, json={"access_token": "acc", "id_token": "id_tok"})

        async def get(self, url, params=None):
            return httpx.Response(
                200,
                json={
                    "sub": "123",
                    "email": "user@vshield.internal",
                    "email_verified": True,
                    "aud": "different-rogue-audience",
                    "iss": "https://accounts.google.com",
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClientAudienceMismatch)

    resp = local_client.get(
        f"/api/v1/auth/google/callback?code=mock_code&state={valid_state}",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=invalid_token_audience" in resp.headers["location"]


def test_google_callback_invalid_issuer_rejected(monkeypatch):
    """Verify callback rejects Google token with untrusted issuer claim."""
    from app.core.auth import create_oauth_state
    import httpx

    local_client = TestClient(app)
    valid_state = create_oauth_state()
    client_id = "vshield-official-client-id"

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-secret")

    class MockAsyncClientIssuerMismatch:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, data=None):
            return httpx.Response(200, json={"access_token": "acc", "id_token": "id_tok"})

        async def get(self, url, params=None):
            return httpx.Response(
                200,
                json={
                    "sub": "123",
                    "email": "user@vshield.internal",
                    "email_verified": True,
                    "aud": client_id,
                    "iss": "https://evil-untrusted-issuer.com",
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClientIssuerMismatch)

    resp = local_client.get(
        f"/api/v1/auth/google/callback?code=mock_code&state={valid_state}",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=invalid_token_issuer" in resp.headers["location"]


def test_google_callback_unverified_email_rejected(monkeypatch):
    """Verify callback rejects Google token with unverified email."""
    from app.core.auth import create_oauth_state
    import httpx

    local_client = TestClient(app)
    valid_state = create_oauth_state()
    client_id = "vshield-official-client-id"

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-secret")

    class MockAsyncClientUnverifiedEmail:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, data=None):
            return httpx.Response(200, json={"access_token": "acc", "id_token": "id_tok"})

        async def get(self, url, params=None):
            return httpx.Response(
                200,
                json={
                    "sub": "123",
                    "email": "unverified@vshield.internal",
                    "email_verified": False,
                    "aud": client_id,
                    "iss": "https://accounts.google.com",
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClientUnverifiedEmail)

    resp = local_client.get(
        f"/api/v1/auth/google/callback?code=mock_code&state={valid_state}",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=unverified_google_email" in resp.headers["location"]


def test_google_user_auth_me_authentication(monkeypatch):
    """Verify full end-to-end flow: Google login provisions user, issues JWT, and authenticates via /auth/me."""
    from app.core.auth import create_oauth_state
    import httpx
    import urllib.parse

    local_client = TestClient(app)
    valid_state = create_oauth_state()
    client_id = "vshield-client-id-test"
    client_secret = "vshield-secret-test"

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", client_secret)

    class MockAsyncClientSuccess:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, data=None):
            return httpx.Response(
                200,
                json={"access_token": "google_acc_tok", "id_token": "google_id_tok"},
            )

        async def get(self, url, params=None):
            return httpx.Response(
                200,
                json={
                    "sub": "googlesub_e2e_987654",
                    "email": "e2e.analyst@vshield.internal",
                    "email_verified": True,
                    "name": "E2E Analyst",
                    "picture": "https://lh3.googleusercontent.com/a/e2e",
                    "aud": client_id,
                    "iss": "https://accounts.google.com",
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClientSuccess)

    callback_resp = local_client.get(
        f"/api/v1/auth/google/callback?code=valid_auth_code&state={valid_state}",
        follow_redirects=False,
    )
    assert callback_resp.status_code == 307
    location = callback_resp.headers["location"]
    assert "auth_token=" in location

    # Extract token
    parsed = urllib.parse.urlparse(location)
    token = urllib.parse.parse_qs(parsed.query)["auth_token"][0]

    # Authenticate via /api/v1/auth/me
    me_resp = local_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == "e2e.analyst@vshield.internal"
    assert me_data["name"] == "E2E Analyst"
    assert me_data["role"] == "analyst"
    assert me_data["picture"] == "https://lh3.googleusercontent.com/a/e2e"


def test_google_oauth_endpoint_aliases(monkeypatch):
    """Verify /api/auth/google/login and /api/auth/google/callback aliases work identically."""
    local_client = TestClient(app)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)

    # Alias /api/auth/google/login
    resp = local_client.get("/api/auth/google/login", follow_redirects=False)
    assert resp.status_code == 307
    assert "error=google_not_configured" in resp.headers["location"]

    # Alias /api/auth/google/callback
    resp_cb = local_client.get("/api/auth/google/callback?error=user_cancelled", follow_redirects=False)
    assert resp_cb.status_code == 307
    assert "error=user_cancelled" in resp_cb.headers["location"]

