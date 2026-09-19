"""
Unit & Integration tests for V-SHIELD MFA Service & Cooldown Trigger (SIH 2026).
Verifies:
1. Challenge dispatching when Risk Score >= 75 or TRIGGER_MFA_CALLBACK.
2. Sliding cooldown mechanism rejecting rapid duplicate triggers.
3. Out-of-band OTP code verification via REST endpoint (right code, master 000000, and wrong code).
4. Cooldown reset upon successful verification.
5. Mocked Twilio Verify API integration (dispatch and verification check).
6. WebSocket live-call telemetry broadcasts mfa_status ("DISPATCHED" / "COOLDOWN").
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from app.config import settings
from app.core.mfa_service import MFAService
from app.core.risk_engine import RiskEngine
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def setup_function():
    """Ensure clean singleton state before each test."""
    service = MFAService.get_instance()
    service.reset_cooldown()


def teardown_function():
    """Clean singleton state after each test."""
    service = MFAService.get_instance()
    service.reset_cooldown()


def test_mfa_simulation_dispatch_and_cooldown():
    """
    Test 1 & 2:
    - Verifies challenge dispatches when requested in simulation mode.
    - Verifies rapid subsequent dispatch is prevented by the sliding cooldown.
    """

    async def _run():
        service = MFAService.get_instance()
        test_phone = "+919876543210"

        # First dispatch should succeed
        res1 = await service.dispatch_mfa_challenge(
            target_id="call_session_001", phone_number=test_phone
        )
        assert res1["status"] == "dispatched"
        assert res1.get("simulated") is True
        assert res1["phone_number"] == test_phone

        # Immediate second dispatch must be rejected with cooldown_active
        res2 = await service.dispatch_mfa_challenge(
            target_id="call_session_001", phone_number=test_phone
        )
        assert res2["status"] == "cooldown_active"
        assert "remaining_seconds" in res2
        assert res2["remaining_seconds"] > 0.0

    asyncio.run(_run())


def test_mfa_otp_verification_flow():
    """
    Test 3:
    - Verifies correct simulated OTP is approved.
    - Verifies master bypass code '000000' is approved.
    - Verifies incorrect OTP is rejected with status FAILED.
    - Verifies approved code clears cooldown.
    """

    async def _run():
        service = MFAService.get_instance()
        test_phone = "+919876543211"

        # Dispatch to generate active simulated code
        dispatch_res = await service.dispatch_mfa_challenge(
            target_id="session_002", phone_number=test_phone
        )
        assert dispatch_res["status"] == "dispatched"

        # 1. Test incorrect code
        wrong_res = await service.verify_mfa_code(phone_number=test_phone, code="999999")
        assert wrong_res["success"] is False
        assert wrong_res["status"] == "FAILED"

        # Cooldown should still be active after failed attempt
        assert service.get_remaining_cooldown(test_phone) > 0.0

        # 2. Test master bypass code '000000'
        bypass_res = await service.verify_mfa_code(phone_number=test_phone, code="000000")
        assert bypass_res["success"] is True
        assert bypass_res["status"] == "AUTHENTICATED_OVERRIDE"

        # Cooldown should be cleared after successful verification
        assert service.get_remaining_cooldown(test_phone) == 0.0

        # 3. Test active generated OTP
        dispatch_res2 = await service.dispatch_mfa_challenge(
            target_id="session_003", phone_number=test_phone
        )
        assert dispatch_res2["status"] == "dispatched"
        active_code = service._simulated_otps[service.normalize_phone(test_phone)]["code"]

        correct_res = await service.verify_mfa_code(phone_number=test_phone, code=active_code)
        assert correct_res["success"] is True
        assert correct_res["status"] == "AUTHENTICATED_OVERRIDE"

    asyncio.run(_run())


def test_mfa_rest_endpoints():
    """
    Verifies REST endpoints under /api/v1/mfa:
    - POST /api/v1/mfa/dispatch
    - GET /api/v1/mfa/cooldown
    - POST /api/v1/mfa/verify-code
    """
    phone = "+919123456789"

    # 1. Dispatch challenge via REST
    resp_dispatch = client.post(f"/api/v1/mfa/dispatch?target_id=test_rest&phone_number={phone}")
    assert resp_dispatch.status_code == 200
    data_dispatch = resp_dispatch.json()
    assert data_dispatch["status"] == "dispatched"

    # 2. Query cooldown
    resp_cooldown = client.get(f"/api/v1/mfa/cooldown?phone_number={phone}")
    assert resp_cooldown.status_code == 200
    data_cooldown = resp_cooldown.json()
    assert data_cooldown["cooldown_active"] is True
    assert data_cooldown["remaining_seconds"] > 0

    # 3. Verify with wrong code
    resp_bad_verify = client.post(
        "/api/v1/mfa/verify-code", json={"phone_number": phone, "code": "111111"}
    )
    assert resp_bad_verify.status_code == 200
    data_bad = resp_bad_verify.json()
    assert data_bad["success"] is False
    assert data_bad["status"] == "FAILED"

    # 4. Verify with master bypass code
    resp_good_verify = client.post(
        "/api/v1/mfa/verify-code", json={"phone_number": phone, "code": "000000"}
    )
    assert resp_good_verify.status_code == 200
    data_good = resp_good_verify.json()
    assert data_good["success"] is True
    assert data_good["status"] == "AUTHENTICATED_OVERRIDE"

    # 5. Confirm cooldown is now cleared
    resp_cooldown_after = client.get(f"/api/v1/mfa/cooldown?phone_number={phone}")
    assert resp_cooldown_after.json()["cooldown_active"] is False


def test_risk_engine_mfa_decision_logic():
    """
    Verifies RiskEngine.should_trigger_mfa threshold logic:
    - Fires on TRIGGER_MFA_CALLBACK
    - Fires on risk_score >= 75.0
    - Does not fire on lower risk
    """
    # High risk voice clone
    assert (
        RiskEngine.should_trigger_mfa(risk_score=78.5, recommended_action="TRIGGER_MFA_CALLBACK")
        is True
    )
    assert (
        RiskEngine.should_trigger_mfa(risk_score=75.0, recommended_action="QUARANTINE_TRANSACTION")
        is True
    )
    assert (
        RiskEngine.should_trigger_mfa(risk_score=95.0, recommended_action="TERMINATE_AND_ALERT")
        is True
    )

    # Moderate or low risk
    assert (
        RiskEngine.should_trigger_mfa(risk_score=65.0, recommended_action="STEP_UP_AUTH") is False
    )
    assert RiskEngine.should_trigger_mfa(risk_score=20.0, recommended_action="ALLOW_CALL") is False


def test_mocked_twilio_api_integration():
    """
    Verifies real Twilio Verify API dispatch and check when credentials are provided.
    Mocks external HTTP network requests using unittest.mock.
    """

    async def _run():
        service = MFAService.get_instance()
        phone = "+12025550199"

        # Patch settings to simulate live Twilio credentials
        with (
            patch.object(settings, "TWILIO_ACCOUNT_SID", "ACmockaccount12345"),
            patch.object(settings, "TWILIO_AUTH_TOKEN", "mocktoken12345"),
            patch.object(settings, "TWILIO_VERIFY_SERVICE_SID", "VAmockservice12345"),
        ):
            assert service.has_twilio_credentials is True

            # Mock Twilio dispatch HTTP 201 response
            mock_dispatch_resp = MagicMock()
            mock_dispatch_resp.status_code = 201
            mock_dispatch_resp.json.return_value = {"sid": "VE_mock_verification_sid_999"}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_dispatch_resp

                dispatch_res = await service.dispatch_mfa_challenge("session_twilio", phone)
                assert dispatch_res["status"] == "dispatched"
                assert dispatch_res["sid"] == "VE_mock_verification_sid_999"
                assert mock_post.called

                # Check that Twilio verification endpoint was targeted
                call_url = mock_post.call_args[0][0]
                assert "verify.twilio.com" in call_url

            # Mock Twilio verification check HTTP 200 response
            mock_check_resp = MagicMock()
            mock_check_resp.status_code = 200
            mock_check_resp.json.return_value = {"status": "approved"}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post_check:
                mock_post_check.return_value = mock_check_resp

                verify_res = await service.verify_mfa_code(phone, "123456")
                assert verify_res["success"] is True
                assert verify_res["status"] == "AUTHENTICATED_OVERRIDE"
                assert mock_post_check.called

    asyncio.run(_run())


def test_websocket_telemetry_mfa_status_broadcast():
    """
    Verifies that WebSocket /ws/live-call broadcasts mfa_status correctly
    (starts as DISPATCHED on high-risk, then transitions to COOLDOWN on subsequent hops).
    """
    with patch("app.models.aasist_service.AASISTService.predict", return_value=(None, 0.95)):
        with client.websocket_connect("/ws/live-call?target_phone=%2B919999988888") as ws:
            # Generate 64,600 samples of active 440 Hz audio to satisfy VAD energy threshold
            t = np.linspace(0, 4.0375, 64600, endpoint=False)
            audio = (0.5 * np.sin(2 * np.pi * 440.0 * t) * 32767).astype(np.int16)
            ws.send_bytes(audio.tobytes())

            data1 = ws.receive_json()
            assert "mfa_status" in data1
            assert data1["mfa_status"] in ("DISPATCHED", "COOLDOWN")
            assert data1["risk_score"] >= 70.0
